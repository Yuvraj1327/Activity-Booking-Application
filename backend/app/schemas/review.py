"""Reviews and owner replies (Step 10)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.profile import StrictModel


class ReviewCreate(StrictModel):
    rating: int = Field(ge=1, le=5, strict=True)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        v = v.strip() if v else v
        return v or None


class ReplyCreate(StrictModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A reply cannot be empty.")
        return v


class ReplyOut(BaseModel):
    body: str
    created_at: datetime


class ReviewOut(BaseModel):
    id: UUID
    rating: int
    comment: str | None
    reviewer_name: str  # first name and last initial only
    created_at: datetime
    reply: ReplyOut | None = None


class OwnerReviewOut(ReviewOut):
    venue_id: UUID
    venue_name: str
    booking_code: str


class RatingSummary(BaseModel):
    average: float | None
    count: int
    distribution: dict[str, int]  # "1".."5" -> count


class ReviewPage(BaseModel):
    items: list[ReviewOut]
    summary: RatingSummary
    limit: int
    offset: int
    has_more: bool


class OwnerReviewPage(BaseModel):
    items: list[OwnerReviewOut]
    summary: RatingSummary
    limit: int
    offset: int
    has_more: bool
