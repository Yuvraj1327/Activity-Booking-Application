from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin, uuid_pk

VENUE_STATUSES = ("draft", "published", "archived")


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"
    id: Mapped[UUID] = uuid_pk()
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("owner_profiles.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    city_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cities.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    address_line: Mapped[str | None] = mapped_column(Text)
    postal_code: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    google_place_id: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    starting_price_paise: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="INR")
    rating_avg: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class VenueCategory(Base):
    __tablename__ = "venue_categories"
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class VenueAmenity(Base):
    __tablename__ = "venue_amenities"
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    amenity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("amenities.id", ondelete="RESTRICT"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class VenueImage(Base):
    __tablename__ = "venue_images"
    id: Mapped[UUID] = uuid_pk()
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alt_text: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class VenueResource(TimestampMixin, Base):
    """A bookable unit inside a venue (e.g. a court). Structural only until Q1/Q2/Q17 are answered."""

    __tablename__ = "venue_resources"
    id: Mapped[UUID] = uuid_pk()
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # Set by the owner. While either is NULL the resource is "not configured" and has no slots.
    slot_minutes: Mapped[int | None] = mapped_column(Integer)
    slot_price_paise: Mapped[int | None] = mapped_column(BigInteger)


class Favorite(Base):
    __tablename__ = "favorites"
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ScheduleRule(Base):
    """One open interval on a weekday (0 = Monday). Local time at the venue."""

    __tablename__ = "schedule_rules"
    id: Mapped[UUID] = uuid_pk()
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    opens_at: Mapped[time] = mapped_column(Time, nullable=False)
    closes_at: Mapped[time] = mapped_column(Time, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class ScheduleException(Base):
    """Special date: a closure or one custom interval that replaces the regular hours."""

    __tablename__ = "schedule_exceptions"
    id: Mapped[UUID] = uuid_pk()
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    on_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    opens_at: Mapped[time | None] = mapped_column(Time)
    closes_at: Mapped[time | None] = mapped_column(Time)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
