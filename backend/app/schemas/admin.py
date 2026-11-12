"""Step 8: admin console response/request schemas. Money is integer paise.

Anything that depends on an unapproved business rule (platform revenue, owner earnings,
refund totals) is an `Unavailable` object, never a made-up number.
"""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from app.schemas.booking import AdminBookingOut
from app.schemas.owner import Unavailable
from app.schemas.payment import AdminPaymentOut
from app.schemas.profile import StrictModel

Granularity = Literal["day", "week", "month"]


class Page(BaseModel):
    limit: int
    offset: int
    has_more: bool


# ------------------------------------------------------------------ account status
class StatusChange(StrictModel):
    status: Literal["active", "suspended"]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


class StatusChangeOut(BaseModel):
    id: UUID
    role: str
    status: str
    changed: bool


# ------------------------------------------------------------------ people
class OwnerRow(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone_masked: str | None
    business_name: str
    status: str
    created_at: datetime
    venues_count: int
    published_venues_count: int
    bookings_count: int


class OwnerPage(Page):
    items: list[OwnerRow]


class VenueBrief(BaseModel):
    id: UUID
    name: str
    status: str
    city: str | None
    created_at: datetime
    bookings_count: int
    confirmed_count: int


class BookingBrief(BaseModel):
    id: UUID
    booking_code: str
    venue_name: str
    customer_name: str
    booking_date: date
    status: str
    payment_status: str
    total_amount_paise: int
    currency: str
    created_at: datetime


class OwnerDetail(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    business_name: str
    business_phone: str | None
    business_email: str | None
    business_address: str | None
    status: str
    created_at: datetime
    venues: list[VenueBrief]
    bookings_count: int
    confirmed_count: int
    gross_paid_paise: int
    recent_bookings: list[BookingBrief]


class CustomerRow(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone_masked: str | None
    status: str
    created_at: datetime
    bookings_count: int
    confirmed_count: int


class CustomerPage(Page):
    items: list[CustomerRow]


class CustomerDetail(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    status: str
    created_at: datetime
    bookings_count: int
    confirmed_count: int
    cancelled_count: int
    gross_paid_paise: int
    bookings: list[BookingBrief]


# ------------------------------------------------------------------ venues
class VenueRow(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    owner_name: str
    business_name: str
    categories: list[str]
    city: str | None
    address_line: str | None
    status: str
    created_at: datetime
    published_at: datetime | None
    bookings_count: int
    confirmed_count: int


class VenuePage(Page):
    items: list[VenueRow]


class VenueDetail(VenueRow):
    description: str | None
    contact_phone: str | None
    timezone: str
    resources_count: int
    active_resources_count: int
    gross_paid_paise: int
    rating_avg: float | None
    rating_count: int


# ------------------------------------------------------------------ bookings / payments (extended)
class AdminBookingRow(AdminBookingOut):
    owner_name: str
    payment_amount_paise: int | None = None
    payment_id: UUID | None = None


class AdminBookingRowPage(Page):
    items: list[AdminBookingRow]


class AdminBookingDetailOut(AdminBookingRow):
    payments: list[AdminPaymentOut]


# ------------------------------------------------------------------ analytics
class DateRange(BaseModel):
    date_from: date
    date_to: date
    timezone: str


class MoneyBreakdown(BaseModel):
    """Different money figures are never merged: each has its own meaning."""

    currency: str = "INR"
    gross_booking_value_paise: int  # sum of booking totals for bookings that are confirmed/completed
    successful_payment_paise: int  # captured gateway payments (gross)
    platform_revenue: Unavailable
    owner_earnings: Unavailable
    refunds: Unavailable


class BookingBucket(BaseModel):
    bucket: date
    total: int
    confirmed: int
    pending: int
    cancelled: int
    other: int


class StatusShare(BaseModel):
    status: str
    count: int


class BookingAnalytics(BaseModel):
    range: DateRange
    granularity: Granularity
    total: int
    series: list[BookingBucket]
    status_distribution: list[StatusShare]


class PaymentBucket(BaseModel):
    bucket: date
    captured_count: int
    captured_paise: int
    failed_count: int
    open_count: int


class RevenueAnalytics(BaseModel):
    range: DateRange
    granularity: Granularity
    transactions_total: int
    captured_count: int
    failed_count: int
    open_count: int
    success_rate_percent: float | None
    money: MoneyBreakdown
    series: list[PaymentBucket]


class RegistrationBucket(BaseModel):
    bucket: date
    customers: int
    owners: int
    venues_created: int


class CategoryShare(BaseModel):
    category: str
    bookings: int


class TopVenue(BaseModel):
    venue_id: UUID
    name: str
    bookings: int
    confirmed: int


class PlatformAnalytics(BaseModel):
    range: DateRange
    granularity: Granularity
    new_customers: int
    new_owners: int
    new_venues: int
    series: list[RegistrationBucket]
    popular_categories: list[CategoryShare]
    top_venues: list[TopVenue]


class DashboardTotals(BaseModel):
    customers: int
    owners: int
    venues: int
    published_venues: int
    bookings: int
    payments: int


class DashboardPeriod(BaseModel):
    bookings: int
    confirmed: int
    pending: int
    cancelled: int
    transactions: int
    money: MoneyBreakdown
    new_customers: int
    new_owners: int


class RegistrationRow(BaseModel):
    id: UUID
    full_name: str
    role: str
    created_at: datetime


class ActivityItem(BaseModel):
    kind: str  # booking | account | export | payment
    title: str
    detail: str | None
    created_at: datetime
    entity_id: str | None = None


class DashboardOut(BaseModel):
    range: DateRange
    totals: DashboardTotals
    period: DashboardPeriod
    booking_trend: list[BookingBucket]
    revenue_trend: list[PaymentBucket]
    recent_bookings: list[BookingBrief]
    recent_registrations: list[RegistrationRow]
    popular_venues: list[TopVenue]
    activity: list[ActivityItem]


class ActivityPage(BaseModel):
    items: list[ActivityItem]


# ------------------------------------------------------------------ audit log
class AuditRow(BaseModel):
    id: UUID
    action: str
    actor_id: UUID | None
    actor_role: str | None
    entity_type: str | None
    entity_id: str | None
    metadata: dict[str, object]
    created_at: datetime


class AuditPage(Page):
    items: list[AuditRow]
