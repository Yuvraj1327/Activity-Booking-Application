"""Admin commission management: rules (global / activity / venue), history, booking detail, reports.

Reading needs `commission.view` (reports: `finance.view`); every change needs `commission.manage`.
Customers and owners have no route here (see owner_business for the owner's own read-only views).
"""

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, require_permission
from app.models import Booking, BookingCommissionSnapshot, Category, LedgerEntry, Venue
from app.schemas.catalog import Limit
from app.schemas.commission import CommissionRuleChange, CommissionRuleCreate
from app.services import audit
from app.services.admin import AdminService
from app.services.commission import CommissionService

router = APIRouter(prefix="/admin/commission", tags=["admin-commission"])
export_router = APIRouter(prefix="/admin/exports", tags=["admin-commission"])

Offset = Annotated[int, Query(ge=0, le=100_000)]
DateFrom = Annotated[date | None, Query(alias="from")]
DateTo = Annotated[date | None, Query(alias="to")]
Scope = Literal["global", "activity", "venue"]
View = Annotated[CurrentUser, Depends(require_permission("commission.view"))]
Manage = Annotated[CurrentUser, Depends(require_permission("commission.manage"))]
Report = Annotated[CurrentUser, Depends(require_permission("finance.view"))]


def _svc(request: Request, session: DbSession) -> CommissionService:
    return CommissionService(session, request.app.state.settings)


def _bounds(
    request: Request, session: DbSession, f: date | None, t: date | None
) -> tuple[datetime | None, datetime | None]:
    if not (f or t):
        return None, None
    a = AdminService(session, request.app.state.settings)
    start, end = a.resolve_range(f or t, t or f)
    return a._bounds(start, end)


# ------------------------------------------------------------------ rules
@router.get("/rules", summary="All commission rules with the version in force now and any scheduled change")
async def list_rules(
    request: Request,
    _: View,
    session: DbSession,
    scope: Scope | None = None,
    active_only: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> dict[str, Any]:
    return await _svc(request, session).list_rules(scope, active_only, q)


@router.get("/active", summary="What applies right now: the global percentage and every active override")
async def active(request: Request, _: View, session: DbSession) -> dict[str, Any]:
    return await _svc(request, session).active_summary()


@router.post("/rules", status_code=201, summary="Create the global, an activity or a venue rule")
async def create_rule(
    body: CommissionRuleCreate, request: Request, user: Manage, session: DbSession
) -> dict[str, Any]:
    return await _svc(request, session).create_rule(
        user,
        scope=body.scope,
        category_id=body.category_id,
        venue_id=body.venue_id,
        commission_bps=body.commission_bps,
        is_active=body.is_active,
        effective_from=body.effective_from,
        reason=body.reason,
    )


@router.get("/rules/{rule_id}", summary="One rule with every version")
async def get_rule(rule_id: UUID, request: Request, _: View, session: DbSession) -> dict[str, Any]:
    return await _svc(request, session).get_rule(rule_id)


@router.post(
    "/rules/{rule_id}/versions",
    status_code=201,
    summary="Change the percentage, activate or deactivate: appends a version, never edits the past",
)
async def change_rule(
    rule_id: UUID, body: CommissionRuleChange, request: Request, user: Manage, session: DbSession
) -> dict[str, Any]:
    return await _svc(request, session).add_version(
        user,
        rule_id,
        commission_bps=body.commission_bps,
        is_active=body.is_active,
        effective_from=body.effective_from,
        reason=body.reason,
    )


# ------------------------------------------------------------------ history
@router.get("/history", summary="Immutable rule history (filter by scope, venue, activity, date)")
async def history(
    request: Request,
    _: View,
    session: DbSession,
    scope: Scope | None = None,
    venue_id: UUID | None = None,
    category_id: UUID | None = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    lo, hi = _bounds(request, session, date_from, date_to)
    return await _svc(request, session).history(
        scope=scope, venue_id=venue_id, category_id=category_id, lo=lo, hi=hi, limit=limit, offset=offset
    )


# ------------------------------------------------------------------ calculation and booking detail
@router.get("/calculate", summary="Which rule applies, and the commission for an amount (read-only preview)")
async def calculate(
    request: Request,
    _: View,
    session: DbSession,
    venue_id: UUID,
    base_paise: Annotated[int, Query(ge=0, le=1_000_000_000)],
    category_id: UUID | None = None,
    at: datetime | None = None,
) -> dict[str, Any]:
    return await _svc(request, session).calculate(
        venue_id=venue_id, category_id=category_id, base_paise=base_paise, at=at
    )


@router.get("/bookings/{booking_id}", summary="The commission snapshot and calculation of one booking")
async def booking_commission(
    booking_id: UUID, request: Request, _: Report, session: DbSession
) -> dict[str, Any]:
    return await _svc(request, session).booking_detail(booking_id)


# ------------------------------------------------------------------ reports
@router.get(
    "/report", summary="Commission totals, by activity / venue / day / rule scope, with reconciliation checks"
)
async def report(
    request: Request,
    _: Report,
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    venue_id: UUID | None = None,
    category_id: UUID | None = None,
    owner_id: UUID | None = None,
) -> dict[str, Any]:
    start, end = AdminService(session, request.app.state.settings).resolve_range(date_from, date_to)
    lo, hi = _bounds(request, session, start, end)
    out = await _svc(request, session).report(
        lo, hi, venue_id=venue_id, category_id=category_id, owner_id=owner_id
    )
    return {"range": {"date_from": start, "date_to": end}, **out}


@router.get("/owners/{owner_id}/earnings", summary="An owner's booking-wise earnings, as the owner sees them")
async def owner_earnings(
    owner_id: UUID,
    request: Request,
    _: Report,
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    lo, hi = _bounds(request, session, date_from, date_to)
    return await _svc(request, session).owner_earnings(
        owner_id, venue_id=None, lo=lo, hi=hi, limit=limit, offset=offset
    )


# ------------------------------------------------------------------ CSV exports
@export_router.get(
    "/commission.csv", summary="Commission report: one row per ledger entry with its rule and percentage"
)
async def export_commission(
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("exports.download", "finance.view"))],
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    venue_id: UUID | None = None,
    category_id: UUID | None = None,
    owner_id: UUID | None = None,
) -> Response:
    lo, hi = _bounds(request, session, date_from, date_to)
    L = LedgerEntry
    stmt = (
        select(L, Booking.booking_code, Venue.name, Category.name)
        .join(Venue, Venue.id == L.venue_id)
        .join(Booking, Booking.id == L.booking_id)
        .outerjoin(BookingCommissionSnapshot, BookingCommissionSnapshot.booking_id == L.booking_id)
        .outerjoin(Category, Category.id == BookingCommissionSnapshot.category_id)
    )
    for c in _svc(request, session).ledger_filters(lo, hi, venue_id, category_id, owner_id):
        stmt = stmt.where(c)
    cap = request.app.state.settings.admin_export_max_rows
    rows = (await session.execute(stmt.order_by(L.occurred_at.desc(), L.id).limit(cap))).all()
    data = [
        [
            e.id,
            e.kind,
            code,
            vname,
            cname or "",
            e.gross_paise,
            e.commission_base_paise if e.commission_base_paise is not None else "",
            e.commission_bps if e.commission_bps is not None else "",
            e.commission_scope or "legacy",
            e.commission_rule_id or "",
            e.commission_rule_version or "",
            e.commission_paise,
            e.owner_amount_paise,
            e.platform_amount_paise,
            e.tax_paise,
            e.config_version,
            e.occurred_at.isoformat(),
        ]
        for e, code, vname, cname in rows
    ]
    audit.record(session, user.profile, "admin.export", "commission", None, rows=len(data),
                 filters={"from": str(date_from), "to": str(date_to), "venue_id": str(venue_id) if venue_id else None})  # fmt: skip
    await session.commit()
    body = AdminService._csv(
        [
            "entry_id",
            "kind",
            "booking_code",
            "venue",
            "activity",
            "gross_paise",
            "commission_base_paise",
            "commission_bps",
            "rule_scope",
            "rule_id",
            "rule_version",
            "commission_paise",
            "owner_net_paise",
            "platform_paise",
            "tax_paise",
            "finance_config_version",
            "occurred_at_utc",
        ],
        data,
    )
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="zuruv-commission.csv"',
            "Cache-Control": "no-store",
        },
    )
