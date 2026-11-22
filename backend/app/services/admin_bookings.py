"""Admin intervention on bookings: exceptional cancellation and dispute handling.

Booking status only changes through `BookingService._move`, i.e. the existing state machine
(extended with one admin target, `cancelled_by_admin`). Nothing here writes a status directly.
Money is never touched by a cancellation: a paid booking stays `paid` until an explicit,
separately audited refund is made (see RefundService), so booking and payment cannot drift apart.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.domain import booking_state as bst
from app.models import Booking, Dispute, DisputeEvent, Payment, Profile, Refund, Venue
from app.services import audit
from app.services.bookings import BookingService

ACTIVE = ("open", "investigating")


class AdminBookingOps:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.s = session
        self.settings = settings

    # ================================================================== exceptional cancellation
    async def cancel(
        self, actor: CurrentUser, booking_id: UUID, reason: str, dispute_id: UUID | None
    ) -> dict[str, Any]:
        booking = await self.s.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
        if booking is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        if dispute_id is not None:
            d = await self.s.get(Dispute, dispute_id)
            if d is None or d.booking_id != booking.id:
                raise ValidationFailedError(
                    "That dispute does not belong to this booking.", code="DISPUTE_MISMATCH"
                )
        before = {"status": booking.status, "payment_status": booking.payment_status}
        svc = BookingService(self.s, self.settings)
        svc._move(booking, bst.CANCELLED_ADMIN, "admin", actor.id, reason)  # raises on an illegal transition
        now = datetime.now(UTC)
        booking.cancelled_at = now
        booking.cancelled_by = actor.id
        booking.cancel_reason = reason[:300]
        await svc._unblock(booking.id)
        venue = await self.s.get(Venue, booking.venue_id)
        if venue is not None:
            await svc._notify_cancelled(venue, booking)
        paid = booking.payment_status in ("paid", "partially_refunded")
        audit.record(self.s, actor.profile, "admin.booking_cancelled", "booking", booking.id, before=before,
                     after={"status": bst.CANCELLED_ADMIN, "payment_status": booking.payment_status},
                     reason=reason, refund_decision_needed=paid)  # fmt: skip
        if dispute_id:
            self._event(dispute_id, actor.profile, "action", "Booking cancelled by an administrator.",
                        {"booking_id": str(booking.id)})  # fmt: skip
        await self.s.commit()
        return {
            "id": booking.id, "status": booking.status, "payment_status": booking.payment_status,
            "refund_decision_needed": paid,
            "message": "The booking is cancelled and the slot released. "
            + ("No money was moved: decide on a refund separately." if paid else "No payment had been taken."),
        }  # fmt: skip

    # ================================================================== disputes
    def _event(
        self,
        dispute_id: UUID,
        actor: Profile | None,
        kind: str,
        body: str | None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.s.add(
            DisputeEvent(
                dispute_id=dispute_id, kind=kind, body=body, data=audit.jsonable(data or {}),
                actor_id=actor.id if actor else None, actor_role=actor.role if actor else "system",
            )
        )  # fmt: skip

    def _base(self) -> Any:
        return (
            select(Dispute, Booking.booking_code, Booking.venue_name, Profile.full_name)
            .join(Booking, Booking.id == Dispute.booking_id)
            .join(Profile, Profile.id == Booking.customer_id)
        )

    @staticmethod
    def _row(d: Dispute, code: str, venue: str, customer: str) -> dict[str, Any]:
        return {
            "id": d.id, "booking_id": d.booking_id, "booking_code": code, "venue_name": venue,
            "customer_name": customer, "payment_id": d.payment_id, "raised_by_role": d.raised_by_role,
            "subject": d.subject, "description": d.description, "status": d.status, "priority": d.priority,
            "resolution_type": d.resolution_type, "resolution_note": d.resolution_note,
            "resolved_at": d.resolved_at, "created_at": d.created_at, "updated_at": d.updated_at,
        }  # fmt: skip

    async def list_disputes(
        self, status: str | None, priority: str | None, booking_id: UUID | None, limit: int, offset: int
    ) -> dict[str, Any]:
        stmt = self._base()
        if status:
            stmt = stmt.where(Dispute.status == status)
        if priority:
            stmt = stmt.where(Dispute.priority == priority)
        if booking_id:
            stmt = stmt.where(Dispute.booking_id == booking_id)
        rows = (
            await self.s.execute(
                stmt.order_by(Dispute.created_at.desc(), Dispute.id).limit(limit + 1).offset(offset)
            )
        ).all()
        return {
            "items": [self._row(*r) for r in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    async def get_dispute(self, dispute_id: UUID) -> dict[str, Any]:
        row = (await self.s.execute(self._base().where(Dispute.id == dispute_id))).first()
        if row is None:
            raise NotFoundError("Dispute not found.", code="DISPUTE_NOT_FOUND")
        d = row[0]
        b = await self.s.get(Booking, d.booking_id)
        pay = await self.s.get(Payment, d.payment_id) if d.payment_id else None
        refunds = (
            await self.s.scalars(select(Refund).where(Refund.dispute_id == d.id).order_by(Refund.created_at))
        ).all()
        events = (
            await self.s.execute(
                select(DisputeEvent, Profile.full_name)
                .outerjoin(Profile, Profile.id == DisputeEvent.actor_id)
                .where(DisputeEvent.dispute_id == d.id)
                .order_by(DisputeEvent.created_at, DisputeEvent.id)
            )
        ).all()
        assert b is not None
        return {
            **self._row(*row),
            "booking": {
                "id": b.id, "status": b.status, "payment_status": b.payment_status,
                "total_amount_paise": b.total_amount_paise, "currency": b.currency, "booking_date": b.booking_date,
                "customer_id": b.customer_id, "venue_id": b.venue_id,
            },
            "payment": None if pay is None else {
                "id": pay.id, "status": pay.status, "amount_paise": pay.amount_paise,
                "razorpay_payment_id": pay.provider_payment_id,
            },
            "refunds": [
                {"id": r.id, "amount_paise": r.amount_paise, "status": r.status, "created_at": r.created_at}
                for r in refunds
            ],
            "events": [
                {"id": e.id, "kind": e.kind, "body": e.body, "data": e.data, "actor_role": e.actor_role,
                 "actor_name": n, "created_at": e.created_at}
                for e, n in events
            ],
        }  # fmt: skip

    async def create_dispute(
        self, actor: CurrentUser, booking_id: UUID, subject: str, description: str | None,
        raised_by_role: str, priority: str,
    ) -> dict[str, Any]:  # fmt: skip
        booking = await self.s.get(Booking, booking_id)
        if booking is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        pay_id = await self.s.scalar(
            select(Payment.id)
            .where(Payment.booking_id == booking_id)
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
        d = Dispute(
            booking_id=booking_id, payment_id=pay_id, raised_by_role=raised_by_role, subject=subject,
            description=description, priority=priority, created_by=actor.id,
            raised_by=booking.customer_id if raised_by_role == "customer" else None,
        )  # fmt: skip
        self.s.add(d)
        try:
            await self.s.flush()
        except IntegrityError as exc:
            await self.s.rollback()
            raise ConflictError(
                "This booking already has an open dispute.", code="DISPUTE_ALREADY_OPEN"
            ) from exc
        self._event(d.id, actor.profile, "opened", subject, {"raised_by_role": raised_by_role})
        audit.record(self.s, actor.profile, "admin.dispute_opened", "dispute", d.id,
                     after={"booking_id": booking_id, "status": "open", "priority": priority}, reason=subject)  # fmt: skip
        await self.s.commit()
        return await self.get_dispute(d.id)

    async def _active(self, dispute_id: UUID) -> Dispute:
        d = await self.s.scalar(select(Dispute).where(Dispute.id == dispute_id).with_for_update())
        if d is None:
            raise NotFoundError("Dispute not found.", code="DISPUTE_NOT_FOUND")
        if d.status not in ACTIVE:
            raise ConflictError("This dispute is closed.", code="DISPUTE_CLOSED")
        return d

    async def add_event(self, actor: CurrentUser, dispute_id: UUID, kind: str, body: str) -> dict[str, Any]:
        d = await self._active(dispute_id)
        self._event(d.id, actor.profile, kind, body)
        audit.record(
            self.s, actor.profile, f"admin.dispute_{kind}", "dispute", d.id, after={"length": len(body)}
        )
        await self.s.commit()
        return await self.get_dispute(dispute_id)

    async def update(
        self,
        actor: CurrentUser,
        dispute_id: UUID,
        status: str | None,
        priority: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        d = await self._active(dispute_id)
        before = {"status": d.status, "priority": d.priority}
        if status and status != d.status:
            d.status = status
            self._event(
                d.id, actor.profile, "status_changed", reason, {"from": before["status"], "to": status}
            )
        if priority and priority != d.priority:
            d.priority = priority
            self._event(
                d.id, actor.profile, "priority_changed", reason, {"from": before["priority"], "to": priority}
            )
        audit.record(self.s, actor.profile, "admin.dispute_updated", "dispute", d.id, before=before,
                     after={"status": d.status, "priority": d.priority}, reason=reason)  # fmt: skip
        await self.s.commit()
        return await self.get_dispute(dispute_id)

    async def resolve(
        self, actor: CurrentUser, dispute_id: UUID, outcome: str, resolution_type: str, note: str
    ) -> dict[str, Any]:
        d = await self._active(dispute_id)
        booking = await self.s.get(Booking, d.booking_id)
        assert booking is not None
        # A resolution may only claim an action that really happened.
        if resolution_type in ("refund_full", "refund_partial"):
            n = await self.s.scalar(
                select(func.count()).where(
                    Refund.dispute_id == d.id, Refund.status.in_(("pending", "processed"))
                )
            )
            if not n:
                raise ConflictError(
                    "No accepted refund is linked to this dispute yet.", code="RESOLUTION_NOT_BACKED"
                )
        if resolution_type == "booking_cancelled" and booking.status not in (
            bst.CANCELLED_ADMIN, bst.CANCELLED_CUSTOMER, bst.CANCELLED_OWNER, bst.REFUND_PENDING, bst.REFUNDED
        ):  # fmt: skip
            raise ConflictError("The booking has not been cancelled.", code="RESOLUTION_NOT_BACKED")
        before = {"status": d.status}
        d.status = outcome
        d.resolution_type = resolution_type
        d.resolution_note = note
        d.resolved_by = actor.id
        d.resolved_at = datetime.now(UTC)
        self._event(
            d.id, actor.profile, "resolved", note, {"outcome": outcome, "resolution_type": resolution_type}
        )
        audit.record(self.s, actor.profile, "admin.dispute_resolved", "dispute", d.id, before=before,
                     after={"status": outcome, "resolution_type": resolution_type}, reason=note)  # fmt: skip
        await self.s.commit()
        return await self.get_dispute(dispute_id)
