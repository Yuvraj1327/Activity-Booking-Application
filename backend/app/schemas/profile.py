from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Phone = Annotated[str, StringConstraints(pattern=r"^\+[1-9][0-9]{6,14}$")]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
BusinessName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Email = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]

Language = Literal["en", "hi"]
Role = Literal["customer", "owner", "admin"]
SelfServiceRole = Literal["customer", "owner"]  # "admin" can never be requested through the API


class StrictModel(BaseModel):
    """Rejects unknown fields, so a client sending `role`, `status` or `id` gets a 422."""

    model_config = ConfigDict(extra="forbid")


class NonNullableUpdate(StrictModel):
    """PATCH body: omitted = unchanged, null = clear (only for fields that may be cleared)."""

    _non_nullable: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _reject_null_for_required(self) -> "NonNullableUpdate":
        for name in self._non_nullable:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: Role
    status: Literal["active", "suspended"]
    full_name: str
    email: str | None
    phone: str | None
    avatar_path: str | None
    language: Language
    deletion_requested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProfileCreate(StrictModel):
    role: SelfServiceRole
    full_name: PersonName
    phone: Phone | None = None
    # Owner accounts only
    business_name: BusinessName | None = None
    business_phone: Phone | None = None
    business_email: Email | None = None
    business_address: Address | None = None

    @model_validator(mode="after")
    def _owner_fields(self) -> "ProfileCreate":
        owner_only = (self.business_name, self.business_phone, self.business_email, self.business_address)
        if self.role == "owner" and not self.business_name:
            raise ValueError("business_name is required for owner accounts")
        if self.role == "customer" and any(v is not None for v in owner_only):
            raise ValueError("business fields are only valid for owner accounts")
        return self


class ProfileUpdate(NonNullableUpdate):
    _non_nullable = ("full_name", "language")

    full_name: PersonName | None = None
    language: Language | None = None
    phone: Phone | None = None
    avatar_path: Annotated[str, StringConstraints(min_length=1, max_length=300)] | None = None


class MeResponse(BaseModel):
    """Identity from the verified token plus the profile, if one exists yet."""

    user_id: UUID
    email: str | None
    phone: str | None
    has_profile: bool
    profile: ProfileOut | None


class CustomerMe(BaseModel):
    profile: ProfileOut
    preferred_city_id: UUID | None
    preferred_category_ids: list[UUID] = []


class CustomerUpdate(NonNullableUpdate):
    _non_nullable = ("preferred_category_ids",)

    preferred_city_id: UUID | None = None
    preferred_category_ids: Annotated[list[UUID], Field(max_length=20)] | None = None


class OwnerMe(BaseModel):
    profile: ProfileOut
    business_name: str
    business_phone: str | None
    business_email: str | None
    business_address: str | None


class OwnerUpdate(NonNullableUpdate):
    _non_nullable = ("business_name",)

    business_name: BusinessName | None = None
    business_phone: Phone | None = None
    business_email: Email | None = None
    business_address: Address | None = None


SupportKind = Literal["support", "feedback", "issue"]


class SupportTicketCreate(StrictModel):
    kind: SupportKind
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]
    app_version: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    platform: Literal["android", "ios", "web", "other"] | None = None


class SupportTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: SupportKind
    subject: str
    status: Literal["open", "closed"]
    created_at: datetime
