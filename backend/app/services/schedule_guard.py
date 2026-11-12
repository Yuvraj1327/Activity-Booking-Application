"""Schedule-change policy (open question Q16, architecture 9.5 default).

A change to hours, special dates, slot length, courts or blocks is REFUSED when it would
invalidate a future reservation. Reservations are never cancelled automatically. The check runs
after the change has been flushed (but not committed), so it sees the would-be state.
"""

from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.domain import slot_engine as engine
from app.domain.booking_state import BLOCKING, HOLDS
from app.models import AvailabilityBlock, Booking, Venue, VenueResource
from app.services.availability import is_configured, load_schedule

MAX_LISTED = 20


async def ensure_no_conflicts(session: AsyncSession, venue: Venue, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    stale = and_(Booking.status.in_(tuple(HOLDS)), Booking.expires_at <= now)
    bookings = (
        await session.scalars(
            select(Booking).where(
                Booking.venue_id == venue.id,
                Booking.status.in_(tuple(BLOCKING)),
                Booking.ends_at > now,
                ~stale,
            )
        )
    ).all()
    if not bookings:
        return
    tz = ZoneInfo(venue.timezone)
    resources = {
        r.id: r
        for r in (await session.scalars(select(VenueResource).where(VenueResource.venue_id == venue.id)))
    }
    days = [b.starts_at.astimezone(tz).date() for b in bookings]
    data = await load_schedule(session, venue.id, min(days), max(days))
    blocks = [
        (blk.resource_id, blk.block_range)
        for blk in await session.scalars(
            select(AvailabilityBlock).where(AvailabilityBlock.venue_id == venue.id)
        )
    ]
    broken: list[Booking] = []
    for b in bookings:
        res: VenueResource | None = resources.get(b.resource_id)
        if res is None or not res.is_active or not is_configured(res):
            broken.append(b)
            continue
        assert res.slot_minutes is not None
        day = b.starts_at.astimezone(tz).date()
        plan = engine.plan_day(day, data.weekly, data.special.get(day))
        windows = engine.generate_windows(day, tz, plan.intervals, res.slot_minutes) if plan.intervals else []
        if not any(w.starts_at == b.starts_at and w.ends_at == b.ends_at for w in windows):
            broken.append(b)
            continue
        for rid, rng in blocks:
            applies = rid is None or rid == b.resource_id
            if applies and rng.lower and rng.upper and b.starts_at < rng.upper and rng.lower < b.ends_at:
                broken.append(b)
                break
    if broken:
        # Read everything BEFORE the rollback: it expires the loaded objects.
        listed = [
            {
                "booking_id": str(b.id),
                "booking_code": b.booking_code,
                "starts_at": b.starts_at.isoformat(),
                "ends_at": b.ends_at.isoformat(),
                "status": b.status,
            }
            for b in sorted(broken, key=lambda x: x.starts_at)[:MAX_LISTED]
        ]
        count = len(broken)
        await session.rollback()
        raise ConflictError(
            "This change would affect existing bookings. Nothing was changed.",
            code="SCHEDULE_CONFLICT",
            details={"count": count, "bookings": listed},
        )


async def has_bookings(
    session: AsyncSession, *, venue_id: UUID | None = None, resource_id: UUID | None = None
) -> bool:
    stmt = select(Booking.id).limit(1)
    if venue_id is not None:
        stmt = stmt.where(Booking.venue_id == venue_id)
    if resource_id is not None:
        stmt = stmt.where(Booking.resource_id == resource_id)
    return (await session.scalar(stmt)) is not None
