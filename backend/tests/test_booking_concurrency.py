"""Double-booking prevention under real concurrency (separate app instances, separate DB pools)."""

import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import pytest

from tests.booking_helpers import API, book, future_day, iso, make_app, new_customer, seed_world
from tests.conftest import sql

HOLD = {"booking_hold_minutes": 10}
N = 10


def _race(clients, calls):
    """Run one callable per client at the same instant; return their results."""
    barrier = threading.Barrier(len(calls))

    def run(fn):
        barrier.wait()
        return fn()

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return [f.result() for f in [pool.submit(run, c) for c in calls]]


def test_many_customers_one_slot_exactly_one_wins(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    people = [new_customer(clean_db, f"P{i}") for i in range(N)]
    with ExitStack() as stack:
        clients = [stack.enter_context(make_app(clean_db, **HOLD)) for _ in range(N)]
        results = _race(
            clients,
            [
                (lambda c=c, h=h: book(c, w, iso(day, 9), headers=h))
                for c, (_, h) in zip(clients, people, strict=True)
            ],
        )
    codes = Counter(r.status_code for r in results)
    assert codes == {201: 1, 409: N - 1}, [r.text for r in results if r.status_code not in (201, 409)]
    assert {r.json()["code"] for r in results if r.status_code == 409} == {"SLOT_UNAVAILABLE"}
    assert sql(clean_db, "SELECT count(*) AS n FROM public.bookings")[0]["n"] == 1
    assert sql(clean_db, "SELECT count(*) AS n FROM public.booking_slots WHERE is_blocking")[0]["n"] == 1


def test_same_customer_same_key_creates_one_booking(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with ExitStack() as stack:
        clients = [stack.enter_context(make_app(clean_db, **HOLD)) for _ in range(6)]
        results = _race(
            clients, [(lambda c=c: book(c, w, iso(day, 9), key="same-key-12345")) for c in clients]
        )
    assert all(r.status_code in (200, 201) for r in results), [r.text for r in results]
    assert len({r.json()["id"] for r in results}) == 1
    assert sql(clean_db, "SELECT count(*) AS n FROM public.bookings")[0]["n"] == 1


def test_different_slots_all_succeed_in_parallel(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    people = [new_customer(clean_db, f"P{i}") for i in range(8)]
    with ExitStack() as stack:
        clients = [stack.enter_context(make_app(clean_db, **HOLD)) for _ in people]
        results = _race(
            clients,
            [
                (lambda c=c, h=h, hour=7 + i: book(c, w, iso(day, hour), headers=h))
                for i, (c, (_, h)) in enumerate(zip(clients, people, strict=True))
            ],
        )
    assert [r.status_code for r in results] == [201] * 8


def test_two_courts_same_time_both_succeed(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    court2 = sql(
        clean_db,
        "INSERT INTO public.venue_resources (venue_id,name,slot_minutes,slot_price_paise) VALUES ($1,'Court 2',60,40000) RETURNING id",
        w["venue"],
    )[0]["id"]
    people = [new_customer(clean_db, f"P{i}") for i in range(4)]
    targets = [w["resource"], court2, w["resource"], court2]
    with ExitStack() as stack:
        clients = [stack.enter_context(make_app(clean_db, **HOLD)) for _ in people]
        results = _race(
            clients,
            [
                (lambda c=c, h=h, t=t: book(c, {**w, "resource": t}, iso(day, 9), headers=h))
                for c, (_, h), t in zip(clients, people, targets, strict=True)
            ],
        )
    assert sorted(r.status_code for r in results) == [201, 201, 409, 409]


def _race_book_vs_close(db):
    w = seed_world(db)
    day = future_day()
    close = {"special": [{"on_date": day.isoformat(), "is_closed": True}]}
    url = f"{API}/owners/venues/{w['venue']}/schedules"
    with make_app(db, **HOLD) as c1, make_app(db, **HOLD) as c2:
        r_book, r_close = _race(
            [c1, c2],
            [
                lambda: book(c1, w, iso(day, 9)),
                lambda: c2.put(url, json=close, headers=w["owner_h"]),
            ],
        )
    return w, r_book, r_close


def test_booking_races_with_owner_schedule_change_never_leaves_an_invalid_booking(clean_db):
    """Either the booking wins (and the owner change is refused), or the change wins (and the
    booking is rejected). A booking on a now-closed day must never result."""
    for _ in range(4):
        w, r_book, r_close = _race_book_vs_close(clean_db)
        closed = sql(
            clean_db, "SELECT count(*) AS n FROM public.schedule_exceptions WHERE venue_id=$1", w["venue"]
        )[0]["n"]
        booked = sql(clean_db, "SELECT count(*) AS n FROM public.bookings WHERE venue_id=$1", w["venue"])[0][
            "n"
        ]
        assert not (closed == 1 and booked == 1), (r_book.text, r_close.text)
        assert r_book.status_code in (201, 422) and r_close.status_code in (200, 409)
        if booked == 1:
            assert r_close.status_code == 409 and r_close.json()["code"] == "SCHEDULE_CONFLICT"


def test_database_itself_refuses_overlapping_blocking_slots(clean_db):
    """Even code that bypasses the service cannot double-book: the exclusion constraint is the last line."""
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        b = book(api, w, iso(day, 9)).json()
    other, _ = new_customer(clean_db)
    second = sql(
        clean_db,
        "INSERT INTO public.bookings (booking_code,customer_id,venue_id,resource_id,status,booking_date,starts_at,ends_at,"
        "duration_minutes,base_amount_paise,total_amount_paise,venue_name,resource_name,timezone,expires_at) "
        "SELECT 'ZUR-RAWTEST1',$1,venue_id,resource_id,'pending_payment',booking_date,starts_at,ends_at,duration_minutes,"
        "base_amount_paise,total_amount_paise,venue_name,resource_name,timezone,now()+interval '5 min' "
        "FROM public.bookings WHERE id=$2 RETURNING id",
        other, uuid.UUID(b["id"]),
    )[0]["id"]  # fmt: skip
    with pytest.raises(Exception) as err:
        sql(
            clean_db,
            "INSERT INTO public.booking_slots (booking_id,resource_id,slot_range,is_blocking) "
            "SELECT $1,resource_id,slot_range,true FROM public.booking_slots WHERE booking_id=$2",
            second, uuid.UUID(b["id"]),
        )  # fmt: skip
    assert "ex_booking_slots_no_overlap" in str(err.value) or "conflicting key" in str(err.value)
    # a non-blocking (cancelled/expired) row may overlap, and a back-to-back slot is fine
    sql(
        clean_db,
        "INSERT INTO public.booking_slots (booking_id,resource_id,slot_range,is_blocking) "
        "SELECT $1,resource_id,slot_range,false FROM public.booking_slots WHERE booking_id=$2",
        second, uuid.UUID(b["id"]),
    )  # fmt: skip
    sql(
        clean_db,
        "INSERT INTO public.booking_slots (booking_id,resource_id,slot_range,is_blocking) "
        "SELECT $1,resource_id,tstzrange(upper(slot_range), upper(slot_range)+interval '1 hour'),true "
        "FROM public.booking_slots WHERE booking_id=$2 AND is_blocking",
        second, uuid.UUID(b["id"]),
    )  # fmt: skip
