"""Shared fixtures.

DB-backed tests need a PostgreSQL SUPERUSER URL in TEST_DATABASE_URL (a throwaway server:
`scripts/dev_pg.sh start`, `docker compose up -d db`, or a CI service container). Each test
session creates its own database, loads the local Supabase stub, runs `alembic upgrade head`
and drops the database afterwards. Without TEST_DATABASE_URL those tests are SKIPPED and the
skip reason says so; they are never silently counted as passed.
"""

import asyncio
import os
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import asyncpg
import jwt
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import Settings, get_settings
from app.main import create_app

# Tests must never pick up a developer's real .env or credentials.
for _k in list(os.environ):
    if _k.startswith(("DATABASE_URL", "SUPABASE_", "ALEMBIC_")):
        os.environ.pop(_k)

BACKEND = Path(__file__).resolve().parents[1]
STUB_SQL = BACKEND.parent / "supabase" / "local" / "supabase_stub.sql"

JWT_SECRET = "test-secret-" + "x" * 40
SUPABASE_URL = "https://testproject.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"

CLEAN_SQL = """
TRUNCATE public.email_deliveries, public.notification_preferences, public.user_device_tokens, public.payment_events, public.payments, public.booking_status_history, public.booking_slots, public.bookings, public.availability_blocks, public.schedule_exceptions, public.schedule_rules, public.favorites, public.audit_logs, public.notifications, public.venue_resources, public.venue_images,
         public.venue_amenities, public.venue_categories, public.venues, public.owner_profiles,
         public.customer_profiles, public.profiles, public.cities, public.categories,
         public.amenities, auth.users CASCADE;
DELETE FROM storage.objects;
"""


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"environment": "test", "log_json": False, "background_sweep_seconds": 0}
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _admin_exec(url: str, sql: str) -> None:
    conn = await asyncpg.connect(url.replace("+asyncpg", ""))
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


def with_database(url: str, name: str) -> str:
    return make_url(url).set(database=name).render_as_string(hide_password=False)


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    os.environ["ALEMBIC_DATABASE_URL"] = url
    get_settings.cache_clear()
    return cfg


def require_server() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set: start a throwaway Postgres (scripts/dev_pg.sh start)")
    return url


def create_migrated_database(server_url: str) -> str:
    name = f"zuruv_test_{uuid.uuid4().hex[:8]}"
    run(_admin_exec(server_url, f'CREATE DATABASE "{name}"'))
    url = with_database(server_url, name)
    run(_admin_exec(url, STUB_SQL.read_text()))
    command.upgrade(alembic_config(url), "head")
    return url


def drop_database(server_url: str, url: str) -> None:
    name = make_url(url).database
    run(_admin_exec(server_url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@pytest.fixture(scope="session")
def db_url() -> Iterator[str]:
    server = require_server()
    url = create_migrated_database(server)
    yield url
    drop_database(server, url)
    os.environ.pop("ALEMBIC_DATABASE_URL", None)


@pytest.fixture
def clean_db(db_url: str) -> str:
    run(_admin_exec(db_url, CLEAN_SQL))
    return db_url


# ---------------------------------------------------------------------------- data helpers
async def _fetch(url: str, sql: str, *args: object) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(url)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def sql(url: str, query: str, *args: object) -> list[asyncpg.Record]:
    return run(_fetch(url, query, *args))  # type: ignore[no-any-return]


def make_auth_user(url: str, email: str | None = None, phone: str | None = None) -> uuid.UUID:
    uid = uuid.uuid4()
    sql(url, "INSERT INTO auth.users (id, email, phone) VALUES ($1, $2, $3)", uid, email, phone)
    return uid


def seed_profile(
    url: str,
    role: str,
    *,
    name: str = "Test User",
    status: str = "active",
    email: str | None = None,
    business_name: str = "Test Business",
) -> uuid.UUID:
    email = email or f"{uuid.uuid4().hex[:8]}@example.com"
    uid = make_auth_user(url, email)
    sql(
        url,
        "INSERT INTO public.profiles (id, role, status, full_name, email) VALUES ($1, $2, $3, $4, $5)",
        uid, role, status, name, email,
    )  # fmt: skip
    if role == "customer":
        sql(url, "INSERT INTO public.customer_profiles (user_id) VALUES ($1)", uid)
    elif role == "owner":
        sql(
            url,
            "INSERT INTO public.owner_profiles (user_id, business_name) VALUES ($1, $2)",
            uid,
            business_name,
        )
    return uid


def make_token(
    sub: uuid.UUID | str,
    *,
    email: str | None = "user@example.com",
    phone: str | None = None,
    aal: str = "aal1",
    exp_in: int = 3600,
    secret: str = JWT_SECRET,
    **extra: object,
) -> str:
    claims: dict[str, object] = {
        "sub": str(sub),
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_in,
        "role": "authenticated",
        "email": email,
        "phone": phone or "",
        "aal": aal,
        "app_metadata": {"provider": "email"},
        "user_metadata": {},
    }
    claims.update(extra)
    return jwt.encode(claims, secret, algorithm="HS256")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def auth_headers(uid: uuid.UUID, **kw: Any) -> dict[str, str]:
    return bearer(make_token(uid, **kw))


@pytest.fixture
def client() -> Iterator[TestClient]:
    """App with NO database configured (for tests that never reach the database)."""
    app = create_app(make_settings(supabase_jwt_secret=JWT_SECRET, supabase_url=SUPABASE_URL))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def api(clean_db: str) -> Iterator[TestClient]:
    """App wired to the migrated test database with JWT verification configured."""
    app = create_app(
        make_settings(supabase_jwt_secret=JWT_SECRET, supabase_url=SUPABASE_URL, database_url=clean_db)
    )
    with TestClient(app) as c:
        yield c
