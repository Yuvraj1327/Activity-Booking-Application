"""Admin operations tables (migration 0011): permissions, moderation, KYC, refunds, finance, coupons, CMS."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, FetchedValue, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin, uuid_pk


def _fk(target: str, *, ondelete: str, nullable: bool = True, pk: bool = False) -> Mapped[Any]:
    return mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable, primary_key=pk
    )


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


def _ts() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True))


class PlatformSetting(Base):
    __tablename__ = "platform_settings"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    updated_at: Mapped[datetime] = _now()


class AdminRole(TimestampMixin, Base):
    __tablename__ = "admin_roles"
    id: Mapped[UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    permissions: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")


class AdminProfile(Base):
    __tablename__ = "admin_profiles"
    user_id: Mapped[UUID] = _fk("profiles.id", ondelete="CASCADE", nullable=False, pk=True)
    role_id: Mapped[UUID] = _fk("admin_roles.id", ondelete="RESTRICT", nullable=False)
    assigned_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    assigned_at: Mapped[datetime] = _now()


class VenueModerationEvent(Base):
    __tablename__ = "venue_moderation_events"
    id: Mapped[UUID] = uuid_pk()
    venue_id: Mapped[UUID] = _fk("venues.id", ondelete="CASCADE", nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    actor_role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _now()


class VenueReport(TimestampMixin, Base):
    __tablename__ = "venue_reports"
    id: Mapped[UUID] = uuid_pk()
    venue_id: Mapped[UUID] = _fk("venues.id", ondelete="CASCADE", nullable=False)
    reporter_id: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    resolved_at: Mapped[datetime | None] = _ts()


class OwnerKycDocument(TimestampMixin, Base):
    __tablename__ = "owner_kyc_documents"
    id: Mapped[UUID] = uuid_pk()
    owner_id: Mapped[UUID] = _fk("owner_profiles.user_id", ondelete="CASCADE", nullable=False)
    doc_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    original_filename: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    reviewed_at: Mapped[datetime | None] = _ts()


class SupportTicketMessage(Base):
    __tablename__ = "support_ticket_messages"
    id: Mapped[UUID] = uuid_pk()
    ticket_id: Mapped[UUID] = _fk("support_tickets.id", ondelete="CASCADE", nullable=False)
    author_id: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    author_role: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _now()


class Dispute(TimestampMixin, Base):
    __tablename__ = "disputes"
    id: Mapped[UUID] = uuid_pk()
    booking_id: Mapped[UUID] = _fk("bookings.id", ondelete="RESTRICT", nullable=False)
    payment_id: Mapped[UUID | None] = _fk("payments.id", ondelete="SET NULL")
    raised_by_role: Mapped[str] = mapped_column(Text, nullable=False)
    raised_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    priority: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'normal'"))
    resolution_type: Mapped[str | None] = mapped_column(Text)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    resolved_at: Mapped[datetime | None] = _ts()
    created_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")


class DisputeEvent(Base):
    __tablename__ = "dispute_events"
    id: Mapped[UUID] = uuid_pk()
    dispute_id: Mapped[UUID] = _fk("disputes.id", ondelete="CASCADE", nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    actor_id: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    actor_role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _now()


class Refund(TimestampMixin, Base):
    __tablename__ = "refunds"
    id: Mapped[UUID] = uuid_pk()
    payment_id: Mapped[UUID] = _fk("payments.id", ondelete="RESTRICT", nullable=False)
    booking_id: Mapped[UUID] = _fk("bookings.id", ondelete="RESTRICT", nullable=False)
    dispute_id: Mapped[UUID | None] = _fk("disputes.id", ondelete="SET NULL")
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'requested'"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'admin'"))
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    provider_refund_id: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    initiated_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    processed_at: Mapped[datetime | None] = _ts()


class FinanceConfig(Base):
    __tablename__ = "finance_configs"
    id: Mapped[UUID] = uuid_pk()
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, server_default=FetchedValue())
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    platform_fee_bps: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    platform_fee_fixed_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    tax_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tax_on: Mapped[str] = mapped_column(Text, nullable=False)
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    discount_borne_by: Mapped[str] = mapped_column(Text, nullable=False)
    commission_base: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'base'"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    created_at: Mapped[datetime] = _now()
    approved_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    approved_at: Mapped[datetime | None] = _ts()
    effective_from: Mapped[datetime | None] = _ts()
    retired_at: Mapped[datetime | None] = _ts()


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id: Mapped[UUID] = uuid_pk()
    entry_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[UUID] = _fk("owner_profiles.user_id", ondelete="RESTRICT", nullable=False)
    venue_id: Mapped[UUID] = _fk("venues.id", ondelete="RESTRICT", nullable=False)
    booking_id: Mapped[UUID] = _fk("bookings.id", ondelete="RESTRICT", nullable=False)
    payment_id: Mapped[UUID] = _fk("payments.id", ondelete="RESTRICT", nullable=False)
    refund_id: Mapped[UUID | None] = _fk("refunds.id", ondelete="RESTRICT")
    config_id: Mapped[UUID] = _fk("finance_configs.id", ondelete="RESTRICT", nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    platform_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    commission_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _now()
    # The commission actually applied (NULL on entries written before commission management existed).
    commission_bps: Mapped[int | None] = mapped_column(Integer)
    commission_scope: Mapped[str | None] = mapped_column(Text)
    commission_rule_id: Mapped[UUID | None] = _fk("commission_rules.id", ondelete="RESTRICT")
    commission_rule_version: Mapped[int | None] = mapped_column(Integer)
    commission_base_paise: Mapped[int | None] = mapped_column(BigInteger)


class Payout(TimestampMixin, Base):
    __tablename__ = "payouts"
    id: Mapped[UUID] = uuid_pk()
    owner_id: Mapped[UUID] = _fk("owner_profiles.user_id", ondelete="RESTRICT", nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    period_from: Mapped[date | None] = mapped_column(Date)
    period_to: Mapped[date | None] = mapped_column(Date)
    method: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    approved_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    approved_at: Mapped[datetime | None] = _ts()
    paid_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    paid_at: Mapped[datetime | None] = _ts()
    cancel_reason: Mapped[str | None] = mapped_column(Text)


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"
    id: Mapped[UUID] = uuid_pk()
    period_from: Mapped[date] = mapped_column(Date, nullable=False)
    period_to: Mapped[date] = mapped_column(Date, nullable=False)
    gateway_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    gateway_note: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    mismatch_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    run_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")
    created_at: Mapped[datetime] = _now()


class ReconciliationItem(Base):
    __tablename__ = "reconciliation_items"
    id: Mapped[UUID] = uuid_pk()
    run_id: Mapped[UUID] = _fk("reconciliation_runs.id", ondelete="CASCADE", nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payment_id: Mapped[UUID | None] = _fk("payments.id", ondelete="SET NULL")
    refund_id: Mapped[UUID | None] = _fk("refunds.id", ondelete="SET NULL")
    provider_payment_id: Mapped[str | None] = mapped_column(Text)
    expected_paise: Mapped[int | None] = mapped_column(BigInteger)
    actual_paise: Mapped[int | None] = mapped_column(BigInteger)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()


class Coupon(TimestampMixin, Base):
    __tablename__ = "coupons"
    id: Mapped[UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    discount_type: Mapped[str] = mapped_column(Text, nullable=False)
    percent_bps: Mapped[int | None] = mapped_column(Integer)
    fixed_paise: Mapped[int | None] = mapped_column(BigInteger)
    max_discount_paise: Mapped[int | None] = mapped_column(BigInteger)
    min_booking_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    valid_from: Mapped[datetime | None] = _ts()
    valid_until: Mapped[datetime | None] = _ts()
    usage_limit_total: Mapped[int | None] = mapped_column(Integer)
    usage_limit_per_user: Mapped[int | None] = mapped_column(Integer)
    first_booking_only: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    eligible_category_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, server_default=text("'{}'")
    )
    eligible_city_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, server_default=text("'{}'")
    )
    eligible_venue_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, server_default=text("'{}'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"
    id: Mapped[UUID] = uuid_pk()
    coupon_id: Mapped[UUID] = _fk("coupons.id", ondelete="RESTRICT", nullable=False)
    booking_id: Mapped[UUID] = _fk("bookings.id", ondelete="RESTRICT", nullable=False, pk=False)
    customer_id: Mapped[UUID] = _fk("customer_profiles.user_id", ondelete="RESTRICT", nullable=False)
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = _now()


class CmsContent(TimestampMixin, Base):
    __tablename__ = "cms_contents"
    id: Mapped[UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    audience: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'all'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    published_at: Mapped[datetime | None] = _ts()
    updated_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="SET NULL")


class CommissionRule(Base):
    """Identity of a commission rule (one per global / category / venue). Its history is in the versions."""

    __tablename__ = "commission_rules"
    id: Mapped[UUID] = uuid_pk()
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[UUID | None] = _fk("categories.id", ondelete="RESTRICT")
    venue_id: Mapped[UUID | None] = _fk("venues.id", ondelete="RESTRICT")
    created_by: Mapped[UUID | None] = _fk("profiles.id", ondelete="RESTRICT")
    created_at: Mapped[datetime] = _now()


class CommissionRuleVersion(Base):
    """Append-only: every change is a new row. The state at time T is the row with the greatest effective_from <= T."""

    __tablename__ = "commission_rule_versions"
    id: Mapped[UUID] = uuid_pk()
    rule_id: Mapped[UUID] = _fk("commission_rules.id", ondelete="RESTRICT", nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_bps: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[UUID] = _fk("profiles.id", ondelete="RESTRICT", nullable=False)
    created_at: Mapped[datetime] = _now()


class BookingCommissionSnapshot(Base):
    """The commission resolved for a booking when it was created. Never updated."""

    __tablename__ = "booking_commission_snapshots"
    booking_id: Mapped[UUID] = _fk("bookings.id", ondelete="RESTRICT", nullable=False, pk=True)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[UUID | None] = _fk("commission_rules.id", ondelete="RESTRICT")
    rule_version_id: Mapped[UUID | None] = _fk("commission_rule_versions.id", ondelete="RESTRICT")
    rule_version: Mapped[int | None] = mapped_column(Integer)
    category_id: Mapped[UUID | None] = _fk("categories.id", ondelete="RESTRICT")
    commission_bps: Mapped[int | None] = mapped_column(Integer)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime] = _now()
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'booking_created'"))
    ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    priority: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
