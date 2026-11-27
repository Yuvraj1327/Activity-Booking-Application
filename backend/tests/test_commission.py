"""Commission management: rules, priority, snapshots, ledger integration, owner earnings, reports, authorization."""

import json
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from app.domain import commission as dom
from app.domain.finance_math import mul_bps
from tests.admin_helpers import admin_with, audit_rows
from tests.conftest import auth_headers, seed_profile, sql
from tests.payment_helpers import (
    API,
    create_order,
    hold_booking,
    paid_booking,
    payment_app,
    post_webhook,
    refund_webhook,
    rows,
    seed_world,
    webhook,
)
from tests.test_finance import CFG, approve_config

A = f"{API}/admin"
C = f"{A}/commission"


# ------------------------------------------------------------------ helpers
def cand(scope, bps, *, active=True, slug="x"):
    return dom.Candidate(scope, f"{scope}-{slug}", "v", 1, bps, active, category_slug=slug)


def mk_rule(api, h, scope="global", bps=1000, *, expect=201, **extra):
    body = {"scope": scope, "commission_bps": bps, "reason": "initial setup", **extra}
    r = api.post(f"{C}/rules", json=body, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def change(api, h, rule_id, *, expect=201, **body):
    r = api.post(f"{C}/rules/{rule_id}/versions", json={"reason": "business decision", **body}, headers=h)
    assert r.status_code == expect, r.text
    return r.json()


def category_of(db, venue):
    return sql(db, "SELECT category_id FROM public.venue_categories WHERE venue_id=$1", venue)[0][
        "category_id"
    ]


def snapshot(db, booking_id):
    return sql(db, "SELECT * FROM public.booking_commission_snapshots WHERE booking_id=$1", booking_id)


def sale_entry(db, booking_id):
    return sql(db, "SELECT * FROM public.ledger_entries WHERE booking_id=$1 AND kind='sale'", booking_id)[0]


def setup(db):
    a1, a2 = admin_with(db), admin_with(db)
    w = seed_world(db, price=40000)
    return a1, a2, w


# ------------------------------------------------------------------ pure priority
def test_priority_venue_beats_activity_beats_global_and_exactly_one_rule_is_chosen():
    g, a, v = cand("global", 1000), cand("activity", 1200, slug="cricket"), cand("venue", 1500)
    assert dom.pick([g]).bps == 1000  # global only
    assert dom.pick([g, a]).bps == 1200  # activity overrides global
    assert dom.pick([g, v]).bps == 1500  # venue overrides global
    assert dom.pick([g, a, v]).bps == 1500  # all three overlap: venue wins, never a blend
    assert (
        dom.pick([g, a, cand("venue", 1500, active=False)]).bps == 1200
    )  # a deactivated venue rule is skipped
    assert dom.pick([cand("global", 1000, active=False)]) is None
    assert dom.pick([]) is None


def test_competing_activity_rules_are_never_guessed_without_an_approved_tiebreak():
    a1, a2 = cand("activity", 1500, slug="cricket"), cand("activity", 900, slug="tennis")
    g = cand("global", 1000)
    # no tie-break approved: nothing is chosen and the global rule is NOT silently used instead
    assert dom.resolve([a1, a2, g]) == (None, True)
    assert dom.pick([a1, a2, g]) is None
    # a venue rule still wins first, so there is nothing ambiguous to decide
    assert dom.resolve([a1, a2, g, cand("venue", 1200)])[0].bps == 1200
    # the same percentage twice is not a conflict
    assert dom.resolve([a1, cand("activity", 1500, slug="tennis")])[1] is False
    # once the client approves a tie-break it is applied, independent of input order
    assert dom.pick([a1, a2], activity_tiebreak="lowest").bps == 900
    assert dom.pick([a2, a1], activity_tiebreak="lowest").bps == 900
    assert dom.pick([a1, a2], activity_tiebreak="highest").bps == 1500
    # the priority is configurable in the architecture, but only as an unambiguous permutation
    assert dom.pick([cand("global", 1000), cand("activity", 1200), cand("venue", 1500)],
                    ("global", "activity", "venue")).bps == 1000  # fmt: skip
    for bad in (("venue", "venue", "global"), ("venue", "activity"), ("venue", "activity", "global", "x")):
        with pytest.raises(ValueError):
            dom.validate_priority(bad)


def test_two_sports_with_different_rates_block_accrual_until_the_client_decides(clean_db):
    a1, a2, w = setup(clean_db)
    cat1 = category_of(clean_db, w["venue"])
    cat2 = sql(clean_db, "INSERT INTO public.categories (slug, name) VALUES ('tennis-x','Tennis') RETURNING id")[0]["id"]
    sql(clean_db, "INSERT INTO public.venue_categories (venue_id, category_id) VALUES ($1,$2)", w["venue"], cat2)
    with payment_app(clean_db) as env:  # COMMISSION_ACTIVITY_TIEBREAK is unset
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2, commission_bps=1000)
        mk_rule(api, h, "global", 1000)
        mk_rule(api, h, "activity", 1500, category_id=str(cat1))
        mk_rule(api, h, "activity", 900, category_id=str(cat2))
        rules = api.get(f"{C}/rules", headers=h).json()
        assert rules["activity_tiebreak"] is None and [v["venue_id"] for v in rules["ambiguous_venues"]] == [str(w["venue"])]
        calc = api.get(f"{C}/calculate?venue_id={w['venue']}&base_paise=40000", headers=h).json()
        assert calc["ambiguous"] is True and calc["commission_bps"] is None
        b, _, _ = paid_booking(env, w, hour=9)
        s = snapshot(clean_db, b["id"])[0]
        assert s["ambiguous"] is True and s["scope"] == "none" and s["commission_bps"] is None
        out = api.post(f"{A}/finance/accrue", headers=h).json()
        assert out["sales"] == 0 and out["blocked_ambiguous_commission"] == 1
        assert rows(clean_db, "SELECT count(*) n FROM public.ledger_entries")[0]["n"] == 0
        # a venue-specific rule resolves the conflict for that venue (new bookings)
        mk_rule(api, h, "venue", 1200, venue_id=str(w["venue"]))
        assert api.get(f"{C}/rules", headers=h).json()["ambiguous_venues"] == []
        b2, _, _ = paid_booking(env, w, hour=11)
        assert snapshot(clean_db, b2["id"])[0]["commission_bps"] == 1200
        # the earlier booking stays blocked: its snapshot is immutable and no rate was ever chosen for it
        api.post(f"{A}/finance/accrue", headers=h)
        assert rows(clean_db, "SELECT count(*) n FROM public.ledger_entries WHERE booking_id=$1", b["id"])[0]["n"] == 0


def test_an_approved_tiebreak_setting_is_applied_and_recorded(clean_db):
    a1, a2, w = setup(clean_db)
    cat1 = category_of(clean_db, w["venue"])
    cat2 = sql(clean_db, "INSERT INTO public.categories (slug, name) VALUES ('tennis-y','Tennis') RETURNING id")[0]["id"]
    sql(clean_db, "INSERT INTO public.venue_categories (venue_id, category_id) VALUES ($1,$2)", w["venue"], cat2)
    with payment_app(clean_db, commission_activity_tiebreak="lowest") as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2)
        mk_rule(api, h, "activity", 1500, category_id=str(cat1))
        mk_rule(api, h, "activity", 900, category_id=str(cat2))
        b, _, _ = paid_booking(env, w, hour=9)
        s = snapshot(clean_db, b["id"])[0]
        assert (s["ambiguous"], s["commission_bps"], s["scope"]) == (False, 900, "activity")
        assert api.post(f"{A}/finance/accrue", headers=h).json()["sales"] == 1


def test_commission_amount_is_integer_paise_half_up():
    assert dom.commission_paise(10001, 1250) == 1250  # 1250.125 -> 1250
    assert dom.commission_paise(10005, 1250) == 1251  # 1250.625 -> 1251
    assert dom.commission_paise(1, 5000) == 1  # 0.5 -> 1 (half up)
    assert mul_bps(40000, 1000) == 4000


# ------------------------------------------------------------------ rule management API
def test_global_rule_lifecycle_versions_history_and_audit(clean_db):
    a1, _, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api = env.api
        empty = api.get(f"{C}/active", headers=a1["h"]).json()
        assert empty["global"] is None and empty["priority"] == ["venue", "activity", "global"]
        r = mk_rule(api, a1["h"], bps=1000)
        assert r["scope"] == "global" and r["current"]["commission_pct"] == "10%" and r["is_active_now"]
        mk_rule(api, a1["h"], expect=409)  # only one global rule
        v2 = change(api, a1["h"], r["id"], commission_bps=1250)
        assert v2["current"]["version"] == 2 and v2["current"]["previous_bps"] == 1000
        assert v2["current"]["commission_pct"] == "12.5%"
        v3 = change(api, a1["h"], r["id"], is_active=False)
        assert v3["is_active_now"] is False and v3["current"]["commission_bps"] == 1250
        change(api, a1["h"], r["id"], expect=422, is_active=False)  # nothing changes
        assert (
            api.post(f"{C}/rules/{r['id']}/versions", json={"reason": "x y z"}, headers=a1["h"]).status_code
            == 422
        )
        change(api, a1["h"], r["id"], is_active=True)
        act = api.get(f"{C}/active", headers=a1["h"]).json()
        assert act["global"]["commission_bps"] == 1250 and act["global"]["version"] == 4
        # history: newest first, with previous percentage, admin, reason and the end of each version
        h = api.get(f"{C}/history", headers=a1["h"]).json()["items"]
        assert [x["version"] for x in h] == [4, 3, 2, 1]
        assert h[3]["effective_to"] == h[2]["effective_from"] and h[0]["effective_to"] is None
        assert h[2]["previous_bps"] == 1000 and h[2]["commission_bps"] == 1250
        assert h[0]["changed_by"] == str(a1["id"]) and h[0]["reason"] == "business decision"
        assert api.get(f"{C}/history?scope=venue", headers=a1["h"]).json()["items"] == []
        assert len(api.get(f"{C}/history?scope=global", headers=a1["h"]).json()["items"]) == 4
        tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
        assert api.get(f"{C}/history?from={tomorrow}", headers=a1["h"]).json()["items"] == []
        meta = json.loads(audit_rows(clean_db, "admin.commission_rule_changed")[0]["metadata"])
        assert (
            meta["before"]["commission_bps"] == 1000
            and meta["after"]["commission_bps"] == 1250
            and meta["reason"]
        )
        assert len(audit_rows(clean_db, "admin.commission_rule_created")) == 1
        # history is immutable in the database itself
        for stmt in ("UPDATE public.commission_rule_versions SET commission_bps = 1",
                     "DELETE FROM public.commission_rule_versions",
                     "UPDATE public.commission_rules SET scope = 'global'",
                     "DELETE FROM public.commission_rules"):  # fmt: skip
            with pytest.raises(asyncpg.exceptions.IntegrityConstraintViolationError):
                sql(clean_db, stmt)


def test_activity_and_venue_rules_validate_targets_and_filter_history(clean_db):
    a1, _, w = setup(clean_db)
    cat = category_of(clean_db, w["venue"])
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        bad = [
            {"scope": "activity"}, {"scope": "venue"}, {"scope": "global", "venue_id": str(w["venue"])},
            {"scope": "activity", "category_id": str(cat), "venue_id": str(w["venue"])},
            {"scope": "global", "commission_bps": 10001}, {"scope": "global", "commission_bps": -1},
        ]  # fmt: skip
        for b in bad:
            r = api.post(
                f"{C}/rules", json={"commission_bps": 1000, "reason": "valid reason", **b}, headers=h
            )
            assert r.status_code == 422, (b, r.text)
        unknown = "00000000-0000-0000-0000-000000000001"
        mk_rule(api, h, "activity", category_id=unknown, expect=404)
        mk_rule(api, h, "venue", venue_id=unknown, expect=404)
        mk_rule(api, h, "global", 1000)
        act = mk_rule(api, h, "activity", 1200, category_id=str(cat))
        ven = mk_rule(api, h, "venue", 1500, venue_id=str(w["venue"]))
        assert act["category_name"] == "Cricket" and ven["venue_name"] == "Ace Arena"
        mk_rule(api, h, "venue", 1600, venue_id=str(w["venue"]), expect=409)  # one rule per target
        assert len(api.get(f"{C}/rules?scope=venue", headers=h).json()["items"]) == 1
        assert len(api.get(f"{C}/rules?q=ace", headers=h).json()["items"]) == 1
        assert api.get(f"{C}/rules?q=zzz", headers=h).json()["items"] == []
        change(api, h, ven["id"], is_active=False)
        assert api.get(f"{C}/rules?active_only=true", headers=h).json()["items"][0]["scope"] == "activity"
        for q, n in (
            (f"venue_id={w['venue']}", 2),
            (f"category_id={cat}", 1),
            ("scope=activity", 1),
            ("", 4),
        ):
            assert len(api.get(f"{C}/history?{q}", headers=h).json()["items"]) == n, q


def test_changes_cannot_be_back_dated_and_future_versions_apply_only_when_effective(clean_db):
    a1, _, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        r = mk_rule(api, h, bps=1000)
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        change(api, h, r["id"], expect=422, commission_bps=2000, effective_from=past)
        naive = (datetime.now(UTC) + timedelta(days=1)).replace(tzinfo=None).isoformat()
        change(api, h, r["id"], expect=422, commission_bps=2000, effective_from=naive)
        soon = datetime.now(UTC) + timedelta(days=2)
        out = change(api, h, r["id"], commission_bps=2000, effective_from=soon.isoformat())
        assert out["current"]["commission_bps"] == 1000 and out["pending"][0]["commission_bps"] == 2000
        calc = lambda at=None: api.get(  # noqa: E731
            f"{C}/calculate?venue_id={w['venue']}&base_paise=40000" + (f"&at={at}" if at else ""), headers=h
        ).json()
        assert calc()["commission_bps"] == 1000 and calc()["commission_paise"] == 4000
        later = (soon + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        assert calc(later)["commission_bps"] == 2000 and calc(later)["commission_paise"] == 8000
        assert calc(later)["owner_net_paise"] == 32000
        # a booking made now still gets the OLD rate; the future one does not leak backwards
        b = hold_booking(env, w, hour=9)
        assert snapshot(clean_db, b["id"])[0]["commission_bps"] == 1000


def test_no_rule_means_no_percentage_and_the_calculation_says_so(clean_db):
    a1, _, w = setup(clean_db)
    with payment_app(clean_db) as env:
        c = env.api.get(f"{C}/calculate?venue_id={w['venue']}&base_paise=40000", headers=a1["h"]).json()
        assert c["scope"] == "none" and c["commission_bps"] is None and c["commission_paise"] is None
        assert (
            env.api.get(f"{C}/calculate?venue_id={w['venue']}&base_paise=-5", headers=a1["h"]).status_code
            == 422
        )


# ------------------------------------------------------------------ snapshots + ledger
def test_global_rule_snapshot_ledger_and_booking_detail(clean_db):
    a1, a2, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2, commission_bps=500)  # the finance config percentage is only a fallback
        rule = mk_rule(api, h, bps=1000)
        b, _, gp = paid_booking(env, w, hour=9)
        s = snapshot(clean_db, b["id"])[0]
        assert (s["scope"], s["commission_bps"], s["rule_version"], str(s["rule_id"])) == (
            "global",
            1000,
            1,
            rule["id"],
        )
        assert api.post(f"{A}/finance/accrue", headers=h).json()["sales"] == 1
        e = sale_entry(clean_db, b["id"])
        # 10% of the 400.00 slot price; fee and tax are not part of the commission base
        assert (e["commission_bps"], e["commission_scope"], e["commission_rule_version"]) == (
            1000,
            "global",
            1,
        )
        assert (e["commission_base_paise"], e["commission_paise"], e["owner_amount_paise"]) == (
            40000,
            4000,
            36000,
        )
        assert str(e["commission_rule_id"]) == rule["id"]
        d = api.get(f"{C}/bookings/{b['id']}", headers=h).json()
        assert d["snapshot"]["scope"] == "global" and d["snapshot"]["commission_pct"] == "10%"
        assert d["calculation"]["commission_paise"] == 4000 and d["net"]["owner_net_paise"] == 36000
        assert d["snapshot"]["candidates"][0]["selected"] is True
        assert api.get(f"{C}/bookings/{b['id']}", headers=a1["h"]).status_code == 200
        assert api.get(f"{C}/bookings/00000000-0000-0000-0000-000000000009", headers=h).status_code == 404
        # snapshots cannot be rewritten
        for stmt in ("UPDATE public.booking_commission_snapshots SET commission_bps = 1",
                     "DELETE FROM public.booking_commission_snapshots"):  # fmt: skip
            with pytest.raises(asyncpg.exceptions.IntegrityConstraintViolationError):
                sql(clean_db, stmt)


def test_all_three_rules_overlap_and_history_is_not_rewritten_by_later_edits(clean_db):
    a1, a2, w = setup(clean_db)
    cat = category_of(clean_db, w["venue"])
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2)
        g = mk_rule(api, h, "global", 1000)
        a = mk_rule(api, h, "activity", 1200, category_id=str(cat))
        v = mk_rule(api, h, "venue", 1500, venue_id=str(w["venue"]))
        calc = api.get(f"{C}/calculate?venue_id={w['venue']}&base_paise=40000", headers=h).json()
        assert calc["scope"] == "venue" and calc["commission_paise"] == 6000
        assert [c["scope"] for c in calc["candidates"]] == ["venue", "activity", "global"]
        assert [c["selected"] for c in calc["candidates"]] == [True, False, False]
        b1, _, _ = paid_booking(env, w, hour=9)  # venue rule 15%
        api.post(f"{A}/finance/accrue", headers=h)
        before = dict(sale_entry(clean_db, b1["id"]))
        # deactivate the venue rule: new bookings fall to the activity rule
        change(api, h, v["id"], is_active=False)
        b2, _, _ = paid_booking(env, w, hour=11)
        assert snapshot(clean_db, b2["id"])[0]["scope"] == "activity"
        # deactivate the activity rule too, then edit global: new bookings use the new global rate
        change(api, h, a["id"], is_active=False)
        change(api, h, g["id"], commission_bps=2000)
        b3, _, _ = paid_booking(env, w, hour=13)
        assert (
            snapshot(clean_db, b3["id"])[0]["scope"],
            snapshot(clean_db, b3["id"])[0]["commission_bps"],
        ) == ("global", 2000)
        api.post(f"{A}/finance/accrue", headers=h)
        assert sale_entry(clean_db, b2["id"])["commission_paise"] == 4800  # 12% of 400.00
        assert sale_entry(clean_db, b3["id"])["commission_paise"] == 8000  # 20%
        # b1 is exactly as it was: no recalculation after three rule changes
        assert dict(sale_entry(clean_db, b1["id"])) == before and before["commission_paise"] == 6000
        assert snapshot(clean_db, b1["id"])[0]["commission_bps"] == 1500
        # re-running accrual changes nothing
        assert api.post(f"{A}/finance/accrue", headers=h).json()["sales"] == 0


def test_rule_edited_between_booking_and_payment_keeps_the_booking_time_rate(clean_db):
    a1, a2, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2)
        g = mk_rule(api, h, bps=1000)
        b = hold_booking(env, w, hour=9)  # snapshot: 10%
        change(api, h, g["id"], commission_bps=3000)  # admin edits before the customer pays
        order = create_order(env, b["id"], w["customer_h"]).json()
        env.gw.customer_pays(order["checkout"]["order_id"])
        gp = env.gw.customer_pays  # noqa: F841  (payment is captured through the verify path below)
        from tests.payment_helpers import sign_checkout

        pay = list(env.gw.payments.values())[-1]
        assert env.api.post(f"{API}/payments/verify", json={"razorpay_order_id": pay.order_id, "razorpay_payment_id": pay.id,
                            "razorpay_signature": sign_checkout(pay.order_id, pay.id)}, headers=w["customer_h"]).status_code == 200  # fmt: skip
        api.post(f"{A}/finance/accrue", headers=h)
        assert sale_entry(clean_db, b["id"])["commission_paise"] == 4000  # 10%, not 30%
        # a payment retry (second order for the same booking) does not create a second snapshot
        assert len(snapshot(clean_db, b["id"])) == 1


def test_unpaid_and_failed_bookings_earn_no_commission_and_missing_snapshot_is_backfilled_as_of_booking_time(
    clean_db,
):
    a1, a2, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2)
        g = mk_rule(api, h, bps=1000)
        unpaid = hold_booking(env, w, hour=9)
        failed = hold_booking(env, w, hour=11)
        order = create_order(env, failed["id"], w["customer_h"]).json()
        bad = env.gw.customer_pays(order["checkout"]["order_id"], status="failed")
        assert post_webhook(env, *webhook("payment.failed", bad)).json()["outcome"] == "applied"
        assert api.post(f"{A}/finance/accrue", headers=h).json()["sales"] == 0
        assert rows(clean_db, "SELECT count(*) n FROM public.ledger_entries")[0]["n"] == 0
        assert api.get(f"{C}/bookings/{unpaid['id']}", headers=h).json()["calculation"] is None
        # a booking that has no snapshot (made before this feature) is resolved as of its CREATION time
        paid, _, _ = paid_booking(env, w, hour=13)
        sql(clean_db, "ALTER TABLE public.booking_commission_snapshots DISABLE TRIGGER USER")
        sql(clean_db, "DELETE FROM public.booking_commission_snapshots WHERE booking_id=$1", paid["id"])
        sql(clean_db, "ALTER TABLE public.booking_commission_snapshots ENABLE TRIGGER USER")
        change(api, h, g["id"], commission_bps=9000)
        api.post(f"{A}/finance/accrue", headers=h)
        e = sale_entry(clean_db, paid["id"])
        assert (
            e["commission_paise"] == 4000
            and snapshot(clean_db, paid["id"])[0]["source"] == "accrual_backfill"
        )


def test_duplicate_webhooks_and_repeated_accrual_never_double_count(clean_db):
    a1, a2, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2)
        mk_rule(api, h, bps=1000)
        b, _, gp = paid_booking(env, w, hour=9)
        evt = webhook("payment.captured", gp, event_id="evt_dup_commission_1")
        for _ in range(3):
            assert post_webhook(env, *evt).status_code == 200  # the same event, delivered again and again
        assert (
            post_webhook(env, *webhook("payment.captured", gp)).status_code == 200
        )  # a new event id, same payment
        for _ in range(3):
            api.post(f"{A}/finance/accrue", headers=h)
        n = rows(clean_db, "SELECT count(*) n FROM public.ledger_entries WHERE booking_id=$1", b["id"])[0][
            "n"
        ]
        assert n == 1 and len(snapshot(clean_db, b["id"])) == 1
        # the database allows ONE payment per booking (retries reuse it), so a second one cannot even exist
        pay = rows(clean_db, "SELECT * FROM public.payments WHERE booking_id=$1", b["id"])[0]
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            sql(clean_db, "INSERT INTO public.payments (booking_id, customer_id, venue_id, provider, provider_order_id, "
                "provider_payment_id, amount_paise, currency, status, captured_at) SELECT booking_id, customer_id, venue_id, "
                "provider, 'order_dup', 'pay_dup', amount_paise, currency, 'captured', now() FROM public.payments WHERE id=$1", pay["id"])  # fmt: skip
        rep = api.get(f"{C}/report", headers=h).json()
        assert rep["totals"]["net_commission_paise"] == 4000 and rep["totals"]["bookings"] == 1


def test_refunds_reverse_commission_proportionally_and_totals_are_not_double_counted(clean_db):
    a1, a2, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2)
        mk_rule(api, h, bps=1000)
        b, _, gp = paid_booking(env, w, hour=9)  # customer paid 495.60; commission 40.00; owner 360.00
        api.post(f"{A}/finance/accrue", headers=h)
        api.put(f"{A}/settings/refunds_enabled", json={"value": True, "reason": "policy ok"}, headers=h)
        pid = str(
            rows(clean_db, "SELECT id FROM public.payments WHERE provider_payment_id=$1", gp.id)[0]["id"]
        )
        api.post(f"{A}/bookings/{b['id']}/cancel", json={"reason": "closure"}, headers=h)

        def refund(amount, key):
            r = api.post(f"{A}/payments/{pid}/refunds", json={"amount_paise": amount, "reason": "Venue closed"},
                         headers={**h, "Idempotency-Key": key}).json()  # fmt: skip
            done = env.gw.set_refund_status(r["provider_refund_id"], "processed")
            body, hd = refund_webhook("refund.processed", done)
            assert post_webhook(env, body, hd).status_code == 200
            assert post_webhook(env, body, hd).status_code == 200  # webhook delivered twice
            api.post(f"{A}/finance/accrue", headers=h)

        refund(24780, "commission-refund-1")  # exactly half
        rep = api.get(f"{C}/report", headers=h).json()["totals"]
        assert rep["sales_gross_paise"] == 49560 and rep["refunded_gross_paise"] == 24780
        assert (
            rep["commission_accrued_paise"],
            rep["commission_reversed_paise"],
            rep["net_commission_paise"],
        ) == (4000, 2000, 2000)
        assert rep["owner_net_paise"] == 18000
        d = api.get(f"{C}/bookings/{b['id']}", headers=h).json()
        assert d["net"]["refunded_paise"] == 24780 and d["net"]["commission_paise"] == 2000
        refund(24780, "commission-refund-2")
        rep = api.get(f"{C}/report", headers=h).json()["totals"]
        assert (rep["net_commission_paise"], rep["owner_net_paise"], rep["net_gross_paise"]) == (0, 0, 0)
        assert rows(clean_db, "SELECT count(*) n FROM public.ledger_entries WHERE kind='refund'")[0]["n"] == 2
        refund_entry = rows(clean_db, "SELECT * FROM public.ledger_entries WHERE kind='refund' LIMIT 1")[0]
        assert refund_entry["commission_bps"] == 1000 and refund_entry["commission_scope"] == "global"


# ------------------------------------------------------------------ finance-config fallback and base
def test_without_a_commission_rule_the_approved_finance_config_percentage_still_applies(clean_db):
    a1, a2, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2, commission_bps=1000)
        b, _, _ = paid_booking(env, w, hour=9)
        assert snapshot(clean_db, b["id"])[0]["scope"] == "none"
        api.post(f"{A}/finance/accrue", headers=h)
        e = sale_entry(clean_db, b["id"])
        assert (e["commission_scope"], e["commission_bps"], e["commission_paise"]) == (
            "finance_config",
            1000,
            4000,
        )
        assert e["commission_rule_id"] is None
        # a rule created afterwards does not rewrite that booking
        mk_rule(api, h, bps=2500)
        assert snapshot(clean_db, b["id"])[0]["scope"] == "none"
        assert sale_entry(clean_db, b["id"])["commission_paise"] == 4000


def test_commission_base_is_configurable_but_defaults_to_the_slot_price(clean_db):
    a1, a2, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api = env.api
        c = approve_config(api, a1, a2)
        assert c["commission_base"] == "base"
        bad = api.post(f"{A}/finance/configs", json={**CFG, "commission_base": "total"}, headers=a1["h"])
        assert bad.status_code == 422
        c2 = api.post(
            f"{A}/finance/configs", json={**CFG, "commission_base": "base_after_discount"}, headers=a1["h"]
        )
        assert c2.status_code == 201 and c2.json()["commission_base"] == "base_after_discount"


# ------------------------------------------------------------------ owner earnings
def test_owner_sees_exactly_how_each_booking_net_was_calculated_and_only_their_own(clean_db):
    a1, a2, w = setup(clean_db)
    other = seed_world(clean_db, price=40000)
    with payment_app(clean_db) as env:
        api, h, oh = env.api, a1["h"], w["owner_h"]
        before = api.get(f"{API}/owners/earnings/breakdown", headers=oh).json()
        assert before["available"] is False and "Q8" in before["reason"]
        approve_config(api, a1, a2)
        mk_rule(api, h, bps=1000)
        mk_rule(api, h, "venue", 2000, venue_id=str(other["venue"]), reason="special deal")
        b, _, _ = paid_booking(env, w, hour=9)
        ob, _, _ = paid_booking(env, other, hour=11)
        api.post(f"{A}/finance/accrue", headers=h)
        e = api.get(f"{API}/owners/earnings/breakdown", headers=oh).json()
        assert e["available"] is True and len(e["items"]) == 1
        it = e["items"][0]
        assert it["booking_code"] == b["booking_code"] and it["customer_paid_paise"] == 49560
        assert (
            it["court_charge_paise"],
            it["commission_bps"],
            it["commission_pct"],
            it["commission_paise"],
        ) == (40000, 1000, "10%", 4000)
        assert (
            it["platform_fee_paise"],
            it["tax_paise"],
            it["other_deductions_paise"],
            it["net_payable_paise"],
        ) == (2000, 7560, 0, 36000)
        assert "10%" in it["formula"]
        assert e["totals"]["net_payable_paise"] == 36000 and e["totals"]["commission_paise"] == 4000
        assert "not a transfer" in e["note"]
        d = api.get(f"{API}/owners/earnings/bookings/{b['id']}", headers=oh).json()
        assert d["calculation"]["owner_net_paise"] == 36000 and "candidates" not in d["snapshot"]
        assert (
            api.get(f"{API}/owners/earnings/bookings/{ob['id']}", headers=oh).status_code == 404
        )  # not theirs
        # the other owner is charged their own rate, and never sees ours
        oe = api.get(f"{API}/owners/earnings/breakdown", headers=other["owner_h"]).json()
        assert oe["items"][0]["commission_pct"] == "20%" and oe["items"][0]["net_payable_paise"] == 32000
        # customers cannot read it
        assert api.get(f"{API}/owners/earnings/breakdown", headers=w["customer_h"]).status_code == 403
        # commission page: current rate per venue + history without admin identity or reasons
        cm = api.get(f"{API}/owners/commission", headers=oh).json()
        assert cm["current"][0]["commission_pct"] == "10%" and cm["current"][0]["scope"] == "global"
        assert all("changed_by" not in x and "reason" not in x for x in cm["history"]["items"])
        assert {x["scope"] for x in cm["history"]["items"]} == {"global"}  # not the other owner's venue deal
        assert (
            api.get(f"{API}/owners/commission", headers=other["owner_h"]).json()["current"][0][
                "commission_pct"
            ]
            == "20%"
        )
        # the pre-existing earnings endpoint is untouched
        old = api.get(f"{API}/owners/earnings", headers=oh).json()
        assert old["gross_paid_paise"] == 49560 and old["net_earnings"]["available"] is False
        # filters: another venue id yields nothing
        none = api.get(f"{API}/owners/earnings/breakdown?venue_id={other['venue']}", headers=oh).json()
        assert none["items"] == [] and none["totals"]["net_payable_paise"] == 0


# ------------------------------------------------------------------ reports and reconciliation
def test_reports_by_activity_venue_day_scope_reconcile_with_payments_and_export_csv(clean_db):
    a1, a2, w = setup(clean_db)
    other = seed_world(clean_db, price=40000)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        approve_config(api, a1, a2)
        mk_rule(api, h, bps=1000)
        mk_rule(api, h, "venue", 2000, venue_id=str(other["venue"]))
        paid_booking(env, w, hour=9)
        paid_booking(env, w, hour=11)
        paid_booking(env, other, hour=9)
        unpaid = hold_booking(env, w, hour=13)  # noqa: F841 — never earns commission
        assert api.post(f"{A}/finance/accrue", headers=h).json()["sales"] == 3
        rep = api.get(f"{C}/report", headers=h).json()
        t = rep["totals"]
        assert (t["bookings"], t["sales_gross_paise"], t["net_commission_paise"]) == (
            3,
            3 * 49560,
            4000 * 2 + 8000,
        )
        captured = rows(clean_db, "SELECT sum(amount_paise) s FROM public.payments WHERE status='captured'")[
            0
        ]["s"]
        assert t["sales_gross_paise"] == captured  # reconciles with the payment records
        assert t["owner_net_paise"] + t["platform_net_paise"] + t["tax_paise"] == t["net_gross_paise"]
        by_venue = sorted(v["net_commission_paise"] for v in rep["by_venue"])
        assert by_venue == [8000, 8000]
        assert sum(x["net_commission_paise"] for x in rep["by_activity"]) == t["net_commission_paise"]
        assert sum(x["net_commission_paise"] for x in rep["by_day"]) == t["net_commission_paise"]
        assert {s["scope"] for s in rep["by_scope"]} == {"global", "venue"}
        assert rep["reconciliation"]["ok"] is True
        assert {c["key"] for c in rep["reconciliation"]["checks"]} >= {
            "sale_equals_payment",
            "no_duplicate_sales",
            "commission_recomputes",
        }
        # filters
        one = api.get(f"{C}/report?venue_id={other['venue']}", headers=h).json()["totals"]
        assert one["net_commission_paise"] == 8000 and one["bookings"] == 1
        cat = category_of(clean_db, w["venue"])
        assert api.get(f"{C}/report?category_id={cat}", headers=h).json()["totals"]["bookings"] == 2
        assert (
            api.get(f"{C}/report?from=2000-01-01&to=2000-01-02", headers=h).json()["totals"]["bookings"] == 0
        )
        # a payment that no longer matches its ledger entry is caught
        sql(
            clean_db,
            "UPDATE public.payments SET amount_paise = amount_paise + 100 WHERE id = (SELECT id FROM public.payments LIMIT 1)",
        )
        bad = api.get(f"{C}/report", headers=h).json()["reconciliation"]
        assert (
            bad["ok"] is False
            and next(c for c in bad["checks"] if c["key"] == "sale_equals_payment")["mismatches"] == 1
        )
        # owner earnings as seen by an admin, and the CSV export (audited)
        oe = api.get(f"{C}/owners/{w['owner']}/earnings", headers=h).json()
        assert oe["totals"]["commission_paise"] == 8000
        csv = api.get(f"{A}/exports/commission.csv", headers=h)
        assert csv.status_code == 200 and "commission_bps" in csv.text.splitlines()[0]
        assert len(csv.text.strip().splitlines()) == 4 and ",1000," in csv.text and ",2000," in csv.text
        assert len(audit_rows(clean_db, "admin.export")) >= 1


# ------------------------------------------------------------------ authorization
def test_only_authorised_admins_can_read_or_change_commission(clean_db):
    a1, _, w = setup(clean_db)
    viewer = admin_with(clean_db, ["commission.view"])
    finance = admin_with(clean_db, ["finance.view", "finance.manage", "finance.approve"])
    nobody = admin_with(clean_db, ["dashboard.view"])
    mfa_less = auth_headers(seed_profile(clean_db, "admin"))
    with payment_app(clean_db) as env:
        api = env.api
        r = mk_rule(api, a1["h"], bps=1000)
        body = {"scope": "global", "commission_bps": 1, "reason": "no way"}
        chg = {"commission_bps": 5, "reason": "no way"}
        # anonymous, customer and owner: never
        for who in (None, w["customer_h"], w["owner_h"]):
            h = who or {}
            want = 401 if who is None else 403
            assert api.get(f"{C}/rules", headers=h).status_code == want
            assert api.post(f"{C}/rules", json=body, headers=h).status_code == want
            assert api.post(f"{C}/rules/{r['id']}/versions", json=chg, headers=h).status_code == want
            assert api.get(f"{C}/history", headers=h).status_code == want
            assert api.get(f"{C}/report", headers=h).status_code == want
        # a viewer reads, never writes
        assert api.get(f"{C}/rules", headers=viewer["h"]).status_code == 200
        assert api.get(f"{C}/history", headers=viewer["h"]).status_code == 200
        assert api.post(f"{C}/rules", json=body, headers=viewer["h"]).status_code == 403
        assert api.post(f"{C}/rules/{r['id']}/versions", json=chg, headers=viewer["h"]).status_code == 403
        assert api.get(f"{C}/report", headers=viewer["h"]).status_code == 403  # reports need finance.view
        # finance admins read reports but cannot change rates unless granted commission.manage
        assert api.get(f"{C}/report", headers=finance["h"]).status_code == 200
        assert api.post(f"{C}/rules/{r['id']}/versions", json=chg, headers=finance["h"]).status_code == 403
        assert api.get(f"{C}/rules", headers=nobody["h"]).status_code == 403
        assert api.get(f"{A}/exports/commission.csv", headers=viewer["h"]).status_code == 403
        # nothing changed
        assert api.get(f"{C}/rules/{r['id']}", headers=a1["h"]).json()["latest_version"] == 1
        assert rows(clean_db, "SELECT count(*) n FROM public.commission_rule_versions")[0]["n"] == 1
        del mfa_less


def test_nothing_is_accrued_while_no_finance_configuration_is_approved(clean_db):
    """Commission rules may exist and snapshots are stored, but money is not recorded until Q7/Q8 are approved."""
    a1, a2, w = setup(clean_db)
    with payment_app(clean_db) as env:
        api, h = env.api, a1["h"]
        mk_rule(api, h, bps=1000)
        b, _, _ = paid_booking(env, w, hour=9)
        assert snapshot(clean_db, b["id"])[0]["commission_bps"] == 1000  # the rate is remembered...
        out = api.post(f"{A}/finance/accrue", headers=h).json()
        assert out["sales"] == 0 and out["skipped_no_rule_or_no_sale"] == 1  # ...but no ledger entry is written
        assert rows(clean_db, "SELECT count(*) n FROM public.ledger_entries")[0]["n"] == 0
        assert api.get(f"{API}/owners/earnings/breakdown", headers=w["owner_h"]).json()["available"] is False
        assert api.get(f"{A}/finance/summary", headers=h).json()["commission"] is None
        # approving a configuration later accrues using the rate fixed at booking time
        approve_config(api, a1, a2)
        assert api.post(f"{A}/finance/accrue", headers=h).json()["sales"] == 0  # captured BEFORE the approval: stays out
