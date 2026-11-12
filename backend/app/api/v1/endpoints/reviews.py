"""Reviews: customers review completed bookings, anyone signed in reads a venue's reviews."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.api.deps import AnyUser, CustomerUser, DbSession
from app.schemas.catalog import Limit
from app.schemas.review import ReviewCreate, ReviewOut, ReviewPage
from app.services.reviews import ReviewService

router = APIRouter(tags=["reviews"])


def _svc(request: Request, session: DbSession) -> ReviewService:
    return ReviewService(session, request.app.state.settings)


@router.post(
    "/bookings/{booking_id}/review",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Review a completed booking (once)",
)
async def create_review(
    booking_id: UUID, body: ReviewCreate, request: Request, user: CustomerUser, session: DbSession
) -> ReviewOut:
    return await _svc(request, session).create(user.id, booking_id, body.rating, body.comment)


@router.get("/bookings/{booking_id}/review", response_model=ReviewOut, summary="My review of a booking")
async def my_review(booking_id: UUID, request: Request, user: CustomerUser, session: DbSession) -> ReviewOut:
    return await _svc(request, session).mine(user.id, booking_id)


@router.get("/venues/{venue_id}/reviews", response_model=ReviewPage, summary="Reviews of a published venue")
async def venue_reviews(
    venue_id: UUID,
    request: Request,
    _: AnyUser,
    session: DbSession,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> ReviewPage:
    return await _svc(request, session).venue_reviews(venue_id, limit, offset)
