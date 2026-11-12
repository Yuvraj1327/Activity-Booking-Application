"""Step 7: device tokens, preferences, history/read state, push and email delivery."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.gateways.resend import EmailSendError
from app.services.dispatch import sweep_once
from tests.booking_helpers import API, new_customer, seed_world
from tests.conftest import auth_headers, seed_profile, sql
from tests.payment_helpers import (
    create_order,
    hold_booking,
    paid_booking,
    payment_app,
    post_webhook,
    rows,
    webhook,
)

TOKEN_A = "fcm-token-android-aaaaaaaaaaaaaaaa"
TOKEN_B = "fcm-token-android-bbbbbbbbbbbbbbbb"
DEV = f"{API}/devices/token"


def _register(env, headers, token=TOKEN_A, app="customer", platform="android"):
    return env.api.put(DEV, json={"token": token, "platform": platform, "app": app}, headers=headers)


# ------------------------------------------------------------------ device tokens
def test_token_registration_refresh_and_persistence(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        assert _register(env, w["customer_h"]).status_code == 204
        assert _register(env, w["customer_h"]).status_code == 204  # idempotent
        assert len(rows(clean_db, "SELECT 1 FROM public.user_device_tokens")) == 1
        # token refresh: the app now has a new token (old one is removed on sign-out/refresh)
        assert _register(env, w["customer_h"], token=TOKEN_B).status_code == 204
        assert len(rows(clean_db, "SELECT 1 FROM public.user_device_tokens")) == 2
        r = env.api.post(f"{DEV}/remove", json={"token": TOKEN_A}, headers=w["customer_h"])
        assert r.status_code == 204
        left = rows(clean_db, "SELECT token, platform, app FROM public.user_device_tokens")
        assert [(t["token"], t["platform"], t["app"]) for t in left] == [(TOKEN_B, "android", "customer")]


def test_token_moves_to_the_new_account_on_the_same_phone(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        _register(env, w["customer_h"])
        _register(env, w["owner_h"], app="owner")
        t = rows(clean_db, "SELECT user_id, app FROM public.user_device_tokens")
        assert len(t) == 1 and t[0]["user_id"] == w["owner"] and t[0]["app"] == "owner"
        # the previous user cannot remove someone else's token
        env.api.post(f"{DEV}/remove", json={"token": TOKEN_A}, headers=w["customer_h"])
        assert len(rows(clean_db, "SELECT 1 FROM public.user_device_tokens")) == 1


def test_token_validation_and_auth(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        assert (
            env.api.put(DEV, json={"token": TOKEN_A, "platform": "android", "app": "customer"}).status_code
            == 401
        )
        assert _register(env, w["customer_h"], token="short").status_code == 422
        assert _register(env, w["customer_h"], platform="symbian").status_code == 422
        r = env.api.put(
            DEV,
            json={"token": TOKEN_A, "platform": "ios", "app": "customer", "user_id": str(w["owner"])},
            headers=w["customer_h"],
        )
        assert r.status_code == 422  # a client can never register a token for another user


# ------------------------------------------------------------------ recipients, history and read state
def test_correct_recipients_for_a_verified_payment(clean_db):
    w = seed_world(clean_db)
    bystander, bystander_h = new_customer(clean_db)
    admin = seed_profile(clean_db, "admin")
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        cust = {
            n["type"] for n in env.api.get(f"{API}/notifications", headers=w["customer_h"]).json()["items"]
        }
        own = {n["type"] for n in env.api.get(f"{API}/notifications", headers=w["owner_h"]).json()["items"]}
        assert cust == {"booking.confirmed", "payment.received"}
        assert own == {"booking.created", "payment.received"}
        assert env.api.get(f"{API}/notifications", headers=bystander_h).json()["items"] == []
        assert (
            env.api.get(f"{API}/notifications", headers=auth_headers(admin, aal="aal2")).json()["items"] == []
        )
        # payload carries ids only
        raw = rows(clean_db, "SELECT data FROM public.notifications WHERE type='booking.confirmed'")[0][
            "data"
        ]
        data = json.loads(raw) if isinstance(raw, str) else raw
        assert set(data) <= {"booking_id", "payment_id"}


def test_read_unread_flow_and_isolation(clean_db):
    w = seed_world(clean_db)
    other, other_h = new_customer(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        h = w["customer_h"]
        assert env.api.get(f"{API}/notifications/unread-count", headers=h).json() == {"unread_count": 2}
        first = env.api.get(f"{API}/notifications", headers=h).json()["items"][0]
        assert env.api.post(f"{API}/notifications/{first['id']}/read", headers=other_h).status_code == 404
        assert env.api.post(f"{API}/notifications/{first['id']}/read", headers=h).status_code == 204
        assert env.api.get(f"{API}/notifications/unread-count", headers=h).json()["unread_count"] == 1
        only = env.api.get(f"{API}/notifications", params={"unread_only": "true"}, headers=h).json()["items"]
        assert len(only) == 1 and only[0]["is_read"] is False
        pay = env.api.get(f"{API}/notifications", params={"group": "payments"}, headers=h).json()["items"]
        assert [n["type"] for n in pay] == ["payment.received"]
        assert env.api.post(f"{API}/notifications/read-all", headers=h).status_code == 204
        assert env.api.get(f"{API}/notifications/unread-count", headers=h).json()["unread_count"] == 0
        assert (
            env.api.get(f"{API}/notifications/unread-count", headers=w["owner_h"]).json()["unread_count"] == 2
        )


def test_preferences_default_update_and_effect(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        h = w["customer_h"]
        assert env.api.get(f"{API}/notifications/preferences", headers=h).json() == {
            "push_enabled": True,
            "email_enabled": True,
        }
        r = env.api.put(f"{API}/notifications/preferences", json={"email_enabled": False}, headers=h)
        assert r.json() == {"push_enabled": True, "email_enabled": False}
        _register(env, h)
        paid_booking(env, w)
        # in-app + push yes, email no (customer opted out); owner still gets theirs
        assert {m.to for m, _ in env.mail.sent} == {
            rows(clean_db, "SELECT email FROM public.profiles WHERE id=$1", w["owner"])[0]["email"]
        }
        assert len(env.push.sent) == 2
        env.api.put(f"{API}/notifications/preferences", json={"push_enabled": False}, headers=h)
        before = len(env.push.sent)
        from tests.booking_helpers import future_day, iso

        b = env.api.post(
            f"{API}/bookings",
            json={"resource_id": str(w["resource"]), "starts_at": iso(future_day(), 12)},
            headers=h,
        ).json()
        order = create_order(env, b["id"], h).json()
        post_webhook(env, *webhook("payment.captured", env.gw.customer_pays(order["checkout"]["order_id"])))
        assert len(env.push.sent) == before
        assert (
            rows(
                clean_db,
                "SELECT push_status FROM public.notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 1",
                w["customer"],
            )[0]["push_status"]
            == "skipped"
        )


# ------------------------------------------------------------------ push delivery
def test_push_goes_to_the_right_devices_once(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        _register(env, w["customer_h"], token=TOKEN_A)
        _register(env, w["owner_h"], token=TOKEN_B, app="owner")
        b, order, gp = paid_booking(env, w)
        by_token: dict[str, list[str]] = {}
        for token, _title, data in env.push.sent:
            by_token.setdefault(token, []).append(data["type"])
        assert sorted(by_token[TOKEN_A]) == ["booking.confirmed", "payment.received"]
        assert sorted(by_token[TOKEN_B]) == ["booking.created", "payment.received"]
        payload = env.push.sent[0][2]
        assert (
            payload["booking_id"] == b["id"]
            and "amount" not in str(payload)
            and "secret" not in str(payload).lower()
        )
        # repeated webhooks never push again
        count = len(env.push.sent)
        body, hdr = webhook("payment.captured", gp)
        for _ in range(2):
            post_webhook(env, body, hdr)
        assert len(env.push.sent) == count


def test_invalid_tokens_are_removed_and_no_token_means_skipped(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        _register(env, w["customer_h"], token=TOKEN_A)
        env.push.invalid.add(TOKEN_A)
        paid_booking(env, w)
        assert rows(clean_db, "SELECT 1 FROM public.user_device_tokens") == []
        statuses = {
            r["push_status"]
            for r in rows(
                clean_db, "SELECT push_status FROM public.notifications WHERE user_id=$1", w["owner"]
            )
        }
        assert statuses == {"skipped"}  # owner had no device


def test_push_not_configured_never_blocks_the_payment(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        env.push.configured = False  # type: ignore[misc]
        _register(env, w["customer_h"])
        paid_booking(env, w)
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "confirmed"
        assert env.push.sent == []


# ------------------------------------------------------------------ email
def test_confirmation_emails_are_sent_once_with_escaped_content(clean_db):
    w = seed_world(clean_db)
    sql(clean_db, "UPDATE public.venues SET name = $1", "Ace <b>Arena</b>")
    with payment_app(clean_db) as env:
        b, _, gp = paid_booking(env, w)
        subjects = sorted(m.subject for m, _ in env.mail.sent)
        assert any(s.startswith("Booking confirmed") for s in subjects)
        assert any(s.startswith("Payment received") for s in subjects)
        assert any(s.startswith("New booking at") for s in subjects)
        assert len(env.mail.sent) == 3
        html = "".join(m.html for m, _ in env.mail.sent)
        assert "<b>Arena</b>" not in html and "&lt;b&gt;Arena&lt;/b&gt;" in html
        # repeated provider events do not produce more emails
        body, hdr = webhook("payment.captured", gp)
        post_webhook(env, body, hdr)
        post_webhook(env, body, hdr)
        post_webhook(env, *webhook("order.paid", gp))
        assert len(env.mail.sent) == 3
        d = rows(clean_db, "SELECT status, provider_message_id FROM public.email_deliveries")
        assert {r["status"] for r in d} == {"sent"} and all(r["provider_message_id"] for r in d)
        assert b["booking_code"] in env.mail.sent[0][0].text


def test_email_provider_failure_is_logged_retried_and_never_affects_payment(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        env.mail.fail = EmailSendError("Resend returned HTTP 503.", retryable=True)
        paid_booking(env, w)
        assert rows(clean_db, "SELECT status FROM public.bookings")[0]["status"] == "confirmed"
        d = rows(clean_db, "SELECT status, attempts, last_error FROM public.email_deliveries")
        assert {r["status"] for r in d} == {"queued"} and all(
            r["attempts"] == 1 and "503" in r["last_error"] for r in d
        )
        env.mail.fail = None
        env.api.portal.call(sweep_once, env.api.app)  # the background sweep retries
        d = rows(clean_db, "SELECT status, attempts FROM public.email_deliveries")
        assert {r["status"] for r in d} == {"sent"} and all(r["attempts"] == 2 for r in d)
        assert len(env.mail.sent) == 3


def test_non_retryable_email_error_marks_failed(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        env.mail.fail = EmailSendError("Resend returned HTTP 422.", retryable=False)
        paid_booking(env, w)
        d = rows(clean_db, "SELECT status FROM public.email_deliveries")
        assert {r["status"] for r in d} == {"failed"}


def test_email_not_configured_is_skipped_with_a_reason(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        env.mail.configured = False  # type: ignore[misc]
        paid_booking(env, w)
        d = rows(clean_db, "SELECT status, last_error FROM public.email_deliveries")
        assert {r["status"] for r in d} == {"skipped"} and all("not configured" in r["last_error"] for r in d)


def test_cancellation_notifies_customer_and_owner_once(clean_db):
    w = seed_world(clean_db)
    with payment_app(
        clean_db, booking_mode="instant", booking_hold_minutes="", cancellation_min_notice_hours=1
    ) as env:
        b = hold_booking(env, w)
        r = env.api.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=w["customer_h"])
        assert r.status_code == 200, r.text
        env.api.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=w["customer_h"])  # second attempt
        for h in (w["customer_h"], w["owner_h"]):
            types = [n["type"] for n in env.api.get(f"{API}/notifications", headers=h).json()["items"]]
            assert types.count("booking.cancelled") == 1
        subjects = [m.subject for m, _ in env.mail.sent]
        assert sum(s.startswith("Booking cancelled") for s in subjects) == 2


# ------------------------------------------------------------------ concurrency
def test_concurrent_duplicate_webhooks_apply_exactly_once(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        body, hdr = webhook("payment.captured", gp)
        with ThreadPoolExecutor(6) as pool:
            results = list(pool.map(lambda _: post_webhook(env, body, hdr), range(6)))
        assert all(r.status_code == 200 for r in results)
        outcomes = sorted(r.json()["outcome"] for r in results)
        assert outcomes.count("applied") == 1 and outcomes.count("duplicate") == 5
        assert (
            len(rows(clean_db, "SELECT 1 FROM public.booking_status_history WHERE to_status='confirmed'"))
            == 1
        )
        assert len(rows(clean_db, "SELECT 1 FROM public.notifications WHERE type='booking.confirmed'")) == 1
        assert len(rows(clean_db, "SELECT 1 FROM public.email_deliveries")) == 3


def test_concurrent_verify_and_webhook_apply_exactly_once(clean_db):
    from tests.payment_helpers import sign_checkout

    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = hold_booking(env, w)
        order = create_order(env, b["id"], w["customer_h"]).json()
        gp = env.gw.customer_pays(order["checkout"]["order_id"])
        body, hdr = webhook("payment.captured", gp)
        verify = {
            "razorpay_order_id": gp.order_id,
            "razorpay_payment_id": gp.id,
            "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
        }

        def go(i: int):
            if i % 2:
                return post_webhook(env, body, hdr)
            return env.api.post(f"{API}/payments/verify", json=verify, headers=w["customer_h"])

        with ThreadPoolExecutor(6) as pool:
            results = list(pool.map(go, range(6)))
        assert all(r.status_code == 200 for r in results)
        assert (
            len(rows(clean_db, "SELECT 1 FROM public.booking_status_history WHERE to_status='confirmed'"))
            == 1
        )
        assert len(rows(clean_db, "SELECT 1 FROM public.notifications WHERE type='booking.confirmed'")) == 1


def test_unknown_uuid_notification_is_404(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        r = env.api.post(f"{API}/notifications/{uuid.uuid4()}/read", headers=w["customer_h"])
        assert r.status_code == 404
