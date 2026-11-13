"""Load clearly-labelled DEMO venues so the mobile app (customer role) has something to browse in development.

    python -m scripts.seed_demo_venues --owner-email owner@example.com

* Refuses to run when ENVIRONMENT=production.
* Needs an EXISTING owner account (sign one up through the mobile app (choose "Venue owner") / Supabase first) and the
  reference data (`python -m scripts.seed_reference_data`).
* Every demo venue name ends in "(Demo)". They have no images (the app shows its placeholder),
  no ratings and no reviews: nothing here fabricates social proof. Prices are invented sample
  values. Re-running does not duplicate venues. `--remove` deletes them again.
"""

import argparse
import asyncio
import sys

import asyncpg

from app.core.config import get_settings

DEMO = [  # name, city, lat, lng, address, price_paise, category slugs, amenity slugs, description
    ("Smash Point Badminton (Demo)", "Bengaluru", 12.9352, 77.6245, "80 Feet Rd, Koramangala", 40000,
     ["badminton"], ["parking", "changing-room", "drinking-water", "floodlights"],
     "Indoor wooden-floor badminton courts. Sample listing for development."),
    ("Baseline Tennis Club (Demo)", "Bengaluru", 12.9716, 77.5946, "Cubbon Park Rd, Central Bengaluru", 90000,
     ["tennis"], ["parking", "shower", "equipment-rental", "floodlights"],
     "Clay and hard courts with coaching. Sample listing for development."),
    ("Aqua Lap Swimming Pool (Demo)", "Mumbai", 19.1197, 72.8464, "Andheri West", 35000,
     ["swimming"], ["changing-room", "shower", "lockers", "first-aid"],
     "25 m heated pool with lap lanes. Sample listing for development."),
    ("IronWorks Gym (Demo)", "Pune", 18.5204, 73.8567, "FC Road, Shivajinagar", 25000,
     ["gym"], ["shower", "lockers", "air-conditioning", "wifi"],
     "Strength and cardio floor. Sample listing for development."),
    ("Prana Yoga Studio (Demo)", "Hyderabad", 17.4239, 78.4738, "Jubilee Hills", 30000,
     ["yoga"], ["changing-room", "drinking-water", "air-conditioning"],
     "Daily drop-in classes. Sample listing for development."),
    ("Turf Arena Football & Cricket (Demo)", "Delhi", 28.5355, 77.2100, "Saket", 120000,
     ["football", "cricket"], ["parking", "floodlights", "washroom", "cafe"],
     "5-a-side turf with nets. Sample listing for development."),
]  # fmt: skip


async def run(dsn: str, owner_email: str, remove: bool) -> str:
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        async with conn.transaction():
            if remove:
                n = await conn.execute("DELETE FROM public.venues WHERE name LIKE '% (Demo)'")
                return f"Removed demo venues ({n})."
            owner = await conn.fetchval(
                "SELECT p.id FROM public.profiles p WHERE lower(p.email)=lower($1) AND p.role='owner'",
                owner_email,
            )
            if owner is None:
                raise SystemExit(f"No owner profile with e-mail {owner_email!r}. Sign up an owner first.")
            created = 0
            for name, city, lat, lng, addr, price, cats, ams, desc in DEMO:
                city_id = await conn.fetchval(
                    "SELECT id FROM public.cities WHERE name=$1 AND country_code='IN'", city
                )
                if city_id is None:
                    raise SystemExit(f"City {city!r} missing. Run: python -m scripts.seed_reference_data")
                if await conn.fetchval("SELECT 1 FROM public.venues WHERE name=$1", name):
                    continue
                venue = await conn.fetchval(
                    "INSERT INTO public.venues (owner_id, city_id, name, description, address_line, latitude, "
                    "longitude, timezone, status, published_at, starting_price_paise) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,'Asia/Kolkata','published', now(), $8) RETURNING id",
                    owner, city_id, name, desc, addr, lat, lng, price,
                )  # fmt: skip
                await conn.execute(
                    "INSERT INTO public.venue_categories SELECT $1, id FROM public.categories WHERE slug = ANY($2)",
                    venue,
                    cats,
                )
                await conn.execute(
                    "INSERT INTO public.venue_amenities SELECT $1, id FROM public.amenities WHERE slug = ANY($2)",
                    venue,
                    ams,
                )
                created += 1
            return f"{created} demo venues created ({len(DEMO) - created} already existed)."
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--owner-email", help="E-mail of an existing owner account")
    parser.add_argument("--remove", action="store_true", help="Delete the demo venues")
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment == "production":
        sys.exit("Refusing to seed demo data when ENVIRONMENT=production.")
    if not args.remove and not args.owner_email:
        parser.error("--owner-email is required unless --remove is given")
    secret = settings.alembic_database_url or settings.database_url
    if secret is None:
        sys.exit("No database configured: set DATABASE_URL (or ALEMBIC_DATABASE_URL) in backend/.env")
    dsn = secret.get_secret_value().replace("postgresql+asyncpg://", "postgresql://")
    print(asyncio.run(run(dsn, args.owner_email or "", args.remove)))


if __name__ == "__main__":
    main()
