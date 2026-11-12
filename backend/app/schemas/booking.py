"""Request/response models for availability, bookings and owner resources (Step 6)."""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.schemas.profile import NonNullableUpdate, StrictModel

ResourceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
BlockReason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
SlotMinutes = Annotated[int, Field(ge=5, le=720)]
SlotPrice = Annotated[int, Field(ge=0, le=100_000_000)]  # paise per slot

MAX_AVAILABILITY_DAYS = 31
MAX_ADVANCE_QUERY_DAYS = 400  # technical limit for the date picker, not a business rule


class SlotOut(BaseModel):
    starts_at: datetime
    ends_at: datetime
    local_start: str  # "HH:MM" in the venue's time zone
    local_end: str
    price_paise: int


ResourceState = Literal["available", "fully_booked", "closed", "not_configured"]


class ResourceAvailability(BaseModel):
    resource_id: UUID
    name: str
    slot_minutes: int | None
    slot_price_paise: int | None
    currency: str
    state: ResourceState
    message: str | None
    slots: list[SlotOut]  # only genuinely available slots


class AvailabilityOut(BaseModel):
    venue_id: UUID
    date: date
    timezone: str
    closed_reason: Literal["special_closure", "weekly_closed"] | None
    note: str | None
    resources: list[ResourceAvailability]


class AvailableDatesOut(BaseModel):
    venue_id: UUID
    date_from: date
    date_to: date
    dates: list[date]  # dates with at least one available slot on any resource


class BookingRequest(StrictModel):
    resource_id: UUID
    starts_at: datetime

    @field_validator("starts_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("starts_at must include a time zone offset")
        return v


class CancelRequest(StrictModel):
    reason: Reason | None = None


class QuoteOut(BaseModel):
    resource_id: UUID
    venue_id: UUID
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    currency: str
    base_amount_paise: int
    fees_paise: int
    tax_paise: int
    discount_paise: int
    total_amount_paise: int
    note: str


class StatusEvent(BaseModel):
    from_status: str | None
    to_status: str
    actor_role: str
    reason: str | None
    created_at: datetime


class BookingOut(BaseModel):
    id: UUID
    booking_code: str
    status: str
    payment_status: str
    venue_id: UUID
    venue_name: str
    resource_id: UUID
    resource_name: str
    booking_date: date
    starts_at: datetime
    ends_at: datetime
    local_start: str
    local_end: str
    timezone: str
    duration_minutes: int
    currency: str
    base_amount_paise: int
    total_amount_paise: int
    price: dict[str, Any]
    expires_at: datetime | None
    created_at: datetime
    cancelled_at: datetime | None
    cancel_reason: str | None
    can_cancel: bool = False
    history: list[StatusEvent] = []


class BookingPage(BaseModel):
    items: list[BookingOut]
    limit: int
    offset: int
    has_more: bool


class OwnerBookingOut(BookingOut):
    customer_name: str  # name only: phone/e-mail visibility is undecided (N9)


class OwnerBookingPage(BaseModel):
    items: list[OwnerBookingOut]
    limit: int
    offset: int
    has_more: bool
    available: Literal[True] = True


class AdminBookingOut(OwnerBookingOut):
    customer_id: UUID
    owner_id: UUID


class AdminBookingPage(BaseModel):
    items: list[AdminBookingOut]
    limit: int
    offset: int
    has_more: bool


class CancellationPreview(BaseModel):
    can_cancel: bool
    code: str
    message: str


# ------------------------------------------------------------------ owner: resources and blocks
class ResourceCreate(StrictModel):
    name: ResourceName
    slot_minutes: SlotMinutes | None = None
    slot_price_paise: SlotPrice | None = None
    sort_order: Annotated[int, Field(ge=0, le=1000)] = 0
    is_active: bool = True


class ResourceUpdate(NonNullableUpdate):
    _non_nullable = ("name", "sort_order", "is_active")

    name: ResourceName | None = None
    slot_minutes: SlotMinutes | None = None
    slot_price_paise: SlotPrice | None = None
    sort_order: Annotated[int, Field(ge=0, le=1000)] | None = None
    is_active: bool | None = None


class ResourceOut(BaseModel):
    id: UUID
    venue_id: UUID
    name: str
    slot_minutes: int | None
    slot_price_paise: int | None
    sort_order: int
    is_active: bool
    configured: bool  # has both slot length and price


class BlockCreate(StrictModel):
    resource_id: UUID | None = None  # null = the whole venue
    starts_at: datetime
    ends_at: datetime
    reason: BlockReason | None = None

    @model_validator(mode="after")
    def _valid(self) -> "BlockCreate":
        for v in (self.starts_at, self.ends_at):
            if v.tzinfo is None or v.utcoffset() is None:
                raise ValueError("times must include a time zone offset")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class BlockOut(BaseModel):
    id: UUID
    venue_id: UUID
    resource_id: UUID | None
    starts_at: datetime
    ends_at: datetime
    reason: str | None
