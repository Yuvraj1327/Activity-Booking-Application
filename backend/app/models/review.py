"""Customer reviews and owner replies (Step 10)."""

from uuid import UUID

from sqlalchemy import ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin, uuid_pk


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    id: Mapped[UUID] = uuid_pk()
    booking_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    venue_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)


class ReviewResponse(TimestampMixin, Base):
    __tablename__ = "review_responses"
    id: Mapped[UUID] = uuid_pk()
    review_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    owner_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("owner_profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
