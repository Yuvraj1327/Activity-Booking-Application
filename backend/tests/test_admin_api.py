"""Step 8: admin console API. Authorisation, aggregation, management reads, audited status changes, CSV."""

import csv
import io
import uuid
from datetime import timedelta

import pytest

from tests.booking_helpers import API, future_day, new_customer, seed_world
from tests.conftest import auth_headers, seed_profile, sql
from tests.payment_helpers import hold_booking, make_admin, paid_booking, payment_app, rows

ADMIN_GET_PATHS = [
    "/admin/dashboard",
    "/admin/analytics/bookings",
    "/admin/analytics/revenue",
    "/admin/analytics/platform",
    "/admin/activity",
    "/admin/owners",
    "/admin/customers",
    "/admin/venues",
    "/admin/bookings",
    "/admin/payments",
    "/admin/payments/summary",
    "/admin/audit-logs",
    "/admin/exports/bookings.csv",
    "/admin/exports/payments.csv",
    "/admin/exports/customers.csv",
    "/admin/exports/owners.csv",
]


def today_params() -> dict[str, str]:
    d = (future_day(0)).isoformat()
    return {"from": d, "to": d}


# ------------------------------------------------------------------ authorisation
@pytest.mark.parametrize("path", ADMIN_GET_PATHS)
def test_every_admin_route_rejects_anonymous_customer_owner_and_unverified_admin(clean_db, path):
    w = seed_world(clean_db)
    with payment_app(clean_db, admin_require_mfa=True) as env:
        assert env.api.get(f"{API}{path}").status_code == 401
        assert env.api.get(f"{API}{path}", headers=w["customer_h"]).status_code == 403
        assert env.api.get(f"{API}{path}", headers=w["owner_h"]).status_code == 403
        admin = seed_profile(clean_db, "admin")
        no_mfa = env.api.get(f"{API}{path}", headers=auth_headers(admin, aal="aal1"))
        assert no_mfa.status_code == 403 and no_mfa.json()["code"] == "MFA_REQUIRED"
        assert env.api.get(f"{API}{path}", headers=auth_headers(admin, aal="aal2")).status_code == 200


def test_suspended_admin_is_refused(clean_db):
    admin = seed_profile(clean_db, "admin", status="suspended")
    with payment_app(clean_db) as env:
        r = env.api.get(f"{API}/admin/dashboard", headers=auth_headers(admin, aal="aal2"))
        assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_SUSPENDED"


def test_status_change_routes_reject_non_admins(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        body = {"status": "suspended", "reason": "testing"}
        for path in (f"/admin/owners/{w['owner']}/status", f"/admin/customers/{w['customer']}/status"):
            assert env.api.patch(f"{API}{path}", json=body).status_code == 401
            assert env.api.patch(f"{API}{path}", json=body, headers=w["customer_h"]).status_code == 403
            assert env.api.patch(f"{API}{path}", json=body, headers=w["owner_h"]).status_code == 403
        assert (
            rows(clean_db, "SELECT status FROM public.profiles WHERE id=$1", w["owner"])[0]["status"]
            == "active"
        )
        assert (
            rows(clean_db, "SELECT 1 FROM public.audit_logs WHERE action='admin.account_status_changed'")
            == []
        )


def test_a_user_cannot_make_themselves_admin(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        r = env.api.patch(
            f"{API}/profiles/me", json={"role": "admin", "full_name": "x"}, headers=w["customer_h"]
        )
        assert r.status_code in (404, 405, 422)
        assert (
            rows(clean_db, "SELECT role FROM public.profiles WHERE id=$1", w["customer"])[0]["role"]
            == "customer"
        )


# ------------------------------------------------------------------ empty platform
def test_empty_data_returns_zeroes_and_empty_lists_not_errors(clean_db):
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        d = env.api.get(f"{API}/admin/dashboard", headers=admin_h).json()
        assert d["totals"] == {
            "customers": 0, "owners": 0, "venues": 0, "published_venues": 0, "bookings": 0, "payments": 0,
        }  # fmt: skip
        assert d["period"]["bookings"] == 0 and d["period"]["money"]["successful_payment_paise"] == 0
        assert len(d["booking_trend"]) == 30 and all(b["total"] == 0 for b in d["booking_trend"])
        assert d["recent_bookings"] == [] and d["popular_venues"] == []
        rev = env.api.get(f"{API}/admin/analytics/revenue", headers=admin_h).json()
        assert rev["success_rate_percent"] is None and rev["transactions_total"] == 0
        for p in ("owners", "customers", "venues", "bookings", "payments"):
            page = env.api.get(f"{API}/admin/{p}", headers=admin_h).json()
            assert page["items"] == [] and page["has_more"] is False


# ------------------------------------------------------------------ dashboard + analytics
def test_dashboard_numbers_come_from_the_database(clean_db):
    w = seed_world(clean_db, price=75000)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w, hour=9)
        hold_booking(env, w, hour=11)  # stays pending_payment
        d = env.api.get(f"{API}/admin/dashboard", headers=admin_h).json()
        assert d["totals"]["customers"] == 1 and d["totals"]["owners"] == 1
        assert d["totals"]["venues"] == 1 and d["totals"]["published_venues"] == 1
        assert d["totals"]["bookings"] == 2 and d["totals"]["payments"] == 1
        p = d["period"]
        assert (p["bookings"], p["confirmed"], p["pending"], p["cancelled"]) == (2, 1, 1, 0)
        m = p["money"]
        assert m["gross_booking_value_paise"] == 75000 and m["successful_payment_paise"] == 75000
        # Rules that are not approved are never computed.
        for k in ("platform_revenue", "owner_earnings", "refunds"):
            assert m[k]["available"] is False and m[k]["depends_on"]
        assert sum(b["total"] for b in d["booking_trend"]) == 2
        assert d["popular_venues"][0]["name"] == "Ace Arena" and d["popular_venues"][0]["bookings"] == 2
        assert d["recent_bookings"][0]["venue_name"] == "Ace Arena"
        assert {r["role"] for r in d["recent_registrations"]} == {"customer", "owner"}
        assert d["activity"], "activity feed is built from real booking/payment events"


def test_date_filter_excludes_data_outside_the_range(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        far = {"from": "2020-01-01", "to": "2020-01-31"}
        d = env.api.get(f"{API}/admin/dashboard", params=far, headers=admin_h).json()
        assert d["period"]["bookings"] == 0 and d["period"]["money"]["successful_payment_paise"] == 0
        assert d["totals"]["bookings"] == 1  # all-time totals are not range-limited
        inc = env.api.get(f"{API}/admin/dashboard", params=today_params(), headers=admin_h).json()
        assert inc["period"]["bookings"] == 1


def test_invalid_ranges_are_rejected(clean_db):
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        r = env.api.get(
            f"{API}/admin/dashboard", params={"from": "2026-02-01", "to": "2026-01-01"}, headers=admin_h
        )
        assert r.status_code == 422 and r.json()["code"] == "INVALID_RANGE"
        r = env.api.get(
            f"{API}/admin/analytics/bookings",
            params={"from": "2020-01-01", "to": "2026-01-01"},
            headers=admin_h,
        )
        assert r.status_code == 422 and r.json()["code"] == "RANGE_TOO_LARGE"
        assert (
            env.api.get(
                f"{API}/admin/analytics/bookings", params={"granularity": "hour"}, headers=admin_h
            ).status_code
            == 422
        )


def test_booking_analytics_buckets_and_status_distribution(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w, hour=9)
        hold_booking(env, w, hour=11)
        for g, n in (("day", 30), ("week", None), ("month", None)):
            a = env.api.get(
                f"{API}/admin/analytics/bookings", params={"granularity": g}, headers=admin_h
            ).json()
            assert a["total"] == 2 and sum(b["total"] for b in a["series"]) == 2
            if n:
                assert len(a["series"]) == n
        dist = {s["status"]: s["count"] for s in a["status_distribution"]}
        assert dist == {"confirmed": 1, "pending_payment": 1}
        today = env.api.get(f"{API}/admin/analytics/bookings", params=today_params(), headers=admin_h).json()[
            "series"
        ]
        assert len(today) == 1 and today[0]["total"] == 2 and today[0]["confirmed"] == 1


def test_revenue_analytics_counts_only_recorded_payments_and_never_invents_revenue(clean_db):
    w = seed_world(clean_db, price=40000)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w, hour=9)
        b2 = hold_booking(env, w, hour=11)
        from tests.payment_helpers import create_order

        create_order(env, b2["id"], w["customer_h"])  # an open (unpaid) order
        r = env.api.get(f"{API}/admin/analytics/revenue", headers=admin_h).json()
        assert (r["captured_count"], r["failed_count"], r["open_count"], r["transactions_total"]) == (
            1,
            0,
            1,
            2,
        )
        assert r["success_rate_percent"] == 100.0
        assert r["money"]["successful_payment_paise"] == 40000
        assert r["money"]["platform_revenue"]["available"] is False
        assert r["money"]["owner_earnings"]["available"] is False
        assert sum(p["captured_paise"] for p in r["series"]) == 40000


def test_platform_analytics_registrations_categories_and_top_venues(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        a = env.api.get(f"{API}/admin/analytics/platform", headers=admin_h).json()
        assert (a["new_customers"], a["new_owners"], a["new_venues"]) == (1, 1, 1)
        assert a["popular_categories"] == [{"category": "Cricket", "bookings": 1}]
        assert a["top_venues"][0]["name"] == "Ace Arena"
        assert "admin" not in str(a["series"])  # admins are not counted as registrations


# ------------------------------------------------------------------ owners and customers
def test_owner_list_search_filter_sort_and_detail(clean_db):
    w = seed_world(clean_db)
    other = seed_profile(
        clean_db, "owner", name="Zed Zephyr", business_name="Zephyr Sports", status="suspended"
    )
    sql(clean_db, "UPDATE public.profiles SET phone='+919876543210' WHERE id=$1", w["owner"])
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        lst = env.api.get(f"{API}/admin/owners", headers=admin_h).json()
        assert {o["id"] for o in lst["items"]} == {str(w["owner"]), str(other)}
        mine = next(o for o in lst["items"] if o["id"] == str(w["owner"]))
        assert (mine["venues_count"], mine["published_venues_count"], mine["bookings_count"]) == (1, 1, 1)
        assert mine["phone_masked"].endswith("3210") and "98765" not in mine["phone_masked"]
        assert "phone" not in mine

        def by(**p):
            return [
                o["id"] for o in env.api.get(f"{API}/admin/owners", params=p, headers=admin_h).json()["items"]
            ]  # noqa: E731

        assert by(status="suspended") == [str(other)]
        assert by(q="zephyr") == [str(other)]
        assert by(q="%") == []  # wildcards are literal
        assert by(sort="name", order="asc") == [str(w["owner"]), str(other)]
        assert by(sort="bookings", order="desc")[0] == str(w["owner"])
        assert (
            env.api.get(f"{API}/admin/owners", params={"sort": "email"}, headers=admin_h).status_code == 422
        )
        d = env.api.get(f"{API}/admin/owners/{w['owner']}", headers=admin_h).json()
        assert d["phone"] == "+919876543210" and d["business_name"] == "Test Business"
        assert [v["name"] for v in d["venues"]] == ["Ace Arena"] and d["venues"][0]["bookings_count"] == 1
        assert d["bookings_count"] == 1 and d["gross_paid_paise"] == 50000
        assert d["recent_bookings"][0]["customer_name"] == "Cathy Customer"
        # A customer id is not an owner; unknown ids are 404.
        assert env.api.get(f"{API}/admin/owners/{w['customer']}", headers=admin_h).status_code == 404
        assert env.api.get(f"{API}/admin/owners/{uuid.uuid4()}", headers=admin_h).status_code == 404


def test_customer_list_and_detail_hide_what_lists_should_not_show(clean_db):
    w = seed_world(clean_db)
    sql(clean_db, "UPDATE public.profiles SET phone='+919812345678' WHERE id=$1", w["customer"])
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        lst = env.api.get(f"{API}/admin/customers", headers=admin_h).json()
        c = lst["items"][0]
        assert c["full_name"] == "Cathy Customer" and c["bookings_count"] == 1 and c["confirmed_count"] == 1
        assert "phone" not in c and c["phone_masked"].endswith("5678")
        assert env.api.get(f"{API}/admin/customers", params={"q": "cathy"}, headers=admin_h).json()["items"]
        assert (
            env.api.get(f"{API}/admin/customers", params={"q": "nobody"}, headers=admin_h).json()["items"]
            == []
        )
        d = env.api.get(f"{API}/admin/customers/{w['customer']}", headers=admin_h).json()
        assert d["gross_paid_paise"] == 50000 and len(d["bookings"]) == 1
        assert d["bookings"][0]["venue_name"] == "Ace Arena"
        assert env.api.get(f"{API}/admin/customers/{w['owner']}", headers=admin_h).status_code == 404


# ------------------------------------------------------------------ audited status changes
def test_suspend_and_reactivate_are_enforced_audited_and_notified(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    second_admin = seed_profile(clean_db, "admin", name="Second Admin")
    with payment_app(clean_db) as env:
        assert env.api.get(f"{API}/owners/dashboard", headers=w["owner_h"]).status_code == 200
        r = env.api.patch(
            f"{API}/admin/owners/{w['owner']}/status",
            json={"status": "suspended", "reason": "Policy review"},
            headers=admin_h,
        )
        assert r.status_code == 200 and r.json() == {
            "id": str(w["owner"]), "role": "owner", "status": "suspended", "changed": True,
        }  # fmt: skip
        # Enforced on the next request, by the backend.
        blocked = env.api.get(f"{API}/owners/dashboard", headers=w["owner_h"])
        assert blocked.status_code == 403 and blocked.json()["code"] == "ACCOUNT_SUSPENDED"
        audit = rows(clean_db, "SELECT * FROM public.audit_logs WHERE action='admin.account_status_changed'")
        assert (
            len(audit) == 1 and audit[0]["actor_role"] == "admin" and audit[0]["entity_id"] == str(w["owner"])
        )
        import json

        meta = (
            json.loads(audit[0]["metadata"])
            if isinstance(audit[0]["metadata"], str)
            else audit[0]["metadata"]
        )
        assert meta == {
            "from": "active",
            "to": "suspended",
            "reason": "Policy review",
            "target_role": "owner",
        }
        # Other admins get a notification.
        types = {
            n["type"]
            for n in env.api.get(
                f"{API}/notifications", headers=auth_headers(second_admin, aal="aal2")
            ).json()["items"]
        }
        assert "admin.account_status" in types
        # Same status again: nothing changes, nothing is audited.
        again = env.api.patch(
            f"{API}/admin/owners/{w['owner']}/status",
            json={"status": "suspended", "reason": "again"},
            headers=admin_h,
        )
        assert again.json()["changed"] is False
        assert (
            len(rows(clean_db, "SELECT 1 FROM public.audit_logs WHERE action='admin.account_status_changed'"))
            == 1
        )
        back = env.api.patch(
            f"{API}/admin/owners/{w['owner']}/status",
            json={"status": "active", "reason": "Cleared"},
            headers=admin_h,
        )
        assert back.json()["changed"] is True
        assert env.api.get(f"{API}/owners/dashboard", headers=w["owner_h"]).status_code == 200
        log = env.api.get(
            f"{API}/admin/audit-logs", params={"action": "admin.account_status_changed"}, headers=admin_h
        )
        assert len(log.json()["items"]) == 2


def test_suspended_customer_cannot_book(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        r = env.api.patch(
            f"{API}/admin/customers/{w['customer']}/status",
            json={"status": "suspended", "reason": "Chargeback abuse"},
            headers=admin_h,
        )
        assert r.status_code == 200
        assert env.api.get(f"{API}/bookings", headers=w["customer_h"]).status_code == 403


def test_status_change_validation_and_protection(clean_db):
    w = seed_world(clean_db)
    admin = seed_profile(clean_db, "admin")
    admin_h = auth_headers(admin, aal="aal2")
    other_admin = seed_profile(clean_db, "admin")
    with payment_app(clean_db) as env:
        url = f"{API}/admin/owners/{w['owner']}/status"
        assert (
            env.api.patch(url, json={"status": "suspended"}, headers=admin_h).status_code == 422
        )  # reason required
        assert (
            env.api.patch(url, json={"status": "suspended", "reason": "x"}, headers=admin_h).status_code
            == 422
        )
        assert (
            env.api.patch(url, json={"status": "inactive", "reason": "because"}, headers=admin_h).status_code
            == 422
        )
        assert (
            env.api.patch(url, json={"status": "admin", "reason": "because"}, headers=admin_h).status_code
            == 422
        )
        extra = env.api.patch(
            url, json={"status": "active", "reason": "ok ok", "role": "admin"}, headers=admin_h
        )
        assert extra.status_code == 422
        # Admins are protected, including self.
        for target in (admin, other_admin):
            for kind in ("owners", "customers"):
                r = env.api.patch(
                    f"{API}/admin/{kind}/{target}/status",
                    json={"status": "suspended", "reason": "nope"},
                    headers=admin_h,
                )
                assert r.status_code == 403 and r.json()["code"] == "ADMIN_ACCOUNT_PROTECTED"
        # Wrong-role route is "not found", not a silent change.
        wrong = env.api.patch(
            f"{API}/admin/customers/{w['owner']}/status",
            json={"status": "suspended", "reason": "nope"},
            headers=admin_h,
        )
        assert wrong.status_code == 404
        assert (
            env.api.patch(
                f"{API}/admin/owners/{uuid.uuid4()}/status",
                json={"status": "suspended", "reason": "nope"},
                headers=admin_h,
            ).status_code
            == 404
        )
        assert all(r["status"] == "active" for r in rows(clean_db, "SELECT status FROM public.profiles"))
        assert (
            rows(clean_db, "SELECT 1 FROM public.audit_logs WHERE action='admin.account_status_changed'")
            == []
        )


# ------------------------------------------------------------------ venues
def test_venue_monitoring_is_read_only_and_filterable(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    draft_owner = seed_profile(clean_db, "owner", name="Draft Owner")
    sql(
        clean_db,
        "INSERT INTO public.venues (owner_id, name, timezone, status) VALUES ($1,'Quiet Draft','Asia/Kolkata','draft')",
        draft_owner,
    )
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        lst = env.api.get(f"{API}/admin/venues", headers=admin_h).json()
        assert {v["name"] for v in lst["items"]} == {"Ace Arena", "Quiet Draft"}
        ace = next(v for v in lst["items"] if v["name"] == "Ace Arena")
        assert ace["categories"] == ["Cricket"] and ace["owner_name"] == "Test User"
        assert ace["bookings_count"] == 1 and ace["confirmed_count"] == 1 and ace["status"] == "published"

        def get(**p):
            return [
                v["name"]
                for v in env.api.get(f"{API}/admin/venues", params=p, headers=admin_h).json()["items"]
            ]  # noqa: E731

        assert get(status="draft") == ["Quiet Draft"]
        assert get(q="arena") == ["Ace Arena"]
        assert get(owner_id=str(draft_owner)) == ["Quiet Draft"]
        cat_id = rows(clean_db, "SELECT id FROM public.categories")[0]["id"]
        assert get(category_id=str(cat_id)) == ["Ace Arena"]
        d = env.api.get(f"{API}/admin/venues/{w['venue']}", headers=admin_h).json()
        assert (
            d["resources_count"] == 1 and d["gross_paid_paise"] == 50000 and d["timezone"] == "Asia/Kolkata"
        )
        assert env.api.get(f"{API}/admin/venues/{uuid.uuid4()}", headers=admin_h).status_code == 404
        # No edit / delete / publish routes exist for admins.
        for method in ("patch", "put", "delete", "post"):
            r = getattr(env.api, method)(f"{API}/admin/venues/{w['venue']}", headers=admin_h)
            assert r.status_code in (404, 405)
        assert rows(clean_db, "SELECT count(*) AS n FROM public.venues")[0]["n"] == 2


# ------------------------------------------------------------------ bookings and payments
def test_admin_bookings_search_filters_and_detail_with_payments(clean_db):
    w = seed_world(clean_db, price=60000)
    admin_h = make_admin(clean_db)
    other, other_h = new_customer(clean_db, "Olive Other")
    with payment_app(clean_db) as env:
        b, order, gp = paid_booking(env, w, hour=9)
        pending = hold_booking(env, w, hour=11)
        lst = env.api.get(f"{API}/admin/bookings", headers=admin_h).json()
        assert len(lst["items"]) == 2
        row = next(i for i in lst["items"] if i["id"] == b["id"])
        assert row["customer_name"] == "Cathy Customer" and row["owner_name"] == "Test User"
        assert row["payment_amount_paise"] == 60000 and row["payment_status"] == "paid"
        assert row["duration_minutes"] == 60 and row["local_start"] == "09:00"

        def q(**p):
            return [
                i["id"]
                for i in env.api.get(f"{API}/admin/bookings", params=p, headers=admin_h).json()["items"]
            ]  # noqa: E731

        assert q(q=b["booking_code"]) == [b["id"]]
        assert q(q=b["booking_code"].lower()) == [b["id"]]
        assert q(q=b["id"]) == [b["id"]]
        assert q(q="cathy") and q(q="olive") == []
        assert q(status="confirmed") == [b["id"]]
        assert q(status="pending_payment") == [pending["id"]]
        assert q(payment_status="paid") == [b["id"]]
        assert q(venue_id=str(w["venue"])) and q(venue_id=str(uuid.uuid4())) == []
        day = future_day().isoformat()
        assert len(q(**{"from": day, "to": day})) == 2
        assert q(**{"from": (future_day() + timedelta(days=5)).isoformat()}) == []
        assert (
            env.api.get(f"{API}/admin/bookings", params={"status": "nope"}, headers=admin_h).status_code
            == 422
        )
        assert (
            env.api.get(
                f"{API}/admin/bookings", params={"payment_status": "nope"}, headers=admin_h
            ).status_code
            == 422
        )
        page1 = env.api.get(f"{API}/admin/bookings", params={"limit": 1}, headers=admin_h).json()
        assert len(page1["items"]) == 1 and page1["has_more"] is True
        d = env.api.get(f"{API}/admin/bookings/{b['id']}", headers=admin_h).json()
        assert len(d["payments"]) == 1 and d["payments"][0]["razorpay_payment_id"] == gp.id
        assert d["payments"][0]["status"] == "captured" and d["history"]
        assert env.api.get(f"{API}/admin/bookings/{pending['id']}", headers=admin_h).json()["payments"] == []
        # Booking status cannot be changed by an admin through the API.
        for method in ("patch", "put", "post", "delete"):
            r = env.api.request(
                method.upper(),
                f"{API}/admin/bookings/{b['id']}",
                json={"status": "cancelled_by_owner"},
                headers=admin_h,
            )
            assert r.status_code in (404, 405)
        assert (
            rows(clean_db, "SELECT status FROM public.bookings WHERE id=$1", uuid.UUID(b["id"]))[0]["status"]
            == "confirmed"
        )
        assert other_h


def test_admin_payments_search_and_filters(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        b, order, gp = paid_booking(env, w)

        def q(**p):
            return [
                i["id"]
                for i in env.api.get(f"{API}/admin/payments", params=p, headers=admin_h).json()["items"]
            ]  # noqa: E731

        pid = order["payment"]["id"]
        assert q(q=b["booking_code"]) == [pid]
        assert q(q=gp.id) == [pid]
        assert q(q=order["checkout"]["order_id"]) == [pid]
        assert q(q="pay_does_not_exist") == []
        assert q(status="captured") == [pid] and q(status="failed") == []
        assert q(venue_id=str(w["venue"])) == [pid] and q(venue_id=str(uuid.uuid4())) == []
        assert q(**today_params()) == [pid]
        assert q(**{"from": "2020-01-01", "to": "2020-01-02"}) == []
        assert (
            env.api.get(f"{API}/admin/payments", params={"status": "bogus"}, headers=admin_h).status_code
            == 422
        )


# ------------------------------------------------------------------ exports
def _parse(resp):
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"] and resp.headers["cache-control"] == "no-store"
    return list(csv.DictReader(io.StringIO(resp.text)))


def test_csv_exports_are_filtered_private_and_audited(clean_db):
    w = seed_world(clean_db)
    sql(
        clean_db,
        "UPDATE public.profiles SET full_name='=HYPERLINK(\"http://evil\")', phone='+919812345678' WHERE id=$1",
        w["customer"],
    )
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        b, order, gp = paid_booking(env, w, hour=9)
        hold_booking(env, w, hour=11)
        data = _parse(env.api.get(f"{API}/admin/exports/bookings.csv", headers=admin_h))
        assert len(data) == 2
        assert set(data[0]) == {
            "booking_code", "booking_id", "customer_id", "customer_name", "venue", "owner_name", "booking_date",
            "start_local", "end_local", "duration_minutes", "total_amount_paise", "currency", "payment_status",
            "booking_status", "created_at_utc",
        }  # fmt: skip
        raw = env.api.get(f"{API}/admin/exports/bookings.csv", headers=admin_h).text
        assert "9812345678" not in raw and "@example.com" not in raw
        # Formula injection is neutralised.
        assert all(r["customer_name"].startswith("'=") for r in data)
        only = _parse(
            env.api.get(f"{API}/admin/exports/bookings.csv", params={"status": "confirmed"}, headers=admin_h)
        )
        assert [r["booking_code"] for r in only] == [b["booking_code"]]
        pays = _parse(env.api.get(f"{API}/admin/exports/payments.csv", headers=admin_h))
        assert (
            len(pays) == 1 and pays[0]["razorpay_payment_id"] == gp.id and pays[0]["amount_paise"] == "50000"
        )
        assert "key_secret" not in env.api.get(f"{API}/admin/exports/payments.csv", headers=admin_h).text
        for kind in ("customers", "owners"):
            people = _parse(env.api.get(f"{API}/admin/exports/{kind}.csv", headers=admin_h))
            assert len(people) == 1 and set(people[0]) == {
                "id",
                "name",
                "status",
                "registered_at_utc",
                "bookings_count",
            }
        audit = rows(
            clean_db,
            "SELECT entity_type FROM public.audit_logs WHERE action='admin.export' ORDER BY created_at",
        )
        assert [a["entity_type"] for a in audit].count("bookings") == 3  # three booking exports above
        assert {"payments", "customers", "owners"} <= {a["entity_type"] for a in audit}
        assert (
            env.api.get(
                f"{API}/admin/exports/bookings.csv", params={"status": "x"}, headers=admin_h
            ).status_code
            == 422
        )


def test_export_row_cap_is_enforced_and_recorded(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db, admin_export_max_rows=1) as env:
        paid_booking(env, w, hour=9)
        hold_booking(env, w, hour=11)
        assert len(_parse(env.api.get(f"{API}/admin/exports/bookings.csv", headers=admin_h))) == 1
        meta = rows(clean_db, "SELECT metadata FROM public.audit_logs WHERE action='admin.export'")[0][
            "metadata"
        ]
        assert '"truncated": true' in str(meta)


# ------------------------------------------------------------------ notifications + activity + audit
def test_new_registrations_notify_active_admins_and_can_be_marked_read(clean_db):
    admin = seed_profile(clean_db, "admin")
    admin_h = auth_headers(admin, aal="aal2")
    with payment_app(clean_db) as env:
        uid = sql(
            clean_db,
            "INSERT INTO auth.users (id,email) VALUES (gen_random_uuid(),'new@example.com') RETURNING id",
        )[0]["id"]
        r = env.api.post(
            f"{API}/auth/profile",
            json={"role": "customer", "full_name": "Newbie"},
            headers=auth_headers(uid, email="new@example.com"),
        )
        assert r.status_code in (200, 201), r.text
        # Registering again does not create a second notification.
        env.api.post(
            f"{API}/auth/profile",
            json={"role": "customer", "full_name": "Newbie"},
            headers=auth_headers(uid, email="new@example.com"),
        )
        items = env.api.get(f"{API}/notifications", headers=admin_h).json()["items"]
        assert [n["type"] for n in items] == ["admin.new_customer"] and items[0]["is_read"] is False
        assert env.api.get(f"{API}/notifications/unread-count", headers=admin_h).json() == {"unread_count": 1}
        assert env.api.post(f"{API}/notifications/{items[0]['id']}/read", headers=admin_h).status_code in (
            200,
            204,
        )
        assert env.api.get(f"{API}/notifications/unread-count", headers=admin_h).json() == {"unread_count": 0}
        act = env.api.get(f"{API}/admin/activity", headers=admin_h).json()["items"]
        assert any(a["kind"] == "account" and "registered" in a["title"] for a in act)


def test_other_roles_do_not_see_admin_notifications(clean_db):
    w = seed_world(clean_db)
    admin = seed_profile(clean_db, "admin")
    with payment_app(clean_db) as env:
        uid = sql(
            clean_db,
            "INSERT INTO auth.users (id,email) VALUES (gen_random_uuid(),'o@example.com') RETURNING id",
        )[0]["id"]
        env.api.post(
            f"{API}/auth/profile",
            json={"role": "owner", "full_name": "New Owner", "business_name": "NO Sports"},
            headers=auth_headers(uid, email="o@example.com"),
        )
        assert env.api.get(f"{API}/notifications", headers=w["customer_h"]).json()["items"] == []
        assert env.api.get(f"{API}/notifications", headers=w["owner_h"]).json()["items"] == []
        assert (
            len(env.api.get(f"{API}/notifications", headers=auth_headers(admin, aal="aal2")).json()["items"])
            == 1
        )


def test_audit_log_endpoint_is_read_only_and_paginated(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        for i, st in enumerate(("suspended", "active", "suspended")):
            env.api.patch(
                f"{API}/admin/customers/{w['customer']}/status",
                json={"status": st, "reason": f"step {i}"},
                headers=admin_h,
            )
        page = env.api.get(f"{API}/admin/audit-logs", params={"limit": 2}, headers=admin_h).json()
        assert len(page["items"]) == 2 and page["has_more"] is True
        assert page["items"][0]["metadata"]["reason"] == "step 2"
        assert env.api.delete(f"{API}/admin/audit-logs", headers=admin_h).status_code in (404, 405)
