"""Customer-facing availability and bookings."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request, Response, status

from app.api.deps import AnyUser, CustomerUser, DbSession
from app.schemas.booking import (
    AvailabilityOut,
    AvailableDatesOut,
    BookingOut,
    BookingPage,
    BookingRequest,
    CancellationPreview,
    CancelRequest,
    QuoteOut,
)
from app.schemas.catalog import Limit
from app.services.availability import AvailabilityService
from app.services.bookings import BookingService
from app.services.dispatch import dispatch_in_background

router = APIRouter(tags=["bookings"])


def _avail(request: Request, session: DbSession) -> AvailabilityService:
    return AvailabilityService(session, request.app.state.settings)


def _book(request: Request, session: DbSession) -> BookingService:
    return BookingService(session, request.app.state.settings)


@router.get(
    "/venues/{venue_id}/availability",
    response_model=AvailabilityOut,
    summary="Genuinely available slots for one date (per court)",
)
async def availability(
    venue_id: UUID,
    request: Request,
    _: AnyUser,
    session: DbSession,
    date_: Annotated[date, Query(alias="date")],
    resource_id: UUID | None = None,
) -> AvailabilityOut:
    svc = _avail(request, session)
    return await svc.for_date(venue_id, date_, resource_id)


@router.get(
    "/venues/{venue_id}/availability/dates",
    response_model=AvailableDatesOut,
    summary="Dates in a range (max 31 days) that have at least one free slot",
)
async def availability_dates(
    venue_id: UUID,
    request: Request,
    _: AnyUser,
    session: DbSession,
    date_from: date,
    date_to: date,
) -> AvailableDatesOut:
    return await _avail(request, session).dates(venue_id, date_from, date_to)


@router.post("/bookings/quote", response_model=QuoteOut, summary="Server-side price for a slot")
async def quote(body: BookingRequest, request: Request, user: CustomerUser, session: DbSession) -> QuoteOut:
    out = await _book(request, session).quote(body, user.id)
    await session.commit()
    return out


@router.post(
    "/bookings",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a booking (hold). Send an Idempotency-Key header to make retries safe.",
)
async def create_booking(
    body: BookingRequest,
    request: Request,
    response: Response,
    user: CustomerUser,
    session: DbSession,
    background: BackgroundTasks,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> BookingOut:
    out, created = await _book(request, session).create(user.id, body, idempotency_key)
    background.add_task(dispatch_in_background, request.app)
    if not created:
        response.status_code = status.HTTP_200_OK  # replay of an earlier identical request
    return out


@router.get("/bookings", response_model=BookingPage, summary="My bookings")
async def my_bookings(
    request: Request,
    user: CustomerUser,
    session: DbSession,
    bucket: Literal["upcoming", "past", "cancelled"] = "upcoming",
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> BookingPage:
    return await _book(request, session).list_mine(user.id, bucket, limit, offset)


@router.get("/bookings/{booking_id}", response_model=BookingOut, summary="One of my bookings")
async def my_booking(
    booking_id: UUID, request: Request, user: CustomerUser, session: DbSession
) -> BookingOut:
    return await _book(request, session).get_mine(user.id, booking_id)


@router.get(
    "/bookings/{booking_id}/cancellation-preview",
    response_model=CancellationPreview,
    summary="Can this booking be cancelled, and why not",
)
async def cancellation_preview(
    booking_id: UUID, request: Request, user: CustomerUser, session: DbSession
) -> CancellationPreview:
    return await _book(request, session).cancellation_preview(user.id, booking_id)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut, summary="Cancel my booking")
async def cancel_booking(
    booking_id: UUID,
    request: Request,
    user: CustomerUser,
    session: DbSession,
    background: BackgroundTasks,
    body: CancelRequest | None = None,
) -> BookingOut:
    out = await _book(request, session).cancel(user.id, booking_id, body.reason if body else None)
    background.add_task(dispatch_in_background, request.app)
    return out
