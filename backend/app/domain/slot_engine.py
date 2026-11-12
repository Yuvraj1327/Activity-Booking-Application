"""Slot generation. Pure functions: no database, no clock (callers pass `now`).

One implementation serves the customer slot screen, the booking transaction's validation and
the owner schedule-conflict check, so they cannot disagree.

Rules (see docs/AVAILABILITY_LOGIC.md):
* Times in rules are LOCAL to the venue's time zone; every slot is converted to UTC instants.
* A special date REPLACES the regular hours of that date (assumption for Q16, not a decision
  about existing bookings: those are protected separately).
* Slots start at an interval's opening time and repeat every `slot_minutes`; a slot must end at
  or before the interval's closing time. A remainder shorter than a slot is unused.
* Local times that do not exist or are ambiguous (daylight-saving changes) are skipped.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

Interval = tuple[time, time]


@dataclass(frozen=True, order=True)
class Window:
    starts_at: datetime  # timezone-aware, UTC
    ends_at: datetime

    def overlaps(self, other_start: datetime, other_end: datetime) -> bool:
        return self.starts_at < other_end and other_start < self.ends_at


@dataclass(frozen=True)
class SpecialDay:
    is_closed: bool
    opens_at: time | None = None
    closes_at: time | None = None
    note: str | None = None


@dataclass(frozen=True)
class DayPlan:
    intervals: list[Interval]
    closed_reason: str | None  # None when open; else "special_closure" | "weekly_closed"
    note: str | None = None


def plan_day(day: date, weekly: dict[int, list[Interval]], special: SpecialDay | None) -> DayPlan:
    """Which local intervals the venue is open on `day` (weekday 0 = Monday)."""
    if special is not None:
        if special.is_closed:
            return DayPlan([], "special_closure", special.note)
        assert special.opens_at is not None and special.closes_at is not None
        return DayPlan([(special.opens_at, special.closes_at)], None, special.note)
    intervals = sorted(weekly.get(day.weekday(), []))
    return DayPlan(intervals, None if intervals else "weekly_closed")


def local_to_utc(day: date, at: time, tz: ZoneInfo) -> datetime | None:
    """Local wall time -> UTC, or None when that wall time does not exist / is ambiguous."""
    naive = datetime.combine(day, at)
    aware = naive.replace(tzinfo=tz, fold=0)
    other = naive.replace(tzinfo=tz, fold=1)
    if aware.utcoffset() != other.utcoffset():
        return None  # ambiguous (clocks go back) or non-existent (clocks go forward)
    return aware.astimezone(UTC)


def generate_windows(day: date, tz: ZoneInfo, intervals: list[Interval], slot_minutes: int) -> list[Window]:
    """Every slot the venue offers on `day`, before bookings and blocks are applied."""
    if slot_minutes <= 0:
        raise ValueError("slot_minutes must be positive")
    step = timedelta(minutes=slot_minutes)
    out: list[Window] = []
    for opens, closes in intervals:
        start_local = datetime.combine(day, opens)
        end_local = datetime.combine(day, closes)
        cursor = start_local
        while cursor + step <= end_local:
            s = local_to_utc(day, cursor.time(), tz)
            e_naive = cursor + step
            e = local_to_utc(day, e_naive.time(), tz)
            if s is not None and e is not None and e - s == step:
                out.append(Window(s, e))
            cursor += step
    return out


def day_utc_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """UTC instants [start, end) of the local calendar day (handles 23/25-hour days)."""
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)
    return start, end


def filter_available(
    windows: list[Window],
    busy: list[tuple[datetime, datetime]],
    *,
    now: datetime,
    min_notice_minutes: int | None = None,
    max_advance_days: int | None = None,
) -> list[Window]:
    """Drop slots that overlap a booking/block or fall outside the booking window.

    A slot that has already started is never offered. Minimum notice and maximum advance are
    optional settings (open question N6): when unset, no extra rule is applied.
    """
    earliest = now + timedelta(minutes=min_notice_minutes or 0)
    latest = now + timedelta(days=max_advance_days) if max_advance_days is not None else None
    out: list[Window] = []
    for w in windows:
        if w.starts_at <= now or w.starts_at < earliest:
            continue
        if latest is not None and w.starts_at > latest:
            continue
        if any(w.overlaps(s, e) for s, e in busy):
            continue
        out.append(w)
    return out
