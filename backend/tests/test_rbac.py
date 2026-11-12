"""Role-based access: every protected endpoint against every role."""

import pytest

from tests.conftest import auth_headers, seed_profile

# endpoint -> roles that may call it (anything else must get 403)
MATRIX = {
    "/api/v1/profiles/me": {"customer", "owner", "admin"},
    "/api/v1/customers/me": {"customer"},
    "/api/v1/owners/me": {"owner"},
    "/api/v1/admin/me": {"admin"},
}


@pytest.mark.parametrize("path", MATRIX)
@pytest.mark.parametrize("role", ["customer", "owner", "admin"])
def test_role_matrix(api, clean_db, path, role):
    uid = seed_profile(clean_db, role)
    r = api.get(path, headers=auth_headers(uid, aal="aal2"))
    if role in MATRIX[path]:
        assert r.status_code == 200, r.text
    else:
        assert r.status_code == 403, r.text
        assert r.json()["code"] == "INSUFFICIENT_ROLE"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("patch", "/api/v1/owners/me", {"business_name": "Hacked"}),
        ("patch", "/api/v1/customers/me", {"preferred_city_id": None}),
    ],
)
def test_wrong_role_cannot_write(api, clean_db, method, path, body):
    wrong = "customer" if "owners" in path else "owner"
    uid = seed_profile(clean_db, wrong)
    assert getattr(api, method)(path, json=body, headers=auth_headers(uid)).status_code == 403


def test_customer_and_owner_cannot_reach_admin(api, clean_db):
    for role in ("customer", "owner"):
        uid = seed_profile(clean_db, role)
        assert api.get("/api/v1/admin/me", headers=auth_headers(uid, aal="aal2")).status_code == 403


def test_unauthenticated_admin_is_401(api):
    assert api.get("/api/v1/admin/me").status_code == 401


def test_admin_requires_mfa_when_enabled(clean_db):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import JWT_SECRET, SUPABASE_URL, make_settings

    app = create_app(
        make_settings(
            supabase_jwt_secret=JWT_SECRET,
            supabase_url=SUPABASE_URL,
            database_url=clean_db,
            admin_require_mfa=True,
        )
    )
    uid = seed_profile(clean_db, "admin")
    with TestClient(app) as c:
        weak = c.get("/api/v1/admin/me", headers=auth_headers(uid, aal="aal1"))
        strong = c.get("/api/v1/admin/me", headers=auth_headers(uid, aal="aal2"))
    assert weak.status_code == 403 and weak.json()["code"] == "MFA_REQUIRED"
    assert strong.status_code == 200


def test_suspended_admin_is_rejected(api, clean_db):
    uid = seed_profile(clean_db, "admin", status="suspended")
    r = api.get("/api/v1/admin/me", headers=auth_headers(uid, aal="aal2"))
    assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_SUSPENDED"


def test_cannot_become_admin_through_any_endpoint(api, clean_db):
    uid = seed_profile(clean_db, "customer")
    h = auth_headers(uid, aal="aal2")
    for path, body in (
        ("/api/v1/profiles/me", {"role": "admin"}),
        ("/api/v1/customers/me", {"role": "admin"}),
        ("/api/v1/auth/profile", {"role": "admin", "full_name": "x"}),
    ):
        method = api.post if path.endswith("profile") and "auth" in path else api.patch
        assert method(path, json=body, headers=h).status_code == 422
    assert api.get("/api/v1/admin/me", headers=h).status_code == 403
