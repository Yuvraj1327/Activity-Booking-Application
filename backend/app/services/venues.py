from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.repositories.venues import VenueFilters, VenueRepository
from app.schemas.catalog import (
    AmenityOut,
    CategoryOut,
    VenueCard,
    VenueDetail,
    VenueImageOut,
    VenuePage,
)
from app.services.availability import AvailabilityService

AVAILABLE_TODAY_BATCH = 25
AVAILABLE_TODAY_SCAN_LIMIT = 150


def public_image_url(settings: Settings, storage_path: str | None) -> str | None:
    """Public URL of an object in the (public, backend-write-only) venue-images bucket."""
    if not storage_path or not settings.supabase_url:
        return None
    bucket = settings.supabase_storage_bucket_venue_images
    return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}/{storage_path}"


def _num(value: Decimal | float | None) -> float | None:
    return float(value) if value is not None else None


class VenueService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.repo = VenueRepository(session)
        self.session = session
        self.settings = settings

    def _card(self, row: Row[Any], slugs: list[str]) -> VenueCard:
        venue = row.Venue
        distance = _num(row.distance_km)
        return VenueCard(
            id=venue.id,
            name=venue.name,
            city_id=venue.city_id,
            city_name=row.city_name,
            address_line=venue.address_line,
            latitude=_num(venue.latitude),
            longitude=_num(venue.longitude),
            cover_image_url=public_image_url(self.settings, row.cover_path),
            categories=slugs,
            starting_price_paise=venue.starting_price_paise,
            currency=venue.currency,
            rating_avg=_num(venue.rating_avg),
            rating_count=venue.rating_count,
            distance_km=round(distance, 2) if distance is not None else None,
            is_favorite=bool(row.is_favorite),
        )

    async def _page(self, rows: Sequence[Row[Any]], limit: int, offset: int) -> VenuePage:
        has_more = len(rows) > limit
        rows = rows[:limit]
        slugs = await self.repo.category_slugs([r.Venue.id for r in rows])
        return VenuePage(
            items=[self._card(r, slugs.get(r.Venue.id, [])) for r in rows],
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    async def list_venues(self, f: VenueFilters, customer_id: UUID | None) -> VenuePage:
        if (f.lat is None) != (f.lng is None):
            raise ValidationFailedError("lat and lng must be sent together.", code="INVALID_LOCATION")
        if f.sort == "distance" and f.lat is None:
            raise ValidationFailedError("Sorting by distance needs lat and lng.", code="LOCATION_REQUIRED")
        if f.radius_km is not None and f.lat is None:
            raise ValidationFailedError("radius_km needs lat and lng.", code="LOCATION_REQUIRED")
        if f.min_price is not None and f.max_price is not None and f.min_price > f.max_price:
            raise ValidationFailedError("min_price cannot exceed max_price.", code="INVALID_PRICE_RANGE")
        if f.available_today:
            return await self._available_today(f, customer_id)
        return await self._page(await self.repo.search(f, customer_id), f.limit, f.offset)

    async def _available_today(self, f: VenueFilters, customer_id: UUID | None) -> VenuePage:
        """Venues with at least one bookable slot left today (venue-local day), by the real slot engine.

        Filtering happens after the normal search order, in batches, so paging is over the filtered
        list. At most SCAN_LIMIT candidates are examined per request (a bound on work, documented in
        STEP_10 notes); a result past that window is simply not reached.
        """
        need = f.offset + f.limit + 1
        kept: list[Row[Any]] = []
        scanned = 0
        now = datetime.now(UTC)
        availability = AvailabilityService(self.session, self.settings)
        while len(kept) < need and scanned < AVAILABLE_TODAY_SCAN_LIMIT:
            batch = min(AVAILABLE_TODAY_BATCH, AVAILABLE_TODAY_SCAN_LIMIT - scanned)
            rows = await self.repo.search(
                replace(f, limit=batch, offset=scanned, available_today=False), customer_id
            )
            page = rows[:batch]
            for row in page:
                today = now.astimezone(ZoneInfo(row.Venue.timezone)).date()
                if (await availability.dates(row.Venue.id, today, today, now)).dates:
                    kept.append(row)
            scanned += len(page)
            if len(rows) <= batch:
                break
        return await self._page(kept[f.offset : f.offset + f.limit + 1], f.limit, f.offset)

    async def venue_detail(
        self, venue_id: UUID, customer_id: UUID | None, lat: float | None, lng: float | None
    ) -> VenueDetail:
        if (lat is None) != (lng is None):
            raise ValidationFailedError("lat and lng must be sent together.", code="INVALID_LOCATION")
        row = await self.repo.get_published(venue_id, customer_id, lat, lng)
        if row is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        categories = await self.repo.categories_of(venue_id)
        amenities = await self.repo.amenities_of(venue_id)
        images = await self.repo.images_of(venue_id)
        card = self._card(row, [c.slug for c in categories])
        venue = row.Venue
        return VenueDetail(
            **card.model_dump(),
            description=venue.description,
            postal_code=venue.postal_code,
            google_place_id=venue.google_place_id,
            contact_phone=venue.contact_phone,
            timezone=venue.timezone,
            category_details=[CategoryOut.model_validate(c) for c in categories],
            amenities=[AmenityOut.model_validate(a) for a in amenities],
            images=[
                VenueImageOut(
                    id=i.id,
                    url=public_image_url(self.settings, i.storage_path),
                    alt_text=i.alt_text,
                    is_cover=i.is_cover,
                    width=i.width,
                    height=i.height,
                )
                for i in images
            ],
        )

    async def list_favorites(self, customer_id: UUID, limit: int, offset: int) -> VenuePage:
        return await self._page(await self.repo.favorites(customer_id, limit, offset), limit, offset)

    async def add_favorite(self, customer_id: UUID, venue_id: UUID) -> None:
        if not await self.repo.published_exists(venue_id):
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        await self.repo.add_favorite(customer_id, venue_id)
        await self.repo.session.commit()

    async def remove_favorite(self, customer_id: UUID, venue_id: UUID) -> None:
        await self.repo.remove_favorite(customer_id, venue_id)
        await self.repo.session.commit()
