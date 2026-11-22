import pytest

from scripts.create_admin import promote
from tests.conftest import auth_headers, make_auth_user, run, seed_profile, sql


def test_promote_existing_auth_user_to_admin(api, clean_db):
    uid = make_auth_user(clean_db, "boss@example.com")
    assert "now an admin" in run(promote(clean_db, "BOSS@example.com", "The Boss"))
    row = sql(clean_db, "SELECT role, status FROM public.profiles WHERE id=$1", uid)[0]
    assert (row["role"], row["status"]) == ("admin", "active")
    assert api.get("/api/v1/admin/me", headers=auth_headers(uid, aal="aal2")).status_code == 200
    assert sql(clean_db, "SELECT action, actor_role FROM public.audit_logs")[0]["action"] == "admin.created"


def test_promote_is_idempotent_and_refuses_other_roles(clean_db):
    make_auth_user(clean_db, "a@example.com")
    run(promote(clean_db, "a@example.com", "A"))
    assert "already an admin" in run(promote(clean_db, "a@example.com", "A"))
    cust = seed_profile(clean_db, "customer", email="c@example.com")
    with pytest.raises(SystemExit, match="immutable"):
        run(promote(clean_db, "c@example.com", "C"))
    assert sql(clean_db, "SELECT role FROM public.profiles WHERE id=$1", cust)[0]["role"] == "customer"


def test_unknown_email_is_refused(clean_db):
    with pytest.raises(SystemExit, match="No auth user"):
        run(promote(clean_db, "nobody@example.com", "N"))


def test_new_admin_has_no_role_until_assigned_and_role_flag_assigns(api, clean_db):
    a = make_auth_user(clean_db, "norole@example.com")
    assert "NO role" in run(promote(clean_db, "norole@example.com", "No Role"))
    h = auth_headers(a, aal="aal2")
    assert api.get("/api/v1/admin/me", headers=h).json()["permissions"] == []
    assert api.get("/api/v1/admin/dashboard", headers=h).json()["code"] == "ADMIN_ROLE_REQUIRED"
    b = make_auth_user(clean_db, "boss2@example.com")
    assert "super_admin" in run(promote(clean_db, "boss2@example.com", "Boss", "super_admin"))
    assert api.get("/api/v1/admin/dashboard", headers=auth_headers(b, aal="aal2")).status_code == 200
    with pytest.raises(SystemExit, match="No admin role"):
        make_auth_user(clean_db, "x@example.com")
        run(promote(clean_db, "x@example.com", "X", "nonexistent"))
