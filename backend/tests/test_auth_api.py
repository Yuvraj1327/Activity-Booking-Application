"""Registration, identity and token handling through the real API + migrated database."""

import time
import uuid

import jwt
import pytest

from tests.conftest import (
    ISSUER,
    auth_headers,
    bearer,
    make_auth_user,
    make_token,
    seed_profile,
    sql,
)


# ------------------------------------------------------------------ token handling (no DB needed)
@pytest.mark.parametrize("path", ["/api/v1/auth/me", "/api/v1/profiles/me", "/api/v1/admin/me"])
def test_missing_token_is_401(client, path):
    r = client.get(path)
    assert r.status_code == 401
    assert r.json()["code"] == "MISSING_TOKEN"
    assert r.headers["www-authenticate"] == "Bearer"


def test_garbage_token_is_401(client):
    r = client.get("/api/v1/auth/me", headers=bearer("not-a-jwt"))
    assert r.status_code == 401 and r.json()["code"] == "INVALID_TOKEN"


def test_expired_token_is_401(client):
    r = client.get("/api/v1/auth/me", headers=auth_headers(uuid.uuid4(), exp_in=-3600))
    assert r.status_code == 401 and r.json()["code"] == "TOKEN_EXPIRED"


def test_wrong_signature_is_401(client):
    t = make_token(uuid.uuid4(), secret="y" * 48)
    assert client.get("/api/v1/auth/me", headers=bearer(t)).status_code == 401


def test_wrong_audience_and_issuer_are_401(client):
    for over in ({"aud": "anon"}, {"iss": "https://evil.example/auth/v1"}):
        t = make_token(uuid.uuid4(), **over)
        assert client.get("/api/v1/auth/me", headers=bearer(t)).status_code == 401


def test_alg_none_token_is_401(client):
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 600},
        None,
        algorithm="none",
    )
    assert client.get("/api/v1/auth/me", headers=bearer(forged)).status_code == 401


def test_non_uuid_subject_is_401(api):
    t = make_token("not-a-uuid")
    r = api.get("/api/v1/auth/me", headers=bearer(t))
    assert r.status_code == 401 and r.json()["code"] == "INVALID_TOKEN"


def test_verification_unconfigured_fails_closed():
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import make_settings

    with TestClient(create_app(make_settings())) as c:
        r = c.get("/api/v1/auth/me", headers=bearer(make_token(uuid.uuid4())))
    assert r.status_code == 401 and r.json()["code"] == "AUTH_NOT_CONFIGURED"


# ------------------------------------------------------------------ identity
def test_me_without_profile(api, clean_db):
    uid = make_auth_user(clean_db, "new@example.com")
    r = api.get("/api/v1/auth/me", headers=auth_headers(uid, email="new@example.com"))
    assert r.status_code == 200
    body = r.json()
    assert body["has_profile"] is False and body["profile"] is None
    assert body["user_id"] == str(uid)


def test_profile_required_for_profile_endpoints(api, clean_db):
    uid = make_auth_user(clean_db, "np@example.com")
    r = api.get("/api/v1/profiles/me", headers=auth_headers(uid))
    assert r.status_code == 403 and r.json()["code"] == "PROFILE_REQUIRED"


# ------------------------------------------------------------------ registration
def test_customer_registration_and_authentication(api, clean_db):
    uid = make_auth_user(clean_db, "Cust@Example.com")
    h = auth_headers(uid, email="Cust@Example.com")
    r = api.post("/api/v1/auth/profile", json={"role": "customer", "full_name": "  Asha Rao "}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == str(uid) and body["role"] == "customer" and body["status"] == "active"
    assert body["full_name"] == "Asha Rao"
    assert body["email"] == "cust@example.com"

    assert api.get("/api/v1/auth/me", headers=h).json()["has_profile"] is True
    assert api.get("/api/v1/customers/me", headers=h).status_code == 200
    assert sql(clean_db, "SELECT count(*) AS n FROM public.customer_profiles")[0]["n"] == 1
    assert sql(clean_db, "SELECT action FROM public.audit_logs")[0]["action"] == "profile.registered"


def test_owner_registration_and_authentication(api, clean_db):
    uid = make_auth_user(clean_db, "owner@example.com")
    h = auth_headers(uid, email="owner@example.com")
    r = api.post(
        "/api/v1/auth/profile",
        json={"role": "owner", "full_name": "Ravi K", "business_name": "Ravi Sports Arena"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "owner"
    me = api.get("/api/v1/owners/me", headers=h).json()
    assert me["business_name"] == "Ravi Sports Arena"


def test_registration_is_idempotent_for_same_role(api, clean_db):
    uid = make_auth_user(clean_db, "idem@example.com")
    h = auth_headers(uid)
    body = {"role": "customer", "full_name": "Idem"}
    assert api.post("/api/v1/auth/profile", json=body, headers=h).status_code == 201
    again = api.post("/api/v1/auth/profile", json=body, headers=h)
    assert again.status_code == 200
    assert sql(clean_db, "SELECT count(*) AS n FROM public.profiles")[0]["n"] == 1


def test_registration_with_other_role_conflicts(api, clean_db):
    uid = make_auth_user(clean_db, "c@example.com")
    h = auth_headers(uid)
    api.post("/api/v1/auth/profile", json={"role": "customer", "full_name": "C"}, headers=h)
    r = api.post(
        "/api/v1/auth/profile",
        json={"role": "owner", "full_name": "C", "business_name": "Biz"},
        headers=h,
    )
    assert r.status_code == 409 and r.json()["code"] == "ROLE_CONFLICT"
    # role unchanged
    assert sql(clean_db, "SELECT role FROM public.profiles WHERE id=$1", uid)[0]["role"] == "customer"


@pytest.mark.parametrize(
    "body",
    [
        {"role": "admin", "full_name": "Evil"},  # cannot self-assign admin
        {"role": "superuser", "full_name": "Evil"},
        {"role": "customer", "full_name": "Evil", "status": "active"},  # unknown field
        {"role": "customer", "full_name": "Evil", "id": str(uuid.uuid4())},  # client-supplied id
        {"role": "owner", "full_name": "No Business"},  # business_name required
        {"role": "customer", "full_name": "X", "business_name": "Nope"},
        {"role": "customer", "full_name": ""},
        {"role": "customer", "full_name": "A", "phone": "12345"},
    ],
)
def test_registration_validation(api, clean_db, body):
    uid = make_auth_user(clean_db, "v@example.com")
    r = api.post("/api/v1/auth/profile", json=body, headers=auth_headers(uid))
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "VALIDATION_ERROR"
    assert sql(clean_db, "SELECT count(*) AS n FROM public.profiles")[0]["n"] == 0


def test_registration_ignores_client_user_id_uses_token(api, clean_db):
    victim = make_auth_user(clean_db, "victim@example.com")
    attacker = make_auth_user(clean_db, "attacker@example.com")
    r = api.post(
        "/api/v1/auth/profile",
        json={"role": "customer", "full_name": "Attacker"},
        headers=auth_headers(attacker),
        params={"user_id": str(victim), "id": str(victim)},
    )
    assert r.status_code == 201 and r.json()["id"] == str(attacker)
    assert sql(clean_db, "SELECT count(*) AS n FROM public.profiles WHERE id=$1", victim)[0]["n"] == 0


def test_registration_for_deleted_auth_user_is_401(api, clean_db):
    ghost = uuid.uuid4()  # valid token, but no auth.users row
    r = api.post(
        "/api/v1/auth/profile", json={"role": "customer", "full_name": "Ghost"}, headers=auth_headers(ghost)
    )
    assert r.status_code == 401 and r.json()["code"] == "USER_NOT_FOUND"


def test_verified_phone_claim_is_used(api, clean_db):
    uid = make_auth_user(clean_db, None, "919876543210")
    r = api.post(
        "/api/v1/auth/profile",
        json={"role": "customer", "full_name": "Phone User"},
        headers=auth_headers(uid, email=None, phone="919876543210"),
    )
    assert r.status_code == 201 and r.json()["phone"] == "+919876543210"


# ------------------------------------------------------------------ account status
def test_suspended_account_is_rejected_even_with_valid_token(api, clean_db):
    uid = seed_profile(clean_db, "customer", status="suspended")
    h = auth_headers(uid)
    for path in ("/api/v1/profiles/me", "/api/v1/customers/me"):
        r = api.get(path, headers=h)
        assert r.status_code == 403 and r.json()["code"] == "ACCOUNT_SUSPENDED"
    # /auth/me still tells the client why
    assert api.get("/api/v1/auth/me", headers=h).json()["profile"]["status"] == "suspended"


def test_suspension_takes_effect_immediately(api, clean_db):
    uid = seed_profile(clean_db, "owner")
    h = auth_headers(uid)
    assert api.get("/api/v1/owners/me", headers=h).status_code == 200
    sql(clean_db, "UPDATE public.profiles SET status='suspended' WHERE id=$1", uid)
    assert api.get("/api/v1/owners/me", headers=h).status_code == 403


def test_role_in_token_metadata_is_ignored(api, clean_db):
    uid = seed_profile(clean_db, "customer")
    h = auth_headers(
        uid, user_metadata={"role": "admin"}, app_metadata={"role": "admin", "provider": "email"}
    )
    assert api.get("/api/v1/admin/me", headers=h).status_code == 403
    assert api.get("/api/v1/owners/me", headers=h).status_code == 403
