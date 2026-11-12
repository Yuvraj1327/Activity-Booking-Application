"""Booking creation, cancellation and listing.

Double-booking is prevented in the database (exclusion constraint on booking_slots). The service
adds: a venue-row share lock (owners take the exclusive lock when changing schedules), an
in-transaction revalidation with the slot engine, idempotency, and lazy settlement of expired
holds / finished bookings.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.domain import booking_state as st
from app.domain import pricing
from app.domain import slot_engine as engine
from app.models import (
    AuditLog,
    Booking,
    BookingSlot,
    BookingStatusHistory,
    Notification,
    Profile,
    Venue,
    VenueResource,
)
from app.schemas.booking import (
    AdminBookingOut,
    AdminBookingPage,
    BookingOut,
    BookingPage,
    BookingRequest,
    CancellationPreview,
    OwnerBookingOut,
    OwnerBookingPage,
    QuoteOut,
    StatusEvent,
)
from app.services.availability import is_configured, load_busy, load_schedule, utcnow
from app.services.notifications import EmailSpec, NotificationService

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
_BUCKETS = ("upcoming", "past", "cancelled")


def new_code() -> str:
    return "ZUR-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


def _sqlstate(exc: IntegrityError) -> str | None:
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def request_hash(resource_id: UUID, starts_at: datetime) -> str:
    raw = f"{resource_id}|{starts_at.astimezone(UTC).isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


class BookingService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.s = session
        self.settings = settings

    # ------------------------------------------------------------------ status plumbing
    def _move(
        self,
        booking: Booking,
        target: str,
        actor_role: str,
        actor_id: UUID | None,
        reason: str | None = None,
    ) -> None:
        """The single place where a booking's status changes."""
        st.check_transition(booking.status, target, actor_role)
        self.s.add(
            BookingStatusHistory(
                booking_id=booking.id,
                from_status=booking.status,
                to_status=target,
                actor_id=actor_id,
                actor_role=actor_role,
                reason=reason,
            )
        )
        booking.status = target

    async def _unblock(self, booking_id: UUID) -> None:
        await self.s.execute(
            update(BookingSlot).where(BookingSlot.booking_id == booking_id).values(is_blocking=False)
        )

    async def settle_due(
        self,
        *,
        customer_id: UUID | None = None,
        venue_ids: list[UUID] | None = None,
        resource_id: UUID | None = None,
        now: datetime | None = None,
    ) -> None:
        """Expire holds whose time ran out and complete finished bookings (history is written)."""
        now = now or utcnow()
        scope = []
        if customer_id is not None:
            scope.append(Booking.customer_id == customer_id)
        if venue_ids is not None:
            scope.append(Booking.venue_id.in_(venue_ids))
        if resource_id is not None:
            scope.append(Booking.resource_id == resource_id)
        stale = await self.s.scalars(
            select(Booking)
            .where(Booking.status.in_(tuple(st.HOLDS)), Booking.expires_at <= now, *scope)
            .with_for_update(skip_locked=True)
        )
        for b in stale:
            self._move(b, st.EXPIRED, "system", None, "Payment time ran out.")
            await self._unblock(b.id)
        done = await self.s.scalars(
            select(Booking)
            .where(Booking.status == st.CONFIRMED, Booking.ends_at <= now, *scope)
            .with_for_update(skip_locked=True)
        )
        for b in done:
            self._move(b, st.COMPLETED, "system", None)
            await self._unblock(b.id)
        await self.s.flush()

    # ------------------------------------------------------------------ pricing and validation
    async def _resource_and_venue(self, resource_id: UUID, *, lock: bool) -> tuple[VenueResource, Venue]:
        res = await self.s.scalar(
            select(VenueResource).where(VenueResource.id == resource_id, VenueResource.is_active.is_(True))
        )
        if res is None:
            raise NotFoundError("Court not found.", code="RESOURCE_NOT_FOUND")
        stmt = select(Venue).where(Venue.id == res.venue_id, Venue.status == "published")
        if lock:
            stmt = stmt.with_for_update(read=True)  # FOR SHARE: owners' schedule edits wait for us
        venue = await self.s.scalar(stmt)
        if venue is None:
            raise NotFoundError("Court not found.", code="RESOURCE_NOT_FOUND")
        if not is_configured(res):
            raise ConflictError(
                "This court is not open for online booking yet.", code="RESOURCE_NOT_CONFIGURED"
            )
        return res, venue

    async def _validate_slot(
        self, res: VenueResource, venue: Venue, starts_at: datetime, now: datetime
    ) -> engine.Window:
        """The requested start must be exactly one currently offered slot (or taken -> 409)."""
        assert res.slot_minutes is not None
        tz = ZoneInfo(venue.timezone)
        day = starts_at.astimezone(tz).date()
        data = await load_schedule(self.s, venue.id, day, day)
        plan = engine.plan_day(day, data.weekly, data.special.get(day))
        windows = engine.generate_windows(day, tz, plan.intervals, res.slot_minutes) if plan.intervals else []
        start_utc = starts_at.astimezone(UTC)
        window = next((w for w in windows if w.starts_at == start_utc), None)
        if window is None:
            raise ValidationFailedError(
                "That time is not a bookable slot for this court.", code="INVALID_SLOT"
            )
        rules = engine.filter_available(
            [window],
            [],
            now=now,
            min_notice_minutes=self.settings.booking_min_notice_minutes,
            max_advance_days=self.settings.booking_max_advance_days,
        )
        if not rules:
            raise ValidationFailedError("That slot can no longer be booked.", code="SLOT_NOT_BOOKABLE")
        busy = await load_busy(self.s, venue.id, [res.id], window.starts_at, window.ends_at, now)
        if busy[res.id]:
            raise ConflictError("That slot was just taken. Please pick another.", code="SLOT_UNAVAILABLE")
        return window

    async def quote(self, body: BookingRequest) -> QuoteOut:
        now = utcnow()
        await self.settle_due(resource_id=body.resource_id, now=now)
        res, venue = await self._resource_and_venue(body.resource_id, lock=False)
        window = await self._validate_slot(res, venue, body.starts_at, now)
        assert res.slot_minutes is not None and res.slot_price_paise is not None
        q = pricing.quote(
            slot_price_paise=res.slot_price_paise,
            quantity=1,
            slot_minutes=res.slot_minutes,
            currency=venue.currency,
        )
        return QuoteOut(
            resource_id=res.id,
            venue_id=venue.id,
            starts_at=window.starts_at,
            ends_at=window.ends_at,
            duration_minutes=res.slot_minutes,
            currency=venue.currency,
            base_amount_paise=q["base_amount_paise"],
            fees_paise=q["fees_paise"],
            tax_paise=q["tax_paise"],
            discount_paise=q["discount_paise"],
            total_amount_paise=q["total_amount_paise"],
            note=q["note"],
        )

    # ------------------------------------------------------------------ create
    async def create(
        self, customer_id: UUID, body: BookingRequest, idempotency_key: str | None
    ) -> tuple[BookingOut, bool]:
        mode = self.settings.booking_mode
        hold_minutes = self.settings.booking_hold_minutes
        if mode == "hold" and hold_minutes is None:
            raise ServiceUnavailableError(
                "Online booking is not configured yet.", code="BOOKING_NOT_CONFIGURED"
            )
        if idempotency_key is not None and not (8 <= len(idempotency_key) <= 100):
            raise ValidationFailedError(
                "Idempotency-Key must be 8 to 100 characters.", code="INVALID_IDEMPOTENCY_KEY"
            )
        digest = request_hash(body.resource_id, body.starts_at)
        if idempotency_key is not None:
            existing = await self._by_key(customer_id, idempotency_key)
            if existing is not None:
                return self._replay(existing, digest), False
        try:
            return await self._create(customer_id, body, idempotency_key, digest, mode, hold_minutes)
        except ConflictError as exc:
            if exc.code != "SLOT_UNAVAILABLE" or idempotency_key is None:
                raise
            # A concurrent request with the SAME key may have just won the slot: that is a replay,
            # not a conflict.
            await self.s.rollback()
            again = await self._by_key(customer_id, idempotency_key)
            if again is not None:
                return self._replay(again, digest), False
            raise

    async def _create(
        self,
        customer_id: UUID,
        body: BookingRequest,
        idempotency_key: str | None,
        digest: str,
        mode: str,
        hold_minutes: int | None,
    ) -> tuple[BookingOut, bool]:
        now = utcnow()
        await self.settle_due(resource_id=body.resource_id, now=now)
        res, venue = await self._resource_and_venue(body.resource_id, lock=True)
        window = await self._validate_slot(res, venue, body.starts_at, now)
        assert res.slot_minutes is not None and res.slot_price_paise is not None
        snap = pricing.quote(
            slot_price_paise=res.slot_price_paise,
            quantity=1,
            slot_minutes=res.slot_minutes,
            currency=venue.currency,
        )
        status = st.CONFIRMED if mode == "instant" else st.PENDING
        tz = ZoneInfo(venue.timezone)
        for _ in range(5):  # booking_code collisions are astronomically rare; retry anyway
            booking = Booking(
                booking_code=new_code(),
                customer_id=customer_id,
                venue_id=venue.id,
                resource_id=res.id,
                status=status,
                payment_status="unpaid",
                booking_date=window.starts_at.astimezone(tz).date(),
                starts_at=window.starts_at,
                ends_at=window.ends_at,
                duration_minutes=res.slot_minutes,
                base_amount_paise=snap["base_amount_paise"],
                total_amount_paise=snap["total_amount_paise"],
                currency=venue.currency,
                price_snapshot=snap,
                venue_name=venue.name,
                resource_name=res.name,
                timezone=venue.timezone,
                expires_at=now + timedelta(minutes=hold_minutes or 0) if status == st.PENDING else None,
                confirmed_at=now if status == st.CONFIRMED else None,
                idempotency_key=idempotency_key,
                request_hash=digest,
            )
            try:
                async with self.s.begin_nested():
                    self.s.add(booking)
                    await self.s.flush()
                    self.s.add(
                        BookingSlot(
                            booking_id=booking.id,
                            resource_id=res.id,
                            slot_range=Range(window.starts_at, window.ends_at, bounds="[)"),
                            is_blocking=True,
                        )
                    )
                    await self.s.flush()
            except IntegrityError as exc:
                state = _sqlstate(exc)
                if state == "23P01":  # exclusion violation: someone else holds this slot
                    raise ConflictError(
                        "That slot was just taken. Please pick another.", code="SLOT_UNAVAILABLE"
                    ) from exc
                if state == "23505":
                    text = str(exc.orig)
                    if "uq_bookings_idempotency" in text:  # concurrent retry of the same request
                        await self.s.rollback()
                        again = await self._by_key(customer_id, idempotency_key or "")
                        if again is not None:
                            return self._replay(again, digest), False
                    continue
                raise
            break
        else:
            raise ConflictError("Could not create the booking. Please try again.", code="BOOKING_CONFLICT")
        self.s.add(
            BookingStatusHistory(
                booking_id=booking.id,
                from_status=None,
                to_status=status,
                actor_id=customer_id,
                actor_role="customer",
                reason=None,
            )
        )
        self.s.add(
            AuditLog(
                actor_id=customer_id,
                actor_role="customer",
                action="booking.created",
                entity_type="booking",
                entity_id=str(booking.id),
                metadata_={"venue_id": str(venue.id), "resource_id": str(res.id), "status": status},
            )
        )
        if status == st.CONFIRMED:
            self._notify_owner(venue, booking, "booking.created", "New booking")
        await self.s.commit()
        await self.s.refresh(booking)
        return self._out(booking, now=now), True

    def _replay(self, existing: Booking, digest: str) -> BookingOut:
        if existing.request_hash != digest:
            raise ValidationFailedError(
                "This Idempotency-Key was already used for a different request.",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        return self._out(existing, now=utcnow())

    async def _by_key(self, customer_id: UUID, key: str) -> Booking | None:
        return await self.s.scalar(
            select(Booking).where(Booking.customer_id == customer_id, Booking.idempotency_key == key)
        )

    def _notify_owner(self, venue: Venue, booking: Booking, kind: str, title: str) -> None:
        self.s.add(
            Notification(
                user_id=venue.owner_id,
                type=kind,
                title=title,
                body=f"{booking.venue_name} / {booking.resource_name}: {booking.booking_code}",
                data={"booking_id": str(booking.id), "venue_id": str(venue.id)},
                booking_id=booking.id,
                push_status="pending",
            )
        )

    async def _notify_cancelled(self, venue: Venue, b: Booking) -> None:
        """Customer and owner are told once (dedupe keys), by push, in-app and email."""
        local = b.starts_at.astimezone(ZoneInfo(b.timezone))
        ctx = {
            "booking_code": b.booking_code,
            "venue_name": b.venue_name,
            "resource_name": b.resource_name,
            "when": f"{local:%a %d %b %Y, %H:%M}",
        }
        notes = NotificationService(self.s)
        key = f"booking:{b.id}:cancelled"
        await notes.queue(
            user_id=b.customer_id,
            type_="booking.cancelled",
            title="Booking cancelled",
            body=f"{b.venue_name}: {b.booking_code}",
            dedupe_key=f"{key}:customer",
            booking_id=b.id,
            email=EmailSpec("booking_cancelled", ctx),
        )
        await notes.queue(
            user_id=venue.owner_id,
            type_="booking.cancelled",
            title="Booking cancelled",
            body=f"{b.venue_name} / {b.resource_name}: {b.booking_code}",
            dedupe_key=f"{key}:owner",
            booking_id=b.id,
            email=EmailSpec("owner_booking_cancelled", ctx),
        )

    # ------------------------------------------------------------------ cancel
    def _cancel_decision(self, b: Booking, now: datetime) -> CancellationPreview:
        if b.status not in (st.PENDING, st.FAILED, st.CONFIRMED):
            return CancellationPreview(
                can_cancel=False, code="NOT_CANCELLABLE", message="This booking can no longer be cancelled."
            )
        if b.status in st.HOLDS:
            return CancellationPreview(can_cancel=True, code="OK", message="Cancelling releases the slot.")
        if b.payment_status == "paid":
            return CancellationPreview(
                can_cancel=False,
                code="CANCELLATION_NOT_AVAILABLE",
                message="Paid bookings cannot be cancelled online yet. Refund rules are not defined.",
            )
        hours = self.settings.cancellation_min_notice_hours
        if hours is None:
            return CancellationPreview(
                can_cancel=False,
                code="CANCELLATION_NOT_AVAILABLE",
                message="Cancellation rules are not configured for confirmed bookings.",
            )
        if b.starts_at - now < timedelta(hours=hours):
            return CancellationPreview(
                can_cancel=False,
                code="CANCELLATION_WINDOW_CLOSED",
                message=f"Bookings can be cancelled at least {hours} hour(s) before the start.",
            )
        return CancellationPreview(can_cancel=True, code="OK", message="You can cancel this booking.")

    async def cancellation_preview(self, customer_id: UUID, booking_id: UUID) -> CancellationPreview:
        await self.settle_due(customer_id=customer_id)
        b = await self._mine(customer_id, booking_id)
        return self._cancel_decision(b, utcnow())

    async def cancel(self, customer_id: UUID, booking_id: UUID, reason: str | None) -> BookingOut:
        now = utcnow()
        await self.settle_due(customer_id=customer_id, now=now)
        b = await self.s.scalar(
            select(Booking)
            .where(Booking.id == booking_id, Booking.customer_id == customer_id)
            .with_for_update()
        )
        if b is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        st.check_transition(b.status, st.CANCELLED_CUSTOMER, "customer")
        decision = self._cancel_decision(b, now)
        if not decision.can_cancel:
            raise ConflictError(decision.message, code=decision.code)
        was_confirmed = b.status == st.CONFIRMED
        self._move(b, st.CANCELLED_CUSTOMER, "customer", customer_id, reason)
        b.cancelled_at = now
        b.cancelled_by = customer_id
        b.cancel_reason = reason
        await self._unblock(b.id)
        self.s.add(
            AuditLog(
                actor_id=customer_id,
                actor_role="customer",
                action="booking.cancelled",
                entity_type="booking",
                entity_id=str(b.id),
                metadata_={"was_confirmed": was_confirmed},
            )
        )
        if was_confirmed:
            venue = await self.s.get(Venue, b.venue_id)
            if venue is not None:
                await self._notify_cancelled(venue, b)
        await self.s.commit()
        await self.s.refresh(b)
        return await self._detail(b, now)

    # ------------------------------------------------------------------ reads
    async def _mine(self, customer_id: UUID, booking_id: UUID) -> Booking:
        b = await self.s.scalar(
            select(Booking).where(Booking.id == booking_id, Booking.customer_id == customer_id)
        )
        if b is None:  # someone else's booking looks exactly like a missing one (no IDOR)
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        return b

    def _out(self, b: Booking, *, now: datetime, history: list[StatusEvent] | None = None) -> BookingOut:
        tz = ZoneInfo(b.timezone)
        return BookingOut(
            id=b.id,
            booking_code=b.booking_code,
            status=b.status,
            payment_status=b.payment_status,
            venue_id=b.venue_id,
            venue_name=b.venue_name,
            resource_id=b.resource_id,
            resource_name=b.resource_name,
            booking_date=b.booking_date,
            starts_at=b.starts_at,
            ends_at=b.ends_at,
            local_start=b.starts_at.astimezone(tz).strftime("%H:%M"),
            local_end=b.ends_at.astimezone(tz).strftime("%H:%M"),
            timezone=b.timezone,
            duration_minutes=b.duration_minutes,
            currency=b.currency,
            base_amount_paise=b.base_amount_paise,
            total_amount_paise=b.total_amount_paise,
            price=b.price_snapshot,
            expires_at=b.expires_at,
            created_at=b.created_at,
            cancelled_at=b.cancelled_at,
            cancel_reason=b.cancel_reason,
            can_cancel=self._cancel_decision(b, now).can_cancel,
            history=history or [],
        )

    async def _history(self, booking_id: UUID) -> list[StatusEvent]:
        rows = await self.s.scalars(
            select(BookingStatusHistory)
            .where(BookingStatusHistory.booking_id == booking_id)
            .order_by(BookingStatusHistory.created_at, BookingStatusHistory.id)
        )
        return [
            StatusEvent(
                from_status=h.from_status,
                to_status=h.to_status,
                actor_role=h.actor_role,
                reason=h.reason,
                created_at=h.created_at,
            )
            for h in rows
        ]

    async def _detail(self, b: Booking, now: datetime) -> BookingOut:
        return self._out(b, now=now, history=await self._history(b.id))

    @staticmethod
    def _bucket_filter(bucket: str, now: datetime) -> Any:
        if bucket == "upcoming":
            return and_(Booking.status.in_(tuple(st.BLOCKING)), Booking.ends_at > now)
        if bucket == "cancelled":
            return Booking.status.in_(tuple(st.CANCELLED))
        if bucket == "past":
            return Booking.status.in_((st.COMPLETED, st.EXPIRED))
        raise ValidationFailedError("bucket must be upcoming, past or cancelled.", code="INVALID_BUCKET")

    async def list_mine(self, customer_id: UUID, bucket: str, limit: int, offset: int) -> BookingPage:
        now = utcnow()
        await self.settle_due(customer_id=customer_id, now=now)
        order = Booking.starts_at.asc() if bucket == "upcoming" else Booking.starts_at.desc()
        rows = (
            await self.s.scalars(
                select(Booking)
                .where(Booking.customer_id == customer_id, self._bucket_filter(bucket, now))
                .order_by(order, Booking.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        await self.s.commit()
        return BookingPage(
            items=[self._out(b, now=now) for b in rows[:limit]],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    async def get_mine(self, customer_id: UUID, booking_id: UUID) -> BookingOut:
        now = utcnow()
        await self.settle_due(customer_id=customer_id, now=now)
        b = await self._mine(customer_id, booking_id)
        out = await self._detail(b, now)
        await self.s.commit()
        return out

    # -- owner
    async def _owner_venue_ids(self, owner_id: UUID) -> list[UUID]:
        return list((await self.s.scalars(select(Venue.id).where(Venue.owner_id == owner_id))).all())

    def _owner_out(
        self, b: Booking, name: str, now: datetime, history: list[StatusEvent] | None = None
    ) -> OwnerBookingOut:
        base = self._out(b, now=now, history=history)
        data = base.model_dump()
        data["can_cancel"] = False  # owners cannot cancel yet (N22)
        return OwnerBookingOut(**data, customer_name=name)

    async def list_owner(
        self, owner_id: UUID, bucket: str, venue_id: UUID | None, limit: int, offset: int
    ) -> OwnerBookingPage:
        now = utcnow()
        venue_ids = await self._owner_venue_ids(owner_id)
        if venue_id is not None:
            if venue_id not in venue_ids:
                raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
            venue_ids = [venue_id]
        await self.settle_due(venue_ids=venue_ids, now=now)
        order = Booking.starts_at.asc() if bucket == "upcoming" else Booking.starts_at.desc()
        # Held (unpaid) reservations are shown to owners only once confirmed; see D-60.
        visible = Booking.status.notin_(tuple(st.HOLDS))
        rows = (
            await self.s.execute(
                select(Booking, Profile.full_name)
                .join(Profile, Profile.id == Booking.customer_id)
                .where(Booking.venue_id.in_(venue_ids), visible, self._bucket_filter(bucket, now))
                .order_by(order, Booking.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        await self.s.commit()
        return OwnerBookingPage(
            items=[self._owner_out(b, name, now) for b, name in rows[:limit]],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    async def get_owner(self, owner_id: UUID, booking_id: UUID) -> OwnerBookingOut:
        now = utcnow()
        venue_ids = await self._owner_venue_ids(owner_id)
        await self.settle_due(venue_ids=venue_ids, now=now)
        row = (
            await self.s.execute(
                select(Booking, Profile.full_name)
                .join(Profile, Profile.id == Booking.customer_id)
                .where(Booking.id == booking_id, Booking.venue_id.in_(venue_ids))
            )
        ).first()
        if row is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        out = self._owner_out(row[0], row[1], now, await self._history(booking_id))
        await self.s.commit()
        return out

    async def owner_counts(self, owner_id: UUID) -> dict[str, int]:
        now = utcnow()
        venue_ids = await self._owner_venue_ids(owner_id)
        if not venue_ids:
            return {"total": 0, "upcoming": 0, "completed": 0, "cancelled": 0}
        await self.settle_due(venue_ids=venue_ids, now=now)
        rows = await self.s.execute(
            select(Booking.status, func.count())
            .where(Booking.venue_id.in_(venue_ids), Booking.status.notin_(tuple(st.HOLDS)))
            .group_by(Booking.status)
        )
        by = {k: v for k, v in rows.all()}
        upcoming = by.get(st.CONFIRMED, 0)
        completed = by.get(st.COMPLETED, 0)
        cancelled = sum(by.get(k, 0) for k in st.CANCELLED)
        await self.s.commit()
        return {
            "total": sum(by.values()),
            "upcoming": upcoming,
            "completed": completed,
            "cancelled": cancelled,
        }

    # -- admin
    async def list_admin(
        self, status: str | None, venue_id: UUID | None, limit: int, offset: int
    ) -> AdminBookingPage:
        now = utcnow()
        await self.settle_due(now=now)
        stmt = (
            select(Booking, Profile.full_name, Venue.owner_id)
            .join(Profile, Profile.id == Booking.customer_id)
            .join(Venue, Venue.id == Booking.venue_id)
        )
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        if venue_id is not None:
            stmt = stmt.where(Booking.venue_id == venue_id)
        rows = (
            await self.s.execute(
                stmt.order_by(Booking.created_at.desc(), Booking.id).limit(limit + 1).offset(offset)
            )
        ).all()
        await self.s.commit()
        items = [
            AdminBookingOut(
                **self._owner_out(b, name, now).model_dump(), customer_id=b.customer_id, owner_id=owner_id
            )
            for b, name, owner_id in rows[:limit]
        ]
        return AdminBookingPage(items=items, limit=limit, offset=offset, has_more=len(rows) > limit)

    async def get_admin(self, booking_id: UUID) -> AdminBookingOut:
        now = utcnow()
        await self.settle_due(now=now)
        row = (
            await self.s.execute(
                select(Booking, Profile.full_name, Venue.owner_id)
                .join(Profile, Profile.id == Booking.customer_id)
                .join(Venue, Venue.id == Booking.venue_id)
                .where(Booking.id == booking_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        b, name, owner_id = row
        out = AdminBookingOut(
            **self._owner_out(b, name, now, await self._history(b.id)).model_dump(),
            customer_id=b.customer_id,
            owner_id=owner_id,
        )
        await self.s.commit()
        return out
