"""Refund workflow: switch, permissions, idempotency, partial/full, failure, timeout, webhooks, sync."""

import json

from tests.admin_helpers import admin_with, audit_rows
from tests.payment_helpers import (
    API,
    paid_booking,
    payment_app,
    post_webhook,
    refund_webhook,
    rows,
    seed_world,
)

A = f"{API}/admin"


def enable(env, admin, key="refunds_enabled", value=True):
    r = env.api.put(
        f"{A}/settings/{key}", json={"value": value, "reason": "policy approved"}, headers=admin["h"]
    )
    assert r.status_code == 200, r.text


def refund(env, admin, payment_id, *, amount=None, key="idem-key-0001", reason="Venue closed"):
    return env.api.post(
        f"{A}/payments/{payment_id}/refunds",
        json={"amount_paise": amount, "reason": reason},
        headers={**admin["h"], "Idempotency-Key": key},
    )


def setup(clean_db):
    w = seed_world(clean_db)
    admin = admin_with(clean_db)
    return w, admin


def payment_id(db):
    return str(rows(db, "SELECT id FROM public.payments")[0]["id"])


def cancel(env, admin, booking_id):
    r = env.api.post(
        f"{A}/bookings/{booking_id}/cancel", json={"reason": "Court flooded"}, headers=admin["h"]
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_refunds_are_off_by_default_and_nothing_reaches_the_gateway(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        r = refund(env, admin, payment_id(clean_db), amount=1000)
        assert r.status_code == 409 and r.json()["code"] == "REFUNDS_DISABLED"
        assert env.gw.refund_calls == 0
        assert rows(clean_db, "SELECT 1 FROM public.refunds") == []


def test_refund_needs_the_refund_permission_and_an_idempotency_key(clean_db):
    w, admin = setup(clean_db)
    viewer = admin_with(clean_db, ["payments.view"])
    norole = admin_with(clean_db, [])  # role with no permissions
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        r = refund(env, viewer, pid, amount=1000)
        assert r.status_code == 403 and r.json()["code"] == "PERMISSION_DENIED"
        assert refund(env, norole, pid, amount=1000).status_code == 403
        r = env.api.post(
            f"{A}/payments/{pid}/refunds", json={"amount_paise": 1000, "reason": "x y z"}, headers=admin["h"]
        )
        assert r.status_code == 422 and r.json()["code"] == "INVALID_IDEMPOTENCY_KEY"
        assert env.gw.refund_calls == 0


def test_partial_refunds_keep_booking_and_payment_in_step_until_fully_refunded(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        b, order, gp = paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        env.gw.refund_mode = "pending"
        r = refund(env, admin, pid, amount=10000, key="partial-key-1")
        assert r.status_code == 201, r.text
        first = r.json()
        assert first["status"] == "pending"
        # Processed by the gateway -> payment partially refunded, booking still confirmed.
        gr = env.gw.set_refund_status(first["provider_refund_id"], "processed")
        body, h = refund_webhook("refund.processed", gr)
        assert post_webhook(env, body, h).status_code == 200
        pay = rows(clean_db, "SELECT status, gateway_refs FROM public.payments")[0]
        bk = rows(clean_db, "SELECT status, payment_status FROM public.bookings")[0]
        assert pay["status"] == "partially_refunded" and bk["payment_status"] == "partially_refunded"
        assert bk["status"] == "confirmed"
        # Over-refunding is refused; the exact remainder is allowed.
        over = refund(env, admin, pid, amount=40001, key="partial-key-2")
        assert over.status_code == 422 and over.json()["code"] == "AMOUNT_EXCEEDS_REMAINING"
        # A full refund of a still-active booking is refused: cancel first.
        rest = refund(env, admin, pid, amount=None, key="partial-key-3")
        assert rest.status_code == 409 and rest.json()["code"] == "REFUND_REQUIRES_CANCELLATION"
        res = cancel(env, admin, b["id"])
        assert res["refund_decision_needed"] is True and res["payment_status"] == "partially_refunded"
        rest = refund(env, admin, pid, amount=None, key="partial-key-3")
        assert rest.status_code == 201 and rest.json()["amount_paise"] == 40000
        bk = rows(clean_db, "SELECT status FROM public.bookings")[0]
        assert bk["status"] == "refund_pending"  # accepted by the gateway -> follows the money
        gr2 = env.gw.set_refund_status(rest.json()["provider_refund_id"], "processed")
        body, h = refund_webhook("refund.processed", gr2)
        assert post_webhook(env, body, h).status_code == 200
        pay = rows(clean_db, "SELECT status FROM public.payments")[0]
        bk = rows(clean_db, "SELECT status, payment_status FROM public.bookings")[0]
        assert pay["status"] == "refunded" and (bk["status"], bk["payment_status"]) == (
            "refunded",
            "refunded",
        )
        total = rows(clean_db, "SELECT sum(amount_paise) s FROM public.refunds WHERE status='processed'")[0][
            "s"
        ]
        assert total == 50000
        # Everything went through the booking state machine, with who did it.
        hist = rows(
            clean_db, "SELECT to_status, actor_role FROM public.booking_status_history ORDER BY created_at"
        )
        assert [(x["to_status"], x["actor_role"]) for x in hist][-3:] == [
            ("cancelled_by_admin", "admin"),
            ("refund_pending", "admin"),
            ("refunded", "system"),
        ]
        again = refund(env, admin, pid, amount=1000, key="partial-key-9")
        assert again.status_code == 409 and again.json()["code"] == "ALREADY_REFUNDED"
        # Before/after audit
        a = audit_rows(clean_db, "admin.refund_requested")
        assert len(a) == 2
        meta = json.loads(a[0]["metadata"])
        assert meta["before"]["payment_status"] == "captured" and meta["after"]["amount_paise"] == 10000
        assert meta["reason"] == "Venue closed" and a[0]["request_id"] is not None


def test_same_idempotency_key_never_refunds_twice(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        r1 = refund(env, admin, pid, amount=5000, key="same-key-0001")
        r2 = refund(env, admin, pid, amount=5000, key="same-key-0001")
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]
        assert env.gw.refund_calls == 1
        assert len(rows(clean_db, "SELECT 1 FROM public.refunds")) == 1
        clash = refund(env, admin, pid, amount=6000, key="same-key-0001")
        assert clash.status_code == 409 and clash.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_gateway_rejection_is_recorded_as_failed_and_changes_nothing_else(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        b, _, _ = paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        env.gw.refund_mode = "reject"
        r = refund(env, admin, pid, amount=5000)
        assert r.status_code == 201 and r.json()["status"] == "failed"
        assert "refundable" in r.json()["failure_reason"]
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "captured"
        assert (
            rows(clean_db, "SELECT status, payment_status FROM public.bookings")[0]["payment_status"]
            == "paid"
        )
        # A failed refund frees the balance for a retry under a new key.
        env.gw.refund_mode = "pending"
        assert refund(env, admin, pid, amount=5000, key="retry-key-0002").status_code == 201


def test_timeout_is_uncertain_blocks_new_refunds_and_reconciles_safely(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        env.gw.refund_mode = "timeout_but_created"  # worst case: Razorpay DID create it
        r = refund(env, admin, pid, amount=5000, key="timeout-key-01")
        assert r.status_code == 201 and r.json()["status"] == "uncertain"
        rid = r.json()["id"]
        blocked = refund(env, admin, pid, amount=5000, key="timeout-key-02")
        assert blocked.status_code == 409 and blocked.json()["code"] == "REFUND_IN_FLIGHT"
        # Reconcile finds the gateway's refund by receipt: no second refund is created.
        rec = env.api.post(f"{A}/refunds/{rid}/reconcile", headers=admin["h"])
        assert rec.status_code == 200 and rec.json()["status"] == "pending"
        assert rec.json()["provider_refund_id"] in env.gw.refunds
        assert len(env.gw.refunds) == 1


def test_unreachable_timeout_without_creation_is_resent_by_reconcile(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        env.gw.refund_mode = "timeout"
        r = refund(env, admin, pid, amount=5000, key="lost-key-0001")
        assert r.json()["status"] == "uncertain" and env.gw.refunds == {}
        env.gw.refund_mode = "processed"
        rec = env.api.post(f"{A}/refunds/{r.json()['id']}/reconcile", headers=admin["h"])
        assert rec.json()["status"] == "processed"
        assert len(env.gw.refunds) == 1
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "partially_refunded"


def test_duplicate_and_out_of_order_refund_webhooks_are_harmless(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        env.gw.refund_mode = "pending"
        r = refund(env, admin, pid, amount=5000, key="order-key-0001").json()
        created = env.gw.refunds[r["provider_refund_id"]]
        done = env.gw.set_refund_status(created.id, "processed")
        body, h = refund_webhook("refund.processed", done, event_id="evt_processed_1")
        assert post_webhook(env, body, h).json()["outcome"] == "applied"
        assert post_webhook(env, body, h).json()["outcome"] == "duplicate"  # same event id
        # A late 'created' (pending) must not downgrade a processed refund.
        late_body, late_h = refund_webhook("refund.created", created, event_id="evt_created_late")
        post_webhook(env, late_body, late_h)
        # Same refund delivered again under a new event id: not counted twice.
        body2, h2 = refund_webhook("refund.processed", done, event_id="evt_processed_2")
        post_webhook(env, body2, h2)
        rf = rows(clean_db, "SELECT status FROM public.refunds")
        assert [x["status"] for x in rf] == ["processed"]
        assert rows(clean_db, "SELECT gateway_refs FROM public.payments")[0]["gateway_refs"] is not None
        pay = rows(clean_db, "SELECT status FROM public.payments")[0]
        assert pay["status"] == "partially_refunded"


def test_refund_made_in_the_razorpay_dashboard_is_mirrored(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        b, _, gp = paid_booking(env, w)
        from app.gateways.razorpay import GatewayRefund

        ext = GatewayRefund("rfnd_dashboard_0001", gp.id, 50000, "processed", None)
        body, h = refund_webhook("refund.processed", ext)
        assert post_webhook(env, body, h).status_code == 200
        row = rows(clean_db, "SELECT source, status, amount_paise FROM public.refunds")[0]
        assert (row["source"], row["status"], row["amount_paise"]) == ("gateway", "processed", 50000)
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "refunded"
        assert rows(clean_db, "SELECT payment_status FROM public.bookings")[0]["payment_status"] == "refunded"


def test_refund_failed_webhook_marks_refund_failed(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        r = refund(env, admin, pid, amount=5000, key="fail-key-00001").json()
        failed = env.gw.set_refund_status(r["provider_refund_id"], "failed")
        body, h = refund_webhook("refund.failed", failed)
        assert post_webhook(env, body, h).json()["outcome"] == "applied"
        got = env.api.get(f"{A}/refunds/{r['id']}", headers=admin["h"]).json()
        assert got["status"] == "failed" and got["failure_reason"]
        assert rows(clean_db, "SELECT status FROM public.payments")[0]["status"] == "captured"


def test_refund_history_filters_and_payment_detail(clean_db):
    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        refund(env, admin, pid, amount=5000, key="list-key-00001")
        lst = env.api.get(f"{A}/refunds?status=pending", headers=admin["h"]).json()
        assert len(lst["items"]) == 1 and lst["items"][0]["booking_code"]
        assert env.api.get(f"{A}/refunds?status=processed", headers=admin["h"]).json()["items"] == []
        det = env.api.get(f"{A}/payments/{pid}", headers=admin["h"]).json()
        assert det["refund_in_flight_paise"] == 5000 and len(det["refunds"]) == 1
        f = env.api.get(f"{A}/payments?refund_status=pending", headers=admin["h"]).json()
        assert len(f["items"]) == 1
        assert env.api.get(f"{A}/payments?refund_status=none", headers=admin["h"]).json()["items"] == []
        s = env.api.get(f"{A}/payments/summary", headers=admin["h"]).json()
        assert s["refunds"]["in_flight_count"] == 1


def test_payment_and_refund_reports_download_with_refund_figures(clean_db):
    import csv
    import io

    w, admin = setup(clean_db)
    with payment_app(clean_db) as env:
        b, _, gp = paid_booking(env, w)
        pid = payment_id(clean_db)
        enable(env, admin)
        env.api.post(f"{A}/bookings/{b['id']}/cancel", json={"reason": "Court flooded"}, headers=admin["h"])
        r = refund(env, admin, pid, amount=None, key="report-key-001").json()
        done = env.gw.set_refund_status(r["provider_refund_id"], "processed")
        body, h = refund_webhook("refund.processed", done)
        post_webhook(env, body, h)
        pay = list(
            csv.DictReader(io.StringIO(env.api.get(f"{A}/exports/payments.csv", headers=admin["h"]).text))
        )
        assert (
            pay[0]["refunded_paise"] == "50000"
            and pay[0]["status"] == "refunded"
            and pay[0]["razorpay_payment_id"] == gp.id
        )
        ref = env.api.get(f"{A}/exports/refunds.csv?status=processed", headers=admin["h"])
        rows_ = list(csv.DictReader(io.StringIO(ref.text)))
        assert ref.headers["content-disposition"].endswith('zuruv-refunds.csv"')
        assert len(rows_) == 1 and rows_[0]["amount_paise"] == "50000" and rows_[0]["status"] == "processed"
        assert (
            env.api.get(f"{A}/exports/refunds.csv?status=failed", headers=admin["h"]).text.count("\n") == 1
        )  # header only
        assert len(audit_rows(clean_db, "admin.export")) >= 3
