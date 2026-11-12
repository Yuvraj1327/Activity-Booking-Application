"""Availability: turns schedules, special dates, blocks and bookings into bookable slots."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.domain import slot_engine as engine
from app.domain.booking_state import HOLDS
from app.models import (
    AvailabilityBlock,
    Booking,
    BookingSlot,
    ScheduleException,
    ScheduleRule,
    Venue,
    VenueResource,
)
from app.schemas.booking import (
    MAX_ADVANCE_QUERY_DAYS,
    MAX_AVAILABILITY_DAYS,
    AvailabilityOut,
    AvailableDatesOut,
    ResourceAvailability,
    SlotOut,
)

Busy = list[tuple[datetime, datetime]]


def utcnow() -> datetime:
    return datetime.now(UTC)


def is_configured(res: VenueResource) -> bool:
    return res.slot_minutes is not None and res.slot_price_paise is not None


@dataclass
class ScheduleData:
    weekly: dict[int, list[engine.Interval]]
    special: dict[date, engine.SpecialDay]


async def load_schedule(session: AsyncSession, venue_id: UUID, d_from: date, d_to: date) -> ScheduleData:
    weekly: dict[int, list[engine.Interval]] = {}
    rules = await session.execute(
        select(ScheduleRule.weekday, ScheduleRule.opens_at, ScheduleRule.closes_at).where(
            ScheduleRule.venue_id == venue_id
        )
    )
    for weekday, opens, closes in rules.all():
        weekly.setdefault(weekday, []).append((opens, closes))
    special: dict[date, engine.SpecialDay] = {}
    rows = await session.scalars(
        select(ScheduleException).where(
            ScheduleException.venue_id == venue_id,
            ScheduleException.on_date >= d_from,
            ScheduleException.on_date <= d_to,
        )
    )
    for e in rows:
        special[e.on_date] = engine.SpecialDay(e.is_closed, e.opens_at, e.closes_at, e.note)
    return ScheduleData(weekly, special)


async def load_busy(
    session: AsyncSession,
    venue_id: UUID,
    resource_ids: list[UUID],
    start: datetime,
    end: datetime,
    now: datetime,
) -> dict[UUID, Busy]:
    """Blocking reservations (excluding holds that have already expired) and owner blocks."""
    busy: dict[UUID, Busy] = {rid: [] for rid in resource_ids}
    if not resource_ids:
        return busy
    window = Range(start, end, bounds="[)")
    stale_hold = and_(Booking.status.in_(tuple(HOLDS)), Booking.expires_at <= now)
    booked = await session.execute(
        select(BookingSlot.resource_id, BookingSlot.slot_range)
        .join(Booking, Booking.id == BookingSlot.booking_id)
        .where(
            BookingSlot.resource_id.in_(resource_ids),
            BookingSlot.is_blocking.is_(True),
            ~stale_hold,
            BookingSlot.slot_range.overlaps(window),
        )
    )
    for rid, rng in booked.all():
        assert rng.lower is not None and rng.upper is not None
        busy[rid].append((rng.lower, rng.upper))
    blocks = await session.execute(
        select(AvailabilityBlock.resource_id, AvailabilityBlock.block_range).where(
            AvailabilityBlock.venue_id == venue_id,
            or_(AvailabilityBlock.resource_id.is_(None), AvailabilityBlock.resource_id.in_(resource_ids)),
            AvailabilityBlock.block_range.overlaps(window),
        )
    )
    for block_rid, rng in blocks.all():
        assert rng.lower is not None and rng.upper is not None
        for target in resource_ids if block_rid is None else [block_rid]:
            busy[target].append((rng.lower, rng.upper))
    return busy


class AvailabilityService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.s = session
        self.settings = settings

    async def published_venue(self, venue_id: UUID) -> Venue:
        venue = await self.s.scalar(select(Venue).where(Venue.id == venue_id, Venue.status == "published"))
        if venue is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        return venue

    async def resources(self, venue_id: UUID, resource_id: UUID | None = None) -> list[VenueResource]:
        stmt = select(VenueResource).where(
            VenueResource.venue_id == venue_id, VenueResource.is_active.is_(True)
        )
        if resource_id is not None:
            stmt = stmt.where(VenueResource.id == resource_id)
        rows = await self.s.scalars(stmt.order_by(VenueResource.sort_order, VenueResource.name))
        return list(rows.all())

    def _check_day(self, day: date, tz: ZoneInfo, now: datetime) -> None:
        today = now.astimezone(tz).date()
        if day < today:
            raise ValidationFailedError("Choose today or a later date.", code="INVALID_DATE")
        if day > today + timedelta(days=MAX_ADVANCE_QUERY_DAYS):
            raise ValidationFailedError("That date is too far ahead.", code="INVALID_DATE")

    def resource_windows(
        self, res: VenueResource, day: date, tz: ZoneInfo, plan: engine.DayPlan
    ) -> list[engine.Window]:
        if not is_configured(res) or not plan.intervals:
            return []
        assert res.slot_minutes is not None
        return engine.generate_windows(day, tz, plan.intervals, res.slot_minutes)

    def available(self, windows: list[engine.Window], busy: Busy, now: datetime) -> list[engine.Window]:
        return engine.filter_available(
            windows,
            busy,
            now=now,
            min_notice_minutes=self.settings.booking_min_notice_minutes,
            max_advance_days=self.settings.booking_max_advance_days,
        )

    async def for_date(
        self, venue_id: UUID, day: date, resource_id: UUID | None = None, now: datetime | None = None
    ) -> AvailabilityOut:
        now = now or utcnow()
        venue = await self.published_venue(venue_id)
        tz = ZoneInfo(venue.timezone)
        self._check_day(day, tz, now)
        resources = await self.resources(venue_id, resource_id)
        if resource_id is not None and not resources:
            raise NotFoundError("Resource not found.", code="RESOURCE_NOT_FOUND")
        data = await load_schedule(self.s, venue_id, day, day)
        plan = engine.plan_day(day, data.weekly, data.special.get(day))
        start, end = engine.day_utc_bounds(day, tz)
        busy = await load_busy(self.s, venue_id, [r.id for r in resources], start, end, now)
        out: list[ResourceAvailability] = []
        for res in resources:
            windows = self.resource_windows(res, day, tz, plan)
            free = self.available(windows, busy[res.id], now)
            state, message = self._state(res, plan, windows, free)
            out.append(
                ResourceAvailability(
                    resource_id=res.id,
                    name=res.name,
                    slot_minutes=res.slot_minutes,
                    slot_price_paise=res.slot_price_paise,
                    currency=venue.currency,
                    state=state,
                    message=message,
                    slots=[
                        SlotOut(
                            starts_at=w.starts_at,
                            ends_at=w.ends_at,
                            local_start=w.starts_at.astimezone(tz).strftime("%H:%M"),
                            local_end=w.ends_at.astimezone(tz).strftime("%H:%M"),
                            price_paise=res.slot_price_paise or 0,
                        )
                        for w in free
                    ],
                )
            )
        return AvailabilityOut(
            venue_id=venue_id,
            date=day,
            timezone=venue.timezone,
            closed_reason=plan.closed_reason,
            note=plan.note,
            resources=out,
        )

    @staticmethod
    def _state(
        res: VenueResource, plan: engine.DayPlan, windows: list[engine.Window], free: list[engine.Window]
    ) -> tuple[str, str | None]:
        if not is_configured(res):
            return "not_configured", "This court is not open for online booking yet."
        if plan.closed_reason == "special_closure":
            return "closed", plan.note or "Closed on this date."
        if not plan.intervals:
            return "closed", "Closed on this day of the week."
        if not windows:
            return "closed", "No bookable time on this date."
        if not free:
            return "fully_booked", "No slots left on this date."
        return "available", None

    async def dates(
        self, venue_id: UUID, d_from: date, d_to: date, now: datetime | None = None
    ) -> AvailableDatesOut:
        now = now or utcnow()
        if d_to < d_from or (d_to - d_from).days + 1 > MAX_AVAILABILITY_DAYS:
            raise ValidationFailedError(
                f"Choose a range of 1 to {MAX_AVAILABILITY_DAYS} days.", code="INVALID_DATE_RANGE"
            )
        venue = await self.published_venue(venue_id)
        tz = ZoneInfo(venue.timezone)
        today = now.astimezone(tz).date()
        d_from = max(d_from, today)
        if d_to < d_from or d_to > today + timedelta(days=MAX_ADVANCE_QUERY_DAYS):
            raise ValidationFailedError("That date range is not available.", code="INVALID_DATE_RANGE")
        resources = [r for r in await self.resources(venue_id) if is_configured(r)]
        if not resources:
            return AvailableDatesOut(venue_id=venue_id, date_from=d_from, date_to=d_to, dates=[])
        data = await load_schedule(self.s, venue_id, d_from, d_to)
        range_start = engine.day_utc_bounds(d_from, tz)[0]
        range_end = engine.day_utc_bounds(d_to, tz)[1]
        busy = await load_busy(self.s, venue_id, [r.id for r in resources], range_start, range_end, now)
        days: list[date] = []
        cursor = d_from
        while cursor <= d_to:
            plan = engine.plan_day(cursor, data.weekly, data.special.get(cursor))
            for res in resources:
                if self.available(self.resource_windows(res, cursor, tz, plan), busy[res.id], now):
                    days.append(cursor)
                    break
            cursor += timedelta(days=1)
        return AvailableDatesOut(venue_id=venue_id, date_from=d_from, date_to=d_to, dates=days)


def local_hhmm(value: datetime, tz: ZoneInfo) -> str:
    return value.astimezone(tz).strftime("%H:%M")


def combine_local(day: date, at: time, tz: ZoneInfo) -> datetime | None:
    return engine.local_to_utc(day, at, tz)
