"""Pure unit tests (no database): slot generation, availability rules, pricing, status rules."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.errors import ConflictError
from app.domain import booking_state as st
from app.domain import pricing
from app.domain import slot_engine as eng

IST = ZoneInfo("Asia/Kolkata")
WEEKLY = {d: [(time(6), time(22))] for d in range(7)}
DAY = date(2030, 1, 7)  # a Monday


def test_normal_hours_generate_back_to_back_slots():
    ws = eng.generate_windows(DAY, IST, [(time(6), time(9))], 60)
    assert [w.starts_at.astimezone(IST).strftime("%H:%M") for w in ws] == ["06:00", "07:00", "08:00"]
    assert all(w.ends_at - w.starts_at == timedelta(minutes=60) for w in ws)


def test_remainder_at_close_is_unused_and_nothing_crosses_closing():
    ws = eng.generate_windows(DAY, IST, [(time(6), time(8, 30))], 60)
    assert len(ws) == 2 and ws[-1].ends_at.astimezone(IST).time() == time(8)


def test_slot_longer_than_opening_gives_nothing():
    assert eng.generate_windows(DAY, IST, [(time(6), time(6, 30))], 60) == []


def test_split_hours_generate_each_interval():
    ws = eng.generate_windows(DAY, IST, [(time(6), time(8)), (time(16), time(18))], 60)
    assert len(ws) == 4


def test_closed_weekday_and_special_closure_and_special_hours():
    assert eng.plan_day(DAY, {}, None).closed_reason == "weekly_closed"
    closed = eng.plan_day(DAY, WEEKLY, eng.SpecialDay(True, note="Holi"))
    assert closed.intervals == [] and closed.closed_reason == "special_closure" and closed.note == "Holi"
    custom = eng.plan_day(DAY, WEEKLY, eng.SpecialDay(False, time(10), time(12)))
    assert custom.intervals == [(time(10), time(12))]  # special date REPLACES regular hours


def test_overlapping_booking_and_adjacent_booking():
    ws = eng.generate_windows(DAY, IST, [(time(6), time(9))], 60)
    now = datetime(2029, 1, 1, tzinfo=UTC)
    seven = ws[1]
    free = eng.filter_available(ws, [(seven.starts_at, seven.ends_at)], now=now)
    assert [w.starts_at for w in free] == [ws[0].starts_at, ws[2].starts_at]  # adjacent slots stay free
    half = (seven.starts_at + timedelta(minutes=30), seven.ends_at + timedelta(minutes=30))
    assert len(eng.filter_available(ws, [half], now=now)) == 1  # a partial overlap blocks both


def test_started_slots_and_notice_and_advance_rules():
    ws = eng.generate_windows(DAY, IST, [(time(6), time(9))], 60)
    now = ws[0].starts_at + timedelta(minutes=1)
    assert [w.starts_at for w in eng.filter_available(ws, [], now=now)] == [ws[1].starts_at, ws[2].starts_at]
    just_before = ws[0].starts_at - timedelta(minutes=10)
    assert len(eng.filter_available(ws, [], now=just_before, min_notice_minutes=30)) == 2
    assert eng.filter_available(ws, [], now=just_before - timedelta(days=5), max_advance_days=1) == []
    assert len(eng.filter_available(ws, [], now=just_before)) == 3  # no rule configured -> none applied


def test_dst_nonexistent_time_is_skipped_not_shifted():
    ny = ZoneInfo("America/New_York")
    spring = date(2030, 3, 10)  # clocks jump 02:00 -> 03:00
    ws = eng.generate_windows(spring, ny, [(time(0), time(5))], 60)
    local = [w.starts_at.astimezone(ny).strftime("%H:%M") for w in ws]
    assert "02:00" not in local and "00:00" in local and "03:00" in local
    assert all(w.starts_at.tzinfo is not None for w in ws)


def test_day_bounds_cover_a_23_hour_dst_day():
    ny = ZoneInfo("America/New_York")
    start, end = eng.day_utc_bounds(date(2030, 3, 10), ny)
    assert end - start == timedelta(hours=23)


def test_pricing_has_no_invented_charges_and_validates():
    q = pricing.quote(slot_price_paise=50000, quantity=2, slot_minutes=60)
    assert q["base_amount_paise"] == 100000 == q["total_amount_paise"]
    assert q["fees_paise"] == q["tax_paise"] == q["discount_paise"] == 0
    with pytest.raises(ValueError):
        pricing.quote(slot_price_paise=-1, quantity=1, slot_minutes=60)


def test_status_transitions_and_actor_rules():
    st.check_transition(st.PENDING, st.CANCELLED_CUSTOMER, "customer")
    st.check_transition(st.PENDING, st.CONFIRMED, "system")
    with pytest.raises(ConflictError) as e:
        st.check_transition(st.COMPLETED, st.CONFIRMED, "system")
    assert e.value.code == "INVALID_STATUS_TRANSITION"
    for actor, target in (("customer", st.CONFIRMED), ("owner", st.CANCELLED_OWNER), ("admin", st.CONFIRMED)):
        with pytest.raises(ConflictError) as e:
            st.check_transition(st.CONFIRMED if target != st.CONFIRMED else st.PENDING, target, actor)
        assert e.value.code == "TRANSITION_NOT_ALLOWED"
    for terminal in (st.EXPIRED, st.COMPLETED, st.REFUNDED):
        assert st.TRANSITIONS[terminal] == frozenset()
    assert {st.PENDING, st.FAILED, st.CONFIRMED} == st.BLOCKING
