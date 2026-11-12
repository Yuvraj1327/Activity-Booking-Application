from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.deps import AdminUser, DbSession
from app.core.errors import ValidationFailedError
from app.domain.booking_state import TRANSITIONS
from app.domain.payment_state import TRANSITIONS as PAYMENT_TRANSITIONS
from app.schemas.booking import AdminBookingOut, AdminBookingPage
from app.schemas.catalog import Limit
from app.schemas.payment import AdminPaymentDetail, AdminPaymentPage, AdminPaymentSummary
from app.schemas.profile import ProfileOut
from app.services.bookings import BookingService
from app.services.payments import PaymentService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me", response_model=ProfileOut, summary="Verify the caller is an authorised admin")
async def admin_me(user: AdminUser) -> ProfileOut:
    """Used by the admin web to confirm access server-side. Admin modules arrive in Step 8."""
    return ProfileOut.model_validate(user.profile)


@router.get("/bookings", response_model=AdminBookingPage, summary="All bookings on the platform (read-only)")
async def admin_bookings(
    request: Request,
    _: AdminUser,
    session: DbSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    venue_id: UUID | None = None,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> AdminBookingPage:
    if status_filter is not None and status_filter not in TRANSITIONS:
        raise ValidationFailedError("Unknown booking status.", code="INVALID_STATUS")
    return await BookingService(session, request.app.state.settings).list_admin(
        status_filter, venue_id, limit, offset
    )


@router.get("/bookings/{booking_id}", response_model=AdminBookingOut, summary="Booking with history")
async def admin_booking(
    booking_id: UUID, request: Request, _: AdminUser, session: DbSession
) -> AdminBookingOut:
    return await BookingService(session, request.app.state.settings).get_admin(booking_id)


# ------------------------------------------------------------------ payments (read-only)
def _pay(request: Request, session: DbSession) -> PaymentService:
    return PaymentService(session, request.app.state.settings, request.app.state.payment_gateway)


@router.get("/payments/summary", response_model=AdminPaymentSummary, summary="Payment totals and counts")
async def payments_summary(request: Request, _: AdminUser, session: DbSession) -> AdminPaymentSummary:
    return await _pay(request, session).admin_summary()


@router.get("/payments", response_model=AdminPaymentPage, summary="All payments (read-only)")
async def admin_payments(
    request: Request,
    _: AdminUser,
    session: DbSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    review_required: bool | None = None,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> AdminPaymentPage:
    if status_filter is not None and status_filter not in PAYMENT_TRANSITIONS:
        raise ValidationFailedError("Unknown payment status.", code="INVALID_STATUS")
    return await _pay(request, session).admin_list(status_filter, review_required, limit, offset)


@router.get(
    "/payments/{payment_id}", response_model=AdminPaymentDetail, summary="Payment with gateway events"
)
async def admin_payment(
    payment_id: UUID, request: Request, _: AdminUser, session: DbSession
) -> AdminPaymentDetail:
    return await _pay(request, session).admin_get(payment_id)
