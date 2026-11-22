"""Admin roles / permissions, platform switches and system monitoring."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core import opslog
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.permissions import ALL_PERMISSIONS, PERMISSIONS, SENSITIVE, SUPER_ADMIN
from app.database.health import check_database
from app.models import (
    AdminProfile,
    AdminRole,
    EmailDelivery,
    Notification,
    Payment,
    PaymentEvent,
    Profile,
    Refund,
)
from app.services import audit


def _role_out(r: AdminRole, members: int) -> dict[str, Any]:
    perms = sorted(ALL_PERMISSIONS) if r.is_system and r.name == SUPER_ADMIN else sorted(r.permissions)
    return {
        "id": r.id, "name": r.name, "description": r.description, "permissions": perms,
        "is_system": r.is_system, "members": members, "updated_at": r.updated_at,
    }  # fmt: skip


class RoleService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    @staticmethod
    def catalogue() -> list[dict[str, Any]]:
        return [
            {"key": k, "label": v, "sensitive": k in SENSITIVE, "module": k.split(".")[0]}
            for k, v in PERMISSIONS.items()
        ]

    @staticmethod
    def _validate_permissions(perms: list[str]) -> list[str]:
        unknown = sorted(set(perms) - ALL_PERMISSIONS)
        if unknown:
            raise ValidationFailedError(
                "Unknown permission(s): " + ", ".join(unknown), code="UNKNOWN_PERMISSION"
            )
        return sorted(set(perms))

    async def list_roles(self) -> list[dict[str, Any]]:
        counts = dict(
            (
                await self.s.execute(
                    select(AdminProfile.role_id, func.count()).group_by(AdminProfile.role_id)
                )
            ).all()
        )
        roles = (
            await self.s.scalars(select(AdminRole).order_by(AdminRole.is_system.desc(), AdminRole.name))
        ).all()
        return [_role_out(r, int(counts.get(r.id, 0))) for r in roles]

    async def _role(self, role_id: UUID, lock: bool = False) -> AdminRole:
        stmt = select(AdminRole).where(AdminRole.id == role_id)
        r = (await self.s.scalars(stmt.with_for_update() if lock else stmt)).first()
        if r is None:
            raise NotFoundError("Role not found.", code="ROLE_NOT_FOUND")
        return r

    async def create_role(
        self, actor: CurrentUser, name: str, description: str | None, permissions: list[str]
    ) -> dict[str, Any]:
        perms = self._validate_permissions(permissions)
        if name.strip().lower() == SUPER_ADMIN:
            raise ConflictError("That role name is reserved.", code="ROLE_NAME_RESERVED")
        self._require_holds(actor, perms)
        role = AdminRole(name=name.strip(), description=description, permissions=perms, created_by=actor.id)
        self.s.add(role)
        try:
            await self.s.flush()
        except IntegrityError as exc:
            await self.s.rollback()
            raise ConflictError("A role with that name exists.", code="ROLE_NAME_TAKEN") from exc
        audit.record(self.s, actor.profile, "admin.role_created", "admin_role", role.id,
                     after={"name": role.name, "permissions": perms})  # fmt: skip
        await self.s.commit()
        return _role_out(role, 0)

    @staticmethod
    def _require_holds(actor: CurrentUser, perms: list[str]) -> None:
        """Nobody can hand out a permission they do not hold themselves (no self-escalation)."""
        extra = sorted(set(perms) - actor.permissions)
        if extra:
            raise PermissionDeniedError(
                "You cannot grant permissions you do not hold: " + ", ".join(extra),
                code="CANNOT_GRANT_UNHELD_PERMISSION",
            )

    async def update_role(
        self,
        actor: CurrentUser,
        role_id: UUID,
        description: str | None,
        permissions: list[str] | None,
        reason: str,
    ) -> dict[str, Any]:
        role = await self._role(role_id, lock=True)
        if role.is_system:
            raise PermissionDeniedError("The built-in role cannot be edited.", code="SYSTEM_ROLE_PROTECTED")
        own = await self.s.get(AdminProfile, actor.id)
        if own is not None and own.role_id == role.id:
            raise PermissionDeniedError("You cannot edit your own role.", code="CANNOT_EDIT_OWN_ROLE")
        before = {"description": role.description, "permissions": sorted(role.permissions)}
        if permissions is not None:
            perms = self._validate_permissions(permissions)
            self._require_holds(actor, perms)
            role.permissions = perms
        if description is not None:
            role.description = description
        audit.record(self.s, actor.profile, "admin.role_updated", "admin_role", role.id, before=before,
                     after={"description": role.description, "permissions": sorted(role.permissions)},
                     reason=reason)  # fmt: skip
        members = (await self.s.scalar(select(func.count()).where(AdminProfile.role_id == role.id))) or 0
        await self.s.commit()
        return _role_out(role, int(members))

    async def delete_role(self, actor: CurrentUser, role_id: UUID, reason: str) -> None:
        role = await self._role(role_id, lock=True)
        if role.is_system:
            raise PermissionDeniedError("The built-in role cannot be deleted.", code="SYSTEM_ROLE_PROTECTED")
        used = (await self.s.scalar(select(func.count()).where(AdminProfile.role_id == role.id))) or 0
        if used:
            raise ConflictError("Reassign the administrators who hold this role first.", code="ROLE_IN_USE")
        audit.record(self.s, actor.profile, "admin.role_deleted", "admin_role", role.id,
                     before={"name": role.name, "permissions": sorted(role.permissions)}, reason=reason)  # fmt: skip
        await self.s.execute(delete(AdminRole).where(AdminRole.id == role.id))
        await self.s.commit()

    # ---------------------------------------------------------------- assignments
    async def list_admins(self) -> list[dict[str, Any]]:
        rows = (
            await self.s.execute(
                select(Profile, AdminRole.id, AdminRole.name, AdminProfile.assigned_at)
                .outerjoin(AdminProfile, AdminProfile.user_id == Profile.id)
                .outerjoin(AdminRole, AdminRole.id == AdminProfile.role_id)
                .where(Profile.role == "admin")
                .order_by(Profile.created_at)
            )
        ).all()
        return [
            {"id": p.id, "full_name": p.full_name, "email": p.email, "status": p.status,
             "role_id": rid, "role_name": rname, "assigned_at": at}
            for p, rid, rname, at in rows
        ]  # fmt: skip

    async def _super_count(self) -> int:
        return int(
            (
                await self.s.scalar(
                    select(func.count())
                    .select_from(AdminProfile)
                    .join(AdminRole, AdminRole.id == AdminProfile.role_id)
                    .join(Profile, Profile.id == AdminProfile.user_id)
                    .where(AdminRole.name == SUPER_ADMIN, AdminRole.is_system, Profile.status == "active")
                )
            )
            or 0
        )

    async def assign(
        self, actor: CurrentUser, target_id: UUID, role_id: UUID | None, reason: str
    ) -> dict[str, Any]:
        if target_id == actor.id:
            raise PermissionDeniedError("You cannot change your own role.", code="CANNOT_CHANGE_OWN_ROLE")
        target = await self.s.get(Profile, target_id, with_for_update=True)
        if target is None or target.role != "admin":
            raise NotFoundError("Administrator not found.", code="ADMIN_NOT_FOUND")
        current = await self.s.get(AdminProfile, target_id, with_for_update=True)
        cur_role = await self.s.get(AdminRole, current.role_id) if current else None
        new_role = await self._role(role_id) if role_id else None
        actor_is_super = actor.admin_role == SUPER_ADMIN
        # Changing or revoking a super_admin, or granting it, is reserved to a super_admin.
        touches_super = (cur_role is not None and cur_role.is_system) or (
            new_role is not None and new_role.is_system
        )
        if touches_super and not actor_is_super:
            raise PermissionDeniedError("Only a super_admin can do this.", code="SUPER_ADMIN_ONLY")
        if new_role is not None and not new_role.is_system:
            self._require_holds(actor, sorted(new_role.permissions))
        demoting_super = (
            cur_role is not None and cur_role.is_system and (new_role is None or not new_role.is_system)
        )
        if demoting_super and await self._super_count() <= 1:
            raise ConflictError("At least one active super_admin must remain.", code="LAST_SUPER_ADMIN")
        before = {"role": cur_role.name if cur_role else None}
        if current is None and new_role is not None:
            self.s.add(AdminProfile(user_id=target_id, role_id=new_role.id, assigned_by=actor.id))
        elif current is not None and new_role is not None:
            current.role_id = new_role.id
            current.assigned_by = actor.id
            current.assigned_at = datetime.now(UTC)
        elif current is not None and new_role is None:
            await self.s.execute(delete(AdminProfile).where(AdminProfile.user_id == target_id))
        audit.record(self.s, actor.profile, "admin.role_assigned", "profile", target_id, before=before,
                     after={"role": new_role.name if new_role else None}, reason=reason)  # fmt: skip
        await self.s.commit()
        return {"id": target_id, "role_id": new_role.id if new_role else None,
                "role_name": new_role.name if new_role else None}  # fmt: skip


# ====================================================================== monitoring
async def monitoring_snapshot(app: FastAPI, session: AsyncSession, settings: Settings) -> dict[str, Any]:
    now = datetime.now(UTC)
    db = await check_database(app.state.db, settings.db_health_timeout)
    gw = app.state.payment_gateway
    mode = settings.razorpay_mode
    expected = "live" if settings.is_production else "test"
    mode_ok = mode == expected if mode in ("test", "live") else None
    day = now - timedelta(hours=24)

    webhook_rows = (
        await session.execute(
            select(PaymentEvent.outcome, func.count())
            .where(PaymentEvent.source == "webhook", PaymentEvent.created_at >= day)
            .group_by(PaymentEvent.outcome)
        )
    ).all()
    webhook_24h = {k: int(v) for k, v in webhook_rows}
    last_webhook = await session.scalar(
        select(func.max(PaymentEvent.created_at)).where(PaymentEvent.source == "webhook")
    )
    rejected_total = int(
        (await session.scalar(select(func.count()).where(PaymentEvent.outcome == "rejected"))) or 0
    )
    review = int((await session.scalar(select(func.count()).where(Payment.review_required.is_(True)))) or 0)
    stale_cut = now - timedelta(minutes=settings.payment_reconcile_after_minutes * 2)
    stuck_payments = int(
        (
            await session.scalar(
                select(func.count()).where(
                    Payment.status.in_(("created", "pending", "authorized")), Payment.created_at <= stale_cut
                )
            )
        )
        or 0
    )
    uncertain_refunds = int(
        (await session.scalar(select(func.count()).where(Refund.status.in_(("uncertain", "requested"))))) or 0
    )
    push_pending = int(
        (await session.scalar(select(func.count()).where(Notification.push_status == "pending"))) or 0
    )
    push_failed = int(
        (await session.scalar(select(func.count()).where(Notification.push_status == "failed"))) or 0
    )
    mail = dict(
        (
            await session.execute(select(EmailDelivery.status, func.count()).group_by(EmailDelivery.status))
        ).all()
    )
    sweep = getattr(app.state, "sweep_status", None)
    interval = settings.background_sweep_seconds

    warnings: list[str] = []
    if db.status != "ok":
        warnings.append("The database is not reachable.")
    if not gw.configured:
        warnings.append("Razorpay API credentials are not configured: payments and refunds are unavailable.")
    if gw.configured and not gw.webhook_configured:
        warnings.append("The Razorpay webhook secret is not configured: payment events will be refused.")
    if mode_ok is False:
        warnings.append(
            f"Razorpay is in {mode} mode but this environment ({settings.environment}) expects {expected}."
        )
    if rejected_total:
        warnings.append(f"{rejected_total} gateway event(s) were rejected (mismatched order or amount).")
    if review:
        warnings.append(f"{review} payment(s) need manual review.")
    if stuck_payments:
        warnings.append(
            f"{stuck_payments} payment(s) have been open for a long time without a gateway result."
        )
    if uncertain_refunds:
        warnings.append(
            f"{uncertain_refunds} refund(s) have an uncertain gateway result and need reconciliation."
        )
    if interval and sweep and not sweep.get("last_ok", True):
        warnings.append("The last background sweep failed.")
    if push_failed:
        warnings.append(f"{push_failed} push notification(s) failed to send.")
    if int(mail.get("failed", 0)):
        warnings.append(f"{mail['failed']} e-mail(s) failed to send.")

    return {
        "generated_at": now,
        "backend": {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "started_at": opslog.STARTED_AT,
            "uptime_seconds": int((now - opslog.STARTED_AT).total_seconds()),
        },  # fmt: skip
        "database": {"status": db.status, "latency_ms": db.latency_ms},
        "payment_gateway": {
            "provider": "razorpay",
            "api_configured": gw.configured,
            "webhook_configured": gw.webhook_configured,
            "mode": mode,
            "expected_mode": expected,
            "mode_matches_environment": mode_ok,
            "note": "Only configuration is checked. No live call is made to Razorpay from this page.",
        },  # fmt: skip
        "webhooks": {
            "last_24h": webhook_24h,
            "last_received_at": last_webhook,
            "rejected_total": rejected_total,
            "payments_needing_review": review,
            "stuck_open_payments": stuck_payments,
            "uncertain_refunds": uncertain_refunds,
        },  # fmt: skip
        "background_jobs": {
            "sweep_enabled": bool(interval),
            "sweep_interval_seconds": interval or None,
            "last_run_at": sweep.get("last_run_at") if sweep else None,
            "last_run_ok": sweep.get("last_ok") if sweep else None,
            "note": "In-process loop on this API instance; status resets on restart.",
        },  # fmt: skip
        "delivery": {
            "push_pending": push_pending,
            "push_failed": push_failed,
            "email_queued": int(mail.get("queued", 0)),
            "email_failed": int(mail.get("failed", 0)),
        },  # fmt: skip
        "warnings": warnings,
        "recent_log_events": {
            "scope": "WARNING and above, this API process only, since last restart",
            "counts": opslog.counts(),
            "items": opslog.recent(50),
        },  # fmt: skip
    }
