"""Step 7: Razorpay order creation, verification, webhooks, consistency and security."""

import json
import uuid

from tests.booking_helpers import API, book, future_day, iso, new_customer, seed_world
from tests.payment_helpers import (
    KEY_SECRET,
    FakeGateway,
    create_order,
    hold_booking,
    make_admin,
    paid_booking,
    payment_app,
    post_webhook,
    rows,
    sign_checkout,
    webhook,
)

# ------------------------------------------------------------------ order creation


def test_create_order_uses_server_side_amount_and_returns_checkout_config(clean_db):
    w = seed_world(clean_db, price=75000)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        r = env.api.post(
            f"{API}/payments/create-order",
            json={"booking_id": b["id"], "amount_paise": 1},  # a client-sent amount is rejected outright
            headers=w["customer_h"],
        )
        assert r.status_code == 422
        r = create_order(env, b["id"], w["customer_h"])
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["checkout"]["amount_paise"] == 75000 and out["checkout"]["currency"] == "INR"
        assert out["checkout"]["key_id"].startswith("rzp_test_")
        assert out["payment"]["status"] == "created" and out["payment"]["confirmed"] is False
        assert env.gw.orders[out["checkout"]["order_id"]].amount_paise == 75000
        assert rows(clean_db, "SELECT payment_status FROM public.bookings")[0]["payment_status"] == "pending"
        # the secret is never in any response
        assert KEY_SECRET not in r.text


def test_create_order_twice_reuses_the_same_order(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        a = create_order(env, b["id"], w["customer_h"]).json()
        c = create_order(env, b["id"], w["customer_h"]).json()
        assert a["checkout"]["order_id"] == c["checkout"]["order_id"]
        assert a["payment"]["id"] == c["payment"]["id"]
        assert env.gw.create_calls == 1
        assert len(rows(clean_db, "SELECT 1 FROM public.payments")) == 1


def test_create_order_rules(clean_db):
    w = seed_world(clean_db)
    other, other_h = new_customer(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        # someone else's booking looks like it does not exist
        r = create_order(env, b["id"], other_h)
        assert r.status_code == 404 and r.json()["code"] == "BOOKING_NOT_FOUND"
        assert create_order(env, str(uuid.uuid4()), w["customer_h"]).status_code == 404
        # owners cannot create payments
        assert create_order(env, b["id"], w["owner_h"]).status_code == 403
        assert env.api.post(f"{API}/payments/create-order", json={"booking_id": b["id"]}).status_code == 401
        # expired hold
        sql_exp = "UPDATE public.bookings SET expires_at = now() - interval '1 minute'"
        from tests.conftest import sql

        sql(clean_db, sql_exp)
        r = create_order(env, b["id"], w["customer_h"])
        assert r.status_code == 409 and r.json()["code"] == "HOLD_EXPIRED"


def test_create_order_not_configured_and_free_booking(clean_db):
    w = seed_world(clean_db, price=0)
    with payment_app(clean_db, razorpay_key_secret="") as env:
        b = hold_booking(env, w)
        r = create_order(env, b["id"], w["customer_h"])
        assert r.status_code == 503 and r.json()["code"] == "PAYMENTS_NOT_CONFIGURED"
    with payment_app(clean_db) as env:
        b = env.api.get(f"{API}/bookings", headers=w["customer_h"]).json()["items"][0]
        r = create_order(env, b["id"], w["customer_h"])
        assert r.status_code == 422 and r.json()["code"] == "AMOUNT_NOT_PAYABLE"


def test_instant_mode_booking_needs_no_payment(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db, booking_mode="instant", booking_hold_minutes="") as env:
        b = hold_booking(env, w)
        assert b["status"] == "confirmed"
        r = create_order(env, b["id"], w["customer_h"])
        assert r.status_code == 409 and r.json()["code"] == "PAYMENT_NOT_REQUIRED"


def test_gateway_down_on_order_creation_leaves_no_payment(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        env.gw.unreachable = True
        r = create_order(env, b["id"], w["customer_h"])
        assert r.status_code == 503
        assert rows(clean_db, "SELECT 1 FROM public.payments") == []
        env.gw.unreachable = False
        assert create_order(env, b["id"], w["customer_h"]).status_code == 200


# ------------------------------------------------------------------ verification


def test_verify_valid_signature_confirms_booking_and_payment_together(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b, order, gp = paid_booking(env, w)
        got = env.api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()
        assert got["status"] == "confirmed" and got["payment_status"] == "paid"
        pay = env.api.get(f"{API}/payments/{order['payment']['id']}", headers=w["customer_h"]).json()
        assert pay["status"] == "captured" and pay["confirmed"] is True
        assert pay["razorpay_payment_id"] == gp.id and pay["method"] == "upi"
        hist = rows(
            clean_db, "SELECT to_status, actor_role FROM public.booking_status_history ORDER BY created_at"
        )
        assert [(h["to_status"], h["actor_role"]) for h in hist] == [
            ("pending_payment", "customer"),
            ("confirmed", "system"),
        ]
        # the hold clock no longer applies
        assert rows(clean_db, "SELECT expires_at FROM public.bookings")[0]["expires_at"] is None


def test_verify_invalid_signature_is_rejected_and_changes_nothing(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        r = env.api.post(
            f"{API}/payments/verify",
            json={
                "razorpay_order_id": gp.order_id,
                "razorpay_payment_id": gp.id,
                "razorpay_signature": "0" * 64,
            },
            headers=w["customer_h"],
        )
        assert r.status_code == 400 and r.json()["code"] == "PAYMENT_SIGNATURE_INVALID"
        assert (
            rows(clean_db, "SELECT status, payment_status FROM public.bookings")[0]["status"]
            == "pending_payment"
        )
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "created"
        ev = rows(clean_db, "SELECT outcome FROM public.payment_events WHERE source='verify'")
        assert [e["outcome"] for e in ev] == ["rejected"]
        # a signature made with the WRONG secret is equally rejected
        bad = sign_checkout(gp.order_id or "", gp.id, secret="not-the-secret")
        r = env.api.post(
            f"{API}/payments/verify",
            json={"razorpay_order_id": gp.order_id, "razorpay_payment_id": gp.id, "razorpay_signature": bad},
            headers=w["customer_h"],
        )
        assert r.status_code == 400


def test_verify_signature_swapped_to_another_payment_id_is_rejected(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        r = env.api.post(
            f"{API}/payments/verify",
            json={
                "razorpay_order_id": gp.order_id,
                "razorpay_payment_id": "pay_someoneelses000",
                "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
            },
            headers=w["customer_h"],
        )
        assert r.status_code == 400


def test_verify_wrong_booking_reference_and_other_customer(clean_db):
    w = seed_world(clean_db)
    other, other_h = new_customer(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        body = {
            "razorpay_order_id": gp.order_id,
            "razorpay_payment_id": gp.id,
            "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
        }
        # another customer presenting a genuine signature cannot confirm someone else's booking
        r = env.api.post(f"{API}/payments/verify", json=body, headers=other_h)
        assert r.status_code == 404
        # an order id we never created
        body2 = {**body, "razorpay_order_id": "order_unknown000000"}
        assert env.api.post(f"{API}/payments/verify", json=body2, headers=w["customer_h"]).status_code == 404
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "pending_payment"


def test_verify_amount_mismatch_is_not_confirmed_and_is_flagged(clean_db):
    w = seed_world(clean_db, price=50000)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"], amount=100)  # paid far less
        r = env.api.post(
            f"{API}/payments/verify",
            json={
                "razorpay_order_id": gp.order_id,
                "razorpay_payment_id": gp.id,
                "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
            },
            headers=w["customer_h"],
        )
        assert r.status_code == 200 and r.json()["confirmed"] is False
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "pending_payment"
        p = rows(clean_db, "SELECT status, review_required, review_reason FROM public.payments")[0]
        assert p["status"] == "created" and p["review_required"] and p["review_reason"] == "AMOUNT_MISMATCH"


def test_verify_is_idempotent(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b, order, gp = paid_booking(env, w)
        for _ in range(2):
            r = env.api.post(
                f"{API}/payments/verify",
                json={
                    "razorpay_order_id": gp.order_id,
                    "razorpay_payment_id": gp.id,
                    "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
                },
                headers=w["customer_h"],
            )
            assert r.status_code == 200 and r.json()["confirmed"] is True
        assert (
            len(rows(clean_db, "SELECT 1 FROM public.booking_status_history WHERE to_status='confirmed'"))
            == 1
        )
        assert len(rows(clean_db, "SELECT 1 FROM public.payments")) == 1


def test_verify_when_gateway_unreachable_does_not_confirm_then_reconciles(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        env.gw.unreachable = True
        r = env.api.post(
            f"{API}/payments/verify",
            json={
                "razorpay_order_id": gp.order_id,
                "razorpay_payment_id": gp.id,
                "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
            },
            headers=w["customer_h"],
        )
        assert r.status_code == 200 and r.json()["confirmed"] is False  # "verification in progress"
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "pending_payment"
        # delayed confirmation: the gateway is back, the app polls GET /payments/{id}
        env.gw.unreachable = False
        got = env.api.get(f"{API}/payments/{order['payment']['id']}", headers=w["customer_h"]).json()
        assert got["confirmed"] is True and got["booking_status"] == "confirmed"


# ------------------------------------------------------------------ failure, retry, abandonment


def test_failed_payment_is_not_shown_paid_and_can_be_retried(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        failed = env.gw.customer_pays(order["checkout"]["order_id"], status="failed")
        body, hdr = webhook("payment.failed", failed)
        assert post_webhook(env, body, hdr).json()["outcome"] == "applied"
        bk = env.api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()
        assert bk["status"] == "payment_failed" and bk["payment_status"] == "failed"
        pay = env.api.get(f"{API}/payments/{order['payment']['id']}", headers=w["customer_h"]).json()
        assert pay["status"] == "failed" and pay["confirmed"] is False and pay["failure_reason"]
        # retry: same order, booking back to pending
        again = create_order(env, b["id"], w["customer_h"]).json()
        assert again["checkout"]["order_id"] == order["checkout"]["order_id"]
        assert (
            again["payment"]["status"] == "pending"
            and again["payment"]["booking_status"] == "pending_payment"
        )
        good = env.gw.customer_pays(order["checkout"]["order_id"])
        body, hdr = webhook("payment.captured", good)
        assert post_webhook(env, body, hdr).json()["outcome"] == "applied"
        bk = env.api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()
        assert bk["status"] == "confirmed" and bk["payment_status"] == "paid"


def test_customer_failure_notification_is_created(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        failed = env.gw.customer_pays(order["checkout"]["order_id"], status="failed")
        body, hdr = webhook("payment.failed", failed)
        post_webhook(env, body, hdr)
        n = env.api.get(f"{API}/notifications", headers=w["customer_h"]).json()["items"]
        assert [x["type"] for x in n] == ["payment.failed"]
        assert n[0]["booking_id"] == b["id"]


def test_abandoned_payment_expires_and_frees_the_slot(clean_db):
    w = seed_world(clean_db)
    from tests.conftest import sql

    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        create_order(env, b["id"], w["customer_h"])  # opened checkout, then closed it
        sql(clean_db, "UPDATE public.bookings SET expires_at = now() - interval '1 minute'")
        got = env.api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"]).json()
        assert got["status"] == "expired"
        # the slot can be booked by someone else again
        other, other_h = new_customer(clean_db)
        assert book(env.api, w, iso(future_day(), 9), headers=other_h).status_code == 201


# ------------------------------------------------------------------ late payment (N5 unresolved)


def test_payment_after_hold_expiry_is_recorded_flagged_and_never_confirms(clean_db):
    w = seed_world(clean_db)
    from tests.conftest import sql

    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        sql(clean_db, "UPDATE public.bookings SET expires_at = now() - interval '1 minute'")
        env.api.get(f"{API}/bookings/{b['id']}", headers=w["customer_h"])  # settles -> expired
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        body, hdr = webhook("payment.captured", gp)
        assert post_webhook(env, body, hdr).status_code == 200
        bk = rows(clean_db, "SELECT status, payment_status FROM public.bookings")[0]
        assert bk["status"] == "expired" and bk["payment_status"] == "paid"
        p = rows(clean_db, "SELECT status, review_required, review_reason FROM public.payments")[0]
        assert p["status"] == "captured" and p["review_required"] is True
        assert p["review_reason"] == "LATE_PAYMENT_BOOKING_EXPIRED"
        pay = env.api.get(f"{API}/payments/{order['payment']['id']}", headers=w["customer_h"]).json()
        assert pay["needs_review"] is True and pay["confirmed"] is False
        # no refund is invented
        assert (
            rows(clean_db, "SELECT 1 FROM public.booking_status_history WHERE to_status='refund_pending'")
            == []
        )


# ------------------------------------------------------------------ webhook


def test_webhook_rejects_missing_or_invalid_signature(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        body, hdr = webhook("payment.captured", gp)
        r = env.api.post(
            f"{API}/payments/webhook", content=body, headers={**hdr, "X-Razorpay-Signature": "bad"}
        )
        assert r.status_code == 400 and r.json()["code"] == "WEBHOOK_SIGNATURE_INVALID"
        no_sig = {k: v for k, v in hdr.items() if k != "X-Razorpay-Signature"}
        assert env.api.post(f"{API}/payments/webhook", content=body, headers=no_sig).status_code == 400
        # signed with the API secret instead of the webhook secret: still rejected (secrets are separate)
        body2, hdr2 = webhook("payment.captured", gp, secret=KEY_SECRET)
        assert env.api.post(f"{API}/payments/webhook", content=body2, headers=hdr2).status_code == 400
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "pending_payment"


def test_webhook_signature_is_over_the_raw_body(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        body, hdr = webhook("payment.captured", gp)
        # semantically identical JSON with different bytes must NOT validate
        reformatted = json.dumps(json.loads(body), indent=2).encode()
        assert env.api.post(f"{API}/payments/webhook", content=reformatted, headers=hdr).status_code == 400
        assert post_webhook(env, body, hdr).status_code == 200


def test_webhook_confirms_without_any_client_callback(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])  # customer closed the app after paying
        body, hdr = webhook("payment.captured", gp)
        assert post_webhook(env, body, hdr).json() == {"received": True, "outcome": "applied"}
        assert (
            rows(clean_db, "SELECT status, payment_status FROM public.bookings")[0]["status"] == "confirmed"
        )


def test_duplicate_webhook_is_idempotent(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        body, hdr = webhook("payment.captured", gp)
        outcomes = [post_webhook(env, body, hdr).json()["outcome"] for _ in range(3)]
        assert outcomes == ["applied", "duplicate", "duplicate"]
        assert len(rows(clean_db, "SELECT 1 FROM public.payments")) == 1
        assert (
            len(rows(clean_db, "SELECT 1 FROM public.booking_status_history WHERE to_status='confirmed'"))
            == 1
        )
        # also when a different event id reports the same capture (order.paid after payment.captured)
        body2, hdr2 = webhook("order.paid", gp)
        assert post_webhook(env, body2, hdr2).json()["outcome"] == "duplicate"
        # one notification and one email set, however often the event is redelivered
        assert len(rows(clean_db, "SELECT 1 FROM public.notifications WHERE type='booking.confirmed'")) == 1
        assert (
            len(rows(clean_db, "SELECT 1 FROM public.email_deliveries WHERE template='booking_confirmed'"))
            == 1
        )


def test_webhook_then_client_verify_does_not_duplicate(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        body, hdr = webhook("payment.captured", gp)
        post_webhook(env, body, hdr)
        r = env.api.post(
            f"{API}/payments/verify",
            json={
                "razorpay_order_id": gp.order_id,
                "razorpay_payment_id": gp.id,
                "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
            },
            headers=w["customer_h"],
        )
        assert r.json()["confirmed"] is True
        assert (
            len(rows(clean_db, "SELECT 1 FROM public.booking_status_history WHERE to_status='confirmed'"))
            == 1
        )
        assert (
            len(rows(clean_db, "SELECT 1 FROM public.email_deliveries WHERE template='booking_confirmed'"))
            == 1
        )


def test_delayed_failed_webhook_never_downgrades_a_captured_payment(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        failed = env.gw.customer_pays(order["checkout"]["order_id"], status="failed")
        good = env.gw.customer_pays(order["checkout"]["order_id"])
        post_webhook(env, *webhook("payment.captured", good))
        r = post_webhook(env, *webhook("payment.failed", failed))  # arrives late, out of order
        assert r.json()["outcome"] == "ignored"
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "captured"
        assert (
            rows(clean_db, "SELECT status, payment_status FROM public.bookings")[0]["status"] == "confirmed"
        )


def test_authorized_webhook_triggers_capture_then_confirms(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        auth = env.gw.customer_pays(order["checkout"]["order_id"], status="authorized")
        assert post_webhook(env, *webhook("payment.authorized", auth)).status_code == 200
        assert env.gw.capture_calls == [auth.id]
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "captured"
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "confirmed"


def test_webhook_for_unknown_order_and_unhandled_event_are_acknowledged_not_applied(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        hold_booking(env, w)
        stranger = FakeGateway.customer_pays
        env.gw.orders["order_stranger00000"] = type(
            "O", (), {"id": "order_stranger00000", "amount_paise": 100, "currency": "INR"}
        )()
        gp = stranger(env.gw, "order_stranger00000")
        assert post_webhook(env, *webhook("payment.captured", gp)).json()["outcome"] == "ignored"
        assert post_webhook(env, *webhook("subscription.charged", gp)).json()["outcome"] == "ignored"
        assert rows(clean_db, "SELECT 1 FROM public.payments") == []


def test_webhook_with_amount_mismatch_is_not_applied(clean_db):
    w = seed_world(clean_db, price=50000)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"], amount=1000)
        assert post_webhook(env, *webhook("payment.captured", gp)).json()["outcome"] == "rejected"
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "pending_payment"
        assert (
            rows(clean_db, "SELECT review_reason FROM public.payments")[0]["review_reason"]
            == "AMOUNT_MISMATCH"
        )


def test_webhook_not_configured_is_refused(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db, razorpay_webhook_secret="") as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        r = post_webhook(env, *webhook("payment.captured", gp))
        assert r.status_code == 503 and r.json()["code"] == "WEBHOOK_NOT_CONFIGURED"


# ------------------------------------------------------------------ duplicate payment prevention (DB-level)


def test_database_allows_only_one_payment_per_booking(clean_db):
    import asyncpg
    import pytest

    from tests.conftest import sql

    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        create_order(env, b["id"], w["customer_h"])
        p = rows(clean_db, "SELECT * FROM public.payments")[0]
        with pytest.raises(asyncpg.UniqueViolationError):
            sql(
                clean_db,
                "INSERT INTO public.payments (booking_id, customer_id, venue_id, provider_order_id, amount_paise, currency) "
                "VALUES ($1,$2,$3,'order_dupe',100,'INR')",
                p["booking_id"], p["customer_id"], p["venue_id"],
            )  # fmt: skip


def test_payment_event_rows_cannot_be_modified_and_card_data_is_never_stored(clean_db):
    import asyncpg
    import pytest

    from tests.conftest import sql

    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        post_webhook(env, *webhook("payment.captured", gp))
        with pytest.raises(asyncpg.PostgresError):
            sql(clean_db, "UPDATE public.payment_events SET outcome = 'applied'")
        dump = json.dumps(
            [dict(r) for r in rows(clean_db, "SELECT detail, provider_order_id FROM public.payment_events")],
            default=str,
        )
        payments = json.dumps(
            [dict(r) for r in rows(clean_db, "SELECT gateway_refs FROM public.payments")], default=str
        )
        assert "customer@example.com" not in dump + payments and "+910000000000" not in dump + payments


# ------------------------------------------------------------------ cancellation still follows the (unapproved) policy


def test_paid_booking_cannot_be_cancelled_until_a_refund_policy_exists(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db, cancellation_min_notice_hours=1) as env:
        b, _, _ = paid_booking(env, w)
        r = env.api.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=w["customer_h"])
        assert r.status_code == 409 and r.json()["code"] == "CANCELLATION_NOT_AVAILABLE"


# ------------------------------------------------------------------ reads: history, ownership, owner, admin


def test_history_and_get_are_private_to_the_customer(clean_db):
    w = seed_world(clean_db)
    other, other_h = new_customer(clean_db)
    with payment_app(clean_db) as env:
        _, order, _ = paid_booking(env, w)
        h = env.api.get(f"{API}/payments/history", headers=w["customer_h"]).json()
        assert [p["id"] for p in h["items"]] == [order["payment"]["id"]]
        assert env.api.get(f"{API}/payments/history", headers=other_h).json()["items"] == []
        r = env.api.get(f"{API}/payments/{order['payment']['id']}", headers=other_h)
        assert r.status_code == 404
        assert (
            env.api.get(f"{API}/payments/{order['payment']['id']}", headers=w["owner_h"]).status_code == 403
        )
        assert env.api.get(f"{API}/payments/history").status_code == 401


def test_owner_sees_only_confirmed_gross_amounts(clean_db):
    w = seed_world(clean_db, price=50000)
    stranger_owner = seed_world(clean_db)["owner_h"]
    with payment_app(clean_db) as env:
        paid_booking(env, w, hour=9)
        hold_booking(env, w, hour=11)  # unpaid hold: must not appear
        e = env.api.get(f"{API}/owners/earnings", headers=w["owner_h"]).json()
        assert e["gross_paid_paise"] == 50000 and e["payments_count"] == 1
        assert e["by_venue"][0]["venue_name"] == "Ace Arena"
        for k in ("deductions", "net_earnings", "payouts"):
            assert e[k]["available"] is False
        pays = env.api.get(f"{API}/owners/payments", headers=w["owner_h"]).json()["items"]
        assert len(pays) == 1 and pays[0]["amount_paise"] == 50000 and pays[0]["status"] == "captured"
        assert "provider_order_id" not in pays[0] and "razorpay_order_id" not in pays[0]
        # another owner sees nothing of it
        other = env.api.get(f"{API}/owners/earnings", headers=stranger_owner).json()
        assert other["gross_paid_paise"] == 0
        assert env.api.get(f"{API}/owners/payments", headers=w["customer_h"]).status_code == 403


def test_admin_payment_visibility_is_admin_only_and_exposes_no_secrets(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        b, order, gp = paid_booking(env, w)
        pid = order["payment"]["id"]
        for path in ("/admin/payments", f"/admin/payments/{pid}", "/admin/payments/summary"):
            assert env.api.get(f"{API}{path}", headers=w["customer_h"]).status_code == 403
            assert env.api.get(f"{API}{path}", headers=w["owner_h"]).status_code == 403
            assert env.api.get(f"{API}{path}").status_code == 401
        lst = env.api.get(f"{API}/admin/payments", headers=admin_h).json()
        assert (
            lst["items"][0]["razorpay_payment_id"] == gp.id
            and lst["items"][0]["booking_code"] == b["booking_code"]
        )
        detail = env.api.get(f"{API}/admin/payments/{pid}", headers=admin_h)
        assert detail.status_code == 200 and {e["source"] for e in detail.json()["events"]} >= {
            "system",
            "verify",
        }
        s = env.api.get(f"{API}/admin/payments/summary", headers=admin_h).json()
        assert s["gross_captured_paise"] == 50000 and s["captured_count"] == 1
        assert s["refunds"]["processed_paise"] == 0
        text = lst and detail.text + json.dumps(s)
        assert KEY_SECRET not in text and "gateway_refs" not in text
        assert (
            env.api.get(f"{API}/admin/payments", params={"status": "bogus"}, headers=admin_h).status_code
            == 422
        )
        assert env.api.get(f"{API}/admin/payments/{uuid.uuid4()}", headers=admin_h).status_code == 404


def test_admin_sees_failed_payments_and_review_queue(clean_db):
    w = seed_world(clean_db)
    admin_h = make_admin(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        post_webhook(
            env,
            *webhook("payment.failed", env.gw.customer_pays(order["checkout"]["order_id"], status="failed")),
        )
        failed = env.api.get(f"{API}/admin/payments", params={"status": "failed"}, headers=admin_h).json()[
            "items"
        ]
        assert len(failed) == 1 and failed[0]["failure_reason"]
        assert (
            env.api.get(f"{API}/admin/payments", params={"review_required": "true"}, headers=admin_h).json()[
                "items"
            ]
            == []
        )


def test_reconciliation_sweep_confirms_a_payment_whose_webhook_never_arrived(clean_db):
    from app.services.dispatch import sweep_once
    from tests.conftest import sql

    w = seed_world(clean_db)
    with payment_app(clean_db, payment_reconcile_after_minutes=1) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        env.gw.customer_pays(order["checkout"]["order_id"])
        sql(clean_db, "UPDATE public.payments SET created_at = now() - interval '5 minutes'")
        env.api.portal.call(sweep_once, env.api.app)
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "confirmed"
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "captured"
