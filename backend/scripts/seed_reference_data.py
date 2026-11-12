"""Idempotently load reference data: categories, amenities and cities. Safe for every environment.

    python -m scripts.seed_reference_data

This is operator-curated catalogue data (architecture section 7), not demo content. Re-running
updates names/ordering and never deletes anything. The customer app reads all of it from the API;
nothing here is compiled into the Flutter apps. City list is an ASSUMPTION (India-first, open
question N1) and should be reviewed before launch.
"""

import asyncio
import sys

import asyncpg

from app.core.config import get_settings

CATEGORIES = [  # slug, name, icon_key
    ("badminton", "Badminton", "badminton"),
    ("tennis", "Tennis", "tennis"),
    ("swimming", "Swimming", "swimming"),
    ("gym", "Gym", "gym"),
    ("yoga", "Yoga", "yoga"),
    ("cricket", "Cricket", "cricket"),
    ("football", "Football", "football"),
    ("basketball", "Basketball", "basketball"),
    ("table-tennis", "Table Tennis", "table_tennis"),
    ("squash", "Squash", "squash"),
    ("snooker", "Snooker", "snooker"),
    ("pickleball", "Pickleball", "pickleball"),
]
AMENITIES = [
    ("parking", "Parking", "parking"),
    ("changing-room", "Changing Room", "changing_room"),
    ("shower", "Shower", "shower"),
    ("drinking-water", "Drinking Water", "water"),
    ("floodlights", "Floodlights", "floodlights"),
    ("equipment-rental", "Equipment Rental", "equipment"),
    ("first-aid", "First Aid", "first_aid"),
    ("cafe", "Café", "cafe"),
    ("wifi", "Wi-Fi", "wifi"),
    ("lockers", "Lockers", "lockers"),
    ("washroom", "Washroom", "washroom"),
    ("air-conditioning", "Air Conditioning", "ac"),
]
CITIES = [
    ("Bengaluru", "Karnataka"),
    ("Mumbai", "Maharashtra"),
    ("Delhi", "Delhi"),
    ("Hyderabad", "Telangana"),
    ("Chennai", "Tamil Nadu"),
    ("Pune", "Maharashtra"),
    ("Kolkata", "West Bengal"),
    ("Ahmedabad", "Gujarat"),
    ("Gurugram", "Haryana"),
    ("Jaipur", "Rajasthan"),
]


async def seed(dsn: str) -> str:
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        async with conn.transaction():
            for order, (slug, name, icon) in enumerate(CATEGORIES, 1):
                await conn.execute(
                    "INSERT INTO public.categories (slug, name, icon_key, sort_order) VALUES ($1,$2,$3,$4) "
                    "ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, icon_key=EXCLUDED.icon_key, "
                    "sort_order=EXCLUDED.sort_order",
                    slug, name, icon, order,
                )  # fmt: skip
            for order, (slug, name, icon) in enumerate(AMENITIES, 1):
                await conn.execute(
                    "INSERT INTO public.amenities (slug, name, icon_key, sort_order) VALUES ($1,$2,$3,$4) "
                    "ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name, icon_key=EXCLUDED.icon_key, "
                    "sort_order=EXCLUDED.sort_order",
                    slug, name, icon, order,
                )  # fmt: skip
            added = 0
            for name, state in CITIES:
                exists = await conn.fetchval(
                    "SELECT 1 FROM public.cities WHERE lower(name)=lower($1) AND country_code='IN'", name
                )
                if not exists:
                    await conn.execute(
                        "INSERT INTO public.cities (name, state, country_code) VALUES ($1,$2,'IN')",
                        name,
                        state,
                    )
                    added += 1
        return f"{len(CATEGORIES)} categories, {len(AMENITIES)} amenities upserted; {added} new cities."
    finally:
        await conn.close()


def main() -> None:
    settings = get_settings()
    secret = settings.alembic_database_url or settings.database_url
    if secret is None:
        sys.exit("No database configured: set DATABASE_URL (or ALEMBIC_DATABASE_URL) in backend/.env")
    print(asyncio.run(seed(secret.get_secret_value().replace("postgresql+asyncpg://", "postgresql://"))))


if __name__ == "__main__":
    main()
