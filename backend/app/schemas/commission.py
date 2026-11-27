"""Request bodies for commission management."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from app.schemas.profile import StrictModel

Bps = Annotated[int, Field(ge=0, le=10000, description="Basis points: 1000 = 10.00%")]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class CommissionRuleCreate(StrictModel):
    scope: Literal["global", "activity", "venue"]
    category_id: UUID | None = None
    venue_id: UUID | None = None
    commission_bps: Bps
    is_active: bool = True
    effective_from: datetime | None = Field(
        default=None, description="Defaults to now. Cannot be in the past."
    )
    reason: Reason

    @model_validator(mode="after")
    def _target(self) -> Self:
        want = {"global": (False, False), "activity": (True, False), "venue": (False, True)}[self.scope]
        if (self.category_id is not None, self.venue_id is not None) != want:
            raise ValueError(
                "global rules take no target; activity rules need category_id only; venue rules need venue_id only"
            )
        return self


class CommissionRuleChange(StrictModel):
    commission_bps: Bps | None = None
    is_active: bool | None = None
    effective_from: datetime | None = None
    reason: Reason

    @model_validator(mode="after")
    def _something(self) -> Self:
        if self.commission_bps is None and self.is_active is None:
            raise ValueError("send commission_bps and/or is_active")
        return self
