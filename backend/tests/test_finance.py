"""Finance: versioned configuration, pricing, immutable ledger, commission/earnings maths, payouts, reconciliation."""

import json
import random

import asyncpg
import pytest

from app.domain.finance_math import Rules, customer_price, reversal, split_sale
from tests.admin_helpers import admin_with, audit_rows
from tests.booking_helpers import future_day, iso
from tests.conftest import sql
from tests.payment_helpers import (
    API,
    hold_booking,
    paid_booking,
    payment_app,
    post_webhook,
    refund_webhook,
    rows,
    seed_world,
)

A = f"{API}/admin"
CFG = {
    "platform_fee_bps": 500, "platform_fee_fixed_paise": 0, "tax_rate_bps": 1800, "tax_on": "base_and_fee",
    "commission_bps": 1000, "discount_borne_by": "platform", "notes": "test rules",
}  # fmt: skip


# ------------------------------------------------------------------ pure maths
def test_customer_price_follows_the_documented_example():
    r = Rules(500, 0, 1800, "base_and_fee", 1000, "platform")
    p = customer_price(40000, 0, r)
    assert (p.fee, p.tax, p.total) == (2000, 7560, 49560)  # 400 + 20 fee + 18% on 420
    assert (
        customer_price(40000, 0, Rules(500, 0, 1800, "fee", 0, "platform")).tax == 360
    )  # 18% on the fee only


def test_split_always_balances_and_refund_reversals_never_drift():
    rnd = random.Random(7)
    for _ in range(500):
        base = rnd.randint(100, 5_000_000)
        r = Rules(rnd.randint(0, 2000), rnd.randint(0, 5000), rnd.randint(0, 2800), rnd.choice(["fee", "base_and_fee"]),
                  rnd.randint(0, 3000), rnd.choice(["platform", "owner"]))  # fmt: skip
        disc = rnd.randint(0, base // 2)
        p = customer_price(base, disc, r)
        sp = split_sale(p.total, base, p.fee, p.tax, disc, r)
        assert sp.owner + sp.platform + sp.tax == sp.gross
        # any sequence of partial refunds adds up to exactly the sale at the end
        left, cum = p.total, 0
        prev = (0, 0, 0)
        while left > 0:
            x = min(left, rnd.randint(1, max(1, p.total // 3)))
            left -= x
            cum += x
            o, t, pl = reversal(sp.gross, sp.owner, sp.tax, cum)
            assert o + t + pl == cum
            prev = (o, t, pl)
        assert prev == (sp.owner, sp.tax, sp.platform)


# ------------------------------------------------------------------ configuration lifecycle
def test_config_is_a_draft_until_a_second_admin_approves_and_then_immutable(clean_db):
    a1, a2 = admin_with(clean_db), admin_with(clean_db)
    viewer = admin_with(clean_db, ["finance.view"])
    with payment_app(clean_db) as env:
        api = env.api
        assert api.post(f"{A}/finance/configs", json=CFG, headers=viewer["h"]).status_code == 403
        bad = api.post(f"{A}/finance/configs", json={**CFG, "commission_bps": 20000}, headers=a1["h"])
        assert bad.status_code == 422
        r = api.post(f"{A}/finance/configs", json=CFG, headers=a1["h"])
        assert r.status_code == 201 and r.json()["status"] == "draft"
        cid = r.json()["id"]
        # the finance summary says what is still undecided
        s = api.get(f"{A}/finance/summary", headers=a1["h"]).json()
        assert s["active_config"] is None and any("Q7/Q8" in d for d in s["decisions_needed"])
        assert s["payouts"]["automatic_gateway_payouts"] is False
        # four-eyes: the drafter cannot approve
        mine = api.post(f"{A}/finance/configs/{cid}/approve", json={"reason": "go live"}, headers=a1["h"])
        assert mine.status_code == 409 and mine.json()["code"] == "APPROVER_MUST_DIFFER"
        ok = api.post(
            f"{A}/finance/configs/{cid}/approve", json={"reason": "Client signed off v1"}, headers=a2["h"]
        )
        assert ok.status_code == 200 and ok.json()["status"] == "approved" and ok.json()["effective_from"]
        # immutable at the database level, and cannot be deleted
        with pytest.raises(asyncpg.exceptions.IntegrityConstraintViolationError):
            sql(clean_db, "UPDATE public.finance_configs SET commission_bps = 5 WHERE id = $1", cid)
        assert api.delete(f"{A}/finance/configs/{cid}", headers=a1["h"]).status_code == 409
        # a new version supersedes it
        c2 = api.post(f"{A}/finance/configs", json={**CFG, "commission_bps": 1500}, headers=a2["h"]).json()
        assert (
            api.post(
                f"{A}/finance/configs/{c2['id']}/approve", json={"reason": "version 2"}, headers=a1["h"]
            ).status_code
            == 200
        )
        cfgs = api.get(f"{A}/finance/configs", headers=a1["h"]).json()["items"]
        assert [(c["version"], c["status"]) for c in cfgs] == [(2, "approved"), (1, "retired")]
        meta = json.loads(audit_rows(clean_db, "admin.finance_config_approved")[0]["metadata"])
        assert (
            meta["before"]["status"] == "draft" and meta["after"]["status"] == "approved" and meta["reason"]
        )


def approve_config(api, a1, a2, **over):
    c = api.post(f"{A}/finance/configs", json={**CFG, **over}, headers=a1["h"]).json()
    r = api.post(f"{A}/finance/configs/{c['id']}/approve", json={"reason": "approved"}, headers=a2["h"])
    assert r.status_code == 200, r.text
    return r.json()


def test_prices_have_no_fees_until_a_config_is_approved_then_quote_and_booking_use_it(clean_db):
    a1, a2 = admin_with(clean_db), admin_with(clean_db)
    w = seed_world(clean_db, price=40000)
    with payment_app(clean_db) as env:
        api = env.api
        body = {"resource_id": str(w["resource"]), "starts_at": iso(future_day(), 9)}
        q = api.post(f"{API}/bookings/quote", json=body, headers=w["customer_h"]).json()
        assert (q["fees_paise"], q["tax_paise"], q["total_amount_paise"]) == (0, 0, 40000)
        approve_config(api, a1, a2)
        q = api.post(f"{API}/bookings/quote", json=body, headers=w["customer_h"]).json()
        assert (q["fees_paise"], q["tax_paise"], q["total_amount_paise"]) == (2000, 7560, 49560)
        b = hold_booking(env, w, hour=9)
        assert b["total_amount_paise"] == 49560 and b["price"]["finance_config_version"] == 1
        o = env.api.post(
            f"{API}/payments/create-order", json={"booking_id": b["id"]}, headers=w["customer_h"]
        ).json()
        assert o["checkout"]["amount_paise"] == 49560


# ------------------------------------------------------------------ ledger
def test_ledger_commission_earnings_and_refund_adjustments(clean_db):
    a1, a2 = admin_with(clean_db), admin_with(clean_db)
    w = seed_world(clean_db, price=40000)
    with payment_app(clean_db) as env:
        api = env.api
        # a payment captured BEFORE any approved rule gets no invented figures
        paid_booking(env, w, hour=7)
        assert api.get(f"{A}/finance/summary", headers=a1["h"]).json()["ledger"] is None
        assert (
            api.get(f"{A}/dashboard", headers=a1["h"]).json()["period"]["money"]["owner_earnings"][
                "available"
            ]
            is False
        )
        approve_config(api, a1, a2)
        b, _, gp = paid_booking(env, w, hour=9)  # captured under v1: 400 + 20 fee + 75.60 tax = 495.60
        acc = api.post(f"{A}/finance/accrue", headers=a1["h"]).json()
        assert acc["sales"] == 1  # the earlier payment predates the rule and stays out
        again = api.post(f"{A}/finance/accrue", headers=a1["h"]).json()
        assert again["sales"] == 0 and again["refunds"] == 0  # idempotent
        e = api.get(f"{A}/finance/ledger", headers=a1["h"]).json()["items"][0]
        # commission 10% of base 400 = 40; owner = 360; platform = fee 20 + commission 40 = 60; tax 75.60
        assert (e["owner_amount_paise"], e["platform_amount_paise"], e["tax_paise"], e["gross_paise"]) == (
            36000,
            6000,
            7560,
            49560,
        )
        assert e["commission_paise"] == 4000 and e["fee_paise"] == 2000
        s = api.get(f"{A}/finance/summary", headers=a1["h"]).json()
        assert (
            s["ledger"]["owner"] == 36000
            and s["ledger"]["platform"] == 6000
            and s["coverage"]["without_ledger_entry"] == 1
        )
        m = api.get(f"{A}/dashboard", headers=a1["h"]).json()["period"]["money"]
        assert m["owner_earnings"]["amount_paise"] == 36000 and m["platform_revenue"]["amount_paise"] == 6000
        assert m["tax_collected"]["amount_paise"] == 7560 and m["ledger_coverage"]["with_ledger_entry"] == 1
        # append-only ledger
        with pytest.raises(asyncpg.exceptions.IntegrityConstraintViolationError):
            sql(clean_db, "UPDATE public.ledger_entries SET owner_amount_paise = 1")
        with pytest.raises(asyncpg.exceptions.IntegrityConstraintViolationError):
            sql(clean_db, "DELETE FROM public.ledger_entries")
        # refunds reverse proportionally; two partials end exactly at zero
        api.put(f"{A}/settings/refunds_enabled", json={"value": True, "reason": "policy ok"}, headers=a1["h"])
        pid = str(
            rows(clean_db, "SELECT id FROM public.payments WHERE provider_payment_id=$1", gp.id)[0]["id"]
        )
        api.post(f"{A}/bookings/{b['id']}/cancel", json={"reason": "closure"}, headers=a1["h"])
        for i, amt in enumerate((20000, 29560)):
            r = api.post(
                f"{A}/payments/{pid}/refunds",
                json={"amount_paise": amt, "reason": "Venue closed"},
                headers={**a1["h"], "Idempotency-Key": f"ledger-key-{i:04d}"},
            ).json()
            done = env.gw.set_refund_status(r["provider_refund_id"], "processed")
            body, h = refund_webhook("refund.processed", done)
            assert post_webhook(env, body, h).status_code == 200
        acc = api.post(f"{A}/finance/accrue", headers=a1["h"]).json()
        assert acc["refunds"] == 2
        tot = rows(
            clean_db,
            "SELECT sum(gross_paise) g, sum(owner_amount_paise) o, sum(platform_amount_paise) p, sum(tax_paise) t "
            "FROM public.ledger_entries WHERE payment_id=$1",
            rows(clean_db, "SELECT id FROM public.payments WHERE provider_payment_id=$1", gp.id)[0]["id"],
        )[0]
        assert (tot["g"], tot["o"], tot["p"], tot["t"]) == (0, 0, 0, 0)
        assert (
            api.get(f"{A}/finance/ledger?kind=refund", headers=a1["h"]).json()["items"][0]["gross_paise"] < 0
        )


# ------------------------------------------------------------------ payouts
def test_payouts_stay_disabled_until_approved_then_follow_balance_kyc_and_four_eyes(clean_db):
    a1, a2 = admin_with(clean_db), admin_with(clean_db)
    w = seed_world(clean_db, price=40000)
    owner = str(w["owner"])
    with payment_app(clean_db) as env:
        api = env.api
        req = {"owner_id": owner, "amount_paise": 1000}
        off = api.post(f"{A}/payouts", json=req, headers=a1["h"])
        assert off.status_code == 409 and off.json()["code"] == "PAYOUTS_DISABLED"
        api.put(
            f"{A}/settings/payouts_enabled", json={"value": True, "reason": "Q10 approved"}, headers=a1["h"]
        )
        assert api.post(f"{A}/payouts", json=req, headers=a1["h"]).json()["code"] == "OWNER_KYC_REQUIRED"
        sql(clean_db, "UPDATE public.owner_profiles SET kyc_status='verified' WHERE user_id=$1", w["owner"])
        assert api.post(f"{A}/payouts", json=req, headers=a1["h"]).json()["code"] == "FINANCE_NOT_APPROVED"
        approve_config(api, a1, a2)
        paid_booking(env, w, hour=9)
        api.post(f"{A}/finance/accrue", headers=a1["h"])
        bal = api.get(f"{A}/finance/owners/{owner}/balance", headers=a1["h"]).json()
        assert bal["payable_paise"] == 36000
        too_much = api.post(f"{A}/payouts", json={**req, "amount_paise": 36001}, headers=a1["h"])
        assert too_much.status_code == 422 and too_much.json()["code"] == "AMOUNT_EXCEEDS_BALANCE"
        p = api.post(f"{A}/payouts", json={**req, "amount_paise": 30000}, headers=a1["h"])
        assert p.status_code == 201 and p.json()["status"] == "draft"
        pid = p.json()["id"]
        assert (
            api.get(f"{A}/finance/owners/{owner}/balance", headers=a1["h"]).json()["payable_paise"] == 6000
        )  # reserved
        assert (
            api.post(
                f"{A}/payouts/{pid}/paid", json={"method": "upi", "reference": "UTR123456"}, headers=a1["h"]
            ).json()["code"]
            == "PAYOUT_NOT_APPROVED"
        )
        assert (
            api.post(f"{A}/payouts/{pid}/approve", headers=a1["h"]).json()["code"] == "APPROVER_MUST_DIFFER"
        )
        assert api.post(f"{A}/payouts/{pid}/approve", headers=a2["h"]).status_code == 200
        assert (
            api.post(
                f"{A}/payouts/{pid}/paid", json={"method": "upi", "reference": "x"}, headers=a2["h"]
            ).status_code
            == 422
        )
        paid = api.post(
            f"{A}/payouts/{pid}/paid",
            json={"method": "bank_transfer", "reference": "UTR998877"},
            headers=a2["h"],
        )
        assert paid.status_code == 200 and paid.json()["status"] == "paid"
        assert (
            api.post(f"{A}/payouts/{pid}/cancel", json={"reason": "oops no"}, headers=a1["h"]).status_code
            == 409
        )
        hist = api.get(f"{A}/owners/{owner}/payouts", headers=a1["h"]).json()
        assert hist["balance"]["paid_paise"] == 30000 and hist["items"][0]["reference"] == "UTR998877"
        # cancelling a draft releases the reservation
        p2 = api.post(f"{A}/payouts", json={**req, "amount_paise": 6000}, headers=a1["h"]).json()
        assert (
            api.post(
                f"{A}/payouts/{p2['id']}/cancel", json={"reason": "wrong owner"}, headers=a2["h"]
            ).status_code
            == 200
        )
        assert api.get(f"{A}/finance/owners/{owner}/balance", headers=a1["h"]).json()["payable_paise"] == 6000
        meta = json.loads(audit_rows(clean_db, "admin.payout_paid")[0]["metadata"])
        assert meta["before"]["status"] == "approved" and meta["after"]["reference"] == "UTR998877"
        csv = api.get(f"{A}/exports/payouts.csv", headers=a1["h"])
        assert csv.status_code == 200 and "UTR998877" in csv.text
        # payout permission is separate from finance viewing
        viewer = admin_with(clean_db, ["finance.view"])
        assert api.post(f"{A}/payouts", json=req, headers=viewer["h"]).status_code == 403


# ------------------------------------------------------------------ reconciliation
def test_reconciliation_reports_every_kind_of_mismatch_and_never_fakes_a_gateway_check(clean_db):
    a1 = admin_with(clean_db)
    w = seed_world(clean_db, price=40000)
    today = str(future_day(0))
    with payment_app(clean_db) as env:
        api = env.api
        b1, _, gp1 = paid_booking(env, w, hour=9)
        b2, _, gp2 = paid_booking(env, w, hour=11)
        run_body = {"date_from": today, "date_to": today}
        clean = api.post(f"{A}/finance/reconciliation", json=run_body, headers=a1["h"]).json()
        assert clean["gateway_checked"] is True and clean["mismatch_count"] == 0
        # gateway disagrees on an amount, drops a payment, and has one we never recorded
        env.gw.payments[gp1.id] = type(gp1)(
            gp1.id, gp1.order_id, gp1.amount_paise + 500, gp1.currency, "captured", "upi", None, None
        )
        del env.gw.payments[gp2.id]
        from app.gateways.razorpay import GatewayPayment

        env.gw.payments["pay_stranger0000001"] = GatewayPayment(
            "pay_stranger0000001", "order_x", 7000, "INR", "captured", "upi", None, None
        )
        bad = api.post(f"{A}/finance/reconciliation", json=run_body, headers=a1["h"]).json()
        kinds = sorted(i["kind"] for i in bad["items"])
        assert kinds == ["amount_mismatch", "missing_in_database", "missing_in_gateway"]
        got = api.get(f"{A}/finance/reconciliation/{bad['id']}", headers=a1["h"]).json()
        assert got["mismatch_count"] == 3 and got["summary"]["db_captured"] == 2
        csv = api.get(f"{A}/exports/reconciliation/{bad['id']}.csv", headers=a1["h"])
        assert csv.status_code == 200 and "pay_stranger0000001" in csv.text
        # unreachable gateway: internal checks only, and it says so
        env.gw.unreachable = True
        down = api.post(f"{A}/finance/reconciliation", json=run_body, headers=a1["h"]).json()
        assert down["gateway_checked"] is False and "could not be reached" in down["gateway_note"]
        # internal drift is caught: payment marked refunded but no processed refund exists
        sql(clean_db, "UPDATE public.payments SET status='refunded' WHERE provider_payment_id=$1", gp1.id)
        env.gw.unreachable = False
        drift = api.post(f"{A}/finance/reconciliation", json=run_body, headers=a1["h"]).json()
        assert any(i["kind"] == "refund_mismatch" for i in drift["items"])
        assert (
            api.post(
                f"{A}/finance/reconciliation",
                json={"date_from": today, "date_to": "2000-01-01"},
                headers=a1["h"],
            ).status_code
            == 422
        )
        runs = api.get(f"{A}/finance/reconciliation", headers=a1["h"]).json()["items"]
        assert len(runs) == 4
