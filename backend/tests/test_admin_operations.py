"""Disputes and exceptional cancellation, support tickets, categories, CMS, coupons, analytics and filters, audit."""

import json
import uuid

from tests.admin_helpers import admin_with, audit_rows
from tests.booking_helpers import book, future_day, iso, make_app, seed_world
from tests.conftest import auth_headers, seed_profile, sql
from tests.payment_helpers import (
    API,
    hold_booking,
    paid_booking,
    payment_app,
    post_webhook,
    refund_webhook,
    rows,
)

A = f"{API}/admin"


# ------------------------------------------------------------------ exceptional cancellation + disputes
def test_admin_cancel_uses_the_state_machine_releases_the_slot_and_never_touches_money(clean_db):
    admin = admin_with(clean_db)
    nocancel = admin_with(clean_db, ["bookings.view"])
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        api = env.api
        b, _, _ = paid_booking(env, w, hour=9)
        denied = api.post(
            f"{A}/bookings/{b['id']}/cancel", json={"reason": "Court flooded"}, headers=nocancel["h"]
        )
        assert denied.status_code == 403
        assert api.post(f"{A}/bookings/{b['id']}/cancel", json={}, headers=admin["h"]).status_code == 422
        r = api.post(f"{A}/bookings/{b['id']}/cancel", json={"reason": "Court flooded"}, headers=admin["h"])
        assert r.status_code == 200 and r.json()["refund_decision_needed"] is True
        bk = rows(clean_db, "SELECT status, payment_status, cancelled_by FROM public.bookings")[0]
        assert (bk["status"], bk["payment_status"]) == ("cancelled_by_admin", "paid")  # money untouched
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "captured"
        assert rows(clean_db, "SELECT is_blocking FROM public.booking_slots")[0]["is_blocking"] is False
        # the slot can be booked again, and the customer was notified
        assert hold_booking(env, w, hour=9)["status"] == "pending_payment"
        assert rows(clean_db, "SELECT 1 FROM public.notifications WHERE type='booking.cancelled'")
        # cancelling again is refused by the state machine
        again = api.post(
            f"{A}/bookings/{b['id']}/cancel", json={"reason": "Court flooded"}, headers=admin["h"]
        )
        assert again.status_code == 409 and again.json()["code"] == "INVALID_STATUS_TRANSITION"
        meta = json.loads(audit_rows(clean_db, "admin.booking_cancelled")[0]["metadata"])
        assert meta["before"] == {"status": "confirmed", "payment_status": "paid"}
        assert meta["after"]["status"] == "cancelled_by_admin" and meta["reason"] == "Court flooded"
        # booking list flags it as awaiting a refund decision, and the filter finds it
        lst = api.get(f"{A}/bookings?refund_status=awaiting", headers=admin["h"]).json()["items"]
        assert [i["id"] for i in lst] == [b["id"]] and lst[0]["refund_status"] == "awaiting"
        det = api.get(f"{A}/bookings/{b['id']}", headers=admin["h"]).json()
        assert [t["to_status"] for t in det["timeline"]][-1] == "cancelled_by_admin"
        assert (
            det["timeline"][-1]["actor_name"] == "Ada Admin"
            and det["timeline"][-1]["reason"] == "Court flooded"
        )


def test_completed_bookings_cannot_be_cancelled_by_admin(clean_db):
    admin = admin_with(clean_db)
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b, _, _ = paid_booking(env, w, hour=9)
        sql(clean_db, "ALTER TABLE public.booking_status_history DISABLE TRIGGER trg_bsh_no_update")
        sql(clean_db, "UPDATE public.bookings SET status='completed'")
        r = env.api.post(
            f"{A}/bookings/{b['id']}/cancel", json={"reason": "too late now"}, headers=admin["h"]
        )
        assert r.status_code == 409 and r.json()["code"] == "INVALID_STATUS_TRANSITION"
        sql(clean_db, "ALTER TABLE public.booking_status_history ENABLE TRIGGER trg_bsh_no_update")


def test_dispute_lifecycle_links_actions_and_only_resolves_what_really_happened(clean_db):
    admin = admin_with(clean_db)
    other = admin_with(clean_db, ["disputes.manage", "bookings.view"])
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        api = env.api
        b, _, gp = paid_booking(env, w, hour=9)
        pid = str(rows(clean_db, "SELECT id FROM public.payments")[0]["id"])
        d = api.post(
            f"{A}/disputes",
            json={"booking_id": b["id"], "subject": "Court was unusable", "description": "Photos attached"},
            headers=admin["h"],
        )
        assert d.status_code == 201 and d.json()["status"] == "open" and d.json()["payment_id"] == pid
        did = d.json()["id"]
        assert (
            api.post(
                f"{A}/disputes", json={"booking_id": b["id"], "subject": "again again"}, headers=admin["h"]
            ).json()["code"]
            == "DISPUTE_ALREADY_OPEN"
        )
        ev = api.post(
            f"{A}/disputes/{did}/events",
            json={"kind": "evidence", "body": "Owner confirmed flooding by phone"},
            headers=other["h"],
        )
        assert ev.status_code == 200
        assert (
            api.patch(
                f"{A}/disputes/{did}",
                json={"status": "investigating", "priority": "high"},
                headers=admin["h"],
            ).json()["status"]
            == "investigating"
        )
        # cannot claim a refund resolution without an accepted refund, nor a cancellation that did not happen
        nr = api.post(
            f"{A}/disputes/{did}/resolve",
            json={
                "outcome": "resolved",
                "resolution_type": "refund_full",
                "resolution_note": "Refunded in full",
            },
            headers=admin["h"],
        )
        assert nr.status_code == 409 and nr.json()["code"] == "RESOLUTION_NOT_BACKED"
        nc = api.post(
            f"{A}/disputes/{did}/resolve",
            json={
                "outcome": "resolved",
                "resolution_type": "booking_cancelled",
                "resolution_note": "Cancelled it",
            },
            headers=admin["h"],
        )
        assert nc.status_code == 409
        # do the work, linked to the dispute
        assert (
            api.post(
                f"{A}/bookings/{b['id']}/cancel",
                json={"reason": "Court flooded", "dispute_id": did},
                headers=admin["h"],
            ).status_code
            == 200
        )
        api.put(
            f"{A}/settings/refunds_enabled",
            json={"value": True, "reason": "policy approved"},
            headers=admin["h"],
        )
        rf = api.post(
            f"{A}/payments/{pid}/refunds",
            json={"reason": "Court flooded", "dispute_id": did},
            headers={**admin["h"], "Idempotency-Key": "dispute-key-001"},
        )
        assert rf.status_code == 201 and rf.json()["status"] == "pending"
        done = env.gw.set_refund_status(rf.json()["provider_refund_id"], "processed")
        body, h = refund_webhook("refund.processed", done)
        post_webhook(env, body, h)
        ok = api.post(
            f"{A}/disputes/{did}/resolve",
            json={
                "outcome": "resolved",
                "resolution_type": "refund_full",
                "resolution_note": "Full refund issued",
            },
            headers=admin["h"],
        )
        assert ok.status_code == 200 and ok.json()["status"] == "resolved"
        full = ok.json()
        kinds = [e["kind"] for e in full["events"]]
        assert (
            kinds[0] == "opened"
            and "evidence" in kinds
            and kinds.count("action") >= 3
            and kinds[-1] == "resolved"
        )
        assert full["booking"]["status"] == "refunded" and full["refunds"][0]["status"] == "processed"
        # closed disputes are closed
        assert (
            api.post(f"{A}/disputes/{did}/events", json={"body": "late note"}, headers=admin["h"]).json()[
                "code"
            ]
            == "DISPUTE_CLOSED"
        )
        assert api.get(f"{A}/disputes?status=resolved", headers=admin["h"]).json()["items"][0]["id"] == did
        meta = json.loads(audit_rows(clean_db, "admin.dispute_resolved")[0]["metadata"])
        assert (
            meta["before"]["status"] == "investigating" and meta["after"]["resolution_type"] == "refund_full"
        )
        assert (
            api.get(f"{A}/disputes", headers=admin_with(clean_db, ["bookings.view"])["h"]).status_code == 403
        )


# ------------------------------------------------------------------ support
def test_support_tickets_replies_status_priority_and_mobile_compatibility(api, clean_db):
    admin = admin_with(clean_db)
    cust = seed_profile(clean_db, "customer", name="Cathy")
    ch = auth_headers(cust)
    t = api.post(
        f"{API}/support/tickets",
        json={
            "kind": "issue",
            "subject": "Payment problem",
            "message": "I was charged twice for one booking.",
        },
        headers=ch,
    )
    assert t.status_code == 201 and t.json()["status"] == "open"
    tid = t.json()["id"]
    lst = api.get(f"{A}/support/tickets", headers=admin["h"]).json()
    assert lst["items"][0]["subject"] == "Payment problem" and lst["counts"]["open"] == 1
    d = api.get(f"{A}/support/tickets/{tid}", headers=admin["h"]).json()
    assert d["customer"]["full_name"] == "Cathy" and d["message"].startswith("I was charged")
    assert (
        api.get(f"{A}/support/tickets", headers=admin_with(clean_db, ["bookings.view"])["h"]).status_code
        == 403
    )
    # internal note: invisible to the customer; public reply: moves to in_progress and notifies
    api.post(
        f"{A}/support/tickets/{tid}/messages",
        json={"body": "Check payment logs first", "internal": True},
        headers=admin["h"],
    )
    r = api.post(
        f"{A}/support/tickets/{tid}/messages", json={"body": "We are looking into it."}, headers=admin["h"]
    ).json()
    assert r["status"] == "in_progress"
    assert [m["kind"] for m in r["messages"]] == ["note", "reply"]
    mine = api.get(f"{API}/support/tickets", headers=ch).json()
    assert mine[0]["status"] == "open"  # mobile only knows open/closed: in_progress shows as open
    replies = api.get(f"{API}/support/tickets/{tid}/messages", headers=ch).json()["items"]
    assert [x["body"] for x in replies] == ["We are looking into it."] and replies[0]["from_team"] is True
    assert (
        api.get(
            f"{API}/support/tickets/{tid}/messages", headers=auth_headers(seed_profile(clean_db, "customer"))
        ).status_code
        == 404
    )
    assert sql(clean_db, "SELECT 1 FROM public.notifications WHERE type='support.reply' AND user_id=$1", cust)
    u = api.patch(
        f"{A}/support/tickets/{tid}",
        json={"priority": "urgent", "status": "resolved", "assigned_to_me": True},
        headers=admin["h"],
    ).json()
    assert (
        u["priority"] == "urgent"
        and u["status"] == "resolved"
        and u["resolved_at"]
        and u["assignee_name"] == "Ada Admin"
    )
    assert api.get(f"{API}/support/tickets", headers=ch).json()[0]["status"] == "closed"
    assert "event" in [m["kind"] for m in u["messages"]]  # support history
    assert (
        api.post(f"{A}/support/tickets/{tid}/messages", json={"body": "one more"}, headers=admin["h"]).json()[
            "code"
        ]
        == "TICKET_CLOSED"
    )
    assert (
        api.patch(f"{A}/support/tickets/{tid}", json={"status": "bogus"}, headers=admin["h"]).status_code
        == 422
    )
    meta = json.loads(audit_rows(clean_db, "admin.ticket_updated")[0]["metadata"])
    assert meta["before"]["status"] == "in_progress" and meta["after"]["status"] == "resolved"
    # linking a booking
    w = seed_world(clean_db)
    with make_app(clean_db, booking_hold_minutes=10) as a2:
        b = book(a2, w, iso(future_day(), 9)).json()
        linked = a2.patch(
            f"{A}/support/tickets/{tid}", json={"booking_id": b["id"]}, headers=admin["h"]
        ).json()
        assert linked["booking"]["booking_code"] == b["booking_code"]
        assert (
            a2.patch(
                f"{A}/support/tickets/{tid}", json={"booking_id": str(uuid.uuid4())}, headers=admin["h"]
            ).status_code
            == 422
        )


# ------------------------------------------------------------------ categories
def test_category_management_keeps_relationships_and_the_apps_only_see_active_ones(api, clean_db):
    admin = admin_with(clean_db)
    w = seed_world(clean_db)
    cust = w["customer_h"]
    cats = api.get(f"{A}/categories", headers=admin["h"]).json()["items"]
    cricket = cats[0]
    assert cricket["venues"] == 1
    assert (
        api.post(
            f"{A}/categories",
            json={"name": "Padel Tennis"},
            headers=admin_with(clean_db, ["dashboard.view"])["h"],
        ).status_code
        == 403
    )
    c = api.post(f"{A}/categories", json={"name": "Padel Tennis", "sort_order": 5}, headers=admin["h"])
    assert c.status_code == 201 and c.json()["slug"] == "padel-tennis" and c.json()["is_active"] is True
    assert (
        api.post(f"{A}/categories", json={"name": "Padel Tennis"}, headers=admin["h"]).json()["code"]
        == "CATEGORY_SLUG_TAKEN"
    )
    assert "padel-tennis" in [x["slug"] for x in api.get(f"{API}/categories", headers=cust).json()]
    e = api.patch(
        f"{A}/categories/{c.json()['id']}", json={"name": "Padel", "is_active": False}, headers=admin["h"]
    )
    assert e.json()["name"] == "Padel" and e.json()["is_active"] is False
    assert "padel-tennis" not in [x["slug"] for x in api.get(f"{API}/categories", headers=cust).json()]
    # deactivating one a venue uses keeps the link (data) but hides it from the app lists
    api.patch(f"{A}/categories/{cricket['id']}", json={"is_active": False}, headers=admin["h"])
    assert sql(clean_db, "SELECT count(*) n FROM public.venue_categories")[0]["n"] == 1
    meta = json.loads(audit_rows(clean_db, "admin.category_deactivated")[-1]["metadata"])
    assert (
        meta["before"]["is_active"] is True
        and meta["after"]["is_active"] is False
        and meta["venues_affected"] == 1
    )
    assert (
        api.patch(f"{A}/categories/{uuid.uuid4()}", json={"name": "x"}, headers=admin["h"]).status_code == 404
    )


# ------------------------------------------------------------------ CMS
def test_cms_content_is_visible_to_the_apps_only_when_published(api, clean_db):
    admin = admin_with(clean_db)
    cust = auth_headers(seed_profile(clean_db, "customer"))
    assert (
        api.post(
            f"{A}/cms",
            json={"kind": "page", "slug": "privacy", "title": "Privacy", "body": "x"},
            headers=admin_with(clean_db, ["dashboard.view"])["h"],
        ).status_code
        == 403
    )
    r = api.post(
        f"{A}/cms",
        json={
            "kind": "page",
            "slug": "terms-customer",
            "audience": "customer",
            "title": "Terms",
            "body": "Draft terms",
        },
        headers=admin["h"],
    )
    assert r.status_code == 201 and r.json()["status"] == "draft"
    cid = r.json()["id"]
    assert (
        api.post(
            f"{A}/cms",
            json={"kind": "page", "slug": "terms-customer", "title": "T", "body": "x"},
            headers=admin["h"],
        ).json()["code"]
        == "CONTENT_SLUG_TAKEN"
    )
    assert (
        api.post(
            f"{A}/cms",
            json={"kind": "page", "slug": "Bad Slug", "title": "T", "body": "x"},
            headers=admin["h"],
        ).status_code
        == 422
    )
    assert api.get(f"{API}/content/terms-customer").status_code == 404  # drafts are never shown
    assert api.get(f"{API}/content").json()["items"] == []
    pub = api.post(f"{A}/cms/{cid}/publish", headers=admin["h"]).json()
    assert pub["status"] == "published" and pub["published_at"]
    got = api.get(f"{API}/content/terms-customer")
    assert (
        got.status_code == 200
        and got.json()["body"] == "Draft terms"
        and "max-age" in got.headers["cache-control"]
    )
    api.post(
        f"{A}/cms",
        json={
            "kind": "faq",
            "slug": "faq-cancel",
            "audience": "owner",
            "title": "How do I cancel?",
            "body": "Ask us.",
            "sort_order": 2,
        },
        headers=admin["h"],
    )
    faq = api.get(f"{A}/cms?kind=faq", headers=admin["h"]).json()["items"][0]
    api.post(f"{A}/cms/{faq['id']}/publish", headers=admin["h"])
    assert [
        x["slug"] for x in api.get(f"{API}/content?kind=faq&audience=owner", headers=cust).json()["items"]
    ] == ["faq-cancel"]
    assert api.get(f"{API}/content?kind=faq&audience=customer").json()["items"] == []
    upd = api.patch(f"{A}/cms/{cid}", json={"body": "Final terms"}, headers=admin["h"]).json()
    assert (
        upd["body"] == "Final terms"
        and api.get(f"{API}/content/terms-customer").json()["body"] == "Final terms"
    )
    meta = json.loads(audit_rows(clean_db, "admin.cms_updated")[0]["metadata"])
    assert meta["before"]["body_preview"] == "Draft terms" and meta["after"]["body_preview"] == "Final terms"
    api.post(f"{A}/cms/{cid}/unpublish", headers=admin["h"])
    assert api.get(f"{API}/content/terms-customer").status_code == 404
    assert (
        len(audit_rows(clean_db, "admin.cms_published")) == 2
        and len(audit_rows(clean_db, "admin.cms_unpublished")) == 1
    )


# ------------------------------------------------------------------ coupons
def coupon(api, admin, **over):
    body = {"code": "WELCOME10", "discount_type": "percent", "percent_bps": 1000, **over}
    r = api.post(f"{A}/coupons", json=body, headers=admin["h"])
    assert r.status_code == 201, r.text
    return r.json()


def quote(api, w, code, hour=9):
    return api.post(
        f"{API}/bookings/quote",
        json={"resource_id": str(w["resource"]), "starts_at": iso(future_day(), hour), "coupon_code": code},
        headers=w["customer_h"],
    )


def test_coupon_discounts_are_validated_and_calculated_on_the_server(clean_db):
    admin = admin_with(clean_db)
    w = seed_world(clean_db, price=50000)
    with payment_app(clean_db) as env:
        api = env.api
        assert (
            api.post(
                f"{A}/coupons",
                json={"code": "X1", "discount_type": "percent", "percent_bps": 1000},
                headers=admin["h"],
            ).status_code
            == 422
        )
        assert (
            api.post(
                f"{A}/coupons",
                json={"code": "BADMIX", "discount_type": "percent", "percent_bps": 1000, "fixed_paise": 5},
                headers=admin["h"],
            ).status_code
            == 422
        )
        assert (
            api.post(
                f"{A}/coupons", json={"code": "FIXED0", "discount_type": "fixed"}, headers=admin["h"]
            ).status_code
            == 422
        )
        c = coupon(api, admin, code="welcome10", description="10% off", max_discount_paise=3000)
        assert c["code"] == "WELCOME10"  # normalised
        assert (
            api.post(
                f"{A}/coupons",
                json={"code": "WELCOME10", "discount_type": "fixed", "fixed_paise": 100},
                headers=admin["h"],
            ).json()["code"]
            == "COUPON_CODE_TAKEN"
        )
        q = quote(api, w, "welcome10").json()
        assert (q["base_amount_paise"], q["discount_paise"], q["total_amount_paise"], q["coupon_code"]) == (
            50000,
            3000,
            47000,
            "WELCOME10",
        )  # capped at 30.00
        assert quote(api, w, "NOPE123").json()["code"] == "COUPON_NOT_FOUND"
        b = api.post(
            f"{API}/bookings",
            json={
                "resource_id": str(w["resource"]),
                "starts_at": iso(future_day(), 9),
                "coupon_code": "WELCOME10",
            },
            headers=w["customer_h"],
        )
        assert (
            b.status_code == 201
            and b.json()["total_amount_paise"] == 47000
            and b.json()["price"]["discount_paise"] == 3000
        )
        # the payment is created for the DISCOUNTED amount, computed server-side
        o = api.post(
            f"{API}/payments/create-order", json={"booking_id": b.json()["id"]}, headers=w["customer_h"]
        ).json()
        assert o["checkout"]["amount_paise"] == 47000
        red = api.get(f"{A}/coupons/{c['id']}/redemptions", headers=admin["h"]).json()["items"]
        assert (
            len(red) == 1 and red[0]["discount_paise"] == 3000 and red[0]["customer_name"] == "Cathy Customer"
        )
        assert api.get(f"{A}/coupons/{c['id']}", headers=admin["h"]).json()["redeemed"] == 1
        det = api.get(f"{A}/bookings/{b.json()['id']}", headers=admin["h"]).json()
        assert det["coupon"] == {"code": "WELCOME10", "discount_paise": 3000}


def test_coupon_rules_dates_limits_eligibility_and_minimum(clean_db):
    admin = admin_with(clean_db)
    w = seed_world(clean_db, price=50000)
    other_h = auth_headers(seed_profile(clean_db, "customer", name="Other"))
    with payment_app(clean_db) as env:
        api = env.api
        coupon(
            api,
            admin,
            code="FIX100",
            discount_type="fixed",
            percent_bps=None,
            fixed_paise=10000,
            usage_limit_total=1,
        )
        coupon(api, admin, code="MINIMUM", min_booking_paise=60000)
        coupon(
            api, admin, code="PASTDATE", valid_from="2020-01-01T00:00:00Z", valid_until="2020-02-01T00:00:00Z"
        )
        coupon(api, admin, code="FUTURE", valid_from="2099-01-01T00:00:00Z")
        coupon(api, admin, code="OTHERVENUE", eligible_venue_ids=[str(uuid.uuid4())])
        coupon(api, admin, code="PERUSER", usage_limit_per_user=1)
        coupon(api, admin, code="FIRSTONLY", first_booking_only=True)
        coupon(api, admin, code="HUGE", discount_type="fixed", percent_bps=None, fixed_paise=90000)
        for code, err in [
            ("MINIMUM", "COUPON_MIN_AMOUNT"),
            ("PASTDATE", "COUPON_EXPIRED"),
            ("FUTURE", "COUPON_NOT_STARTED"),
            ("OTHERVENUE", "COUPON_NOT_ELIGIBLE"),
        ]:
            r = quote(api, w, code)
            assert r.status_code == 422 and r.json()["code"] == err, (code, r.text)
        # a discount can never take the booking below the gateway minimum
        assert quote(api, w, "HUGE").json()["total_amount_paise"] == 100
        # total usage limit: the second customer is refused once the first holds a booking
        assert (
            api.post(
                f"{API}/bookings",
                json={
                    "resource_id": str(w["resource"]),
                    "starts_at": iso(future_day(), 9),
                    "coupon_code": "FIX100",
                },
                headers=w["customer_h"],
            ).status_code
            == 201
        )
        ex = quote(api, {**w, "customer_h": other_h}, "FIX100", hour=11)
        assert ex.json()["code"] == "COUPON_EXHAUSTED"
        # per-user limit
        assert (
            api.post(
                f"{API}/bookings",
                json={
                    "resource_id": str(w["resource"]),
                    "starts_at": iso(future_day(), 11),
                    "coupon_code": "PERUSER",
                },
                headers=w["customer_h"],
            ).status_code
            == 201
        )
        assert quote(api, w, "PERUSER", hour=13).json()["code"] == "COUPON_USER_LIMIT"
        # first-booking-only: valid for a new customer, refused once a paid booking exists
        assert quote(api, {**w, "customer_h": other_h}, "FIRSTONLY", hour=15).status_code == 200
        # expiring an unpaid hold releases the redemption
        sql(
            clean_db,
            "UPDATE public.bookings SET expires_at = now() - interval '1 minute' WHERE status='pending_payment'",
        )
        assert quote(api, {**w, "customer_h": other_h}, "FIX100", hour=17).status_code == 200
        # deactivate / reactivate with audit
        cid = api.get(f"{A}/coupons?q=FIX100", headers=admin["h"]).json()["items"][0]["id"]
        assert (
            api.patch(f"{A}/coupons/{cid}", json={"is_active": False}, headers=admin["h"]).json()["is_active"]
            is False
        )
        assert quote(api, w, "FIX100", hour=17).json()["code"] == "COUPON_INACTIVE"
        assert (
            api.patch(f"{A}/coupons/{cid}", json={"code": "NEWCODE"}, headers=admin["h"]).status_code == 422
        )  # code is immutable
        meta = json.loads(audit_rows(clean_db, "admin.coupon_deactivated")[0]["metadata"])
        assert meta["before"]["is_active"] is True and meta["after"]["is_active"] is False
        assert (
            api.get(f"{A}/coupons", headers=admin_with(clean_db, ["dashboard.view"])["h"]).status_code == 403
        )
        # a customer cannot hit the admin API or read other customers' redemptions
        assert api.get(f"{A}/coupons", headers=w["customer_h"]).status_code == 403


# ------------------------------------------------------------------ analytics, filters, history
def test_sport_city_venue_analytics_filters_and_exports(clean_db):
    admin = admin_with(clean_db)
    w = seed_world(clean_db, price=40000)
    # a second sport on the same venue: bookings must be SPLIT, not double counted
    cat2 = sql(
        clean_db, "INSERT INTO public.categories (slug, name) VALUES ('football','Football') RETURNING id"
    )[0]["id"]
    sql(
        clean_db,
        "INSERT INTO public.venue_categories (venue_id, category_id) VALUES ($1,$2)",
        w["venue"],
        cat2,
    )
    with payment_app(clean_db) as env:
        api = env.api
        paid_booking(env, w, hour=9)
        hold_booking(env, w, hour=11)
        sp = api.get(f"{A}/analytics/sports", headers=admin["h"]).json()
        assert sorted(x["category"] for x in sp["items"]) == ["Cricket", "Football"]
        assert sum(x["bookings"] for x in sp["items"]) == 2.0  # real total, not 4
        assert all(x["tagged_bookings"] == 2 and x["bookings"] == 1.0 for x in sp["items"])
        assert sum(x["gross_paid_paise"] for x in sp["items"]) == 40000
        cities = api.get(f"{A}/analytics/cities", headers=admin["h"]).json()["items"]
        assert (
            len(cities) == 1
            and cities[0]["bookings"] == 2
            and cities[0]["confirmed"] == 1
            and cities[0]["gross_paid_paise"] == 40000
        )
        v = api.get(f"{A}/analytics/venues", headers=admin["h"]).json()["items"][0]
        assert (v["name"], v["bookings"], v["confirmed"], v["completed"], v["gross_paid_paise"]) == (
            "Ace Arena",
            2,
            1,
            0,
            40000,
        )
        # venue detail performance + completed separate from confirmed
        sql(clean_db, "ALTER TABLE public.booking_status_history DISABLE TRIGGER trg_bsh_no_update")
        sql(clean_db, "UPDATE public.bookings SET status='completed' WHERE status='confirmed'")
        sql(clean_db, "ALTER TABLE public.booking_status_history ENABLE TRIGGER trg_bsh_no_update")
        d = api.get(f"{A}/dashboard", headers=admin["h"]).json()
        assert d["period"]["confirmed"] == 0 and d["period"]["completed"] == 1 and d["period"]["pending"] == 1
        vd = api.get(f"{A}/venues/{w['venue']}", headers=admin["h"]).json()
        assert (
            vd["completed_count"] == 1
            and vd["confirmed_count"] == 0
            and vd["performance"][-1]["bookings"] == 2
        )
        # booking filters: sport, city, owner, venue, refund status
        city = sql(clean_db, "SELECT city_id FROM public.venues")[0]["city_id"]
        for qs, n in [
            (f"category_id={cat2}", 2),
            (f"city_id={city}", 2),
            (f"owner_id={w['owner']}", 2),
            (f"venue_id={w['venue']}", 2),
            (f"city_id={uuid.uuid4()}", 0),
            (f"category_id={uuid.uuid4()}", 0),
            ("refund_status=none", 2),
            ("refund_status=processed", 0),
            (f"customer_id={w['customer']}", 2),
        ]:
            got = api.get(f"{A}/bookings?{qs}", headers=admin["h"]).json()
            assert len(got["items"]) == n, qs
        row = api.get(f"{A}/bookings", headers=admin["h"]).json()["items"][0]
        assert (
            row["city"]
            and sorted(row["sports"]) == ["Cricket", "Football"]
            and row["refund_status"] == "none"
        )
        csv = api.get(f"{A}/exports/analytics.csv?dimension=sport", headers=admin["h"])
        assert csv.status_code == 200 and "Cricket" in csv.text
        assert "Ace Arena" in api.get(f"{A}/exports/analytics.csv?dimension=venue", headers=admin["h"]).text
        assert api.get(f"{A}/exports/analytics.csv?dimension=city", headers=admin["h"]).status_code == 200
        assert (
            api.get(
                f"{A}/exports/bookings.csv?refund_status=none&category_id={cat2}", headers=admin["h"]
            ).text.count("ZUR-")
            == 2
        )
        assert len(audit_rows(clean_db, "admin.export")) >= 4


def test_dashboard_counts_active_users_by_real_status_and_pending_approvals(api, clean_db):
    admin = admin_with(clean_db)
    seed_profile(clean_db, "customer")
    seed_profile(clean_db, "customer", status="suspended")
    seed_profile(clean_db, "owner")
    seed_profile(clean_db, "owner", status="suspended")
    seed_profile(clean_db, "owner", status="suspended")
    owner = seed_profile(clean_db, "owner")
    sql(
        clean_db,
        "INSERT INTO public.venues (owner_id, name, timezone, status) VALUES ($1,'Pending Arena','Asia/Kolkata','pending_review')",
        owner,
    )
    t = api.get(f"{A}/dashboard", headers=admin["h"]).json()["totals"]
    assert (t["customers"], t["active_customers"], t["suspended_customers"]) == (2, 1, 1)
    assert (t["owners"], t["active_owners"], t["suspended_owners"]) == (4, 2, 2)
    assert t["pending_venue_approvals"] == 1


def test_account_actions_history_and_audit_filters(api, clean_db):
    admin = admin_with(clean_db)
    other = admin_with(clean_db, name="Bob Admin")
    cust = seed_profile(clean_db, "customer", name="Cathy")
    api.patch(
        f"{A}/customers/{cust}/status",
        json={"status": "suspended", "reason": "Chargeback abuse"},
        headers=admin["h"],
    )
    api.patch(
        f"{A}/customers/{cust}/status",
        json={"status": "active", "reason": "Resolved with customer"},
        headers=other["h"],
    )
    h = api.get(f"{A}/customers/{cust}/history", headers=admin["h"]).json()["items"]
    assert [(x["metadata"]["after"]["status"], x["metadata"]["reason"], x["actor_name"]) for x in h] == [
        ("active", "Resolved with customer", "Bob Admin"),
        ("suspended", "Chargeback abuse", "Ada Admin"),
    ]
    assert h[0]["metadata"]["before"]["status"] == "suspended" and h[0]["request_id"]
    assert (
        api.get(
            f"{A}/customers/{cust}/history", headers=admin_with(clean_db, ["dashboard.view"])["h"]
        ).status_code
        == 403
    )
    f = api.get(f"{A}/audit-logs?actor_id={other['id']}", headers=admin["h"]).json()["items"]
    assert len(f) == 1 and f[0]["actor_name"] == "Bob Admin"
    assert len(api.get(f"{A}/audit-logs?entity_id={cust}", headers=admin["h"]).json()["items"]) >= 2
    today = str(future_day(0))
    assert (
        len(
            api.get(
                f"{A}/audit-logs?action=admin.account_status_changed&from={today}&to={today}",
                headers=admin["h"],
            ).json()["items"]
        )
        == 2
    )
    assert api.get(f"{A}/audit-logs?from=2001-01-01&to=2001-01-02", headers=admin["h"]).json()["items"] == []
    assert "admin.account_status_changed" in api.get(f"{A}/audit-actions", headers=admin["h"]).json()["items"]
    assert (
        api.get(f"{A}/audit-logs", headers=admin_with(clean_db, ["dashboard.view"])["h"]).status_code == 403
    )
    # an admin can still not change another admin or themselves
    assert api.patch(
        f"{A}/customers/{admin['id']}/status",
        json={"status": "suspended", "reason": "no way"},
        headers=admin["h"],
    ).status_code in (403, 404)


def test_failed_payments_are_counted_on_the_dashboard(clean_db):
    admin = admin_with(clean_db)
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w, hour=9)
        o = env.api.post(
            f"{API}/payments/create-order", json={"booking_id": b["id"]}, headers=w["customer_h"]
        ).json()
        gp = env.gw.customer_pays(o["checkout"]["order_id"], status="failed")
        from tests.payment_helpers import webhook

        body, h = webhook("payment.failed", gp)
        post_webhook(env, body, h)
        d = env.api.get(f"{A}/dashboard", headers=admin["h"]).json()
        assert d["period"]["failed_payments"] == 1
