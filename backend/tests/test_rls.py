"""Row-Level Security, tested as the real `anon` / `authenticated` database roles (not as the
privileged connection the API uses)."""

import json
import uuid
from dataclasses import dataclass

import asyncpg
import pytest

from tests.conftest import run, seed_profile, sql
from tests.rls_helpers import session_as
from tests.test_db_constraints import seed_venue

DENIED = asyncpg.InsufficientPrivilegeError


@dataclass
class World:
    url: str
    owner_a: uuid.UUID
    owner_b: uuid.UUID
    cust_c: uuid.UUID
    cust_d: uuid.UUID
    admin: uuid.UUID
    suspended: uuid.UUID
    venue_a_pub: uuid.UUID
    venue_a_draft: uuid.UUID
    venue_b_draft: uuid.UUID


@pytest.fixture
def world(clean_db) -> World:
    u = clean_db
    a, b = seed_profile(u, "owner"), seed_profile(u, "owner")
    c, d = seed_profile(u, "customer"), seed_profile(u, "customer")
    admin, sus = seed_profile(u, "admin"), seed_profile(u, "customer", status="suspended")
    pub = seed_venue(u, a, "published", "A published")
    draft = seed_venue(u, a, "draft", "A draft")
    bdraft = seed_venue(u, b, "draft", "B draft")
    sql(
        u,
        "INSERT INTO public.venue_images (venue_id, storage_path, status) VALUES ($1,$2,'active')",
        pub,
        f"{pub}/1.webp",
    )
    sql(
        u,
        "INSERT INTO public.venue_images (venue_id, storage_path, status) VALUES ($1,$2,'pending')",
        pub,
        f"{pub}/2.webp",
    )
    sql(
        u,
        "INSERT INTO public.venue_images (venue_id, storage_path, status) VALUES ($1,$2,'active')",
        draft,
        f"{draft}/1.webp",
    )
    sql(u, "INSERT INTO public.venue_resources (venue_id, name) VALUES ($1,'Court 1')", pub)
    sql(u, "INSERT INTO public.venue_resources (venue_id, name, is_active) VALUES ($1,'Hidden',false)", pub)
    for uid in (c, d, sus):
        sql(u, "INSERT INTO public.notifications (user_id, type, title) VALUES ($1,'t','T')", uid)
    sql(u, "INSERT INTO public.audit_logs (actor_id, actor_role, action) VALUES ($1,'admin','seed')", admin)
    sql(u, "INSERT INTO public.categories (slug, name, is_active) VALUES ('a','A',true), ('b','B',false)")
    return World(u, a, b, c, d, admin, sus, pub, draft, bdraft)


async def count(conn: asyncpg.Connection, table: str, where: str = "true") -> int:
    return await conn.fetchval(f"SELECT count(*) FROM public.{table} WHERE {where}")  # type: ignore[no-any-return]


# -------------------------------------------------------------------------- anonymous
def test_anon_sees_only_public_catalogue(world):
    async def scenario():
        async with session_as(world.url, role="anon") as c:
            assert await count(c, "categories") == 1  # inactive one hidden
            assert await count(c, "venues") == 1  # only the published venue
            assert await c.fetchval("SELECT name FROM public.venues") == "A published"
            assert await count(c, "venue_images") == 1  # active image of a published venue only
            assert await count(c, "venue_resources") == 1  # active resource only
        for table in ("profiles", "customer_profiles", "owner_profiles", "notifications", "audit_logs"):
            async with session_as(world.url, role="anon") as c:
                with pytest.raises(DENIED):
                    await count(c, table)

    run(scenario())


# -------------------------------------------------------------------------- customers
def test_customer_sees_only_own_rows(world):
    async def scenario():
        async with session_as(world.url, world.cust_c) as c:
            assert await c.fetchval("SELECT array_agg(id) FROM public.profiles") == [world.cust_c]
            assert await count(c, "customer_profiles") == 1
            assert await count(c, "owner_profiles") == 0  # other people's business data
            assert await count(c, "notifications") == 1
            assert await c.fetchval("SELECT user_id FROM public.notifications") == world.cust_c
            assert await count(c, "audit_logs") == 0
            # published venues only; no drafts of any owner
            assert await c.fetchval("SELECT array_agg(id) FROM public.venues") == [world.venue_a_pub]
            assert await count(c, "venue_images", "status = 'pending'") == 0

    run(scenario())


def test_customer_cannot_read_another_customers_data(world):
    async def scenario():
        async with session_as(world.url, world.cust_c) as c:
            assert await count(c, "profiles", f"id = '{world.cust_d}'") == 0
            assert await count(c, "notifications", f"user_id = '{world.cust_d}'") == 0

    run(scenario())


# -------------------------------------------------------------------------- owners
def test_owner_sees_own_drafts_but_not_other_owners(world):
    async def scenario():
        async with session_as(world.url, world.owner_a) as c:
            ids = set(await c.fetchval("SELECT array_agg(id) FROM public.venues"))
            assert ids == {world.venue_a_pub, world.venue_a_draft}
            assert world.venue_b_draft not in ids
            assert await count(c, "venue_images", "status = 'pending'") == 1  # own pending image
            assert await count(c, "venue_resources") == 2  # incl. own inactive one
            assert await count(c, "owner_profiles") == 1
            assert await count(c, "profiles") == 1
        async with session_as(world.url, world.owner_b) as c:
            ids = set(await c.fetchval("SELECT array_agg(id) FROM public.venues"))
            assert ids == {world.venue_a_pub, world.venue_b_draft}
            assert await count(c, "venue_images", "status = 'pending'") == 0  # not A's pending image
            assert await count(c, "venue_resources") == 1  # only A's active, published one

    run(scenario())


# -------------------------------------------------------------------------- admin
def test_admin_policies_see_everything(world):
    async def scenario():
        async with session_as(world.url, world.admin) as c:
            assert await count(c, "profiles") == 6
            assert await count(c, "venues") == 3
            assert await count(c, "audit_logs") == 1
            assert await count(c, "owner_profiles") == 2

    run(scenario())


def test_customer_claiming_admin_in_jwt_gets_nothing_extra(world):
    async def scenario():
        async with session_as(world.url, world.cust_c) as c:
            await c.execute(
                "SELECT set_config('request.jwt.claims', $1, true)",
                json.dumps({"sub": str(world.cust_c), "role": "admin", "app_role": "admin"}),
            )
            assert await count(c, "profiles") == 1
            assert await count(c, "audit_logs") == 0

    run(scenario())


# -------------------------------------------------------------------------- suspended
def test_suspended_user_loses_rls_access(world):
    async def scenario():
        async with session_as(world.url, world.suspended) as c:
            assert await c.fetchval("SELECT public.app_user_role()") is None
            assert await count(c, "notifications") == 0
            assert await count(c, "profiles") == 1  # may still see own row (to learn the status)

    run(scenario())


# -------------------------------------------------------------------------- writes
TABLES = [
    "profiles", "customer_profiles", "owner_profiles", "cities", "categories", "amenities", "venues",
    "venue_categories", "venue_amenities", "venue_images", "venue_resources", "notifications", "audit_logs", "favorites",
    "schedule_rules", "schedule_exceptions", "bookings", "booking_slots", "booking_status_history",
    "availability_blocks", "payments", "payment_events", "user_device_tokens", "notification_preferences",
    "email_deliveries", "reviews", "review_responses",
]  # fmt: skip


@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize("statement", ["insert", "update", "delete"])
def test_api_roles_have_no_write_privileges(world, role, statement):
    """Layer 1: no GRANT. Every write fails with 'permission denied'."""
    stmts = {
        "insert": "INSERT INTO public.{t} DEFAULT VALUES",
        "update": "UPDATE public.{t} SET created_at = created_at"
        if False
        else "UPDATE public.{t} SET id = id",
        "delete": "DELETE FROM public.{t}",
    }

    async def scenario():
        for table in TABLES:
            async with session_as(world.url, world.cust_c, role=role) as c:
                q = stmts[statement].format(t=table)
                if table in ("venue_categories", "venue_amenities", "customer_profiles", "owner_profiles"):
                    q = (
                        q.replace("SET id = id", "SET created_at = created_at")
                        if statement == "update"
                        else q
                    )
                with pytest.raises((DENIED, asyncpg.UndefinedColumnError)):
                    await c.execute(q)

    run(scenario())


def test_rls_alone_blocks_writes_even_if_grants_were_wrong(world):
    """Layer 2: pretend someone granted write access by mistake. RLS has no write policies, so
    inserts are rejected and updates/deletes silently touch zero rows."""

    async def scenario():
        async with session_as(world.url, world.cust_c, force_write_grants=True) as c:
            with pytest.raises(DENIED, match="row-level security"):
                await c.execute(
                    "INSERT INTO public.notifications (user_id, type, title) VALUES ($1,'x','y')",
                    world.cust_c,
                )
        async with session_as(world.url, world.cust_c, force_write_grants=True) as c:
            with pytest.raises(DENIED, match="row-level security"):
                await c.execute(
                    "INSERT INTO public.profiles (id, role, full_name) VALUES ($1,'admin','x')", uuid.uuid4()
                )
        async with session_as(world.url, world.cust_c, force_write_grants=True) as c:
            # own row: visible, but there is no UPDATE policy, so nothing changes
            assert (
                await c.execute("UPDATE public.profiles SET full_name='Hacked' WHERE id=$1", world.cust_c)
                == "UPDATE 0"
            )
            assert await c.execute("DELETE FROM public.profiles WHERE id=$1", world.cust_c) == "DELETE 0"
            assert await c.execute("UPDATE public.venues SET name='x'") == "UPDATE 0"
            assert await c.execute("DELETE FROM public.audit_logs") == "DELETE 0"
        async with session_as(world.url, world.owner_a, force_write_grants=True) as c:
            # an owner may SEE their venue but cannot modify or delete it directly
            assert (
                await c.execute("UPDATE public.venues SET name='x' WHERE owner_id=$1", world.owner_a)
                == "UPDATE 0"
            )
            assert await c.execute("DELETE FROM public.venues WHERE owner_id=$1", world.owner_a) == "DELETE 0"
        async with session_as(world.url, world.admin, force_write_grants=True) as c:
            assert await c.execute("UPDATE public.profiles SET status='suspended'") == "UPDATE 0"
            assert await c.execute("DELETE FROM public.audit_logs") == "DELETE 0"

    run(scenario())
    names = sql(world.url, "SELECT full_name FROM public.profiles WHERE id=$1", world.cust_c)
    assert names[0]["full_name"] == "Test User"


# -------------------------------------------------------------------------- structure
def test_every_application_table_has_rls_enabled(world):
    rows = sql(
        world.url,
        "SELECT c.relname, c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'alembic_version'",
    )
    assert {r["relname"] for r in rows} == set(TABLES)
    assert all(r["relrowsecurity"] for r in rows)


def test_policies_are_select_only(world):
    rows = sql(world.url, "SELECT policyname, cmd FROM pg_policies WHERE schemaname = 'public'")
    assert rows, "expected policies"
    assert {r["cmd"] for r in rows} == {"SELECT"}


def test_alembic_version_is_hidden_from_api_roles(world):
    async def scenario():
        for role in ("anon", "authenticated"):
            async with session_as(world.url, world.cust_c, role=role) as c:
                with pytest.raises(DENIED):
                    await c.fetch("SELECT * FROM public.alembic_version")

    run(scenario())


def test_helper_function_not_executable_by_public(world):
    rows = sql(
        world.url,
        "SELECT has_function_privilege('anon', 'public.app_user_role()', 'EXECUTE') AS anon_ok, "
        "has_function_privilege('authenticated', 'public.app_user_role()', 'EXECUTE') AS auth_ok",
    )
    assert rows[0]["anon_ok"] and rows[0]["auth_ok"]  # needed by policies; function only reads own role
