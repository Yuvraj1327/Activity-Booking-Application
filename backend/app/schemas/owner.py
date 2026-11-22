"""Request/response models for the owner (venue management) API."""

from datetime import date, datetime, time
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.schemas.catalog import AmenityOut, CategoryOut
from app.schemas.profile import NonNullableUpdate, Phone, StrictModel

VenueName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
AddressLine = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
PostalCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=12)]
Price = Annotated[int, Field(ge=0, le=100_000_000)]  # paise, per hour (interim display price, D-40)
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]

MAX_CATEGORIES = 12
MAX_AMENITIES = 40
MAX_IMAGES = 10  # per venue: a configurable assumption, not an approved business rule
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # matches the venue-images bucket limit
OWNER_VENUE_STATUSES = ("draft", "published", "archived")


class OwnerVenueCreate(StrictModel):
    """Only `name` is required, so a draft can be saved early. Publishing has its own checks."""

    name: VenueName
    description: Description | None = None
    address_line: AddressLine | None = None
    city_id: UUID | None = None
    postal_code: PostalCode | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    contact_phone: Phone | None = None
    starting_price_paise: Price | None = None
    timezone: Annotated[str, StringConstraints(min_length=1, max_length=64)] = "Asia/Kolkata"
    category_ids: Annotated[list[UUID], Field(max_length=MAX_CATEGORIES)] = []
    amenity_ids: Annotated[list[UUID], Field(max_length=MAX_AMENITIES)] = []

    @model_validator(mode="after")
    def _coordinates_pair(self) -> "OwnerVenueCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class OwnerVenueUpdate(NonNullableUpdate):
    """PATCH: omitted = unchanged, null = clear (name and timezone cannot be cleared)."""

    _non_nullable = ("name", "timezone")

    name: VenueName | None = None
    description: Description | None = None
    address_line: AddressLine | None = None
    city_id: UUID | None = None
    postal_code: PostalCode | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    contact_phone: Phone | None = None
    starting_price_paise: Price | None = None
    timezone: Annotated[str, StringConstraints(min_length=1, max_length=64)] | None = None
    category_ids: Annotated[list[UUID], Field(max_length=MAX_CATEGORIES)] | None = None
    amenity_ids: Annotated[list[UUID], Field(max_length=MAX_AMENITIES)] | None = None

    @field_validator("category_ids", "amenity_ids")
    @classmethod
    def _lists_not_null(cls, v: list[UUID] | None) -> list[UUID] | None:
        return v  # None means "leave unchanged" for the lists (they are cleared with [])


class OwnerVenueImageOut(BaseModel):
    id: UUID
    url: str | None
    alt_text: str | None
    is_cover: bool
    sort_order: int
    width: int | None
    height: int | None
    byte_size: int | None


class OwnerVenueCard(BaseModel):
    id: UUID
    name: str
    status: Literal["draft", "pending_review", "published", "rejected", "suspended", "archived"]
    status_reason: str | None = None  # why it was rejected / suspended (shown to the owner)
    is_verified: bool = False
    city_name: str | None
    address_line: str | None
    cover_image_url: str | None
    image_count: int
    categories: list[str]
    starting_price_paise: int | None
    currency: str
    rating_avg: float | None
    rating_count: int
    updated_at: datetime


class OwnerVenueDetail(OwnerVenueCard):
    description: str | None
    city_id: UUID | None
    state: str | None  # from the selected city; there is no separate state column
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    contact_phone: str | None
    timezone: str
    published_at: datetime | None
    category_details: list[CategoryOut]
    amenities: list[AmenityOut]
    images: list[OwnerVenueImageOut]
    publish_blockers: list[str]  # what is still missing before this venue can be published


class OwnerVenuePage(BaseModel):
    items: list[OwnerVenueCard]
    limit: int
    offset: int
    has_more: bool


class ImagePatch(NonNullableUpdate):
    alt_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    is_cover: bool | None = None
    sort_order: Annotated[int, Field(ge=0, le=1000)] | None = None


class ImageOrder(StrictModel):
    image_ids: Annotated[list[UUID], Field(min_length=1, max_length=MAX_IMAGES)]


# ------------------------------------------------------------------ schedules
class Interval(StrictModel):
    opens_at: time
    closes_at: time

    @model_validator(mode="after")
    def _ordered(self) -> "Interval":
        if (
            self.opens_at.second
            or self.closes_at.second
            or self.opens_at.microsecond
            or self.closes_at.microsecond
        ):
            raise ValueError("times must be whole minutes")
        if self.opens_at >= self.closes_at:
            raise ValueError("opens_at must be before closes_at (overnight hours are not supported yet)")
        return self


class DayHours(StrictModel):
    weekday: Annotated[int, Field(ge=0, le=6)]  # 0 = Monday … 6 = Sunday
    intervals: Annotated[list[Interval], Field(max_length=5)]  # empty = closed that day


class SpecialDate(StrictModel):
    on_date: date
    is_closed: bool
    opens_at: time | None = None
    closes_at: time | None = None
    note: Note | None = None

    @model_validator(mode="after")
    def _shape(self) -> "SpecialDate":
        if self.is_closed:
            if self.opens_at is not None or self.closes_at is not None:
                raise ValueError("a closed date cannot have opening hours")
        else:
            if self.opens_at is None or self.closes_at is None:
                raise ValueError("modified hours need opens_at and closes_at")
            Interval(opens_at=self.opens_at, closes_at=self.closes_at)  # reuse the interval checks
        return self


class ScheduleOut(BaseModel):
    venue_id: UUID
    timezone: str
    regular: list[DayHours]  # always 7 entries, Monday first
    special: list[SpecialDate]
    slot_configuration: dict[str, Any]


class ScheduleReplace(StrictModel):
    """PUT: each part that is present replaces the stored one; an absent part is untouched."""

    regular: Annotated[list[DayHours], Field(max_length=7)] | None = None
    special: Annotated[list[SpecialDate], Field(max_length=366)] | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "ScheduleReplace":
        if self.regular is None and self.special is None:
            raise ValueError("send regular and/or special")
        return self


# ------------------------------------------------------------------ business (dashboard etc.)
class Unavailable(BaseModel):
    """Returned for data that does not exist yet. Never filled with made-up numbers."""

    available: Literal[False] = False
    depends_on: str
    message: str


class DashboardVenue(BaseModel):
    venue_id: UUID
    name: str
    status: str
    rating_avg: float | None
    rating_count: int
    cover_image_url: str | None
    starting_price_paise: int | None
    currency: str


class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str | None
    data: dict[str, Any]
    is_read: bool
    created_at: datetime
    booking_id: UUID | None = None
    payment_id: UUID | None = None


class BookingOverview(BaseModel):
    upcoming: int
    completed: int
    cancelled: int


class DashboardOut(BaseModel):
    venues_total: int
    venues_published: int
    venues_draft: int
    venues_archived: int
    average_rating: float | None  # review-count-weighted across venues; null when there are no ratings
    ratings_count: int
    venue_performance: list[DashboardVenue]
    recent_activity: list[NotificationOut]
    # Metrics whose source data (bookings, payments) does not exist yet. Each says what it needs.
    total_bookings: int  # real: confirmed, completed and cancelled bookings (unpaid holds excluded)
    booking_overview: BookingOverview
    total_revenue: Unavailable
    monthly_revenue: Unavailable
    average_utilization: Unavailable


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    unread_count: int
    limit: int
    offset: int
    has_more: bool


class PendingList(Unavailable):
    items: list[Any] = []


class EarningsOut(Unavailable):
    total_earnings_paise: None = None
    payouts: Unavailable | None = None
    items: list[Any] = []


class AnalyticsOut(BaseModel):
    date_from: date
    date_to: date
    venue_performance: list[DashboardVenue]  # real: current venue ratings
    total_bookings: Unavailable
    revenue: Unavailable
    utilization: Unavailable
    booking_trends: Unavailable
    popular_time_slots: Unavailable
