"""Refunds: initiation, gateway results, reconciliation.

Safety rules (money moves, so every one of these is enforced here, not in the browser):
* Real refunds stay OFF until the `refunds_enabled` platform switch is turned on by an admin who
  holds `settings.manage` (Q9: the client has not approved a refund / cancellation policy).
* The Razorpay key mode must match the environment (live keys in production only, test keys elsewhere).
* A refund row is committed BEFORE the gateway is called, with the row id as the gateway receipt and
  idempotency key. A crash or timeout therefore leaves a findable, retry-safe record, never a
  money movement we know nothing about.
* A timeout / 5xx marks the refund `uncertain`. It is never assumed to have failed, and the
  remaining refundable amount stays locked until reconciliation settles it.
* Payment, refund and booking state change together under row locks (booking, then payment).
* Only gateway evidence moves a refund to processed. Duplicate or out-of-order webhooks are harmless.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError, ValidationFailedError
from app.domain import booking_state as bst
from app.domain import payment_state as pst
from app.gateways.razorpay import GatewayRefund, GatewayUncertainError, PaymentGateway
from app.models import Booking, Dispute, DisputeEvent, Payment, Profile, Refund, Venue
from app.services import audit, platform_settings
from app.services.bookings import BookingService

logger = logging.getLogger(__name__)

IN_FLIGHT = ("requested", "pending", "uncertain")
COUNTED = ("requested", "pending", "uncertain", "processed")
REFUNDABLE_AFTER_CANCEL = (
    bst.CANCELLED_CUSTOMER, bst.CANCELLED_OWNER, bst.CANCELLED_ADMIN, bst.REFUND_PENDING, bst.EXPIRED, bst.FAILED,
)  # fmt: skip
GATEWAY_STATUS = {"pending": "pending", "processed": "processed", "failed": "failed"}


def refund_out(r: Refund, **extra: Any) -> dict[str, Any]:
    return {
        "id": r.id, "payment_id": r.payment_id, "booking_id": r.booking_id, "dispute_id": r.dispute_id,
        "amount_paise": r.amount_paise, "currency": r.currency, "status": r.status, "source": r.source,
        "provider_refund_id": r.provider_refund_id, "reason": r.reason, "failure_reason": r.failure_reason,
        "initiated_by": r.initiated_by, "created_at": r.created_at, "updated_at": r.updated_at,
        "processed_at": r.processed_at, **extra,
    }  # fmt: skip


class RefundService:
    def __init__(self, session: AsyncSession, settings: Settings, gateway: PaymentGateway) -> None:
        self.s = session
        self.settings = settings
        self.gw = gateway

    # ================================================================== guards
    async def _guard_enabled(self) -> None:
        if not await platform_settings.get(self.s, "refunds_enabled"):
            raise ConflictError(
                "Refunds are switched off until the refund and cancellation policy (Q9) is approved "
                "and an administrator with settings permission enables them.",
                code="REFUNDS_DISABLED",
            )
        if not self.gw.configured:
            raise ServiceUnavailableError(
                "Payments are not configured on the server.", code="PAYMENTS_NOT_CONFIGURED"
            )
        mode = self.settings.razorpay_mode
        expected = "live" if self.settings.is_production else "test"
        if mode != expected:
            raise ConflictError(
                f"Razorpay is in {mode} mode but this environment needs {expected} keys. "
                "Test and live credentials are kept strictly separate.",
                code="GATEWAY_MODE_MISMATCH",
            )

    async def availability(self, payment: Payment) -> dict[str, Any]:
        """Whether a refund can be started on this payment right now, and if not, why (for the admin screen)."""
        counted = await self._counted(payment.id)
        remaining = max(payment.amount_paise - counted, 0)
        reason = None
        if not await platform_settings.get(self.s, "refunds_enabled"):
            reason = "Refunds are switched off until the refund and cancellation policy (Q9) is approved."
        elif not self.gw.configured:
            reason = "Razorpay is not configured on the server."
        elif self.settings.razorpay_mode != ("live" if self.settings.is_production else "test"):
            reason = (
                f"Razorpay is in {self.settings.razorpay_mode} mode, which does not match this environment."
            )
        elif payment.status not in (pst.CAPTURED, pst.PARTIALLY_REFUNDED):
            reason = "Only a captured payment can be refunded."
        elif remaining <= 0:
            reason = "The payment has been refunded in full."
        elif await self._in_flight(payment.id):
            reason = "Another refund for this payment has an unknown result. Reconcile it first."
        return {
            "enabled": reason is None,
            "reason": reason,
            "remaining_paise": remaining,
            "mode": self.settings.razorpay_mode,
        }

    # ================================================================== initiation
    async def create(
        self,
        actor: CurrentUser,
        payment_id: UUID,
        amount_paise: int | None,
        reason: str,
        idempotency_key: str | None,
        dispute_id: UUID | None = None,
    ) -> dict[str, Any]:
        if idempotency_key is None or not (8 <= len(idempotency_key) <= 100):
            raise ValidationFailedError(
                "An Idempotency-Key header of 8 to 100 characters is required.",
                code="INVALID_IDEMPOTENCY_KEY",
            )
        pre = await self.s.get(Payment, payment_id)
        if pre is None:
            raise NotFoundError("Payment not found.", code="PAYMENT_NOT_FOUND")
        # Replays are answered before any switch check, so a retried request is never a surprise.
        existing = await self._by_key(payment_id, idempotency_key)
        if existing is not None:
            if amount_paise not in (None, existing.amount_paise) or (reason != existing.reason):
                raise ConflictError(
                    "That Idempotency-Key was used for a different refund.", code="IDEMPOTENCY_KEY_REUSED"
                )
            return refund_out(existing, replayed=True)
        await self._guard_enabled()

        booking = await self.s.scalar(select(Booking).where(Booking.id == pre.booking_id).with_for_update())
        payment = await self.s.scalar(
            select(Payment)
            .where(Payment.id == payment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert booking is not None and payment is not None
        if payment.status == pst.REFUNDED:
            raise ConflictError("This payment has already been refunded in full.", code="ALREADY_REFUNDED")
        if payment.status not in (pst.CAPTURED, pst.PARTIALLY_REFUNDED) or not payment.provider_payment_id:
            raise ConflictError("Only a captured payment can be refunded.", code="PAYMENT_NOT_REFUNDABLE")
        counted = await self._counted(payment_id)
        if await self._in_flight(payment_id):
            raise ConflictError(
                "Another refund for this payment is still in progress or has an unknown result. "
                "Reconcile it first.",
                code="REFUND_IN_FLIGHT",
            )
        remaining = payment.amount_paise - counted
        amount = remaining if amount_paise is None else amount_paise
        if remaining <= 0:
            raise ConflictError("This payment has already been refunded in full.", code="ALREADY_REFUNDED")
        if amount > remaining:
            raise ValidationFailedError(
                f"The amount exceeds the refundable balance of {remaining} paise.",
                code="AMOUNT_EXCEEDS_REMAINING",
            )
        is_full = counted + amount >= payment.amount_paise
        if is_full and booking.status not in REFUNDABLE_AFTER_CANCEL:
            raise ConflictError(
                "A full refund needs the booking to be cancelled first, so booking and payment stay in step.",
                code="REFUND_REQUIRES_CANCELLATION",
            )
        if not is_full and booking.status in (bst.PENDING, bst.REFUNDED):
            raise ConflictError("This booking cannot take a partial refund.", code="REFUND_NOT_ALLOWED")
        if dispute_id is not None:
            await self._require_dispute(dispute_id, booking.id)

        refund = Refund(
            payment_id=payment.id, booking_id=booking.id, dispute_id=dispute_id, amount_paise=amount,
            currency=payment.currency, status="requested", source="admin", idempotency_key=idempotency_key,
            reason=reason, initiated_by=actor.id,
        )  # fmt: skip
        self.s.add(refund)
        await self.s.flush()
        audit.record(self.s, actor.profile, "admin.refund_requested", "refund", refund.id,
                     before={"payment_status": payment.status, "booking_status": booking.status,
                             "refunded_paise": counted},
                     after={"amount_paise": amount, "status": "requested", "full": is_full},
                     reason=reason, payment_id=str(payment.id), booking_id=str(booking.id))  # fmt: skip
        if dispute_id:
            self._dispute_event(dispute_id, actor.profile, "action",
                                f"Refund of {amount} paise requested.", {"refund_id": str(refund.id)})  # fmt: skip
        await self.s.commit()  # durable intent BEFORE any money moves

        return await self._submit(refund.id, actor.profile)

    async def _submit(self, refund_id: UUID, actor: Profile | None) -> dict[str, Any]:
        refund = await self.s.get(Refund, refund_id)
        assert refund is not None
        payment = await self.s.get(Payment, refund.payment_id)
        assert payment is not None and payment.provider_payment_id
        booking = await self.s.get(Booking, refund.booking_id)
        assert booking is not None
        try:
            gr = await self.gw.create_refund(
                payment.provider_payment_id, refund.amount_paise, receipt=str(refund.id),
                idempotency_key=str(refund.id), notes={"refund_id": str(refund.id), "booking": booking.booking_code},
            )  # fmt: skip
        except GatewayUncertainError:
            await self._set_uncertain(refund.id, actor, "The gateway did not confirm in time.")
            return await self.get(refund.id)
        except ServiceUnavailableError as exc:
            # Definitely not accepted: provider rejection (4xx) or never reached.
            desc = None
            if isinstance(exc.details, dict):
                desc = exc.details.get("description") or exc.details.get("provider_code")
            await self._apply(
                refund.id, "failed", None, actor, failure=str(desc or exc.code)[:300], event="submit"
            )
            await self.s.commit()
            return await self.get(refund.id)
        await self._apply(refund.id, gr.status, gr.id, actor, event="submit")
        await self.s.commit()
        return await self.get(refund.id)

    async def _set_uncertain(self, refund_id: UUID, actor: Profile | None, why: str) -> None:
        await self.s.rollback()
        refund = await self.s.get(Refund, refund_id, with_for_update=True)
        assert refund is not None
        if refund.status == "requested":
            refund.status = "uncertain"
            refund.failure_reason = why
            audit.record(self.s, actor, "admin.refund_uncertain", "refund", refund.id,
                         before={"status": "requested"}, after={"status": "uncertain"}, reason=why)  # fmt: skip
        await self.s.commit()

    # ================================================================== state changes (one place)
    async def _apply(
        self,
        refund_id: UUID,
        gateway_status: str,
        provider_refund_id: str | None,
        actor: Profile | None,
        *,
        failure: str | None = None,
        event: str,
    ) -> str:
        """Apply gateway evidence to refund + payment + booking. Returns what happened."""
        pre = await self.s.get(Refund, refund_id)
        assert pre is not None
        booking = await self.s.scalar(select(Booking).where(Booking.id == pre.booking_id).with_for_update())
        payment = await self.s.scalar(
            select(Payment)
            .where(Payment.id == pre.payment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        refund = await self.s.scalar(
            select(Refund)
            .where(Refund.id == refund_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        assert booking is not None and payment is not None and refund is not None
        target = GATEWAY_STATUS.get(gateway_status)
        if target is None:
            return "ignored"
        if provider_refund_id and not refund.provider_refund_id:
            refund.provider_refund_id = provider_refund_id
        old = refund.status
        # Monotonic: processed is final; failed only stands if money did not move.
        if old == "processed" or (old == "failed" and target != "processed") or old == target:
            return "duplicate" if old == target else "ignored"
        if target == "pending" and old not in ("requested", "uncertain"):
            return "ignored"
        refund.status = target
        refund.updated_at = datetime.now(UTC)
        who = actor.role if actor is not None else "system"
        if target == "failed":
            refund.failure_reason = (
                failure or refund.failure_reason or "The gateway reported the refund as failed."
            )
        else:
            refund.failure_reason = None
        # The booking follows the money: accepted refund on a cancelled booking -> refund_pending.
        if target in ("pending", "processed") and booking.status in (
            bst.CANCELLED_CUSTOMER, bst.CANCELLED_OWNER, bst.CANCELLED_ADMIN
        ):  # fmt: skip
            BookingService(self.s, self.settings)._move(
                booking, bst.REFUND_PENDING, "admin" if who == "admin" else "system",
                actor.id if actor else None, "Refund accepted by the gateway.",
            )  # fmt: skip
        if target == "processed":
            refund.processed_at = datetime.now(UTC)
            total = (
                int(
                    await self.s.scalar(
                        select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                            Refund.payment_id == payment.id,
                            Refund.status == "processed",
                            Refund.id != refund.id,
                        )
                    )
                    or 0
                )
                + refund.amount_paise
            )
            payment.gateway_refs = {**payment.gateway_refs, "refunded_paise": total}
            if total >= payment.amount_paise:
                self._pay_status(payment, pst.REFUNDED)
                booking.payment_status = "refunded"
                if booking.status == bst.REFUND_PENDING:
                    BookingService(self.s, self.settings)._move(
                        booking, bst.REFUNDED, "system", None, "Refund processed."
                    )
            else:
                self._pay_status(payment, pst.PARTIALLY_REFUNDED)
                booking.payment_status = "partially_refunded"
        audit.record(self.s, actor, f"refund.{target}", "refund", refund.id,
                     before={"status": old}, after={"status": target}, source=event,
                     failure_reason=refund.failure_reason if target == "failed" else None)  # fmt: skip
        if refund.dispute_id:
            self._dispute_event(
                refund.dispute_id, actor, "action", f"Refund {target}.", {"refund_id": str(refund.id)}
            )
        return "applied"

    @staticmethod
    def _pay_status(payment: Payment, target: str) -> None:
        if payment.status == target:
            return
        if not pst.can_move(payment.status, target):
            raise ConflictError("Invalid payment status change.", code="PAYMENT_TRANSITION_NOT_ALLOWED")
        payment.status = target

    def _dispute_event(
        self, dispute_id: UUID, actor: Profile | None, kind: str, body: str, data: dict[str, Any]
    ) -> None:
        self.s.add(
            DisputeEvent(
                dispute_id=dispute_id, kind=kind, body=body, data=data,
                actor_id=actor.id if actor else None, actor_role=actor.role if actor else "system",
            )
        )  # fmt: skip

    async def _require_dispute(self, dispute_id: UUID, booking_id: UUID) -> None:
        d = await self.s.get(Dispute, dispute_id)
        if d is None or d.booking_id != booking_id:
            raise ValidationFailedError(
                "That dispute does not belong to this booking.", code="DISPUTE_MISMATCH"
            )

    # ================================================================== webhooks (called by PaymentService)
    async def apply_gateway_event(self, payment: Payment, entity: dict[str, Any], event_type: str) -> str:
        """`refund.created|processed|failed`. Creates a row for refunds made in the Razorpay dashboard."""
        status = {
            "refund.created": "pending",
            "refund.processed": "processed",
            "refund.failed": "failed",
        }.get(event_type)
        rid = entity.get("id")
        if status is None or not rid:
            return "ignored"
        refund = await self.s.scalar(select(Refund).where(Refund.provider_refund_id == str(rid)))
        if refund is None and entity.get("receipt"):
            try:
                refund = await self.s.scalar(select(Refund).where(Refund.id == UUID(str(entity["receipt"]))))
            except ValueError:
                refund = None
        if refund is None:
            amount = int(entity.get("amount", 0))
            if amount <= 0:
                return "ignored"
            refund = Refund(
                payment_id=payment.id, booking_id=payment.booking_id, amount_paise=amount, currency=payment.currency,
                status="requested", source="gateway", provider_refund_id=str(rid),
                reason="Created outside this system (Razorpay dashboard).",
            )  # fmt: skip
            self.s.add(refund)
            await self.s.flush()
        return await self._apply(refund.id, status, str(rid), None, event="webhook")

    # ================================================================== reconciliation
    async def reconcile(self, actor: CurrentUser | None, refund_id: UUID) -> dict[str, Any]:
        refund = await self.s.get(Refund, refund_id)
        if refund is None:
            raise NotFoundError("Refund not found.", code="REFUND_NOT_FOUND")
        if refund.status in ("processed", "failed"):
            return await self.get(refund_id)
        if not self.gw.configured:
            raise ServiceUnavailableError(
                "Payments are not configured on the server.", code="PAYMENTS_NOT_CONFIGURED"
            )
        payment = await self.s.get(Payment, refund.payment_id)
        assert payment is not None and payment.provider_payment_id
        who = actor.profile if actor else None
        try:
            found = await self.gw.fetch_payment_refunds(payment.provider_payment_id)
        except ServiceUnavailableError as exc:
            raise ServiceUnavailableError(
                "Could not reach the gateway to check this refund.", code=exc.code
            ) from exc
        match: GatewayRefund | None = next(
            (g for g in found if g.id == refund.provider_refund_id or g.receipt == str(refund.id)), None
        )
        if match is not None:
            await self._apply(refund.id, match.status, match.id, who, event="reconcile")
            await self.s.commit()
            return await self.get(refund_id)
        if refund.status in ("requested", "uncertain"):
            # The gateway has no record: safe to re-send because the idempotency key is unchanged.
            await self._guard_enabled()
            return await self._submit(refund.id, who)
        return await self.get(refund_id)

    async def reconcile_stuck(self, limit: int = 10) -> int:
        """Called from the background sweep: settle refunds that never got a final answer."""
        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        ids = (
            await self.s.scalars(
                select(Refund.id)
                .where(Refund.status.in_(IN_FLIGHT), Refund.source == "admin", Refund.updated_at <= cutoff)
                .order_by(Refund.created_at)
                .limit(limit)
            )
        ).all()
        done = 0
        for rid in ids:
            try:
                await self.reconcile(None, rid)
                done += 1
            except Exception:  # one bad refund must not stop the rest
                logger.warning("refund_reconcile_failed", extra={"refund_id": str(rid)})
                await self.s.rollback()
        return done

    # ================================================================== reads
    async def _by_key(self, payment_id: UUID, key: str) -> Refund | None:
        return await self.s.scalar(
            select(Refund).where(Refund.payment_id == payment_id, Refund.idempotency_key == key)
        )

    async def _counted(self, payment_id: UUID) -> int:
        return int(
            await self.s.scalar(
                select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                    Refund.payment_id == payment_id, Refund.status.in_(COUNTED)
                )
            )
            or 0
        )

    async def _in_flight(self, payment_id: UUID) -> bool:
        return bool(
            await self.s.scalar(
                select(func.count()).where(
                    Refund.payment_id == payment_id, Refund.status.in_(("requested", "uncertain"))
                )
            )
        )

    def _base(self) -> Any:
        return (
            select(Refund, Booking.booking_code, Venue.name, Payment.provider_payment_id)
            .join(Booking, Booking.id == Refund.booking_id)
            .join(Payment, Payment.id == Refund.payment_id)
            .join(Venue, Venue.id == Booking.venue_id)
        )

    @staticmethod
    def _row(r: Refund, code: str, venue: str, prov_pay: str | None) -> dict[str, Any]:
        return refund_out(r, booking_code=code, venue_name=venue, razorpay_payment_id=prov_pay)

    async def get(self, refund_id: UUID) -> dict[str, Any]:
        row = (await self.s.execute(self._base().where(Refund.id == refund_id))).first()
        if row is None:
            raise NotFoundError("Refund not found.", code="REFUND_NOT_FOUND")
        return self._row(*row)

    def filters(
        self, stmt: Any, *, status: str | None, payment_id: UUID | None, booking_id: UUID | None,
        date_lo: datetime | None, date_hi: datetime | None, q: str | None = None,
    ) -> Any:  # fmt: skip
        if status:
            stmt = stmt.where(Refund.status == status)
        if payment_id:
            stmt = stmt.where(Refund.payment_id == payment_id)
        if booking_id:
            stmt = stmt.where(Refund.booking_id == booking_id)
        if date_lo:
            stmt = stmt.where(Refund.created_at >= date_lo)
        if date_hi:
            stmt = stmt.where(Refund.created_at < date_hi)
        if q and q.strip():
            pat = f"%{q.strip()}%"
            stmt = stmt.where(or_(Booking.booking_code.ilike(pat), Refund.provider_refund_id.ilike(pat)))
        return stmt

    async def list_page(self, *, limit: int, offset: int, **f: Any) -> dict[str, Any]:
        stmt = self.filters(self._base(), **f)
        rows = (
            await self.s.execute(
                stmt.order_by(Refund.created_at.desc(), Refund.id).limit(limit + 1).offset(offset)
            )
        ).all()
        return {
            "items": [self._row(*r) for r in rows[:limit]], "limit": limit, "offset": offset,
            "has_more": len(rows) > limit,
        }  # fmt: skip

    async def for_payment(self, payment_id: UUID) -> list[dict[str, Any]]:
        rows = (
            await self.s.execute(
                self._base().where(Refund.payment_id == payment_id).order_by(Refund.created_at)
            )
        ).all()
        return [self._row(*r) for r in rows]

    async def summary(self) -> dict[str, Any]:
        rows = (
            await self.s.execute(
                select(Refund.status, func.count(), func.coalesce(func.sum(Refund.amount_paise), 0)).group_by(
                    Refund.status
                )
            )
        ).all()
        by = {s: {"count": int(c), "amount_paise": int(a)} for s, c, a in rows}
        return {
            "processed_paise": by.get("processed", {}).get("amount_paise", 0),
            "processed_count": by.get("processed", {}).get("count", 0),
            "in_flight_count": sum(by.get(s, {}).get("count", 0) for s in IN_FLIGHT),
            "failed_count": by.get("failed", {}).get("count", 0),
            "by_status": by,
        }  # fmt: skip
