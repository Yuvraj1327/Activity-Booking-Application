"""Seeding helpers shared by the Step 6 tests."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import JWT_SECRET, SUPABASE_URL, auth_headers, make_settings, seed_profile, sql

IST = timezone(timedelta(hours=5, minutes=30))
API = "/api/v1"


@contextmanager
def make_app(db: str, **settings: Any) -> Iterator[TestClient]:
    app = create_app(
        make_settings(supabase_jwt_secret=JWT_SECRET, supabase_url=SUPABASE_URL, database_url=db, **settings)
    )
    with TestClient(app) as c:
        yield c


def future_day(days: int = 3) -> date:
    return datetime.now(IST).date() + timedelta(days=days)


def iso(day: date, hour: int, minute: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST).isoformat()


def seed_world(
    db: str, *, slot_minutes: int | None = 60, price: int | None = 50000, hours: bool = True
) -> dict[str, Any]:
    owner = seed_profile(db, "owner")
    customer = seed_profile(db, "customer", name="Cathy Customer")
    city = sql(
        db,
        "INSERT INTO public.cities (name, country_code) VALUES ($1,'IN') RETURNING id",
        uuid.uuid4().hex[:6],
    )[0]["id"]
    venue = sql(
        db,
        "INSERT INTO public.venues (owner_id, city_id, name, latitude, longitude, timezone, status, "
        "published_at) VALUES ($1,$2,'Ace Arena',12.9,77.6,'Asia/Kolkata','published', now()) RETURNING id",
        owner, city,
    )[0]["id"]  # fmt: skip
    cat = sql(
        db,
        "INSERT INTO public.categories (slug, name) VALUES ($1,'Cricket') RETURNING id",
        uuid.uuid4().hex[:8],
    )
    sql(db, "INSERT INTO public.venue_categories (venue_id, category_id) VALUES ($1,$2)", venue, cat[0]["id"])
    if hours:
        for wd in range(7):
            sql(
                db,
                "INSERT INTO public.schedule_rules (venue_id, weekday, opens_at, closes_at) "
                "VALUES ($1,$2,'06:00','22:00')",
                venue, wd,
            )  # fmt: skip
    resource = sql(
        db,
        "INSERT INTO public.venue_resources (venue_id, name, slot_minutes, slot_price_paise) "
        "VALUES ($1,'Court 1',$2,$3) RETURNING id",
        venue, slot_minutes, price,
    )[0]["id"]  # fmt: skip
    return {
        "owner": owner,
        "customer": customer,
        "venue": venue,
        "resource": resource,
        "owner_h": auth_headers(owner),
        "customer_h": auth_headers(customer),
    }


def new_customer(db: str, name: str = "Other Person") -> tuple[uuid.UUID, dict[str, str]]:
    uid = seed_profile(db, "customer", name=name)
    return uid, auth_headers(uid)


def book(api: TestClient, w: dict[str, Any], starts_at: str, *, key: str | None = None, headers: Any = None):
    h = dict(headers or w["customer_h"])
    if key:
        h["Idempotency-Key"] = key
    return api.post(
        f"{API}/bookings", json={"resource_id": str(w["resource"]), "starts_at": starts_at}, headers=h
    )


def now_utc() -> datetime:
    return datetime.now(UTC)
