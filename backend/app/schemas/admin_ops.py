"""Request bodies for the admin operations modules. Responses are plain JSON built by the services."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from app.schemas.profile import StrictModel

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Priority = Literal["low", "normal", "high", "urgent"]


class RoleCreate(StrictModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    permissions: list[str] = Field(max_length=100)


class RoleUpdate(StrictModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    permissions: list[str] | None = Field(default=None, max_length=100)
    reason: Reason


class ReasonBody(StrictModel):
    reason: Reason


class AssignRole(StrictModel):
    role_id: UUID | None  # null removes the administrator's role (no access)
    reason: Reason


class SettingChange(StrictModel):
    value: bool
    reason: Reason


# ------------------------------------------------------------------ venues / KYC
class VenueDecision(StrictModel):
    reason: Reason | None = None


class VenueReasonRequired(StrictModel):
    reason: Reason


class ReportResolve(StrictModel):
    status: Literal["reviewing", "dismissed", "action_taken"]
    note: Reason | None = None

    @model_validator(mode="after")
    def _note(self) -> "ReportResolve":
        if self.status in ("dismissed", "action_taken") and not self.note:
            raise ValueError("A note is required to close a report")
        return self


class VenueReportCreate(StrictModel):
    reason: Literal["inaccurate_info", "unsafe", "fraud", "inappropriate", "other"]
    details: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class KycDocDecision(StrictModel):
    decision: Literal["approved", "rejected"]
    reason: Reason | None = None

    @model_validator(mode="after")
    def _reason(self) -> "KycDocDecision":
        if self.decision == "rejected" and not self.reason:
            raise ValueError("A rejection reason is required")
        return self


class KycOwnerDecision(StrictModel):
    decision: Literal["verified", "rejected"]
    reason: Reason | None = None

    @model_validator(mode="after")
    def _reason(self) -> "KycOwnerDecision":
        if self.decision == "rejected" and not self.reason:
            raise ValueError("A rejection reason is required")
        return self


# ------------------------------------------------------------------ bookings / disputes / refunds
class AdminCancel(StrictModel):
    reason: Reason
    dispute_id: UUID | None = None


class DisputeCreate(StrictModel):
    booking_id: UUID
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=160)]
    description: LongText | None = None
    raised_by_role: Literal["customer", "owner", "admin"] = "customer"
    priority: Priority = "normal"


class DisputeNote(StrictModel):
    kind: Literal["note", "evidence"] = "note"
    body: LongText


class DisputeUpdate(StrictModel):
    status: Literal["open", "investigating"] | None = None
    priority: Priority | None = None
    reason: Reason | None = None


class DisputeResolve(StrictModel):
    outcome: Literal["resolved", "rejected"]
    resolution_type: Literal["no_action", "refund_full", "refund_partial", "booking_cancelled", "other"]
    resolution_note: Reason


class RefundCreate(StrictModel):
    amount_paise: int | None = Field(
        default=None, gt=0, le=100_000_000
    )  # null = refund the whole remaining amount
    reason: Reason
    dispute_id: UUID | None = None


# ------------------------------------------------------------------ finance
class FinanceConfigCreate(StrictModel):
    platform_fee_bps: int = Field(ge=0, le=10000)
    platform_fee_fixed_paise: int = Field(ge=0, le=100_000_000)
    tax_rate_bps: int = Field(ge=0, le=10000)
    tax_on: Literal["fee", "base_and_fee"]
    commission_bps: int = Field(ge=0, le=10000)
    discount_borne_by: Literal["platform", "owner"]
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class PayoutCreate(StrictModel):
    owner_id: UUID
    amount_paise: int = Field(gt=0, le=1_000_000_000)
    period_from: date | None = None
    period_to: date | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class PayoutPaid(StrictModel):
    method: Literal["bank_transfer", "upi", "other"]
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=100)]


class ReconcileRun(StrictModel):
    date_from: date
    date_to: date


# ------------------------------------------------------------------ support
class TicketReply(StrictModel):
    body: LongText
    internal: bool = False


class TicketUpdate(StrictModel):
    status: Literal["open", "in_progress", "resolved", "closed"] | None = None
    priority: Priority | None = None
    assigned_to_me: bool | None = None
    booking_id: UUID | None = None  # present (even null) = change the link; absent = leave it


# ------------------------------------------------------------------ catalogue / coupons / CMS
class CategoryCreate(StrictModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    slug: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=80)] | None = None
    icon_key: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    sort_order: int = Field(default=0, ge=0, le=10000)


class CategoryUpdate(StrictModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None = None
    icon_key: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


class CouponBody(StrictModel):
    code: Annotated[
        str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9_-]{3,30}$")
    ]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    discount_type: Literal["percent", "fixed"]
    percent_bps: int | None = Field(default=None, ge=1, le=10000)
    fixed_paise: int | None = Field(default=None, gt=0, le=100_000_000)
    max_discount_paise: int | None = Field(default=None, gt=0, le=100_000_000)
    min_booking_paise: int = Field(default=0, ge=0, le=100_000_000)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    usage_limit_total: int | None = Field(default=None, gt=0, le=10_000_000)
    usage_limit_per_user: int | None = Field(default=None, gt=0, le=1000)
    first_booking_only: bool = False
    eligible_category_ids: list[UUID] = Field(default_factory=list, max_length=50)
    eligible_city_ids: list[UUID] = Field(default_factory=list, max_length=50)
    eligible_venue_ids: list[UUID] = Field(default_factory=list, max_length=200)
    is_active: bool = True

    @model_validator(mode="after")
    def _shape(self) -> "CouponBody":
        if self.discount_type == "percent" and (self.percent_bps is None or self.fixed_paise is not None):
            raise ValueError("A percentage coupon needs percent_bps and no fixed amount")
        if self.discount_type == "fixed" and (self.fixed_paise is None or self.percent_bps is not None):
            raise ValueError("A fixed coupon needs fixed_paise and no percentage")
        if self.valid_from and self.valid_until and self.valid_from >= self.valid_until:
            raise ValueError("valid_from must be before valid_until")
        return self


class CouponPatch(StrictModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    max_discount_paise: int | None = Field(default=None, gt=0, le=100_000_000)
    min_booking_paise: int | None = Field(default=None, ge=0, le=100_000_000)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    usage_limit_total: int | None = Field(default=None, gt=0, le=10_000_000)
    usage_limit_per_user: int | None = Field(default=None, gt=0, le=1000)
    first_booking_only: bool | None = None
    eligible_category_ids: list[UUID] | None = Field(default=None, max_length=50)
    eligible_city_ids: list[UUID] | None = Field(default=None, max_length=50)
    eligible_venue_ids: list[UUID] | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class CmsCreate(StrictModel):
    kind: Literal["page", "faq"]
    slug: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=80)]
    audience: Literal["all", "customer", "owner"] = "all"
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    body: Annotated[str, StringConstraints(min_length=1, max_length=50000)]
    sort_order: int = Field(default=0, ge=0, le=10000)


class CmsUpdate(StrictModel):
    audience: Literal["all", "customer", "owner"] | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = (
        None
    )
    body: Annotated[str, StringConstraints(min_length=1, max_length=50000)] | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)
