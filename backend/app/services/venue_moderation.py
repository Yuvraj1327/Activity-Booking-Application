"""Venue approval, verification, suspension and reports (admin side).

Status changes are explicit transitions with a history row each; nothing else writes
`venues.status` from the admin side. Suspension never touches existing bookings (Q18 is open):
the response says how many future bookings are affected so the admin can decide case by case.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.domain import booking_state as bst
from app.models import (
    Booking,
    Profile,
    Venue,
    VenueCategory,
    VenueModerationEvent,
    VenueReport,
)
from app.services import audit
from app.services.notifications import NotificationService

TRANSITIONS: dict[str, dict[str, str]] = {
    "approve": {"pending_review": "published"},
    "reject": {"pending_review": "rejected"},
    "suspend": {"published": "suspended"},
    "reinstate": {"suspended": "published"},
}


class VenueModeration:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.s = session
        self.settings = settings

    async def _venue(self, venue_id: UUID) -> Venue:
        v = await self.s.scalar(select(Venue).where(Venue.id == venue_id).with_for_update())
        if v is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        return v

    async def _future_bookings(self, venue_id: UUID) -> int:
        return int(
            await self.s.scalar(
                select(func.count()).where(
                    Booking.venue_id == venue_id,
                    Booking.status == bst.CONFIRMED,
                    Booking.starts_at > datetime.now(UTC),
                )
            )
            or 0
        )

    async def _notify_owner(self, v: Venue, title: str, body: str, tag: str) -> None:
        await NotificationService(self.s).queue(
            user_id=v.owner_id, type_="venue.moderation", title=title, body=body[:500],
            dedupe_key=f"venue:{v.id}:{tag}:{datetime.now(UTC).isoformat()}",
        )  # fmt: skip

    def _event(self, v: Venue, action: str, actor: Profile, from_status: str, reason: str | None) -> None:
        self.s.add(
            VenueModerationEvent(
                venue_id=v.id, action=action, from_status=from_status, to_status=v.status, reason=reason,
                actor_id=actor.id, actor_role="admin",
            )
        )  # fmt: skip

    async def _blockers(self, v: Venue) -> list[str]:
        cats = int(await self.s.scalar(select(func.count()).where(VenueCategory.venue_id == v.id)) or 0)
        out = []
        if v.city_id is None:
            out.append("city")
        if v.latitude is None or v.longitude is None:
            out.append("location")
        if cats < 1:
            out.append("category")
        return out

    async def transition(
        self, actor: CurrentUser, venue_id: UUID, verb: str, reason: str | None
    ) -> dict[str, Any]:
        v = await self._venue(venue_id)
        target = TRANSITIONS[verb].get(v.status)
        if target is None:
            raise ConflictError(
                f"A venue that is '{v.status}' cannot be {verb}d.", code="INVALID_VENUE_TRANSITION"
            )
        if verb in ("reject", "suspend") and not reason:
            raise ValidationFailedError("A reason is required.", code="REASON_REQUIRED")
        before = {"status": v.status, "status_reason": v.status_reason}
        old = v.status
        extra: dict[str, Any] = {}
        if verb == "approve":
            blockers = await self._blockers(v)
            if blockers:
                raise ConflictError(
                    "The venue is missing: " + ", ".join(blockers),
                    code="PUBLISH_REQUIREMENTS",
                    details=blockers,
                )
            v.published_at = datetime.now(UTC)
            v.status_reason = None
        elif verb == "reinstate":
            v.published_at = v.published_at or datetime.now(UTC)
            v.status_reason = None
        else:
            v.status_reason = reason
        if verb == "suspend":
            extra["future_confirmed_bookings"] = await self._future_bookings(v.id)
        v.status = target
        past = {
            "approve": "approved",
            "reject": "rejected",
            "suspend": "suspended",
            "reinstate": "reinstated",
        }[verb]
        self._event(v, past, actor.profile, old, reason)
        audit.record(self.s, actor.profile, f"admin.venue_{past}", "venue", v.id, before=before,
                     after={"status": target, "status_reason": v.status_reason}, reason=reason, **extra)  # fmt: skip
        msg = {
            "approved": ("Venue approved", f"{v.name} is now live."),
            "rejected": ("Venue not approved", f"{v.name}: {reason}"),
            "suspended": ("Venue suspended", f"{v.name}: {reason}"),
            "reinstated": ("Venue reinstated", f"{v.name} is live again."),
        }[past]
        await self._notify_owner(v, msg[0], msg[1], past)
        await self.s.commit()
        return {"id": v.id, "status": v.status, **extra}

    async def set_verified(
        self, actor: CurrentUser, venue_id: UUID, verified: bool, reason: str | None
    ) -> dict[str, Any]:
        v = await self._venue(venue_id)
        if v.status in ("draft", "rejected", "archived"):
            raise ConflictError(
                "Only venues that are live, under review or suspended can be verified.",
                code="VENUE_NOT_VERIFIABLE",
            )
        if not verified and not reason:
            raise ValidationFailedError(
                "A reason is required to remove verification.", code="REASON_REQUIRED"
            )
        if v.is_verified == verified:
            return {"id": v.id, "is_verified": v.is_verified, "changed": False}
        before = {"is_verified": v.is_verified}
        v.is_verified = verified
        v.verified_at = datetime.now(UTC) if verified else None
        v.verified_by = actor.id if verified else None
        self._event(v, "verified" if verified else "unverified", actor.profile, v.status, reason)
        audit.record(self.s, actor.profile, "admin.venue_verified" if verified else "admin.venue_unverified",
                     "venue", v.id, before=before, after={"is_verified": verified}, reason=reason)  # fmt: skip
        await self.s.commit()
        return {"id": v.id, "is_verified": verified, "changed": True}

    async def history(self, venue_id: UUID) -> list[dict[str, Any]]:
        rows = (
            await self.s.execute(
                select(VenueModerationEvent, Profile.full_name)
                .outerjoin(Profile, Profile.id == VenueModerationEvent.actor_id)
                .where(VenueModerationEvent.venue_id == venue_id)
                .order_by(VenueModerationEvent.created_at.desc(), VenueModerationEvent.id)
            )
        ).all()
        return [
            {"id": e.id, "action": e.action, "from_status": e.from_status, "to_status": e.to_status,
             "reason": e.reason, "actor_role": e.actor_role, "actor_name": n, "created_at": e.created_at}
            for e, n in rows
        ]  # fmt: skip

    # ================================================================== reports
    async def create_report(
        self, reporter: UUID, venue_id: UUID, reason: str, details: str | None
    ) -> dict[str, Any]:
        v = await self.s.get(Venue, venue_id)
        if v is None or v.status != "published":
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        dup = await self.s.scalar(
            select(func.count()).where(
                VenueReport.venue_id == venue_id,
                VenueReport.reporter_id == reporter,
                VenueReport.status.in_(("open", "reviewing")),
            )
        )
        if dup:
            raise ConflictError(
                "You have already reported this venue. We are looking into it.", code="REPORT_ALREADY_OPEN"
            )
        r = VenueReport(venue_id=venue_id, reporter_id=reporter, reason=reason, details=details)
        self.s.add(r)
        await self.s.commit()
        return {"id": r.id, "status": "open"}

    def _report_base(self) -> Any:
        return (
            select(VenueReport, Venue.name, Profile.full_name)
            .join(Venue, Venue.id == VenueReport.venue_id)
            .outerjoin(Profile, Profile.id == VenueReport.reporter_id)
        )

    @staticmethod
    def _report_row(
        r: VenueReport, venue: str, reporter: str | None, extra: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "id": r.id, "venue_id": r.venue_id, "venue_name": venue, "reporter_id": r.reporter_id,
            "reporter_name": reporter, "reason": r.reason, "details": r.details, "status": r.status,
            "resolution_note": r.resolution_note, "resolved_at": r.resolved_at, "created_at": r.created_at,
            **(extra or {}),
        }  # fmt: skip

    async def list_reports(
        self, status: str | None, venue_id: UUID | None, limit: int, offset: int
    ) -> dict[str, Any]:
        stmt = self._report_base()
        if status:
            stmt = stmt.where(VenueReport.status == status)
        if venue_id:
            stmt = stmt.where(VenueReport.venue_id == venue_id)
        rows = (
            await self.s.execute(
                stmt.order_by(VenueReport.created_at.desc(), VenueReport.id).limit(limit + 1).offset(offset)
            )
        ).all()
        return {
            "items": [self._report_row(*r) for r in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    async def get_report(self, report_id: UUID) -> dict[str, Any]:
        row = (await self.s.execute(self._report_base().where(VenueReport.id == report_id))).first()
        if row is None:
            raise NotFoundError("Report not found.", code="REPORT_NOT_FOUND")
        r = row[0]
        others = int(
            await self.s.scalar(
                select(func.count()).where(VenueReport.venue_id == r.venue_id, VenueReport.id != r.id)
            )
            or 0
        )
        v = await self.s.get(Venue, r.venue_id)
        return self._report_row(
            row[0],
            row[1],
            row[2],
            extra={"other_reports_on_venue": others, "venue_status": v.status if v else None},
        )

    async def resolve_report(
        self, actor: CurrentUser, report_id: UUID, status: str, note: str | None
    ) -> dict[str, Any]:
        r = await self.s.scalar(select(VenueReport).where(VenueReport.id == report_id).with_for_update())
        if r is None:
            raise NotFoundError("Report not found.", code="REPORT_NOT_FOUND")
        if r.status in ("dismissed", "action_taken"):
            raise ConflictError("This report is already closed.", code="REPORT_CLOSED")
        before = {"status": r.status}
        r.status = status
        if note:
            r.resolution_note = note
        if status in ("dismissed", "action_taken"):
            r.resolved_by = actor.id
            r.resolved_at = datetime.now(UTC)
        audit.record(self.s, actor.profile, "admin.venue_report_reviewed", "venue_report", r.id, before=before,
                     after={"status": status}, reason=note, venue_id=str(r.venue_id))  # fmt: skip
        await self.s.commit()
        return await self.get_report(report_id)
