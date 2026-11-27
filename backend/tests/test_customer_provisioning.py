"""A customer account always has the `customer_profiles` row that bookings reference.

Production bug: a `profiles` row with role customer but no `customer_profiles` row passed authentication,
then POST /bookings failed with the foreign key `bookings_customer_id_fkey` (HTTP 500).
"""

import os
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import pytest

from alembic import command
from tests.booking_helpers import API, book, future_day, iso, make_app, seed_world
from tests.conftest import (
    alembic_config,
    auth_headers,
    create_migrated_database,
    drop_database,
    make_auth_user,
    require_server,
    seed_profile,
    sql,
)

HOLD = {"booking_hold_minutes": 10}


def _orphan_customer(db: str, name: str = "Orphan Customer") -> tuple[uuid.UUID, dict[str, str]]:
    """The broken state: a customer profile without its customer_profiles row."""
    uid = seed_profile(db, "customer", name=name)
    sql(db, "DELETE FROM public.customer_profiles WHERE user_id = $1", uid)
    return uid, auth_headers(uid)


def _customer_rows(db: str, uid: uuid.UUID) -> int:
    return sql(db, "SELECT count(*) AS n FROM public.customer_profiles WHERE user_id = $1", uid)[0]["n"]


def test_existing_customer_without_customer_profile_can_book(clean_db):
    w = seed_world(clean_db)
    uid, h = _orphan_customer(clean_db)
    assert _customer_rows(clean_db, uid) == 0
    with make_app(clean_db, **HOLD) as api:
        r = book(api, w, iso(future_day(), 9), headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending_payment"
    assert _customer_rows(clean_db, uid) == 1
    row = sql(clean_db, "SELECT role FROM public.customer_profiles WHERE user_id = $1", uid)[0]
    assert row["role"] == "customer"
    assert sql(clean_db, "SELECT count(*) AS n FROM public.bookings WHERE customer_id = $1", uid)[0]["n"] == 1
    audit = sql(
        clean_db, "SELECT actor_role FROM public.audit_logs WHERE action = 'customer_profile.provisioned'"
    )
    assert [a["actor_role"] for a in audit] == ["system"]


def test_provisioning_keeps_existing_profile_data(clean_db):
    """A customer who already has a row keeps every value; nothing is overwritten."""
    w = seed_world(clean_db)
    uid = seed_profile(clean_db, "customer", name="Has Row")
    city = sql(
        clean_db, "INSERT INTO public.cities (name, country_code) VALUES ('Keepville','IN') RETURNING id"
    )[0]["id"]
    sql(clean_db, "UPDATE public.customer_profiles SET preferred_city_id = $2 WHERE user_id = $1", uid, city)
    with make_app(clean_db, **HOLD) as api:
        assert book(api, w, iso(future_day(), 9), headers=auth_headers(uid)).status_code == 201
    assert (
        sql(clean_db, "SELECT preferred_city_id FROM public.customer_profiles WHERE user_id=$1", uid)[0][
            "preferred_city_id"
        ]
        == city
    )
    assert (
        sql(
            clean_db,
            "SELECT count(*) AS n FROM public.audit_logs WHERE action = 'customer_profile.provisioned'",
        )[0]["n"]
        == 0
    )


def test_new_customer_registration_then_booking(clean_db):
    w = seed_world(clean_db)
    uid = make_auth_user(clean_db, "new@example.com")
    h = auth_headers(uid, email="new@example.com")
    with make_app(clean_db, **HOLD) as api:
        reg = api.post(f"{API}/auth/profile", json={"role": "customer", "full_name": "New Person"}, headers=h)
        assert reg.status_code == 201, reg.text
        assert _customer_rows(clean_db, uid) == 1
        assert book(api, w, iso(future_day(), 10), headers=h).status_code == 201
    assert uid == sql(clean_db, "SELECT customer_id FROM public.bookings")[0]["customer_id"]


def test_google_oauth_customer_registration_then_booking(clean_db):
    """Google sign-in: no phone, provider google, e-mail from the token. Same API path, same guarantee."""
    w = seed_world(clean_db)
    uid = make_auth_user(clean_db, "g.user@gmail.com")
    h = auth_headers(
        uid,
        email="g.user@gmail.com",
        app_metadata={"provider": "google", "providers": ["google"]},
        user_metadata={"full_name": "G User", "iss": "https://accounts.google.com"},
    )
    with make_app(clean_db, **HOLD) as api:
        reg = api.post(f"{API}/auth/profile", json={"role": "customer", "full_name": "G User"}, headers=h)
        assert reg.status_code == 201, reg.text
        assert reg.json()["role"] == "customer" and reg.json()["id"] == str(uid)
        assert _customer_rows(clean_db, uid) == 1
        assert book(api, w, iso(future_day(), 11), headers=h).status_code == 201


def test_repeated_registration_heals_missing_row_and_stays_idempotent(clean_db):
    uid, h = _orphan_customer(clean_db)
    with make_app(clean_db, **HOLD) as api:
        body = {"role": "customer", "full_name": "Orphan Customer"}
        first = api.post(f"{API}/auth/profile", json=body, headers=h)
        again = api.post(f"{API}/auth/profile", json=body, headers=h)
    assert first.status_code == 200 and again.status_code == 200  # profile already existed
    assert _customer_rows(clean_db, uid) == 1
    assert sql(clean_db, "SELECT count(*) AS n FROM public.profiles WHERE id = $1", uid)[0]["n"] == 1
    assert (
        sql(
            clean_db,
            "SELECT count(*) AS n FROM public.audit_logs WHERE action = 'customer_profile.provisioned'",
        )[0]["n"]
        == 1
    )


def test_repeated_bookings_do_not_duplicate_or_fail(clean_db):
    w = seed_world(clean_db)
    uid, h = _orphan_customer(clean_db)
    day = future_day()
    with make_app(clean_db, **HOLD) as api:
        codes = [book(api, w, iso(day, hr), headers=h).status_code for hr in (9, 10, 11)]
    assert codes == [201, 201, 201]
    assert _customer_rows(clean_db, uid) == 1


def test_concurrent_bookings_from_customer_without_profile(clean_db):
    """Several requests race to provision the same missing row: one row, no 500, one winner per slot."""
    w = seed_world(clean_db)
    uid, h = _orphan_customer(clean_db)
    day, n = future_day(), 8
    barrier = threading.Barrier(n)
    with ExitStack() as stack:
        clients = [stack.enter_context(make_app(clean_db, **HOLD)) for _ in range(n)]

        def go(i: int):
            barrier.wait()
            return book(clients[i], w, iso(day, 9), headers=h, key=f"race-key-{i:04d}")

        with ThreadPoolExecutor(max_workers=n) as pool:
            results = [f.result() for f in [pool.submit(go, i) for i in range(n)]]
    codes = Counter(r.status_code for r in results)
    assert codes == {201: 1, 409: n - 1}, [r.text for r in results]
    assert _customer_rows(clean_db, uid) == 1
    assert sql(clean_db, "SELECT count(*) AS n FROM public.bookings")[0]["n"] == 1


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owner_and_admin_cannot_book_and_get_no_customer_profile(clean_db, role):
    w = seed_world(clean_db)
    uid = seed_profile(clean_db, role)
    h = auth_headers(uid, aal="aal2")
    with make_app(clean_db, **HOLD) as api:
        r = book(api, w, iso(future_day(), 9), headers=h)
        q = api.post(
            f"{API}/bookings/quote",
            json={"resource_id": str(w["resource"]), "starts_at": iso(future_day(), 9)},
            headers=h,
        )
    assert r.status_code == 403 and r.json()["code"] == "INSUFFICIENT_ROLE"
    assert q.status_code == 403
    assert _customer_rows(clean_db, uid) == 0
    assert sql(clean_db, "SELECT count(*) AS n FROM public.bookings")[0]["n"] == 0


def test_service_refuses_non_customer_even_if_route_guard_is_bypassed(clean_db):
    """Defence in depth: the service itself never provisions a customer row for an owner."""
    from app.core.errors import PermissionDeniedError
    from app.database.session import Database
    from app.services.profiles import ProfileService
    from tests.conftest import make_settings, run

    owner = seed_profile(clean_db, "owner")

    async def attempt() -> None:
        db = Database(make_settings(database_url=clean_db))
        try:
            async for session in db.session():
                await ProfileService(session).ensure_customer_profile(owner)
        finally:
            await db.dispose()

    with pytest.raises(PermissionDeniedError) as exc:
        run(attempt())
    assert exc.value.code == "CUSTOMER_PROFILE_REQUIRED"
    assert _customer_rows(clean_db, owner) == 0


def test_provisioning_failure_is_an_application_error_not_a_500(clean_db, monkeypatch):
    from app.repositories import profiles as repo

    w = seed_world(clean_db)
    uid, h = _orphan_customer(clean_db)

    async def boom(self, user_id):
        from sqlalchemy.exc import OperationalError

        raise OperationalError("INSERT", {}, Exception("db down"))

    monkeypatch.setattr(repo.ProfileRepository, "insert_customer_profile_if_missing", boom)
    with make_app(clean_db, **HOLD) as api:
        r = book(api, w, iso(future_day(), 9), headers=h)
    assert r.status_code == 503 and r.json()["code"] == "CUSTOMER_PROFILE_UNAVAILABLE"
    assert sql(clean_db, "SELECT count(*) AS n FROM public.bookings")[0]["n"] == 0


# ---------------------------------------------------------------------------- repair migration
@pytest.fixture
def fresh_db():
    server = require_server()
    url = create_migrated_database(server)
    yield url
    drop_database(server, url)
    os.environ.pop("ALEMBIC_DATABASE_URL", None)


def test_repair_migration_backfills_only_customers_and_is_repeatable(fresh_db):
    cust = seed_profile(fresh_db, "customer", name="Broken Customer")
    keeps = seed_profile(fresh_db, "customer", name="Healthy Customer")
    owner = seed_profile(fresh_db, "owner")
    admin = seed_profile(fresh_db, "admin")
    suspended = seed_profile(fresh_db, "customer", name="Suspended", status="suspended")
    city = sql(
        fresh_db, "INSERT INTO public.cities (name, country_code) VALUES ('Keepville','IN') RETURNING id"
    )[0]["id"]
    sql(
        fresh_db, "UPDATE public.customer_profiles SET preferred_city_id = $2 WHERE user_id = $1", keeps, city
    )
    sql(fresh_db, "DELETE FROM public.customer_profiles WHERE user_id = ANY($1::uuid[])", [cust, suspended])

    cfg = alembic_config(fresh_db)
    command.downgrade(cfg, "0012")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0012")  # downgrade is a no-op for data
    command.upgrade(cfg, "head")  # running the repair again inserts nothing new

    rows = {r["user_id"] for r in sql(fresh_db, "SELECT user_id FROM public.customer_profiles")}
    assert rows == {cust, keeps, suspended}
    assert owner not in rows and admin not in rows
    assert (
        sql(fresh_db, "SELECT preferred_city_id FROM public.customer_profiles WHERE user_id=$1", keeps)[0][
            "preferred_city_id"
        ]
        == city
    )
    assert sql(fresh_db, "SELECT count(*) AS n FROM public.profiles")[0]["n"] == 5
    missing = sql(
        fresh_db,
        "SELECT count(*) AS n FROM public.profiles p WHERE p.role='customer' "
        "AND NOT EXISTS (SELECT 1 FROM public.customer_profiles c WHERE c.user_id = p.id)",
    )
    assert missing[0]["n"] == 0
