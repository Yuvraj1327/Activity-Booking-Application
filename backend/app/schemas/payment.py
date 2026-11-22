"""Request/response models for payments, notifications and devices (Step 7)."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.owner import Unavailable
from app.schemas.profile import StrictModel

Ref = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=100)]
Signature = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=256)]


class CreateOrderRequest(StrictModel):
    booking_id: UUID


class VerifyPaymentRequest(StrictModel):
    razorpay_order_id: Ref
    razorpay_payment_id: Ref
    razorpay_signature: Signature


class CheckoutPrefill(BaseModel):
    name: str | None
    email: str | None
    contact: str | None


class CheckoutConfig(BaseModel):
    key_id: str  # public Razorpay key id; the secret never leaves the server
    order_id: str
    amount_paise: int
    currency: str
    name: str
    description: str
    prefill: CheckoutPrefill


class PaymentOut(BaseModel):
    id: UUID
    booking_id: UUID
    booking_code: str
    venue_name: str
    resource_name: str
    amount_paise: int
    currency: str
    status: str
    method: str | None
    razorpay_order_id: str
    razorpay_payment_id: str | None
    failure_reason: str | None
    booking_status: str
    booking_payment_status: str
    #: True only when the backend has verified the payment AND the booking is confirmed.
    confirmed: bool
    #: True when money was taken but the booking could not be confirmed (needs staff review).
    needs_review: bool
    hold_expires_at: datetime | None
    created_at: datetime
    captured_at: datetime | None


class CreateOrderOut(BaseModel):
    payment: PaymentOut
    checkout: CheckoutConfig


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    limit: int
    offset: int
    has_more: bool


class WebhookAck(BaseModel):
    received: bool = True
    outcome: Literal["applied", "duplicate", "ignored", "rejected"]


# ------------------------------------------------------------------ owner / admin
class OwnerPaymentOut(BaseModel):
    id: UUID
    booking_id: UUID
    booking_code: str
    venue_id: UUID
    venue_name: str
    resource_name: str
    amount_paise: int
    currency: str
    status: str
    method: str | None
    captured_at: datetime | None
    created_at: datetime


class OwnerPaymentPage(BaseModel):
    items: list[OwnerPaymentOut]
    limit: int
    offset: int
    has_more: bool


class VenueGross(BaseModel):
    venue_id: UUID
    venue_name: str
    gross_paid_paise: int
    payments: int


class OwnerEarningsOut(BaseModel):
    """Only confirmed facts: gross amounts customers actually paid. Everything that depends on
    unapproved rules (commission, GST, deductions, payouts) is explicitly marked unavailable."""

    available: bool = True
    currency: str = "INR"
    gross_paid_paise: int
    payments_count: int
    by_venue: list[VenueGross]
    deductions: Unavailable
    net_earnings: Unavailable
    payouts: Unavailable


class AdminPaymentOut(BaseModel):
    id: UUID
    booking_id: UUID
    booking_code: str
    booking_status: str
    customer_id: UUID
    venue_id: UUID
    venue_name: str
    amount_paise: int
    currency: str
    status: str
    method: str | None
    razorpay_order_id: str
    razorpay_payment_id: str | None
    failure_code: str | None
    failure_reason: str | None
    review_required: bool
    review_reason: str | None
    created_at: datetime
    captured_at: datetime | None
    failed_at: datetime | None
    refunded_paise: int = 0  # refunds the gateway has processed
    refund_in_flight_paise: int = 0  # requested / pending / uncertain: not final yet


class PaymentEventOut(BaseModel):
    id: UUID
    event_type: str
    source: str
    outcome: str
    provider_event_id: str | None
    provider_payment_id: str | None
    created_at: datetime


class AdminPaymentDetail(AdminPaymentOut):
    events: list[PaymentEventOut]
    refunds: list[dict[str, Any]] = []
    refund_availability: dict[str, Any] | None = None


class AdminPaymentPage(BaseModel):
    items: list[AdminPaymentOut]
    limit: int
    offset: int
    has_more: bool


class AdminPaymentSummary(BaseModel):
    currency: str = "INR"
    gross_captured_paise: int
    captured_count: int
    failed_count: int
    open_count: int
    review_required_count: int
    rejected_events_count: int
    refunds: dict[str, Any]  # real totals from the refunds table (policy decides whether NEW ones may start)


# ------------------------------------------------------------------ devices / notifications
class DeviceTokenRequest(StrictModel):
    token: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=4096)]
    platform: Literal["android", "ios", "web"]
    app: Literal["customer", "owner", "admin"]


class DeviceTokenRemoveRequest(StrictModel):
    token: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=4096)]


class PreferencesOut(BaseModel):
    push_enabled: bool
    email_enabled: bool
    booking_enabled: bool = True
    payment_enabled: bool = True
    promo_enabled: bool = True


class PreferencesUpdate(StrictModel):
    push_enabled: bool | None = None
    email_enabled: bool | None = None
    booking_enabled: bool | None = None
    payment_enabled: bool | None = None
    promo_enabled: bool | None = None


class UnreadCount(BaseModel):
    unread_count: int = Field(ge=0)
