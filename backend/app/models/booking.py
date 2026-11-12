from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TSTZRANGE, Range
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin, uuid_pk

BOOKING_STATUSES = (
    "pending_payment",
    "payment_failed",
    "confirmed",
    "expired",
    "cancelled_by_customer",
    "cancelled_by_owner",
    "completed",
    "refund_pending",
    "refunded",
)


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"
    id: Mapped[UUID] = uuid_pk()
    booking_code: Mapped[str] = mapped_column(Text, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False
    )
    resource_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venue_resources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    payment_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'unpaid'"))
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)  # local date at the venue
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    base_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    price_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    venue_name: Mapped[str] = mapped_column(Text, nullable=False)
    resource_name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    request_hash: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL")
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text)


class BookingSlot(Base):
    """Reserved time. The database forbids overlapping blocking rows on one resource."""

    __tablename__ = "booking_slots"
    id: Mapped[UUID] = uuid_pk()
    booking_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venue_resources.id", ondelete="RESTRICT"), nullable=False
    )
    slot_range: Mapped[Range[datetime]] = mapped_column(TSTZRANGE, nullable=False)
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class BookingStatusHistory(Base):
    __tablename__ = "booking_status_history"
    id: Mapped[UUID] = uuid_pk()
    booking_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL")
    )
    actor_role: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class AvailabilityBlock(Base):
    """A temporary unavailable period set by the owner (whole venue when resource_id is NULL)."""

    __tablename__ = "availability_blocks"
    id: Mapped[UUID] = uuid_pk()
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venue_resources.id", ondelete="CASCADE")
    )
    block_range: Mapped[Range[datetime]] = mapped_column(TSTZRANGE, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
