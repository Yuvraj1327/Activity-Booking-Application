from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.profile import StrictModel


class CityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    state: str | None
    country_code: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    slug: str
    name: str
    icon_key: str | None
    sort_order: int


class AmenityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    slug: str
    name: str
    icon_key: str | None


class VenueImageOut(BaseModel):
    id: UUID
    url: str | None  # public Storage URL; null only if SUPABASE_URL is not configured
    alt_text: str | None
    is_cover: bool
    width: int | None
    height: int | None


class VenueCard(BaseModel):
    id: UUID
    name: str
    city_id: UUID | None
    city_name: str | None
    address_line: str | None
    latitude: float | None
    longitude: float | None
    cover_image_url: str | None
    categories: list[str]  # category slugs
    starting_price_paise: int | None
    currency: str
    rating_avg: float | None
    rating_count: int
    distance_km: float | None  # only when the caller sent lat/lng
    is_favorite: bool


class VenueDetail(VenueCard):
    description: str | None
    postal_code: str | None
    google_place_id: str | None
    contact_phone: str | None
    timezone: str
    category_details: list[CategoryOut]
    amenities: list[AmenityOut]
    images: list[VenueImageOut]


class VenuePage(BaseModel):
    items: list[VenueCard]
    limit: int
    offset: int
    has_more: bool


VenueSort = Literal["popular", "rating", "price_asc", "price_desc", "distance", "newest"]


class FavoriteCreate(StrictModel):
    venue_id: UUID


class FavoriteOut(BaseModel):
    venue_id: UUID
    created_at: datetime


Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
Limit = Annotated[int, Field(ge=1, le=50)]
