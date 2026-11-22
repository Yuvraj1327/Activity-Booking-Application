from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import AdminUser, CurrentUser, DbSession, load_admin_permissions, require_permission
from app.core.errors import ValidationFailedError
from app.domain.booking_state import TRANSITIONS
from app.domain.payment_state import TRANSITIONS as PAYMENT_TRANSITIONS
from app.schemas.admin import (
    ActivityPage,
    AdminBookingDetailOut,
    AdminBookingRowPage,
    AuditPage,
    BookingAnalytics,
    CustomerDetail,
    CustomerPage,
    DashboardOut,
    Granularity,
    OwnerDetail,
    OwnerPage,
    PlatformAnalytics,
    RevenueAnalytics,
    StatusChange,
    StatusChangeOut,
    VenueDetail,
    VenuePage,
)
from app.schemas.catalog import Limit
from app.schemas.payment import AdminPaymentDetail, AdminPaymentPage, AdminPaymentSummary
from app.schemas.profile import ProfileOut
from app.services import audit
from app.services.admin import AdminService
from app.services.payments import PaymentService

router = APIRouter(prefix="/admin", tags=["admin"])

Offset = Annotated[int, Query(ge=0, le=100_000)]
DateFrom = Annotated[date | None, Query(alias="from")]
DateTo = Annotated[date | None, Query(alias="to")]
SortOrder = Literal["asc", "desc"]
AccountStatus = Literal["active", "suspended"]
RefundFilter = Literal["none", "awaiting", "pending", "processed", "failed"]
BOOKING_PAYMENT_STATUSES = {"unpaid", "pending", "paid", "failed", "refunded", "partially_refunded"}


def _svc(request: Request, session: DbSession) -> AdminService:
    return AdminService(session, request.app.state.settings)


def _pay(request: Request, session: DbSession) -> PaymentService:
    return PaymentService(session, request.app.state.settings, request.app.state.payment_gateway)


class AdminMeOut(ProfileOut):
    admin_role: str | None = None
    permissions: list[str] = []


@router.get("/me", response_model=AdminMeOut, summary="Verify the caller is an authorised admin")
async def admin_me(user: AdminUser, session: DbSession) -> AdminMeOut:
    """Used by the admin web to confirm access server-side. Also returns the caller's permissions
    (empty when no role is assigned yet: the admin can sign in but sees nothing)."""
    role, perms = await load_admin_permissions(session, user.id)
    base = ProfileOut.model_validate(user.profile).model_dump()
    return AdminMeOut(**base, admin_role=role, permissions=sorted(perms))


# ------------------------------------------------------------------ dashboard and analytics
@router.get("/dashboard", response_model=DashboardOut, summary="KPIs, trends and recent activity")
async def dashboard(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("dashboard.view"))],
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> DashboardOut:
    return await _svc(request, session).dashboard(date_from, date_to)


@router.get("/analytics/bookings", response_model=BookingAnalytics, summary="Booking trends and status mix")
async def analytics_bookings(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("analytics.view"))],
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    granularity: Granularity = "day",
) -> BookingAnalytics:
    return await _svc(request, session).booking_analytics(date_from, date_to, granularity)


@router.get(
    "/analytics/revenue", response_model=RevenueAnalytics, summary="Recorded transaction totals and trends"
)
async def analytics_revenue(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("analytics.view"))],
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    granularity: Granularity = "day",
) -> RevenueAnalytics:
    return await _svc(request, session).revenue_analytics(date_from, date_to, granularity)


@router.get(
    "/analytics/platform", response_model=PlatformAnalytics, summary="Registrations, venues, categories"
)
async def analytics_platform(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("analytics.view"))],
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    granularity: Granularity = "day",
) -> PlatformAnalytics:
    return await _svc(request, session).platform_analytics(date_from, date_to, granularity)


@router.get("/activity", response_model=ActivityPage, summary="Latest platform events")
async def activity(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("dashboard.view"))],
    session: DbSession,
    limit: Limit = 20,
) -> ActivityPage:
    return ActivityPage(items=await _svc(request, session).activity(limit))


@router.get("/analytics/sports", summary="Bookings per sport (each booking split across a venue's sports)")
async def analytics_sports(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("analytics.view"))],
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> dict[str, Any]:
    svc = _svc(request, session)
    start, end = svc.resolve_range(date_from, date_to)
    shares, none = await svc.sports_breakdown(start, end)
    return {"range": svc._range_out(start, end), "items": shares, "uncategorised_bookings": none,
            "note": "A venue with several sports splits each booking equally between them, so the shares add up to the real total."}  # fmt: skip


@router.get("/analytics/cities", summary="Bookings and revenue per city")
async def analytics_cities(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("analytics.view"))],
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> dict[str, Any]:
    svc = _svc(request, session)
    start, end = svc.resolve_range(date_from, date_to)
    return {"range": svc._range_out(start, end), "items": await svc.cities_breakdown(start, end)}


@router.get("/analytics/venues", summary="Venue-wise booking performance")
async def analytics_venues(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("analytics.view"))],
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    city_id: UUID | None = None,
    category_id: UUID | None = None,
    owner_id: UUID | None = None,
    sort: Literal["bookings", "revenue", "cancellations", "name"] = "bookings",
    order: SortOrder = "desc",
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    svc = _svc(request, session)
    start, end = svc.resolve_range(date_from, date_to)
    items, more = await svc.venues_performance(
        start, end, city_id=city_id, category_id=category_id, owner_id=owner_id, sort=sort, order=order,
        limit=limit, offset=offset,
    )  # fmt: skip
    return {
        "range": svc._range_out(start, end),
        "items": items,
        "limit": limit,
        "offset": offset,
        "has_more": more,
    }


@router.get("/exports/analytics.csv", summary="Sport / city / venue analytics CSV")
async def export_analytics(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_permission("exports.download"))],
    session: DbSession,
    dimension: Literal["sport", "city", "venue"] = "sport",
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> Response:
    svc = _svc(request, session)
    start, end = svc.resolve_range(date_from, date_to)
    if dimension == "sport":
        shares, _none = await svc.sports_breakdown(start, end)
        header = ["sport", "bookings_split", "bookings_tagged", "venues", "gross_paid_paise"]
        rows = [[x.category, x.bookings, x.tagged_bookings, x.venues, x.gross_paid_paise] for x in shares]
    elif dimension == "city":
        header = [
            "city",
            "published_venues",
            "bookings",
            "confirmed",
            "completed",
            "cancelled",
            "gross_paid_paise",
        ]
        rows = [[c.city, c.venues, c.bookings, c.confirmed, c.completed, c.cancelled, c.gross_paid_paise]
                for c in await svc.cities_breakdown(start, end)]  # fmt: skip
    else:
        cap = request.app.state.settings.admin_export_max_rows
        items, _m = await svc.venues_performance(start, end, city_id=None, category_id=None, owner_id=None,
                                                  sort="bookings", order="desc", limit=min(cap, 5000), offset=0)  # fmt: skip
        header = [
            "venue",
            "city",
            "status",
            "bookings",
            "confirmed",
            "completed",
            "cancelled",
            "cancellation_rate_percent",
            "gross_paid_paise",
            "rating",
        ]
        rows = [[v.name, v.city, v.status, v.bookings, v.confirmed, v.completed, v.cancelled,
                 v.cancellation_rate_percent, v.gross_paid_paise, v.rating_avg] for v in items]  # fmt: skip
    audit.record(session, admin.profile, "admin.export", f"analytics_{dimension}", None, rows=len(rows),
                 filters={"from": str(start), "to": str(end)})  # fmt: skip
    await session.commit()
    return _csv(svc._csv(header, rows), f"zuruv-analytics-{dimension}.csv")


# ------------------------------------------------------------------ owners
@router.get("/owners", response_model=OwnerPage, summary="Venue owners (search, filter, sort)")
async def list_owners(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("owners.view"))],
    session: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[AccountStatus | None, Query(alias="status")] = None,
    sort: Literal["created_at", "name", "venues", "bookings"] = "created_at",
    order: SortOrder = "desc",
    limit: Limit = 20,
    offset: Offset = 0,
) -> OwnerPage:
    return await _svc(request, session).list_owners(q, status_filter, sort, order, limit, offset)


@router.get("/owners/{owner_id}", response_model=OwnerDetail, summary="Owner profile, venues and activity")
async def get_owner(
    owner_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("owners.view"))],
    session: DbSession,
) -> OwnerDetail:
    return await _svc(request, session).get_owner(owner_id)


@router.get("/owners/{owner_id}/history", summary="Account actions on this owner (suspensions, KYC, ...)")
async def owner_history(
    owner_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("owners.view"))],
    session: DbSession,
    limit: Limit = 20,
    offset: Offset = 0,
) -> AuditPage:
    return await _svc(request, session).account_history(owner_id, limit, offset)


@router.get("/owners/{owner_id}/payouts", summary="Payout history of an owner")
async def owner_payouts(
    owner_id: UUID,
    _: Annotated[CurrentUser, Depends(require_permission("finance.view"))],
    session: DbSession,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    from app.services.ledger import FinanceService

    svc = FinanceService(session)
    return {
        "balance": await svc.owner_balance(owner_id),
        **await svc.list_payouts(owner_id=owner_id, status=None, limit=limit, offset=offset),
    }


@router.patch(
    "/owners/{owner_id}/status",
    response_model=StatusChangeOut,
    summary="Suspend or reactivate an owner (audited)",
)
async def set_owner_status(
    owner_id: UUID,
    body: StatusChange,
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_permission("owners.manage"))],
    session: DbSession,
) -> StatusChangeOut:
    return await _svc(request, session).change_status(
        admin.profile, owner_id, "owner", body.status, body.reason
    )


# ------------------------------------------------------------------ customers
@router.get("/customers", response_model=CustomerPage, summary="Customers (search, filter, sort)")
async def list_customers(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("customers.view"))],
    session: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[AccountStatus | None, Query(alias="status")] = None,
    sort: Literal["created_at", "name", "bookings"] = "created_at",
    order: SortOrder = "desc",
    limit: Limit = 20,
    offset: Offset = 0,
) -> CustomerPage:
    return await _svc(request, session).list_customers(q, status_filter, sort, order, limit, offset)


@router.get(
    "/customers/{customer_id}", response_model=CustomerDetail, summary="Customer profile and booking history"
)
async def get_customer(
    customer_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("customers.view"))],
    session: DbSession,
) -> CustomerDetail:
    return await _svc(request, session).get_customer(customer_id)


@router.get("/customers/{customer_id}/history", summary="Account actions on this customer")
async def customer_history(
    customer_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("customers.view"))],
    session: DbSession,
    limit: Limit = 20,
    offset: Offset = 0,
) -> AuditPage:
    return await _svc(request, session).account_history(customer_id, limit, offset)


@router.patch(
    "/customers/{customer_id}/status",
    response_model=StatusChangeOut,
    summary="Suspend or reactivate a customer (audited)",
)
async def set_customer_status(
    customer_id: UUID,
    body: StatusChange,
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_permission("customers.manage"))],
    session: DbSession,
) -> StatusChangeOut:
    return await _svc(request, session).change_status(
        admin.profile, customer_id, "customer", body.status, body.reason
    )


# ------------------------------------------------------------------ venues (monitoring only)
@router.get("/venues", response_model=VenuePage, summary="All venues (read-only monitoring)")
async def list_venues(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("venues.view"))],
    session: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[
        Literal["draft", "pending_review", "published", "rejected", "suspended", "archived"] | None,
        Query(alias="status"),
    ] = None,
    city_id: UUID | None = None,
    category_id: UUID | None = None,
    owner_id: UUID | None = None,
    sort: Literal["created_at", "name", "bookings"] = "created_at",
    order: SortOrder = "desc",
    limit: Limit = 20,
    offset: Offset = 0,
) -> VenuePage:
    return await _svc(request, session).list_venues(
        q, status_filter, city_id, category_id, owner_id, sort, order, limit, offset
    )


@router.get("/venues/{venue_id}", response_model=VenueDetail, summary="Venue detail (read-only)")
async def get_venue(
    venue_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("venues.view"))],
    session: DbSession,
) -> VenueDetail:
    return await _svc(request, session).get_venue(venue_id)


# ------------------------------------------------------------------ bookings (read-only)
@router.get(
    "/bookings", response_model=AdminBookingRowPage, summary="All bookings on the platform (read-only)"
)
async def admin_bookings(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("bookings.view"))],
    session: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    payment_status: str | None = None,
    venue_id: UUID | None = None,
    owner_id: UUID | None = None,
    customer_id: UUID | None = None,
    category_id: UUID | None = None,
    city_id: UUID | None = None,
    refund_status: RefundFilter | None = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> AdminBookingRowPage:
    if status_filter is not None and status_filter not in TRANSITIONS:
        raise ValidationFailedError("Unknown booking status.", code="INVALID_STATUS")
    if payment_status is not None and payment_status not in BOOKING_PAYMENT_STATUSES:
        raise ValidationFailedError("Unknown payment status.", code="INVALID_PAYMENT_STATUS")
    if date_from and date_to and date_from > date_to:
        raise ValidationFailedError("from must not be after to.", code="INVALID_RANGE")
    return await _svc(request, session).list_bookings(
        q=q,
        status=status_filter,
        payment_status=payment_status,
        venue_id=venue_id,
        owner_id=owner_id,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
        category_id=category_id,
        city_id=city_id,
        refund_status=refund_status,
    )


@router.get(
    "/bookings/{booking_id}",
    response_model=AdminBookingDetailOut,
    summary="Booking with history and payments",
)
async def admin_booking(
    booking_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("bookings.view"))],
    session: DbSession,
) -> AdminBookingDetailOut:
    return await _svc(request, session).get_booking(booking_id, _pay(request, session))


# ------------------------------------------------------------------ payments (read-only)
@router.get("/payments/summary", response_model=AdminPaymentSummary, summary="Payment totals and counts")
async def payments_summary(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("payments.view"))],
    session: DbSession,
) -> AdminPaymentSummary:
    return await _pay(request, session).admin_summary()


@router.get("/payments", response_model=AdminPaymentPage, summary="All payments (read-only)")
async def admin_payments(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("payments.view"))],
    session: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    review_required: bool | None = None,
    venue_id: UUID | None = None,
    refund_status: Literal["none", "requested", "pending", "processed", "failed", "uncertain"] | None = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> AdminPaymentPage:
    if status_filter is not None and status_filter not in PAYMENT_TRANSITIONS:
        raise ValidationFailedError("Unknown payment status.", code="INVALID_STATUS")
    lo = hi = None
    if date_from or date_to:
        start, end = _svc(request, session).resolve_range(date_from or date_to, date_to or date_from)
        lo, hi = _svc(request, session)._bounds(start, end)
    return await _pay(request, session).admin_list(
        status_filter,
        review_required,
        limit,
        offset,
        q=q,
        venue_id=venue_id,
        created_from=lo,
        created_before=hi,
        refund_status=refund_status,
    )


@router.get(
    "/payments/{payment_id}", response_model=AdminPaymentDetail, summary="Payment with gateway events"
)
async def admin_payment(
    payment_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("payments.view"))],
    session: DbSession,
) -> AdminPaymentDetail:
    return await _pay(request, session).admin_get(payment_id)


# ------------------------------------------------------------------ CSV exports (audited, no contact data)
def _csv(body: str, name: str) -> Response:
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


@router.get("/exports/bookings.csv", summary="Bookings CSV (no customer contact details)")
async def export_bookings(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_permission("exports.download"))],
    session: DbSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    payment_status: str | None = None,
    venue_id: UUID | None = None,
    owner_id: UUID | None = None,
    category_id: UUID | None = None,
    city_id: UUID | None = None,
    refund_status: RefundFilter | None = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> Response:
    if status_filter is not None and status_filter not in TRANSITIONS:
        raise ValidationFailedError("Unknown booking status.", code="INVALID_STATUS")
    if payment_status is not None and payment_status not in BOOKING_PAYMENT_STATUSES:
        raise ValidationFailedError("Unknown payment status.", code="INVALID_PAYMENT_STATUS")
    body = await _svc(request, session).export_bookings(
        admin.profile,
        status=status_filter,
        payment_status=payment_status,
        venue_id=venue_id,
        date_from=date_from,
        date_to=date_to,
        owner_id=owner_id,
        category_id=category_id,
        city_id=city_id,
        refund_status=refund_status,
    )
    return _csv(body, "zuruv-bookings.csv")


@router.get("/exports/payments.csv", summary="Transactions CSV (no card data)")
async def export_payments(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_permission("exports.download"))],
    session: DbSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> Response:
    if status_filter is not None and status_filter not in PAYMENT_TRANSITIONS:
        raise ValidationFailedError("Unknown payment status.", code="INVALID_STATUS")
    body = await _svc(request, session).export_payments(
        admin.profile, status=status_filter, date_from=date_from, date_to=date_to
    )
    return _csv(body, "zuruv-payments.csv")


@router.get("/exports/customers.csv", summary="Customer report CSV (no e-mail or phone)")
async def export_customers(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_permission("exports.download"))],
    session: DbSession,
) -> Response:
    return _csv(await _svc(request, session).export_people(admin.profile, "customer"), "zuruv-customers.csv")


@router.get("/exports/owners.csv", summary="Owner report CSV (no e-mail or phone)")
async def export_owners(
    request: Request,
    admin: Annotated[CurrentUser, Depends(require_permission("exports.download"))],
    session: DbSession,
) -> Response:
    return _csv(await _svc(request, session).export_people(admin.profile, "owner"), "zuruv-owners.csv")


# ------------------------------------------------------------------ audit log (read-only)
@router.get("/audit-logs", response_model=AuditPage, summary="Audit trail of sensitive actions")
async def audit_logs(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("audit.view"))],
    session: DbSession,
    action: Annotated[str | None, Query(max_length=100)] = None,
    entity_type: Annotated[str | None, Query(max_length=60)] = None,
    entity_id: Annotated[str | None, Query(max_length=100)] = None,
    actor_id: UUID | None = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> AuditPage:
    return await _svc(request, session).list_audit(
        action,
        entity_type,
        limit,
        offset,
        entity_id=entity_id,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/audit-actions", summary="Action names that appear in the audit log (for the filter)")
async def audit_actions(
    request: Request, _: Annotated[CurrentUser, Depends(require_permission("audit.view"))], session: DbSession
) -> dict[str, Any]:
    return {"items": await _svc(request, session).audit_actions()}
