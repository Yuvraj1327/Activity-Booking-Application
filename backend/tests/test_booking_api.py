import uuid

from tests.booking_helpers import API, book, future_day, iso, make_app, new_customer, seed_world
from tests.conftest import auth_headers, seed_profile, sql

HOLD = {"booking_hold_minutes": 10}
INSTANT = {"booking_mode": "instant", "cancellation_min_notice_hours": 24}


def _avail(api, w, day, h=None, **params):
    r = api.get(
        f"{API}/venues/{w['venue']}/availability",
        params={"date": day.isoformat(), **params},
        headers=h or w["customer_h"],
    )
    assert r.status_code == 200, r.text
    return r.json()


def _slots(data):
    return [s["local_start"] for s in data["resources"][0]["slots"]]


# ------------------------------------------------------------------ availability
def test_availability_requires_auth_and_lists_only_free_slots(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        assert (
            api.get(f"{API}/venues/{w['venue']}/availability", params={"date": day.isoformat()}).status_code
            == 401
        )
        data = _avail(api, w, day)
        assert data["timezone"] == "Asia/Kolkata" and data["resources"][0]["state"] == "available"
        assert _slots(data)[0] == "06:00" and _slots(data)[-1] == "21:00" and len(_slots(data)) == 16
        assert data["resources"][0]["slot_price_paise"] == 50000
        assert book(api, w, iso(day, 9)).status_code == 201
        after = _slots(_avail(api, w, day))
        assert "09:00" not in after and len(after) == 15


def test_closed_weekday_special_closure_and_custom_hours(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    sql(
        clean_db,
        "DELETE FROM public.schedule_rules WHERE venue_id=$1 AND weekday=$2",
        w["venue"],
        day.weekday(),
    )
    with make_app(clean_db, **HOLD) as api:
        d = _avail(api, w, day)
        assert d["closed_reason"] == "weekly_closed" and d["resources"][0]["state"] == "closed"
        assert d["resources"][0]["slots"] == []
        sql(
            clean_db,
            "INSERT INTO public.schedule_exceptions (venue_id, on_date, is_closed, opens_at, closes_at) "
            "VALUES ($1,$2,false,'10:00','12:00')",
            w["venue"], day,
        )  # fmt: skip
        assert _slots(_avail(api, w, day)) == ["10:00", "11:00"]  # special date replaces weekly hours
        other = future_day(4)
        sql(
            clean_db,
            "INSERT INTO public.schedule_exceptions (venue_id, on_date, is_closed, note) VALUES ($1,$2,true,'Holi')",
            w["venue"], other,
        )  # fmt: skip
        d = _avail(api, w, other)
        assert d["closed_reason"] == "special_closure" and d["note"] == "Holi"
        assert book(api, w, iso(other, 9)).status_code == 422  # cannot book a closed day


def test_not_configured_resource_has_no_slots_and_cannot_be_booked(clean_db):
    w = seed_world(clean_db, slot_minutes=None, price=None)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        d = _avail(api, w, day)
        assert d["resources"][0]["state"] == "not_configured" and d["resources"][0]["slots"] == []
        r = book(api, w, iso(day, 9))
        assert r.status_code == 409 and r.json()["code"] == "RESOURCE_NOT_CONFIGURED"


def test_invalid_dates_and_unknown_venue(clean_db):
    w = seed_world(clean_db)
    with make_app(clean_db, **HOLD) as api:
        past = api.get(
            f"{API}/venues/{w['venue']}/availability", params={"date": "2020-01-01"}, headers=w["customer_h"]
        )
        assert past.status_code == 422 and past.json()["code"] == "INVALID_DATE"
        bad = api.get(
            f"{API}/venues/{w['venue']}/availability", params={"date": "nope"}, headers=w["customer_h"]
        )
        assert bad.status_code == 422
        missing = api.get(
            f"{API}/venues/{uuid.uuid4()}/availability",
            params={"date": future_day().isoformat()},
            headers=w["customer_h"],
        )
        assert missing.status_code == 404 and missing.json()["code"] == "VENUE_NOT_FOUND"
        sql(clean_db, "UPDATE public.venues SET status='draft' WHERE id=$1", w["venue"])
        hidden = api.get(
            f"{API}/venues/{w['venue']}/availability",
            params={"date": future_day().isoformat()},
            headers=w["customer_h"],
        )
        assert hidden.status_code == 404  # unpublished venues are not bookable


def test_available_dates_range(clean_db):
    w = seed_world(clean_db)
    a, b = future_day(2), future_day(5)
    sql(
        clean_db,
        "INSERT INTO public.schedule_exceptions (venue_id,on_date,is_closed) VALUES ($1,$2,true)",
        w["venue"],
        future_day(3),
    )
    with make_app(clean_db, **HOLD) as api:
        r = api.get(
            f"{API}/venues/{w['venue']}/availability/dates",
            params={"date_from": a.isoformat(), "date_to": b.isoformat()},
            headers=w["customer_h"],
        )
        assert r.status_code == 200
        got = r.json()["dates"]
        assert future_day(3).isoformat() not in got and a.isoformat() in got and len(got) == 3
        too_long = api.get(
            f"{API}/venues/{w['venue']}/availability/dates",
            params={"date_from": a.isoformat(), "date_to": future_day(60).isoformat()},
            headers=w["customer_h"],
        )
        assert too_long.status_code == 422 and too_long.json()["code"] == "INVALID_DATE_RANGE"


# ------------------------------------------------------------------ create
def test_create_booking_snapshot_history_and_pricing(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        q = api.post(
            f"{API}/bookings/quote",
            json={"resource_id": str(w["resource"]), "starts_at": iso(day, 9)},
            headers=w["customer_h"],
        )
        assert (
            q.status_code == 200 and q.json()["total_amount_paise"] == 50000 and q.json()["fees_paise"] == 0
        )
        r = book(api, w, iso(day, 9))
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["status"] == "pending_payment" and b["payment_status"] == "unpaid"
        assert b["booking_code"].startswith("ZUR-") and b["duration_minutes"] == 60
        assert b["total_amount_paise"] == b["base_amount_paise"] == 50000 and b["price"]["fees_paise"] == 0
        assert b["local_start"] == "09:00" and b["local_end"] == "10:00" and b["expires_at"]
        assert b["venue_name"] == "Ace Arena" and b["resource_name"] == "Court 1"
        # later price changes never touch an existing booking
        sql(clean_db, "UPDATE public.venue_resources SET slot_price_paise=99900 WHERE id=$1", w["resource"])
        got = api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()
        assert got["total_amount_paise"] == 50000
        assert [h["to_status"] for h in got["history"]] == ["pending_payment"]
        row = sql(
            clean_db,
            "SELECT count(*) AS n FROM public.booking_slots WHERE booking_id=$1 AND is_blocking",
            uuid.UUID(b["id"]),
        )
        assert row[0]["n"] == 1


def test_invalid_requests_are_rejected(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        assert book(api, w, iso(day, 9, 30)).json()["code"] == "INVALID_SLOT"  # not on the slot grid
        assert book(api, w, iso(day, 5)).json()["code"] == "INVALID_SLOT"  # before opening
        assert book(api, w, iso(day, 22)).json()["code"] == "INVALID_SLOT"  # after last slot
        past = book(api, w, "2020-01-01T09:00:00+05:30")
        assert past.status_code == 422
        naive = api.post(
            f"{API}/bookings",
            json={"resource_id": str(w["resource"]), "starts_at": "2030-01-01T09:00:00"},
            headers=w["customer_h"],
        )
        assert naive.status_code == 422  # timezone offset required
        extra = api.post(
            f"{API}/bookings",
            json={"resource_id": str(w["resource"]), "starts_at": iso(day, 9), "total": 1},
            headers=w["customer_h"],
        )
        assert extra.status_code == 422  # clients can never send a price
        unknown = api.post(
            f"{API}/bookings",
            json={"resource_id": str(uuid.uuid4()), "starts_at": iso(day, 9)},
            headers=w["customer_h"],
        )
        assert unknown.status_code == 404 and unknown.json()["code"] == "RESOURCE_NOT_FOUND"
        assert book(api, w, iso(day, 9), key="short").json()["code"] == "INVALID_IDEMPOTENCY_KEY"


def test_unavailable_slot_conflict_and_owner_block(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    other, other_h = new_customer(clean_db)
    with make_app(clean_db, **HOLD) as api:
        assert book(api, w, iso(day, 9)).status_code == 201
        r = book(api, w, iso(day, 9), headers=other_h)
        assert r.status_code == 409 and r.json()["code"] == "SLOT_UNAVAILABLE"
        again = book(api, w, iso(day, 9))  # the same customer, no idempotency key
        assert again.status_code == 409
        blk = api.post(
            f"{API}/owners/venues/{w['venue']}/blocks",
            json={
                "resource_id": str(w["resource"]),
                "starts_at": iso(day, 12),
                "ends_at": iso(day, 14),
                "reason": "Maintenance",
            },
            headers=w["owner_h"],
        )
        assert blk.status_code == 201, blk.text
        assert {"12:00", "13:00"}.isdisjoint(_slots(_avail(api, w, day)))
        assert book(api, w, iso(day, 12)).json()["code"] == "SLOT_UNAVAILABLE"
        assert (
            api.delete(
                f"{API}/owners/venues/{w['venue']}/blocks/{blk.json()['id']}", headers=w["owner_h"]
            ).status_code
            == 204
        )
        assert book(api, w, iso(day, 12)).status_code == 201


def test_multiple_resources_are_independent(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        c2 = api.post(
            f"{API}/owners/venues/{w['venue']}/resources",
            json={"name": "Court 2", "slot_minutes": 30, "slot_price_paise": 30000},
            headers=w["owner_h"],
        )
        assert c2.status_code == 201
        d = _avail(api, w, day)
        assert [r["name"] for r in d["resources"]] == ["Court 1", "Court 2"]
        assert len(d["resources"][1]["slots"]) == 32  # 30-minute slots
        assert book(api, w, iso(day, 9)).status_code == 201
        w2 = {**w, "resource": uuid.UUID(c2.json()["id"])}
        assert book(api, w2, iso(day, 9)).status_code == 201  # other court, same time
        assert book(api, w2, iso(day, 9, 30)).status_code == 201
        assert book(api, w2, iso(day, 9, 30)).status_code == 409


def test_booking_not_configured_and_instant_mode(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db) as api:  # no hold duration configured
        r = book(api, w, iso(day, 9))
        assert r.status_code == 503 and r.json()["code"] == "BOOKING_NOT_CONFIGURED"
    with make_app(clean_db, **INSTANT) as api:
        r = book(api, w, iso(day, 9))
        assert r.status_code == 201 and r.json()["status"] == "confirmed" and r.json()["expires_at"] is None
        assert r.json()["payment_status"] == "unpaid"  # never pretends to be paid


# ------------------------------------------------------------------ idempotency and expiry
def test_idempotency_key_replays_and_detects_reuse(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        first = book(api, w, iso(day, 9), key="key-12345678")
        second = book(api, w, iso(day, 9), key="key-12345678")
        assert first.status_code == 201 and second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        reuse = book(api, w, iso(day, 10), key="key-12345678")
        assert reuse.status_code == 422 and reuse.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
        n = sql(clean_db, "SELECT count(*) AS n FROM public.bookings")[0]["n"]
        assert n == 1


def test_expired_hold_releases_the_slot_and_is_recorded(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    other, other_h = new_customer(clean_db)
    with make_app(clean_db, **HOLD) as api:
        b = book(api, w, iso(day, 9)).json()
        sql(
            clean_db,
            "UPDATE public.bookings SET expires_at = now() - interval '1 minute' WHERE id=$1",
            uuid.UUID(b["id"]),
        )
        assert "09:00" in _slots(_avail(api, w, day))  # shown free again even before settlement
        r = book(api, w, iso(day, 9), headers=other_h)
        assert r.status_code == 201
        old = api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()
        assert old["status"] == "expired"
        assert [h["to_status"] for h in old["history"]] == ["pending_payment", "expired"]
        assert old["history"][-1]["actor_role"] == "system"
        past = api.get(f"{API}/bookings", params={"bucket": "past"}, headers=w["customer_h"]).json()
        assert [x["id"] for x in past["items"]] == [b["id"]]


# ------------------------------------------------------------------ authorization
def test_roles_and_idor(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    other, other_h = new_customer(clean_db)
    owner2 = auth_headers(seed_profile(clean_db, "owner"))
    with make_app(clean_db, **HOLD) as api:
        b = book(api, w, iso(day, 9)).json()
        bid = b["id"]
        assert api.get(f"{API}/bookings").status_code == 401
        assert (
            api.get(f"{API}/bookings/{bid}", headers=other_h).status_code == 404
        )  # not 403: no existence leak
        assert api.get(f"{API}/bookings/{bid}", headers=other_h).json()["code"] == "BOOKING_NOT_FOUND"
        assert api.post(f"{API}/bookings/{bid}/cancel", headers=other_h).status_code == 404
        assert api.get(f"{API}/bookings/{bid}/cancellation-preview", headers=other_h).status_code == 404
        assert api.get(f"{API}/bookings", headers=other_h).json()["items"] == []
        # owners and admins cannot use customer endpoints
        assert (
            api.post(
                f"{API}/bookings",
                json={"resource_id": str(w["resource"]), "starts_at": iso(day, 11)},
                headers=w["owner_h"],
            ).status_code
            == 403
        )
        assert api.get(f"{API}/bookings", headers=w["owner_h"]).status_code == 403
        # another owner cannot see or touch this venue's bookings, courts or blocks
        assert api.get(f"{API}/owners/bookings/{bid}", headers=owner2).status_code == 404
        assert api.get(f"{API}/owners/bookings", headers=owner2).json()["items"] == []
        assert api.get(f"{API}/owners/venues/{w['venue']}/resources", headers=owner2).status_code == 404
        assert (
            api.post(
                f"{API}/owners/venues/{w['venue']}/resources", json={"name": "X"}, headers=owner2
            ).status_code
            == 404
        )
        assert (
            api.get(
                f"{API}/owners/bookings", params={"venue_id": str(w["venue"])}, headers=owner2
            ).status_code
            == 404
        )
        # customers cannot use owner or admin endpoints
        assert api.get(f"{API}/owners/bookings", headers=w["customer_h"]).status_code == 403
        assert api.get(f"{API}/admin/bookings", headers=w["customer_h"]).status_code == 403
        assert api.get(f"{API}/admin/bookings", headers=w["owner_h"]).status_code == 403
        # there is no endpoint that lets anyone set a status
        assert api.patch(
            f"{API}/bookings/{bid}", json={"status": "confirmed"}, headers=w["customer_h"]
        ).status_code in (404, 405)


def test_owner_sees_confirmed_bookings_with_name_only_and_admin_sees_all(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    admin = seed_profile(clean_db, "admin")
    with make_app(clean_db, **INSTANT, admin_mfa_required=False) as api:
        b = book(api, w, iso(day, 9)).json()
        lst = api.get(f"{API}/owners/bookings", headers=w["owner_h"]).json()
        assert lst["available"] is True and [x["id"] for x in lst["items"]] == [b["id"]]
        item = lst["items"][0]
        assert item["customer_name"] == "Cathy Customer" and "customer_id" not in item
        assert "email" not in str(item) and "phone" not in str(item)
        det = api.get(f"{API}/owners/bookings/{b['id']}", headers=w["owner_h"]).json()
        assert det["history"][0]["to_status"] == "confirmed" and det["can_cancel"] is False
        notes = api.get(f"{API}/owners/notifications", headers=w["owner_h"]).json()
        assert any(n["type"] == "booking.created" for n in notes["items"])
        dash = api.get(f"{API}/owners/dashboard", headers=w["owner_h"]).json()
        assert dash["total_bookings"] == 1 and dash["booking_overview"]["upcoming"] == 1
        adm = api.get(f"{API}/admin/bookings", headers=auth_headers(admin, aal="aal2")).json()
        assert adm["items"][0]["customer_id"] == str(w["customer"]) and adm["items"][0]["owner_id"] == str(
            w["owner"]
        )
        one = api.get(f"{API}/admin/bookings/{b['id']}", headers=auth_headers(admin, aal="aal2"))
        assert one.status_code == 200 and one.json()["history"]
        bad = api.get(
            f"{API}/admin/bookings", params={"status": "bogus"}, headers=auth_headers(admin, aal="aal2")
        )
        assert bad.status_code == 422


def test_owner_does_not_see_unpaid_holds(clean_db):
    w = seed_world(clean_db)
    with make_app(clean_db, **HOLD) as api:
        book(api, w, iso(future_day(), 9))
        assert api.get(f"{API}/owners/bookings", headers=w["owner_h"]).json()["items"] == []


# ------------------------------------------------------------------ cancellation
def test_cancel_hold_releases_slot_and_blocks_second_cancel(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        b = book(api, w, iso(day, 9)).json()
        assert b["can_cancel"] is True
        prev = api.get(f"{API}/bookings/{b['id']}/cancellation-preview", headers=w["customer_h"]).json()
        assert prev["can_cancel"] is True and prev["code"] == "OK"
        r = api.post(
            f"{API}/bookings/{b['id']}/cancel", json={"reason": "Plans changed"}, headers=w["customer_h"]
        )
        assert r.status_code == 200 and r.json()["status"] == "cancelled_by_customer"
        assert r.json()["cancel_reason"] == "Plans changed" and r.json()["cancelled_at"]
        assert "09:00" in _slots(_avail(api, w, day))
        again = api.post(f"{API}/bookings/{b['id']}/cancel", headers=w["customer_h"])
        assert again.status_code == 409 and again.json()["code"] == "INVALID_STATUS_TRANSITION"
        assert (
            api.get(f"{API}/bookings", params={"bucket": "cancelled"}, headers=w["customer_h"]).json()[
                "items"
            ][0]["id"]
            == b["id"]
        )
        assert (
            api.get(f"{API}/bookings", params={"bucket": "bogus"}, headers=w["customer_h"]).status_code == 422
        )
        assert book(api, w, iso(day, 9)).status_code == 201  # the slot can be booked again


def test_confirmed_booking_cancellation_follows_configured_notice(clean_db):
    w = seed_world(clean_db)
    far, near = future_day(5), future_day(1)
    with make_app(clean_db, **INSTANT) as api:
        ok = book(api, w, iso(far, 9)).json()
        r = api.post(f"{API}/bookings/{ok['id']}/cancel", headers=w["customer_h"])
        assert r.status_code == 200 and r.json()["status"] == "cancelled_by_customer"
        close = book(api, w, iso(near, 9)).json()
        sql(
            clean_db,
            "UPDATE public.booking_slots SET slot_range = tstzrange(now() + interval '2 hours', now() + interval '3 hours') WHERE booking_id=$1",
            uuid.UUID(close["id"]),
        )
        sql(
            clean_db,
            "UPDATE public.bookings SET starts_at = now() + interval '2 hours', ends_at = now() + interval '3 hours', duration_minutes = 60 WHERE id=$1",
            uuid.UUID(close["id"]),
        )
        r = api.post(f"{API}/bookings/{close['id']}/cancel", headers=w["customer_h"])
        assert r.status_code == 409 and r.json()["code"] == "CANCELLATION_WINDOW_CLOSED"
        notes = api.get(f"{API}/owners/notifications", headers=w["owner_h"]).json()["items"]
        assert any(n["type"] == "booking.cancelled" for n in notes)


def test_cancellation_unavailable_when_policy_unset_or_paid(clean_db):
    w = seed_world(clean_db)
    day = future_day(5)
    with make_app(clean_db, booking_mode="instant") as api:  # no cancellation window configured
        b = book(api, w, iso(day, 9)).json()
        r = api.post(f"{API}/bookings/{b['id']}/cancel", headers=w["customer_h"])
        assert r.status_code == 409 and r.json()["code"] == "CANCELLATION_NOT_AVAILABLE"
        assert api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()["can_cancel"] is False
    with make_app(clean_db, **INSTANT) as api:
        sql(clean_db, "UPDATE public.bookings SET payment_status='paid' WHERE id=$1", uuid.UUID(b["id"]))
        r = api.post(f"{API}/bookings/{b['id']}/cancel", headers=w["customer_h"])
        assert r.status_code == 409 and r.json()["code"] == "CANCELLATION_NOT_AVAILABLE"
        assert api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()["status"] == "confirmed"


def test_finished_confirmed_booking_becomes_completed(clean_db):
    w = seed_world(clean_db)
    with make_app(clean_db, **INSTANT) as api:
        b = book(api, w, iso(future_day(), 9)).json()
        bid = uuid.UUID(b["id"])
        sql(
            clean_db,
            "UPDATE public.booking_slots SET slot_range = tstzrange(now() - interval '3 hours', now() - interval '2 hours') WHERE booking_id=$1",
            bid,
        )
        sql(
            clean_db,
            "UPDATE public.bookings SET starts_at = now() - interval '3 hours', ends_at = now() - interval '2 hours' WHERE id=$1",
            bid,
        )
        got = api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()
        assert got["status"] == "completed" and got["can_cancel"] is False
        assert (
            api.post(f"{API}/bookings/{b['id']}/cancel", headers=w["customer_h"]).json()["code"]
            == "INVALID_STATUS_TRANSITION"
        )


def test_status_history_is_append_only(clean_db):
    w = seed_world(clean_db)
    with make_app(clean_db, **HOLD) as api:
        b = book(api, w, iso(future_day(), 9)).json()
    try:
        sql(
            clean_db,
            "UPDATE public.booking_status_history SET reason='tamper' WHERE booking_id=$1",
            uuid.UUID(b["id"]),
        )
    except Exception as exc:  # asyncpg raises a database error from the trigger
        assert "append-only" in str(exc) or "append_only" in str(exc) or "history" in str(exc).lower()
    else:
        raise AssertionError("history rows must not be updatable")


# ------------------------------------------------------------------ owner schedule policy (Q16)
def test_schedule_changes_that_break_future_bookings_are_refused(clean_db):
    w = seed_world(clean_db)
    day = future_day()
    with make_app(clean_db, **INSTANT) as api:
        b = book(api, w, iso(day, 9)).json()
        base = f"{API}/owners/venues/{w['venue']}"
        # closing that day
        r = api.put(
            f"{base}/schedules",
            json={"special": [{"on_date": day.isoformat(), "is_closed": True}]},
            headers=w["owner_h"],
        )
        assert r.status_code == 409 and r.json()["code"] == "SCHEDULE_CONFLICT"
        assert r.json()["details"]["bookings"][0]["booking_code"] == b["booking_code"]
        # shifting opening so 09:00 is no longer on the grid
        regular = [
            {"weekday": d, "intervals": [{"opens_at": "06:30", "closes_at": "22:00"}]} for d in range(7)
        ]
        assert (
            api.put(f"{base}/schedules", json={"regular": regular}, headers=w["owner_h"]).status_code == 409
        )
        # changing slot length / deactivating the court / blocking the hour / moving time zone
        res = f"{base}/resources/{w['resource']}"
        assert (
            api.patch(res, json={"slot_minutes": 45}, headers=w["owner_h"]).json()["code"]
            == "SCHEDULE_CONFLICT"
        )
        assert (
            api.patch(res, json={"is_active": False}, headers=w["owner_h"]).json()["code"]
            == "SCHEDULE_CONFLICT"
        )
        blk = api.post(
            f"{base}/blocks", json={"starts_at": iso(day, 8), "ends_at": iso(day, 11)}, headers=w["owner_h"]
        )
        assert blk.status_code == 409 and blk.json()["code"] == "SCHEDULE_CONFLICT"
        assert (
            api.patch(base, json={"timezone": "America/New_York"}, headers=w["owner_h"]).json()["code"]
            == "SCHEDULE_CONFLICT"
        )
        # nothing was changed and the booking is intact
        assert sql(clean_db, "SELECT count(*) AS n FROM public.schedule_exceptions")[0]["n"] == 0
        assert (
            sql(clean_db, "SELECT slot_minutes FROM public.venue_resources WHERE id=$1", w["resource"])[0][
                "slot_minutes"
            ]
            == 60
        )
        assert api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()["status"] == "confirmed"
        # harmless changes still work: price, other days, other hours
        assert api.patch(res, json={"slot_price_paise": 70000}, headers=w["owner_h"]).status_code == 200
        later = future_day(6)
        assert (
            api.put(
                f"{base}/schedules",
                json={"special": [{"on_date": later.isoformat(), "is_closed": True}]},
                headers=w["owner_h"],
            ).status_code
            == 200
        )
        assert (
            api.post(
                f"{base}/blocks",
                json={"starts_at": iso(day, 12), "ends_at": iso(day, 13)},
                headers=w["owner_h"],
            ).status_code
            == 201
        )


def test_court_and_venue_with_bookings_cannot_be_deleted(clean_db):
    w = seed_world(clean_db)
    with make_app(clean_db, **HOLD) as api:
        book(api, w, iso(future_day(), 9))
        base = f"{API}/owners/venues/{w['venue']}"
        r = api.delete(f"{base}/resources/{w['resource']}", headers=w["owner_h"])
        assert r.status_code == 409 and r.json()["code"] == "RESOURCE_HAS_BOOKINGS"
        r = api.delete(base, headers=w["owner_h"])
        assert r.status_code == 409 and r.json()["code"] == "VENUE_HAS_BOOKINGS"
        empty = api.post(f"{base}/resources", json={"name": "Spare"}, headers=w["owner_h"]).json()
        assert empty["configured"] is False
        assert api.delete(f"{base}/resources/{empty['id']}", headers=w["owner_h"]).status_code == 204


def test_resource_validation_and_schedule_slot_configuration(clean_db):
    w = seed_world(clean_db, slot_minutes=None, price=None)
    with make_app(clean_db, **HOLD) as api:
        base = f"{API}/owners/venues/{w['venue']}"
        for bad in (
            {"name": ""},
            {"name": "X", "slot_minutes": 2},
            {"name": "X", "slot_price_paise": -1},
            {"name": "X", "extra": 1},
        ):
            assert api.post(f"{base}/resources", json=bad, headers=w["owner_h"]).status_code == 422
        assert (
            api.get(f"{base}/schedules", headers=w["owner_h"]).json()["slot_configuration"]["status"]
            == "not_configured"
        )
        r = api.patch(
            f"{base}/resources/{w['resource']}",
            json={"slot_minutes": 90, "slot_price_paise": 120000},
            headers=w["owner_h"],
        )
        assert r.status_code == 200 and r.json()["configured"] is True
        cfg = api.get(f"{base}/schedules", headers=w["owner_h"]).json()["slot_configuration"]
        assert cfg["status"] == "configured" and cfg["courts"][0]["slot_minutes"] == 90
