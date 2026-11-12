from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Row, Select, and_, asc, cast, desc, exists, func, literal, or_, select
from sqlalchemy import Float as SAFloat
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    Amenity,
    Category,
    City,
    Favorite,
    Venue,
    VenueAmenity,
    VenueCategory,
    VenueImage,
)

EARTH_RADIUS_KM = 6371.0088


@dataclass(slots=True)
class VenueFilters:
    q: str | None = None
    category: str | None = None
    city_id: UUID | None = None
    min_price: int | None = None
    max_price: int | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = None
    sort: str = "popular"
    limit: int = 20
    offset: int = 0


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _distance_km(lat: float, lng: float) -> ColumnElement[float]:
    """Haversine distance in km (no PostGIS dependency; fine at MVP scale, see decision D-41)."""
    lat1, lng1 = func.radians(literal(lat)), func.radians(literal(lng))
    lat2, lng2 = func.radians(cast(Venue.latitude, SAFloat)), func.radians(cast(Venue.longitude, SAFloat))
    a = func.power(func.sin((lat2 - lat1) / 2), 2) + func.cos(lat1) * func.cos(lat2) * func.power(
        func.sin((lng2 - lng1) / 2), 2
    )
    return 2 * EARTH_RADIUS_KM * func.asin(func.least(literal(1.0), func.sqrt(a)))


class VenueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- reference data -------------------------------------------------
    async def cities(self) -> list[City]:
        stmt = select(City).where(City.is_active.is_(True)).order_by(City.name)
        return list((await self.session.scalars(stmt)).all())

    async def categories(self) -> list[Category]:
        stmt = (
            select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.name)
        )
        return list((await self.session.scalars(stmt)).all())

    async def amenities(self) -> list[Amenity]:
        stmt = select(Amenity).where(Amenity.is_active.is_(True)).order_by(Amenity.sort_order, Amenity.name)
        return list((await self.session.scalars(stmt)).all())

    # -- venues ---------------------------------------------------------
    def _base(self, customer_id: UUID | None, lat: float | None, lng: float | None) -> Select[Any]:
        cover = (
            select(VenueImage.storage_path)
            .where(VenueImage.venue_id == Venue.id, VenueImage.status == "active")
            .order_by(VenueImage.is_cover.desc(), VenueImage.sort_order, VenueImage.created_at)
            .limit(1)
            .correlate(Venue)
            .scalar_subquery()
        )
        mine = aliased(Favorite)  # alias: the favorites() query also joins the Favorite table itself
        fav = (
            exists().where(mine.venue_id == Venue.id, mine.customer_id == customer_id)
            if customer_id
            else literal(False)
        )
        dist = _distance_km(lat, lng) if lat is not None and lng is not None else literal(None)
        return (
            select(
                Venue,
                City.name.label("city_name"),
                cover.label("cover_path"),
                fav.label("is_favorite"),
                dist.label("distance_km"),
            )
            .outerjoin(City, City.id == Venue.city_id)
            .where(Venue.status == "published")
        )

    async def search(self, f: VenueFilters, customer_id: UUID | None) -> Sequence[Row[Any]]:
        stmt = self._base(customer_id, f.lat, f.lng)
        if f.q:
            like = f"%{_escape_like(f.q.strip())}%"
            in_category = exists().where(
                VenueCategory.venue_id == Venue.id,
                VenueCategory.category_id == Category.id,
                Category.name.ilike(like, escape="\\"),
            )
            stmt = stmt.where(
                or_(
                    Venue.name.ilike(like, escape="\\"),
                    Venue.address_line.ilike(like, escape="\\"),
                    City.name.ilike(like, escape="\\"),
                    in_category,
                )
            )
        if f.category:
            stmt = stmt.where(
                exists().where(
                    VenueCategory.venue_id == Venue.id,
                    VenueCategory.category_id == Category.id,
                    Category.slug == f.category,
                )
            )
        if f.city_id:
            stmt = stmt.where(Venue.city_id == f.city_id)
        if f.min_price is not None:
            stmt = stmt.where(Venue.starting_price_paise >= f.min_price)
        if f.max_price is not None:
            stmt = stmt.where(Venue.starting_price_paise <= f.max_price)
        if f.radius_km is not None and f.lat is not None and f.lng is not None:
            stmt = stmt.where(
                and_(
                    Venue.latitude.is_not(None),
                    Venue.longitude.is_not(None),
                    _distance_km(f.lat, f.lng) <= f.radius_km,
                )
            )
        stmt = stmt.order_by(*self._order(f), Venue.id).limit(f.limit + 1).offset(f.offset)
        return list((await self.session.execute(stmt)).all())

    @staticmethod
    def _order(f: VenueFilters) -> tuple[Any, ...]:
        if f.sort == "rating":
            return (desc(Venue.rating_avg).nulls_last(), desc(Venue.rating_count))
        if f.sort == "price_asc":
            return (asc(Venue.starting_price_paise).nulls_last(), desc(Venue.rating_count))
        if f.sort == "price_desc":
            return (desc(Venue.starting_price_paise).nulls_last(), desc(Venue.rating_count))
        if f.sort == "newest":
            return (desc(Venue.published_at).nulls_last(), desc(Venue.created_at))
        if f.sort == "distance" and f.lat is not None and f.lng is not None:
            return (asc(_distance_km(f.lat, f.lng)).nulls_last(),)
        # popular: most-reviewed first, then best rated
        return (
            desc(Venue.rating_count),
            desc(Venue.rating_avg).nulls_last(),
            desc(Venue.published_at).nulls_last(),
        )

    async def get_published(
        self, venue_id: UUID, customer_id: UUID | None, lat: float | None, lng: float | None
    ) -> Row[Any] | None:
        stmt = self._base(customer_id, lat, lng).where(Venue.id == venue_id)
        return (await self.session.execute(stmt)).first()  # type: ignore[no-any-return]

    async def category_slugs(self, venue_ids: list[UUID]) -> dict[UUID, list[str]]:
        if not venue_ids:
            return {}
        stmt = (
            select(VenueCategory.venue_id, Category.slug)
            .join(Category, Category.id == VenueCategory.category_id)
            .where(VenueCategory.venue_id.in_(venue_ids), Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.slug)
        )
        out: dict[UUID, list[str]] = {v: [] for v in venue_ids}
        for venue_id, slug in (await self.session.execute(stmt)).all():
            out[venue_id].append(slug)
        return out

    async def categories_of(self, venue_id: UUID) -> list[Category]:
        stmt = (
            select(Category)
            .join(VenueCategory, VenueCategory.category_id == Category.id)
            .where(VenueCategory.venue_id == venue_id, Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.name)
        )
        return list((await self.session.scalars(stmt)).all())

    async def amenities_of(self, venue_id: UUID) -> list[Amenity]:
        stmt = (
            select(Amenity)
            .join(VenueAmenity, VenueAmenity.amenity_id == Amenity.id)
            .where(VenueAmenity.venue_id == venue_id, Amenity.is_active.is_(True))
            .order_by(Amenity.sort_order, Amenity.name)
        )
        return list((await self.session.scalars(stmt)).all())

    async def images_of(self, venue_id: UUID) -> list[VenueImage]:
        stmt = (
            select(VenueImage)
            .where(VenueImage.venue_id == venue_id, VenueImage.status == "active")
            .order_by(VenueImage.is_cover.desc(), VenueImage.sort_order, VenueImage.created_at)
        )
        return list((await self.session.scalars(stmt)).all())

    # -- favorites ------------------------------------------------------
    async def favorites(self, customer_id: UUID, limit: int, offset: int) -> Sequence[Row[Any]]:
        stmt = (
            self._base(customer_id, None, None)
            .join(Favorite, and_(Favorite.venue_id == Venue.id, Favorite.customer_id == customer_id))
            .order_by(Favorite.created_at.desc(), Venue.id)
            .limit(limit + 1)
            .offset(offset)
        )
        return list((await self.session.execute(stmt)).all())

    async def published_exists(self, venue_id: UUID) -> bool:
        stmt = select(Venue.id).where(Venue.id == venue_id, Venue.status == "published")
        return (await self.session.execute(stmt)).first() is not None

    async def add_favorite(self, customer_id: UUID, venue_id: UUID) -> None:
        stmt = (
            insert(Favorite)
            .values(customer_id=customer_id, venue_id=venue_id)
            .on_conflict_do_nothing(index_elements=["customer_id", "venue_id"])
        )
        await self.session.execute(stmt)

    async def remove_favorite(self, customer_id: UUID, venue_id: UUID) -> None:
        from sqlalchemy import delete

        await self.session.execute(
            delete(Favorite).where(Favorite.customer_id == customer_id, Favorite.venue_id == venue_id)
        )
