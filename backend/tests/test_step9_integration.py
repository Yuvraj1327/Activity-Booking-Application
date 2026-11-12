"""Step 9: cross-role integration, rate limiting, CORS, injection and pagination guards.

These run the real FastAPI app against a real Postgres (fake Razorpay/FCM/Resend gateways only).
"""

import pytest

from tests.booking_helpers import API, new_customer, seed_world
from tests.conftest import auth_headers, seed_profile, sql
from tests.payment_helpers import (
    create_order,
    hold_booking,
    make_admin,
    paid_booking,
    payment_app,
    rows,
)


def test_one_booking_is_consistent_across_customer_owner_and_admin(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        b, order, gp = paid_booking(env, w)
        api = env.api

        mine = api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()
        assert (mine["status"], mine["payment_status"]) == ("confirmed", "paid")

        owner_list = api.get(f"{API}/owners/bookings", headers=w["owner_h"])
        assert owner_list.status_code == 200
        assert b["id"] in owner_list.text

        earnings = api.get(f"{API}/owners/earnings", headers=w["owner_h"]).json()
        assert earnings["deductions"]["available"] is False  # no commission/GST rule approved
        assert earnings["net_earnings"]["available"] is False

        admin_row = api.get(f"{API}/admin/bookings", params={"q": b["id"]}, headers=admin_h).json()
        assert [r["id"] for r in admin_row["items"]] == [b["id"]]
        assert admin_row["items"][0]["status"] == "confirmed"

        detail = api.get(f"{API}/admin/bookings/{b['id']}", headers=admin_h).json()
        assert len(detail["payments"]) == 1 and detail["payments"][0]["status"] == "captured"

        assert api.get(f"{API}/admin/payments/summary", headers=admin_h).status_code == 200

        # the amount everyone sees is the server-computed one, identical in all three views
        total = mine["total_amount_paise"]
        assert detail["total_amount_paise"] == total == order["checkout"]["amount_paise"]
        db = rows(clean_db, "SELECT total_amount_paise FROM public.bookings")
        assert [r["total_amount_paise"] for r in db] == [total]


def test_second_owner_cannot_see_or_touch_the_first_owners_records(clean_db):
    w = seed_world(clean_db)
    other_owner = seed_profile(clean_db, "owner", name="Other Owner")
    other_h = auth_headers(other_owner)
    with payment_app(clean_db) as env:
        b, _, _ = paid_booking(env, w)
        listing = env.api.get(f"{API}/owners/bookings", headers=other_h)
        assert listing.status_code == 200 and b["id"] not in listing.text
        assert env.api.get(f"{API}/owners/bookings/{b['id']}", headers=other_h).status_code == 404
        assert env.api.get(f"{API}/owners/venues/{w['venue']}", headers=other_h).status_code == 404
        assert (
            env.api.patch(
                f"{API}/owners/venues/{w['venue']}", json={"name": "Hacked"}, headers=other_h
            ).status_code
            == 404
        )
        assert rows(clean_db, "SELECT name FROM public.venues")[0]["name"] == "Ace Arena"


def test_customer_cannot_read_another_customers_booking_or_payment(clean_db):
    w = seed_world(clean_db)
    _, intruder_h = new_customer(clean_db, "Intruder")
    with payment_app(clean_db) as env:
        b, order, _ = paid_booking(env, w)
        assert env.api.get(f"{API}/bookings/{b['id']}", headers=intruder_h).status_code == 404
        assert env.api.get(f"{API}/payments/{order['payment']['id']}", headers=intruder_h).status_code == 404
        assert create_order(env, b["id"], intruder_h).status_code in (403, 404)


def test_paid_booking_cannot_be_cancelled_until_a_refund_policy_is_approved(clean_db):
    """Q9/Q10 are open: the system must not invent a refund. The refusal is deliberate."""
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b, _, _ = paid_booking(env, w)
        r = env.api.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=w["customer_h"])
        assert r.status_code in (409, 422), r.text
        got = rows(clean_db, "SELECT status, payment_status FROM public.bookings")[0]
        assert (got["status"], got["payment_status"]) == ("confirmed", "paid")


def test_unpaid_hold_can_be_cancelled_and_the_slot_is_free_again(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w, hour=11)
        r = env.api.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=w["customer_h"])
        assert r.status_code == 200, r.text
        again = hold_booking(env, w, hour=11)
        assert again["id"] != b["id"]


# ------------------------------------------------------------------ rate limiting
def test_rate_limit_returns_429_with_envelope_and_retry_after(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db, rate_limit_per_minute=3) as env:
        b = hold_booking(env, w)
        codes = [create_order(env, b["id"], w["customer_h"]).status_code for _ in range(5)]
        assert codes[:2] == [200, 200]  # 1 hold + 2 orders use the 3 booking-write/payment budgets separately
        assert 429 in codes
        r = create_order(env, b["id"], w["customer_h"])
        assert r.status_code == 429
        body = r.json()
        assert body["code"] == "RATE_LIMITED" and "request_id" in body
        assert int(r.headers["Retry-After"]) >= 1


def test_rate_limit_does_not_touch_reads_or_the_webhook(clean_db):
    with payment_app(clean_db, rate_limit_per_minute=2) as env:
        assert all(env.api.get("/health").status_code == 200 for _ in range(6))
        for _ in range(6):
            r = env.api.post(f"{API}/payments/webhook", content=b"{}", headers={})
            assert r.status_code != 429


def test_rate_limit_can_be_disabled(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db, rate_limit_per_minute=0) as env:
        b = hold_booking(env, w)
        assert all(create_order(env, b["id"], w["customer_h"]).status_code == 200 for _ in range(8))


# ------------------------------------------------------------------ CORS
def test_cors_allows_only_configured_origins(clean_db):
    with payment_app(clean_db, cors_origins=["https://admin.example.test"]) as env:
        ok = env.api.options(
            f"{API}/admin/me",
            headers={
                "Origin": "https://admin.example.test",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        assert ok.headers.get("access-control-allow-origin") == "https://admin.example.test"
        bad = env.api.options(
            f"{API}/admin/me",
            headers={"Origin": "https://evil.example.test", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in bad.headers


# ------------------------------------------------------------------ injection and pagination guards
INJECTIONS = ["' OR 1=1 --", "'; DROP TABLE public.bookings; --", "%' UNION SELECT NULL --", "\\", "%", "_"]


@pytest.mark.parametrize("payload", INJECTIONS)
def test_search_parameters_are_never_executed(clean_db, payload):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        for path, headers in [
            ("/admin/bookings", admin_h),
            ("/admin/owners", admin_h),
            ("/admin/customers", admin_h),
            ("/admin/venues", admin_h),
            ("/admin/payments", admin_h),
            ("/venues", w["customer_h"]),
        ]:
            r = env.api.get(f"{API}{path}", params={"q": payload}, headers=headers)
            assert r.status_code in (200, 422), (path, payload, r.text)
        # the table is intact and a wildcard-only search does not match everything
        assert rows(clean_db, "SELECT count(*) AS n FROM public.bookings")[0]["n"] == 1
        wild = env.api.get(f"{API}/admin/owners", params={"q": "%"}, headers=admin_h).json()
        assert wild["items"] == []


@pytest.mark.parametrize(
    "path", ["/admin/bookings", "/admin/owners", "/admin/customers", "/admin/venues", "/admin/payments"]
)
def test_page_size_is_bounded(clean_db, path):
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        assert env.api.get(f"{API}{path}", params={"limit": 1000000}, headers=admin_h).status_code == 422
        assert env.api.get(f"{API}{path}", params={"offset": -1}, headers=admin_h).status_code == 422


def test_unknown_ids_and_malformed_ids_are_clean_errors(clean_db):
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        for path in ("/admin/bookings", "/admin/owners", "/admin/payments", "/admin/venues"):
            assert env.api.get(f"{API}{path}/not-a-uuid", headers=admin_h).status_code == 422
            r = env.api.get(f"{API}{path}/00000000-0000-0000-0000-000000000000", headers=admin_h)
            assert r.status_code == 404 and r.json()["code"]


def test_no_secret_appears_in_any_response_or_openapi(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        texts = [
            env.api.get("/health").text,
            create_order(env, b["id"], w["customer_h"]).text,
            env.api.get("/openapi.json").text if env.api.get("/openapi.json").status_code == 200 else "",
        ]
        from tests.payment_helpers import KEY_SECRET

        blob = "".join(texts)
        assert KEY_SECRET not in blob
        assert "service_role" not in blob.lower()


def test_sql_helper_sanity(clean_db):  # keeps the unused-import linter honest about `sql`
    assert sql(clean_db, "SELECT 1 AS x")[0]["x"] == 1


# ------------------------------------------------------------------ Step 10: "Today" filter
def test_available_today_filter_uses_the_real_slot_engine(clean_db):
    open_w = seed_world(clean_db, slot_minutes=15)  # open 06:00-22:00 every day
    # a second published venue that has no opening hours can never have a slot today
    closed_w = seed_world(clean_db, hours=False)
    sql(clean_db, "UPDATE public.venues SET name = 'Closed Arena' WHERE id = $1", closed_w["venue"])
    with payment_app(clean_db) as env:
        everything = env.api.get(f"{API}/venues", headers=open_w["customer_h"]).json()["items"]
        assert {v["name"] for v in everything} == {"Ace Arena", "Closed Arena"}
        today = env.api.get(f"{API}/venues", params={"available_today": "true"}, headers=open_w["customer_h"])
        assert today.status_code == 200, today.text
        names = {v["name"] for v in today.json()["items"]}
        # Ace Arena has slots today unless the test runs in the last minutes before closing
        assert "Closed Arena" not in names
        assert names <= {"Ace Arena"}
        from datetime import UTC, datetime
        from zoneinfo import ZoneInfo

        if datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).hour < 20:  # venue closes at 22:00
            assert names == {"Ace Arena"}
