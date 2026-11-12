"""Profile operations and cross-user isolation."""

import uuid

import pytest

from tests.conftest import auth_headers, seed_profile, sql


def test_customer_profile_read_update(api, clean_db):
    uid = seed_profile(clean_db, "customer", name="Old Name")
    h = auth_headers(uid)
    assert api.get("/api/v1/profiles/me", headers=h).json()["full_name"] == "Old Name"

    r = api.patch("/api/v1/profiles/me", json={"full_name": "New Name", "phone": "+919876543210"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "New Name" and r.json()["phone"] == "+919876543210"
    assert r.json()["updated_at"] >= r.json()["created_at"]

    cleared = api.patch("/api/v1/profiles/me", json={"phone": None}, headers=h)
    assert cleared.json()["phone"] is None


def test_customer_preferred_city(api, clean_db):
    uid = seed_profile(clean_db, "customer")
    city = sql(
        clean_db, "INSERT INTO public.cities (name, country_code) VALUES ('Bengaluru','IN') RETURNING id"
    )[0]["id"]
    h = auth_headers(uid)
    r = api.patch("/api/v1/customers/me", json={"preferred_city_id": str(city)}, headers=h)
    assert r.status_code == 200 and r.json()["preferred_city_id"] == str(city)
    bad = api.patch("/api/v1/customers/me", json={"preferred_city_id": str(uuid.uuid4())}, headers=h)
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_CITY"


def test_owner_profile_read_update(api, clean_db):
    uid = seed_profile(clean_db, "owner", business_name="Old Biz")
    h = auth_headers(uid)
    assert api.get("/api/v1/owners/me", headers=h).json()["business_name"] == "Old Biz"
    r = api.patch(
        "/api/v1/owners/me",
        json={
            "business_name": "New Biz",
            "business_phone": "+918012345678",
            "business_email": "biz@example.com",
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["business_name"] == "New Biz" and r.json()["business_email"] == "biz@example.com"


@pytest.mark.parametrize(
    "body",
    [
        {},  # nothing to update
        {"full_name": None},  # required field cannot be nulled
        {"full_name": "x" * 121},
        {"phone": "not-a-phone"},
        {"role": "owner"},
        {"status": "suspended"},
        {"id": str(uuid.uuid4())},
        {"email": "other@example.com"},  # e-mail comes from the identity provider
        {"avatar_path": "someone-else/photo.png"},
    ],
)
def test_profile_patch_rejects_bad_input(api, clean_db, body):
    uid = seed_profile(clean_db, "customer")
    before = sql(clean_db, "SELECT role, status, full_name, email FROM public.profiles WHERE id=$1", uid)[0]
    r = api.patch("/api/v1/profiles/me", json=body, headers=auth_headers(uid))
    assert r.status_code == 422, r.text
    after = sql(clean_db, "SELECT role, status, full_name, email FROM public.profiles WHERE id=$1", uid)[0]
    assert dict(before) == dict(after)


def test_owner_patch_rejects_null_business_name(api, clean_db):
    uid = seed_profile(clean_db, "owner")
    r = api.patch("/api/v1/owners/me", json={"business_name": None}, headers=auth_headers(uid))
    assert r.status_code == 422


def test_avatar_path_must_be_in_own_folder(api, clean_db):
    uid = seed_profile(clean_db, "customer")
    h = auth_headers(uid)
    ok = api.patch("/api/v1/profiles/me", json={"avatar_path": f"{uid}/a1b2.webp"}, headers=h)
    assert ok.status_code == 200 and ok.json()["avatar_path"] == f"{uid}/a1b2.webp"
    bad = api.patch("/api/v1/profiles/me", json={"avatar_path": f"{uuid.uuid4()}/x.webp"}, headers=h)
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_AVATAR_PATH"


def test_users_only_ever_see_and_change_their_own_data(api, clean_db):
    a = seed_profile(clean_db, "owner", name="Owner A", business_name="Biz A")
    b = seed_profile(clean_db, "owner", name="Owner B", business_name="Biz B")
    ha, hb = auth_headers(a), auth_headers(b)

    assert api.get("/api/v1/owners/me", headers=ha).json()["business_name"] == "Biz A"
    assert api.get("/api/v1/owners/me", headers=hb).json()["business_name"] == "Biz B"

    # Passing someone else's id anywhere has no effect: identity comes from the token only.
    r = api.patch(
        "/api/v1/owners/me",
        json={"business_name": "A renamed"},
        headers=ha,
        params={"user_id": str(b), "owner_id": str(b)},
    )
    assert r.status_code == 200 and r.json()["profile"]["id"] == str(a)
    assert api.get("/api/v1/owners/me", headers=hb).json()["business_name"] == "Biz B"
    rows = sql(clean_db, "SELECT business_name FROM public.owner_profiles WHERE user_id=$1", b)
    assert rows[0]["business_name"] == "Biz B"

    # No path takes another user's id at all.
    assert api.get(f"/api/v1/owners/{b}", headers=ha).status_code in (404, 405)
    assert api.get(f"/api/v1/profiles/{b}", headers=ha).status_code in (404, 405)


def test_updates_are_audited(api, clean_db):
    uid = seed_profile(clean_db, "customer")
    api.patch("/api/v1/profiles/me", json={"full_name": "Changed"}, headers=auth_headers(uid))
    rows = sql(clean_db, "SELECT action, actor_id, actor_role FROM public.audit_logs")
    assert [(r["action"], r["actor_id"], r["actor_role"]) for r in rows] == [
        ("profile.updated", uid, "customer")
    ]
