from datetime import date, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response, status

from app.api.deps import DbSession, OwnerUser
from app.core.errors import ValidationFailedError
from app.schemas.booking import OwnerBookingOut, OwnerBookingPage
from app.schemas.catalog import Limit
from app.schemas.owner import AnalyticsOut, DashboardOut, NotificationPage
from app.schemas.payment import OwnerEarningsOut, OwnerPaymentPage
from app.schemas.review import OwnerReviewOut, OwnerReviewPage, ReplyCreate
from app.services.bookings import BookingService
from app.services.commission import CommissionService
from app.services.owner_business import OwnerBusinessService
from app.services.payments import PaymentService
from app.services.reviews import ReviewService

router = APIRouter(prefix="/owners", tags=["owner-business"])


def _svc(request: Request, session: DbSession) -> OwnerBusinessService:
    return OwnerBusinessService(session, request.app.state.settings)


@router.get(
    "/dashboard",
    response_model=DashboardOut,
    summary="Dashboard: real venue data; booking/revenue marked unavailable",
)
async def dashboard(request: Request, user: OwnerUser, session: DbSession) -> DashboardOut:
    return await _svc(request, session).dashboard(user.id)


@router.get("/analytics", response_model=AnalyticsOut, summary="Analytics for a date range")
async def analytics(
    request: Request,
    user: OwnerUser,
    session: DbSession,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> AnalyticsOut:
    end = date_to or date.today()
    start = date_from or end - timedelta(days=29)
    if start > end:
        raise ValidationFailedError("date_from cannot be after date_to.", code="INVALID_DATE_RANGE")
    if (end - start).days > 366:
        raise ValidationFailedError("Choose a range of at most one year.", code="INVALID_DATE_RANGE")
    return await _svc(request, session).analytics(user.id, start, end)


# ------------------------------------------------------------------ data that needs later steps
@router.get("/bookings", response_model=OwnerBookingPage, summary="Bookings at the owner's venues")
async def bookings(
    request: Request,
    user: OwnerUser,
    session: DbSession,
    bucket: Literal["upcoming", "past", "cancelled"] = "upcoming",
    venue_id: UUID | None = None,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> OwnerBookingPage:
    svc = BookingService(session, request.app.state.settings)
    return await svc.list_owner(user.id, bucket, venue_id, limit, offset)


@router.get("/bookings/{booking_id}", response_model=OwnerBookingOut, summary="Booking details")
async def booking_detail(
    booking_id: UUID, request: Request, user: OwnerUser, session: DbSession
) -> OwnerBookingOut:
    return await BookingService(session, request.app.state.settings).get_owner(user.id, booking_id)


@router.get(
    "/earnings", response_model=OwnerEarningsOut, summary="Gross paid amounts (confirmed payments only)"
)
async def earnings(request: Request, user: OwnerUser, session: DbSession) -> OwnerEarningsOut:
    """Only what customers actually paid. Commission, tax, deductions and payouts are reported as
    unavailable because those rules are not approved yet (open questions Q7, Q8, Q10)."""
    return await _payments(request, session).owner_earnings(user.id)


@router.get(
    "/earnings/breakdown",
    summary="Booking-wise earnings: gross, commission %, deductions, net payable (own venues only)",
)
async def earnings_breakdown(
    request: Request,
    user: OwnerUser,
    session: DbSession,
    venue_id: UUID | None = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> dict[str, Any]:
    """Read from the immutable ledger. `net_payable` is an accounting figure, not a completed transfer."""
    lo = hi = None
    if date_from or date_to:
        from app.services.admin import AdminService

        svc = AdminService(session, request.app.state.settings)
        start, end = svc.resolve_range(date_from or date_to, date_to or date_from)
        lo, hi = svc._bounds(start, end)
    return await CommissionService(session, request.app.state.settings).owner_earnings(
        user.id, venue_id=venue_id, lo=lo, hi=hi, limit=limit, offset=offset
    )


@router.get("/commission", summary="The commission rate that applies to each of my venues now, and its history")
async def owner_commission(
    request: Request, user: OwnerUser, session: DbSession, limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> dict[str, Any]:
    svc = CommissionService(session, request.app.state.settings)
    hist = await svc.history(scope=None, venue_id=None, category_id=None, lo=None, hi=None,
                             limit=limit, offset=offset, owner_id=user.id)
    for h in hist["items"]:  # owners see rates and dates, never which admin or why
        h.pop("changed_by", None), h.pop("changed_by_name", None), h.pop("reason", None)
    return {"current": await svc.owner_current_rates(user.id), "history": hist,
            "note": "A rate change only applies to bookings made after it takes effect. Bookings already made keep their rate."}


@router.get("/earnings/bookings/{booking_id}", summary="How one booking's net earnings were calculated")
async def earnings_booking(booking_id: UUID, request: Request, user: OwnerUser, session: DbSession) -> dict[str, Any]:
    out = await CommissionService(session, request.app.state.settings).booking_detail(booking_id, owner_id=user.id)
    if out["snapshot"]:  # internal rule ids / the other candidate rules are not for owners
        for k in ("candidates", "priority", "rule_id"):
            out["snapshot"].pop(k, None)
    if out["calculation"]:
        out["calculation"].pop("commission_rule_id", None)
    return out


@router.get("/payments", response_model=OwnerPaymentPage, summary="Payments received for my venues")
async def owner_payments(
    request: Request,
    user: OwnerUser,
    session: DbSession,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> OwnerPaymentPage:
    return await _payments(request, session).owner_payments(user.id, limit, offset)


@router.get("/reviews", response_model=OwnerReviewPage, summary="Reviews of my venues")
async def reviews(
    request: Request,
    user: OwnerUser,
    session: DbSession,
    rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    venue_id: UUID | None = None,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> OwnerReviewPage:
    return await ReviewService(session, request.app.state.settings).owner_reviews(
        user.id, rating, venue_id, limit, offset
    )


@router.post(
    "/reviews/{review_id}/reply",
    response_model=OwnerReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Reply to a review of my venue (once)",
)
async def reply_to_review(
    review_id: UUID, body: ReplyCreate, request: Request, user: OwnerUser, session: DbSession
) -> OwnerReviewOut:
    return await ReviewService(session, request.app.state.settings).reply(user.id, review_id, body.body)


def _payments(request: Request, session: DbSession) -> PaymentService:
    return PaymentService(session, request.app.state.settings, request.app.state.payment_gateway)


# ------------------------------------------------------------------ notifications (real)
@router.get("/notifications", response_model=NotificationPage, summary="Own notifications")
async def notifications(
    request: Request,
    user: OwnerUser,
    session: DbSession,
    group: Literal["all", "bookings", "payments", "reviews"] = "all",
    unread_only: bool = False,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> NotificationPage:
    return await _svc(request, session).notifications(user.id, group, unread_only, limit, offset)


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT, summary="Mark all read")
async def read_all(request: Request, user: OwnerUser, session: DbSession) -> Response:
    await _svc(request, session).mark_all_read(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT, summary="Mark one read"
)
async def read_one(notification_id: UUID, request: Request, user: OwnerUser, session: DbSession) -> Response:
    await _svc(request, session).mark_read(user.id, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
