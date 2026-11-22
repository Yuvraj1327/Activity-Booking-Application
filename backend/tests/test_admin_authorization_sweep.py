"""Every /admin route, found by introspection, is closed to everyone who is not entitled to it.

New admin routes are covered automatically: if one forgets its permission dependency this test fails.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.admin_helpers import admin_with
from tests.conftest import JWT_SECRET, SUPABASE_URL, auth_headers, make_settings, seed_profile

PREFIX = "/api/v1"
# Routes a dashboard-only administrator may legitimately reach.
DASHBOARD_ONLY = {"/admin/me", "/admin/dashboard", "/admin/activity"}


def admin_routes() -> list[tuple[str, str]]:
    """Read from the generated OpenAPI document, so every route FastAPI serves is covered."""
    app = create_app(make_settings(supabase_jwt_secret=JWT_SECRET, supabase_url=SUPABASE_URL))
    out: list[tuple[str, str]] = []
    for full, ops in app.openapi()["paths"].items():
        path = full.removeprefix(PREFIX)
        if path.startswith("/admin"):
            out.extend((m.upper(), path) for m in ops if m in ("get", "post", "put", "patch", "delete"))
    return sorted(out)


ROUTES = admin_routes()


def fill(path: str) -> str:
    import re

    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


def call(client: TestClient, method: str, path: str, headers: dict | None = None):
    h = dict(headers or {})
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        h["Idempotency-Key"] = "sweep-key-000001"
    return client.request(method, f"{PREFIX}{fill(path)}", headers=h, json={} if method != "GET" else None)


def test_the_sweep_actually_found_the_admin_surface():
    assert len(ROUTES) > 90
    paths = {p for _, p in ROUTES}
    for must in (
        "/admin/payments/{payment_id}/refunds",
        "/admin/finance/configs/{config_id}/approve",
        "/admin/roles",
        "/admin/kyc/documents/{doc_id}/file",
        "/admin/bookings/{booking_id}/cancel",
        "/admin/payouts",
    ):
        assert must in paths, must


@pytest.fixture
def mfa_api(clean_db):
    """The production setting: administrators must have completed a second factor."""
    app = create_app(
        make_settings(
            supabase_jwt_secret=JWT_SECRET,
            supabase_url=SUPABASE_URL,
            database_url=clean_db,
            admin_require_mfa=True,
        )
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture
def people(mfa_api, clean_db):
    return {
        "customer": auth_headers(seed_profile(clean_db, "customer")),
        "owner": auth_headers(seed_profile(clean_db, "owner")),
        "no_mfa": auth_headers(admin_with(clean_db)["id"]),  # aal1 token
        "no_role": admin_with(clean_db, [])["h"],  # placeholder replaced below
        "dash": admin_with(clean_db, ["dashboard.view"])["h"],
    }


def test_no_admin_route_is_open_to_the_wrong_caller(mfa_api, clean_db, people):
    api = mfa_api
    bare = seed_profile(clean_db, "admin", grant=None)  # a freshly created admin: no role row at all
    no_role = auth_headers(bare, aal="aal2")
    failures: list[str] = []
    for method, path in ROUTES:
        checks = [
            ("anonymous", call(api, method, path), {401}),
            ("customer", call(api, method, path, people["customer"]), {403}),
            ("owner", call(api, method, path, people["owner"]), {403}),
            ("admin without MFA", call(api, method, path, people["no_mfa"]), {403}),
        ]
        if path != "/admin/me":
            checks.append(("admin with no role", call(api, method, path, no_role), {403}))
            if path not in DASHBOARD_ONLY:
                checks.append(
                    ("admin with only dashboard.view", call(api, method, path, people["dash"]), {403})
                )
        for who, resp, ok in checks:
            if resp.status_code not in ok:
                failures.append(f"{method} {path} as {who}: {resp.status_code}")
    assert not failures, "\n".join(failures)


def test_a_role_with_no_permissions_gets_a_clear_error_not_a_redirect(api, clean_db):
    bare = seed_profile(clean_db, "admin", grant=None)
    r = api.get(f"{PREFIX}/admin/dashboard", headers=auth_headers(bare, aal="aal2"))
    assert r.status_code == 403 and r.json()["code"] == "ADMIN_ROLE_REQUIRED"
    dash = admin_with(clean_db, ["analytics.view"])
    r = api.get(f"{PREFIX}/admin/dashboard", headers=dash["h"])
    assert r.status_code == 403 and r.json()["code"] == "PERMISSION_DENIED"
    assert api.get(f"{PREFIX}/admin/analytics/cities", headers=dash["h"]).status_code == 200
