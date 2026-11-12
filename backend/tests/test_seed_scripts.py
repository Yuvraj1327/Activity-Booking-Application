import asyncio

import pytest

from scripts import seed_demo_venues, seed_reference_data
from tests.conftest import seed_profile, sql


def test_seed_scripts_are_idempotent_and_removable(clean_db):
    owner = seed_profile(clean_db, "owner", email="owner@example.com")
    assert owner
    asyncio.run(seed_reference_data.seed(clean_db))
    first = asyncio.run(seed_reference_data.seed(clean_db))
    assert "0 new cities" in first
    assert sql(clean_db, "SELECT count(*) AS n FROM public.categories")[0]["n"] == len(
        seed_reference_data.CATEGORIES
    )

    assert "6 demo venues created" in asyncio.run(seed_demo_venues.run(clean_db, "owner@example.com", False))
    assert "0 demo venues created" in asyncio.run(seed_demo_venues.run(clean_db, "owner@example.com", False))
    rows = sql(clean_db, "SELECT status, rating_count, starting_price_paise FROM public.venues")
    assert len(rows) == 6 and all(r["status"] == "published" and r["rating_count"] == 0 for r in rows)
    assert sql(clean_db, "SELECT count(*) AS n FROM public.venue_images")[0]["n"] == 0
    asyncio.run(seed_demo_venues.run(clean_db, "", True))
    assert sql(clean_db, "SELECT count(*) AS n FROM public.venues")[0]["n"] == 0


def test_demo_seed_needs_an_existing_owner(clean_db):
    asyncio.run(seed_reference_data.seed(clean_db))
    with pytest.raises(SystemExit):
        asyncio.run(seed_demo_venues.run(clean_db, "nobody@example.com", False))
