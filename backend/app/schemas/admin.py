"""Step 8: admin console response/request schemas. Money is integer paise.

Anything that depends on an unapproved business rule (platform revenue, owner earnings,
refund totals) is an `Unavailable` object, never a made-up number.
"""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from app.schemas.booking import AdminBookingOut
from app.schemas.owner import Unavailable
from app.schemas.payment import AdminPaymentOut
from app.schemas.profile import StrictModel

Granularity = Literal["day", "week", "month"]


class MoneyFigure(BaseModel):
    """A figure that IS backed by recorded data (ledger rows under an approved finance configuration)."""

    available: Literal[True] = True
    amount_paise: int
    note: str


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
    kyc_status: str = "not_submitted"
    kyc_reviewed_at: datetime | None = None
    kyc_note: str | None = None
    pending_kyc_documents: int = 0
    verified_venues: int = 0
    payouts_paid_paise: int = 0
    refunds_paise: int = 0


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
    completed_count: int = 0
    refunded_paise: int = 0
    deletion_requested_at: datetime | None = None
    language: str | None = None
    has_open_dispute: bool = False


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
    is_verified: bool = False
    submitted_at: datetime | None = None
    status_reason: str | None = None
    owner_kyc_status: str | None = None
    open_reports: int = 0


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
    verified_at: datetime | None = None
    completed_count: int = 0
    cancelled_count: int = 0
    future_confirmed_count: int = 0
    performance: list[dict[str, Any]] = []  # last months: bookings, completed, cancelled, gross paid
    owner_earnings: MoneyFigure | Unavailable | None = None


# ------------------------------------------------------------------ bookings / payments (extended)
class AdminBookingRow(AdminBookingOut):
    owner_name: str
    payment_amount_paise: int | None = None
    payment_id: UUID | None = None
    city: str | None = None
    sports: list[str] = []
    refund_status: str = "none"  # none | awaiting | pending | processed | failed
    refunded_paise: int = 0


class AdminBookingRowPage(Page):
    items: list[AdminBookingRow]


class AdminBookingDetailOut(AdminBookingRow):
    payments: list[AdminPaymentOut]
    customer: dict[str, Any] | None = None
    owner: dict[str, Any] | None = None
    venue: dict[str, Any] | None = None
    price_snapshot: dict[str, Any] | None = None
    refunds: list[dict[str, Any]] = []
    disputes: list[dict[str, Any]] = []
    coupon: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = []


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
    platform_revenue: MoneyFigure | Unavailable  # fee + commission, from the ledger (Q7, Q8)
    owner_earnings: MoneyFigure | Unavailable  # owner share, from the ledger (Q8)
    refunds: MoneyFigure | Unavailable  # refunds the gateway has processed in the period
    tax_collected: MoneyFigure | Unavailable | None = None  # GST/tax portion, from the ledger (Q7)
    ledger_coverage: dict[str, Any] | None = None  # captured payments with / without a ledger entry


class BookingBucket(BaseModel):
    bucket: date
    total: int
    confirmed: int  # confirmed (upcoming) only
    pending: int
    cancelled: int
    other: int
    completed: int = 0  # finished bookings, counted separately from confirmed


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
    bookings: float  # each booking is split equally across its venue's sports, so shares add up to the total
    tagged_bookings: int  # bookings at venues tagged with this sport (a multi-sport venue appears in several)
    venues: int
    gross_paid_paise: int = 0


class CityShare(BaseModel):
    city_id: UUID | None
    city: str
    venues: int
    bookings: int
    confirmed: int
    completed: int
    cancelled: int
    gross_paid_paise: int


class VenuePerformance(BaseModel):
    venue_id: UUID
    name: str
    city: str | None
    status: str
    bookings: int
    confirmed: int
    completed: int
    cancelled: int
    cancellation_rate_percent: float | None
    gross_paid_paise: int
    average_booking_paise: int | None
    rating_avg: float | None
    rating_count: int


class TopVenue(BaseModel):
    venue_id: UUID
    name: str
    bookings: int
    confirmed: int
    completed: int = 0


class PlatformAnalytics(BaseModel):
    range: DateRange
    granularity: Granularity
    new_customers: int
    new_owners: int
    new_venues: int
    series: list[RegistrationBucket]
    popular_categories: list[CategoryShare]
    uncategorised_bookings: int = 0
    cities: list[CityShare] = []
    top_venues: list[TopVenue]


class DashboardTotals(BaseModel):
    customers: int  # all customer accounts
    owners: int  # all owner accounts
    active_customers: int = 0  # status = active
    active_owners: int = 0
    suspended_customers: int = 0
    suspended_owners: int = 0
    pending_venue_approvals: int = 0  # venues waiting in pending_review
    open_venue_reports: int = 0
    venues: int
    published_venues: int
    bookings: int
    payments: int


class DashboardPeriod(BaseModel):
    bookings: int
    confirmed: int  # confirmed only
    completed: int = 0  # completed only
    pending: int
    cancelled: int
    transactions: int
    failed_payments: int = 0
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
    actor_name: str | None = None
    entity_type: str | None
    entity_id: str | None
    metadata: dict[str, object]
    request_id: str | None = None
    created_at: datetime


class AuditPage(Page):
    items: list[AuditRow]
