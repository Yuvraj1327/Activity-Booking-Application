"""Identity tables. `profiles.id` equals Supabase `auth.users.id` (that table is not mapped)."""

from uuid import UUID

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin

ROLES = ("customer", "owner", "admin")
STATUSES = ("active", "suspended")


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    avatar_path: Mapped[str | None] = mapped_column(Text)

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class CustomerProfile(TimestampMixin, Base):
    __tablename__ = "customer_profiles"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "role"], ["profiles.id", "profiles.role"], ondelete="CASCADE"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="customer")
    preferred_city_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cities.id", ondelete="SET NULL")
    )


class OwnerProfile(TimestampMixin, Base):
    __tablename__ = "owner_profiles"
    __table_args__ = (
        ForeignKeyConstraint(["user_id", "role"], ["profiles.id", "profiles.role"], ondelete="CASCADE"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="owner")
    business_name: Mapped[str] = mapped_column(Text, nullable=False)
    business_phone: Mapped[str | None] = mapped_column(Text)
    business_email: Mapped[str | None] = mapped_column(Text)
    business_address: Mapped[str | None] = mapped_column(Text)
