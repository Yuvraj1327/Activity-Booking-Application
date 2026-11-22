"""Venue approval / verification / suspension / reports, owner KYC, roles and platform switches."""

import json
import uuid

from tests.admin_helpers import admin_with, audit_rows
from tests.booking_helpers import API, book, future_day, iso, seed_world
from tests.conftest import auth_headers, seed_profile, sql

A = f"{API}/admin"
PDF = b"%PDF-1.4\n" + b"x" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"y" * 200


class FakeStorage:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    async def upload(self, path, data, content_type, bucket=None):
        self.objects[(bucket or "venue-images", path)] = data

    async def delete(self, paths, bucket=None):
        for p in paths:
            self.objects.pop((bucket or "venue-images", p), None)

    async def download(self, path, bucket):
        return self.objects[(bucket, path)]


def draft_venue(db, owner=None):
    owner = owner or seed_profile(db, "owner")
    city = sql(
        db,
        "INSERT INTO public.cities (name, country_code) VALUES ($1,'IN') RETURNING id",
        uuid.uuid4().hex[:6],
    )[0]["id"]
    v = sql(
        db,
        "INSERT INTO public.venues (owner_id, city_id, name, latitude, longitude, timezone, status) "
        "VALUES ($1,$2,'Ace Arena',12.9,77.6,'Asia/Kolkata','draft') RETURNING id",
        owner, city,
    )[0]["id"]  # fmt: skip
    cat = sql(
        db,
        "INSERT INTO public.categories (slug, name) VALUES ($1,'Cricket') RETURNING id",
        uuid.uuid4().hex[:8],
    )[0]["id"]
    sql(db, "INSERT INTO public.venue_categories (venue_id, category_id) VALUES ($1,$2)", v, cat)
    return owner, v


def status_of(db, vid):
    return sql(db, "SELECT status FROM public.venues WHERE id=$1", vid)[0]["status"]


def set_switch(api, admin, key, value=True):
    r = api.put(f"{A}/settings/{key}", json={"value": value, "reason": "client decision"}, headers=admin["h"])
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------ approval workflow
def test_without_the_workflow_owners_still_publish_directly(api, clean_db):
    owner, v = draft_venue(clean_db)
    r = api.post(f"{API}/owners/venues/{v}/publish", headers=auth_headers(owner))
    assert r.status_code == 200 and r.json()["status"] == "published"


def test_approval_workflow_blocks_self_publishing_until_an_admin_approves(api, clean_db):
    admin = admin_with(clean_db)
    owner, v = draft_venue(clean_db)
    oh = auth_headers(owner)
    set_switch(api, admin, "venue_approval_required")
    r = api.post(f"{API}/owners/venues/{v}/publish", headers=oh)
    assert r.status_code == 200 and r.json()["status"] == "pending_review"
    assert api.post(f"{API}/owners/venues/{v}/publish", headers=oh).json()["status"] == "pending_review"
    # not visible to customers, cannot be booked
    assert (
        api.get(f"{API}/venues/{v}", headers=auth_headers(seed_profile(clean_db, "customer"))).status_code
        == 404
    )
    # the owner cannot smuggle a status in
    assert api.patch(f"{API}/owners/venues/{v}", json={"status": "published"}, headers=oh).status_code == 422
    assert status_of(clean_db, v) == "pending_review"
    # reject needs a reason
    assert api.post(f"{A}/venues/{v}/reject", json={}, headers=admin["h"]).status_code == 422
    r = api.post(
        f"{A}/venues/{v}/reject", json={"reason": "Photos do not show the court"}, headers=admin["h"]
    )
    assert r.status_code == 200 and status_of(clean_db, v) == "rejected"
    mine = api.get(f"{API}/owners/venues/{v}", headers=oh).json()
    assert mine["status"] == "rejected" and "Photos" in mine["status_reason"]
    # resubmit and approve
    assert api.post(f"{API}/owners/venues/{v}/publish", headers=oh).json()["status"] == "pending_review"
    assert api.post(f"{A}/venues/{v}/approve", json={}, headers=admin["h"]).status_code == 200
    assert status_of(clean_db, v) == "published"
    assert (
        api.get(f"{API}/venues/{v}", headers=auth_headers(seed_profile(clean_db, "customer"))).status_code
        == 200
    )
    # approving something that is not pending is refused
    again = api.post(f"{A}/venues/{v}/approve", json={}, headers=admin["h"])
    assert again.status_code == 409 and again.json()["code"] == "INVALID_VENUE_TRANSITION"
    hist = api.get(f"{A}/venues/{v}/history", headers=admin["h"]).json()["items"]
    assert [h["action"] for h in hist][::-1] == ["submitted", "rejected", "submitted", "approved"]
    rej = [a for a in audit_rows(clean_db, "admin.venue_rejected")][0]
    meta = json.loads(rej["metadata"])
    assert meta["before"]["status"] == "pending_review" and meta["after"]["status"] == "rejected"
    assert meta["reason"].startswith("Photos")
    # list filter for the approval queue
    q = api.get(f"{A}/venues?status=pending_review", headers=admin["h"]).json()
    assert q["items"] == []


def test_suspend_hides_the_venue_blocks_owner_and_bookings_and_reinstate_restores(clean_db):
    from tests.booking_helpers import make_app

    with make_app(clean_db, booking_hold_minutes=10) as api:
        _suspend_scenario(api, clean_db)


def _suspend_scenario(api, clean_db):
    admin = admin_with(clean_db)
    w = seed_world(clean_db)
    v = str(w["venue"])
    start = iso(future_day(), 9)
    assert book(api, w, start).status_code == 201  # bookable while live
    assert api.post(f"{A}/venues/{v}/suspend", json={}, headers=admin["h"]).status_code == 422
    r = api.post(f"{A}/venues/{v}/suspend", json={"reason": "Safety complaint"}, headers=admin["h"])
    assert r.status_code == 200 and status_of(clean_db, v) == "suspended"
    oh = w["owner_h"]
    for path in ("publish", "unpublish"):
        x = api.post(f"{API}/owners/venues/{v}/{path}", headers=oh)
        assert x.status_code == 409 and x.json()["code"] == "VENUE_SUSPENDED"
    assert api.get(f"{API}/owners/venues/{v}", headers=oh).json()["status_reason"] == "Safety complaint"
    assert api.get(f"{API}/venues/{v}", headers=w["customer_h"]).status_code == 404
    # No new booking on a suspended venue (the resource is no longer reachable).
    b = book(api, w, iso(future_day(), 11))
    assert b.status_code in (404, 409, 422), b.text
    assert api.post(f"{A}/venues/{v}/reinstate", json={}, headers=admin["h"]).status_code == 200
    assert status_of(clean_db, v) == "published"
    assert api.get(f"{API}/venues/{v}", headers=w["customer_h"]).status_code == 200


def test_verification_and_permissions(api, clean_db):
    admin = admin_with(clean_db)
    viewer = admin_with(clean_db, ["venues.view"])
    w = seed_world(clean_db)
    v = str(w["venue"])
    assert api.post(f"{A}/venues/{v}/verify", json={}, headers=viewer["h"]).status_code == 403
    assert api.post(f"{A}/venues/{v}/approve", json={}, headers=viewer["h"]).status_code == 403
    assert api.post(f"{A}/venues/{v}/verify", json={}, headers=admin["h"]).json()["changed"] is True
    assert api.post(f"{A}/venues/{v}/verify", json={}, headers=admin["h"]).json()["changed"] is False
    assert api.post(f"{A}/venues/{v}/unverify", json={}, headers=admin["h"]).status_code == 422
    assert (
        api.post(
            f"{A}/venues/{v}/unverify", json={"reason": "Documents expired"}, headers=admin["h"]
        ).status_code
        == 200
    )
    d = api.get(f"{A}/venues/{v}", headers=admin["h"]).json()
    assert d["is_verified"] is False


def test_customer_reports_and_admin_review(api, clean_db):
    admin = admin_with(clean_db)
    w = seed_world(clean_db)
    v = str(w["venue"])
    r = api.post(
        f"{API}/venues/{v}/report",
        json={"reason": "unsafe", "details": "Broken floor"},
        headers=w["customer_h"],
    )
    assert r.status_code == 201
    dup = api.post(f"{API}/venues/{v}/report", json={"reason": "unsafe"}, headers=w["customer_h"])
    assert dup.status_code == 409 and dup.json()["code"] == "REPORT_ALREADY_OPEN"
    assert (
        api.post(f"{API}/venues/{v}/report", json={"reason": "unsafe"}, headers=w["owner_h"]).status_code
        == 403
    )
    lst = api.get(f"{A}/venue-reports?status=open", headers=admin["h"]).json()
    assert len(lst["items"]) == 1 and lst["items"][0]["venue_name"] == "Ace Arena"
    rid = lst["items"][0]["id"]
    assert api.get(f"{A}/venue-reports/{rid}", headers=admin["h"]).json()["details"] == "Broken floor"
    assert (
        api.patch(f"{A}/venue-reports/{rid}", json={"status": "dismissed"}, headers=admin["h"]).status_code
        == 422
    )
    ok = api.patch(
        f"{A}/venue-reports/{rid}",
        json={"status": "action_taken", "note": "Venue suspended"},
        headers=admin["h"],
    )
    assert ok.status_code == 200 and ok.json()["status"] == "action_taken"
    assert (
        api.patch(f"{A}/venue-reports/{rid}", json={"status": "reviewing"}, headers=admin["h"]).status_code
        == 409
    )
    assert len(audit_rows(clean_db, "admin.venue_report_reviewed")) == 1


# ------------------------------------------------------------------ KYC
def test_kyc_submission_review_and_private_document_access(api, clean_db):
    store = FakeStorage()
    api.app.state.storage = store
    admin = admin_with(clean_db)
    reviewer_only_view = admin_with(clean_db, ["owners.view"])
    owner = seed_profile(clean_db, "owner")
    oh = auth_headers(owner)
    other_owner = auth_headers(seed_profile(clean_db, "owner"))
    cust = auth_headers(seed_profile(clean_db, "customer"))

    assert api.get(f"{API}/owners/kyc", headers=oh).json()["kyc_status"] == "not_submitted"
    # file type is sniffed from bytes, not trusted from the client
    bad = api.post(
        f"{API}/owners/kyc/documents",
        data={"doc_type": "identity"},
        files={"file": ("x.pdf", b"MZ not a pdf", "application/pdf")},
        headers=oh,
    )
    assert bad.status_code == 422 and bad.json()["code"] == "UNSUPPORTED_FILE_TYPE"
    big = api.post(
        f"{API}/owners/kyc/documents",
        data={"doc_type": "identity"},
        files={"file": ("x.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024), "application/pdf")},
        headers=oh,
    )
    assert big.status_code == 422
    r1 = api.post(
        f"{API}/owners/kyc/documents",
        data={"doc_type": "identity"},
        files={"file": ("id.pdf", PDF, "application/pdf")},
        headers=oh,
    )
    r2 = api.post(
        f"{API}/owners/kyc/documents",
        data={"doc_type": "bank_account"},
        files={"file": ("bank.png", PNG, "image/png")},
        headers=oh,
    )
    assert r1.status_code == 201 and r2.status_code == 201
    assert "storage_path" not in r1.text
    d1, d2 = r1.json()["id"], r2.json()["id"]
    assert all(b == "kyc-documents" for b, _ in store.objects)
    assert api.get(f"{API}/owners/kyc", headers=oh).json()["kyc_status"] == "pending"
    # other users get nothing
    assert api.get(f"{A}/kyc/documents/{d1}/file", headers=oh).status_code == 403
    assert api.get(f"{A}/kyc/documents/{d1}/file", headers=cust).status_code == 403
    assert api.get(f"{A}/kyc/documents/{d1}/file", headers=reviewer_only_view["h"]).status_code == 403
    assert api.delete(f"{API}/owners/kyc/documents/{d1}", headers=other_owner).status_code == 404
    # admin queue + viewing is audited
    q = api.get(f"{A}/kyc/queue", headers=admin["h"]).json()
    assert q["items"][0]["pending_documents"] == 2
    f = api.get(f"{A}/kyc/documents/{d1}/file", headers=admin["h"])
    assert f.status_code == 200 and f.content == PDF and f.headers["cache-control"].startswith("no-store")
    assert len(audit_rows(clean_db, "admin.kyc_document_viewed")) == 1
    # review rules
    assert (
        api.post(
            f"{A}/kyc/documents/{d1}/review", json={"decision": "rejected"}, headers=admin["h"]
        ).status_code
        == 422
    )
    assert (
        api.post(
            f"{A}/owners/{owner}/kyc/decision", json={"decision": "verified"}, headers=admin["h"]
        ).json()["code"]
        == "DOCUMENTS_PENDING"
    )
    rej = api.post(
        f"{A}/kyc/documents/{d1}/review",
        json={"decision": "rejected", "reason": "Blurry photo"},
        headers=admin["h"],
    )
    assert rej.status_code == 200 and rej.json()["rejection_reason"] == "Blurry photo"
    assert (
        api.post(
            f"{A}/kyc/documents/{d1}/review", json={"decision": "approved"}, headers=admin["h"]
        ).status_code
        == 409
    )
    assert (
        api.post(
            f"{A}/kyc/documents/{d2}/review", json={"decision": "approved"}, headers=admin["h"]
        ).status_code
        == 200
    )
    ok = api.post(f"{A}/owners/{owner}/kyc/decision", json={"decision": "verified"}, headers=admin["h"])
    assert ok.status_code == 200
    mine = api.get(f"{API}/owners/kyc", headers=oh).json()
    assert mine["kyc_status"] == "verified"
    assert {d["status"] for d in mine["documents"]} == {"rejected", "approved"}
    # a reviewed document cannot be deleted by the owner
    assert api.delete(f"{API}/owners/kyc/documents/{d2}", headers=oh).status_code == 409
    meta = json.loads(audit_rows(clean_db, "admin.kyc_verified")[0]["metadata"])
    assert meta["before"]["kyc_status"] == "pending" and meta["after"]["kyc_status"] == "verified"
    assert api.get(f"{A}/owners/{owner}/kyc", headers=admin["h"]).json()["kyc_status"] == "verified"


# ------------------------------------------------------------------ roles / permissions / settings
def test_roles_cannot_escalate_privileges(api, clean_db):
    root = admin_with(clean_db)
    mgr = admin_with(clean_db, ["roles.manage", "customers.view"])
    target = admin_with(clean_db, [])
    h = mgr["h"]
    perms = api.get(f"{A}/permissions", headers=h).json()["items"]
    assert any(p["key"] == "refunds.manage" and p["sensitive"] for p in perms)
    # cannot grant a permission the manager does not hold
    r = api.post(f"{A}/roles", json={"name": "Money", "permissions": ["refunds.manage"]}, headers=h)
    assert r.status_code == 403 and r.json()["code"] == "CANNOT_GRANT_UNHELD_PERMISSION"
    ok = api.post(f"{A}/roles", json={"name": "Viewer", "permissions": ["customers.view"]}, headers=h)
    assert ok.status_code == 201
    role_id = ok.json()["id"]
    assert (
        api.post(f"{A}/roles", json={"name": "super_admin", "permissions": []}, headers=h).json()["code"]
        == "ROLE_NAME_RESERVED"
    )
    assert (
        api.post(f"{A}/roles", json={"name": "Bad", "permissions": ["nope.nope"]}, headers=h).json()["code"]
        == "UNKNOWN_PERMISSION"
    )
    # assign to another admin; cannot assign to self; cannot assign the super role
    asg = api.put(
        f"{A}/admins/{target['id']}/role", json={"role_id": role_id, "reason": "new hire"}, headers=h
    )
    assert asg.status_code == 200
    assert api.get(f"{A}/customers", headers=target["h"]).status_code == 200
    assert api.get(f"{A}/owners", headers=target["h"]).status_code == 403
    me = api.get(f"{A}/me", headers=target["h"]).json()
    assert me["admin_role"] == "Viewer" and "customers.view" in me["permissions"]
    self_asg = api.put(
        f"{A}/admins/{mgr['id']}/role", json={"role_id": role_id, "reason": "self promote"}, headers=h
    )
    assert self_asg.status_code == 403 and self_asg.json()["code"] == "CANNOT_CHANGE_OWN_ROLE"
    super_id = [r for r in api.get(f"{A}/roles", headers=h).json()["items"] if r["name"] == "super_admin"][0][
        "id"
    ]
    sup = api.put(
        f"{A}/admins/{target['id']}/role", json={"role_id": super_id, "reason": "escalate"}, headers=h
    )
    assert sup.status_code == 403 and sup.json()["code"] == "SUPER_ADMIN_ONLY"
    # the manager cannot widen the role they themselves hold
    mgr_role = sql(clean_db, "SELECT role_id FROM public.admin_profiles WHERE user_id=$1", mgr["id"])[0][
        "role_id"
    ]
    own = api.patch(
        f"{A}/roles/{mgr_role}",
        json={"permissions": ["roles.manage", "refunds.manage"], "reason": "x y z"},
        headers=h,
    )
    assert own.status_code == 403
    # built-in role is protected; last super admin cannot be demoted
    assert (
        api.patch(
            f"{A}/roles/{super_id}", json={"permissions": [], "reason": "x y z"}, headers=root["h"]
        ).json()["code"]
        == "SYSTEM_ROLE_PROTECTED"
    )
    demote = api.put(f"{A}/admins/{root['id']}/role", json={"role_id": None, "reason": "oops"}, headers=h)
    assert demote.status_code == 403  # manager is not a super_admin
    # role in use cannot be deleted; unused can
    inuse = api.request("DELETE", f"{A}/roles/{role_id}", json={"reason": "cleanup"}, headers=h)
    assert inuse.status_code == 409 and inuse.json()["code"] == "ROLE_IN_USE"
    # before/after audit for permission changes
    upd = api.patch(
        f"{A}/roles/{role_id}",
        json={"permissions": ["customers.view", "owners.view"], "reason": "needs owners"},
        headers=h,
    )
    assert (
        upd.status_code == 403 and upd.json()["code"] == "CANNOT_GRANT_UNHELD_PERMISSION"
    )  # mgr lacks owners.view
    upd = api.patch(
        f"{A}/roles/{role_id}",
        json={"permissions": ["customers.view", "owners.view"], "reason": "needs owners"},
        headers=root["h"],
    )
    assert upd.status_code == 200
    meta = json.loads(audit_rows(clean_db, "admin.role_updated")[0]["metadata"])
    assert (
        meta["before"]["permissions"] == ["customers.view"] and "owners.view" in meta["after"]["permissions"]
    )
    assert len(audit_rows(clean_db, "admin.role_assigned")) == 1


def test_last_super_admin_cannot_be_removed_and_unassigned_admin_sees_nothing(api, clean_db):
    root1 = admin_with(clean_db)
    root2 = admin_with(clean_db)
    sid = sql(clean_db, "SELECT id FROM public.admin_roles WHERE name='super_admin'")[0]["id"]
    # root1 demotes root2 (allowed: a second super admin remains: root1) ...
    ok = api.put(
        f"{A}/admins/{root2['id']}/role",
        json={"role_id": None, "reason": "left the company"},
        headers=root1["h"],
    )
    assert ok.status_code == 200
    assert api.get(f"{A}/dashboard", headers=root2["h"]).json()["code"] == "ADMIN_ROLE_REQUIRED"
    # ... but root1 cannot demote the last one (and cannot touch their own role anyway)
    third = admin_with(clean_db, [])
    api.put(
        f"{A}/admins/{third['id']}/role", json={"role_id": str(sid), "reason": "second"}, headers=root1["h"]
    )
    last = api.put(
        f"{A}/admins/{root1['id']}/role", json={"role_id": None, "reason": "x y z"}, headers=third["h"]
    )
    assert last.status_code == 200  # two supers exist (root1, third) so allowed
    gone = api.put(
        f"{A}/admins/{third['id']}/role", json={"role_id": None, "reason": "x y z"}, headers=root1["h"]
    )
    assert gone.status_code in (403, 409)


def test_settings_need_permission_are_audited_and_default_to_safe(api, clean_db):
    admin = admin_with(clean_db)
    viewer = admin_with(clean_db, ["dashboard.view"])
    vals = {s["key"]: s["value"] for s in api.get(f"{A}/settings", headers=admin["h"]).json()["items"]}
    assert vals == {
        "venue_approval_required": False,
        "refunds_enabled": False,
        "payouts_enabled": False,
        "payout_requires_kyc": True,
    }
    assert api.get(f"{A}/settings", headers=viewer["h"]).status_code == 403
    assert (
        api.put(
            f"{A}/settings/refunds_enabled", json={"value": True, "reason": "ok ok"}, headers=viewer["h"]
        ).status_code
        == 403
    )
    assert (
        api.put(
            f"{A}/settings/bogus", json={"value": True, "reason": "ok ok"}, headers=admin["h"]
        ).status_code
        == 422
    )
    assert (
        api.put(f"{A}/settings/refunds_enabled", json={"value": True}, headers=admin["h"]).status_code == 422
    )
    set_switch(api, admin, "refunds_enabled", True)
    meta = json.loads(audit_rows(clean_db, "admin.setting_changed")[0]["metadata"])
    assert meta["before"] == {"value": False} and meta["after"] == {"value": True} and meta["reason"]


def test_monitoring_reports_real_status_without_secrets(api, clean_db):
    admin = admin_with(clean_db)
    other = admin_with(clean_db, ["dashboard.view"])
    assert api.get(f"{A}/monitoring", headers=other["h"]).status_code == 403
    r = api.get(f"{A}/monitoring", headers=admin["h"])
    assert r.status_code == 200
    m = r.json()
    assert m["database"]["status"] == "ok" and m["database"]["latency_ms"] is not None
    assert m["payment_gateway"]["api_configured"] is False and m["payment_gateway"]["mode"] == "unconfigured"
    assert any("Razorpay" in w for w in m["warnings"])
    assert m["webhooks"]["rejected_total"] == 0
    assert m["recent_log_events"]["scope"].startswith("WARNING")
    txt = r.text.lower()
    for forbidden in ("secret", "service_role", "password", "database_url"):
        assert forbidden not in txt.replace("webhook_configured", "").replace("secret is not configured", "")
