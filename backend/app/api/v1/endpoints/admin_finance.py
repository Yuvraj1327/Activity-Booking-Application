"""Admin: refunds, booking intervention and disputes (finance configuration is added below)."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request

from app.api.deps import DbSession, Perm
from app.schemas.admin_ops import (
    AdminCancel,
    DisputeCreate,
    DisputeNote,
    DisputeResolve,
    DisputeUpdate,
    RefundCreate,
)
from app.schemas.catalog import Limit
from app.services.admin import AdminService
from app.services.admin_bookings import AdminBookingOps
from app.services.refunds import RefundService

router = APIRouter(prefix="/admin", tags=["admin-finance"])

Offset = Annotated[int, Query(ge=0, le=100_000)]
DateFrom = Annotated[date | None, Query(alias="from")]
DateTo = Annotated[date | None, Query(alias="to")]
RefundStatus = Literal["requested", "pending", "processed", "failed", "uncertain"]


def _refunds(request: Request, session: DbSession) -> RefundService:
    return RefundService(session, request.app.state.settings, request.app.state.payment_gateway)


def _ops(request: Request, session: DbSession) -> AdminBookingOps:
    return AdminBookingOps(session, request.app.state.settings)


# ------------------------------------------------------------------ refunds
@router.get("/refunds", summary="Refund history (filter by status, payment, booking, date)")
async def list_refunds(
    request: Request,
    _: Perm("payments.view"),
    session: DbSession,
    status_filter: Annotated[RefundStatus | None, Query(alias="status")] = None,
    payment_id: UUID | None = None,
    booking_id: UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    lo = hi = None
    if date_from or date_to:
        svc = AdminService(session, request.app.state.settings)
        start, end = svc.resolve_range(date_from or date_to, date_to or date_from)
        lo, hi = svc._bounds(start, end)
    return await _refunds(request, session).list_page(
        status=status_filter,
        payment_id=payment_id,
        booking_id=booking_id,
        date_lo=lo,
        date_hi=hi,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/refunds/{refund_id}", summary="One refund")
async def get_refund(refund_id: UUID, request: Request, _: Perm("payments.view"), session: DbSession) -> dict:
    return await _refunds(request, session).get(refund_id)


@router.post("/payments/{payment_id}/refunds", status_code=201, summary="Start a full or partial refund")
async def create_refund(
    payment_id: UUID,
    body: RefundCreate,
    request: Request,
    user: Perm("refunds.manage"),
    session: DbSession,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    """Disabled until the refund policy (Q9) is approved and the `refunds_enabled` switch is on."""
    return await _refunds(request, session).create(
        user, payment_id, body.amount_paise, body.reason, idempotency_key, body.dispute_id
    )


@router.post("/refunds/{refund_id}/reconcile", summary="Ask the gateway what happened to this refund")
async def reconcile_refund(
    refund_id: UUID, request: Request, user: Perm("refunds.manage"), session: DbSession
) -> dict:
    return await _refunds(request, session).reconcile(user, refund_id)


# ------------------------------------------------------------------ booking intervention
@router.post("/bookings/{booking_id}/cancel", summary="Exceptional cancellation (state machine, audited)")
async def cancel_booking(
    booking_id: UUID, body: AdminCancel, request: Request, user: Perm("bookings.manage"), session: DbSession
) -> dict:
    return await _ops(request, session).cancel(user, booking_id, body.reason, body.dispute_id)


# ------------------------------------------------------------------ disputes
@router.get("/disputes", summary="Disputes")
async def list_disputes(
    request: Request,
    _: Perm("disputes.manage"),
    session: DbSession,
    status_filter: Annotated[
        Literal["open", "investigating", "resolved", "rejected"] | None, Query(alias="status")
    ] = None,
    priority: Literal["low", "normal", "high", "urgent"] | None = None,
    booking_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    return await _ops(request, session).list_disputes(status_filter, priority, booking_id, limit, offset)


@router.post("/disputes", status_code=201, summary="Open a dispute on a booking")
async def create_dispute(
    body: DisputeCreate, request: Request, user: Perm("disputes.manage"), session: DbSession
) -> dict:
    return await _ops(request, session).create_dispute(
        user, body.booking_id, body.subject, body.description, body.raised_by_role, body.priority
    )


@router.get("/disputes/{dispute_id}", summary="Dispute with booking, payment, refunds and full history")
async def get_dispute(
    dispute_id: UUID, request: Request, _: Perm("disputes.manage"), session: DbSession
) -> dict:
    return await _ops(request, session).get_dispute(dispute_id)


@router.post("/disputes/{dispute_id}/events", summary="Add an admin note or evidence")
async def add_dispute_event(
    dispute_id: UUID, body: DisputeNote, request: Request, user: Perm("disputes.manage"), session: DbSession
) -> dict:
    return await _ops(request, session).add_event(user, dispute_id, body.kind, body.body)


@router.patch("/disputes/{dispute_id}", summary="Change status or priority")
async def update_dispute(
    dispute_id: UUID, body: DisputeUpdate, request: Request, user: Perm("disputes.manage"), session: DbSession
) -> dict:
    return await _ops(request, session).update(user, dispute_id, body.status, body.priority, body.reason)


@router.post("/disputes/{dispute_id}/resolve", summary="Resolve or reject a dispute")
async def resolve_dispute(
    dispute_id: UUID,
    body: DisputeResolve,
    request: Request,
    user: Perm("disputes.manage"),
    session: DbSession,
) -> dict:
    return await _ops(request, session).resolve(
        user, dispute_id, body.outcome, body.resolution_type, body.resolution_note
    )


# ====================================================================== finance configuration, ledger, payouts
from fastapi import Response  # noqa: E402

from app.schemas.admin_ops import (  # noqa: E402
    FinanceConfigCreate,
    PayoutCreate,
    PayoutPaid,
    ReasonBody,
    ReconcileRun,
)
from app.services import audit, platform_settings  # noqa: E402
from app.services.ledger import FinanceService, active_config, any_approved  # noqa: E402
from app.services.reconciliation import ReconciliationService  # noqa: E402


def _fin(session: DbSession) -> FinanceService:
    return FinanceService(session)


def _range(request: Request, session: DbSession, date_from: date | None, date_to: date | None):
    svc = AdminService(session, request.app.state.settings)
    start, end = svc.resolve_range(date_from, date_to)
    lo, hi = svc._bounds(start, end)
    return start, end, lo, hi


@router.get("/finance/configs", summary="Fee / tax / commission configurations, newest first")
async def list_configs(_: Perm("finance.view"), session: DbSession) -> dict:
    return {"items": await _fin(session).list_configs()}


@router.post(
    "/finance/configs", status_code=201, summary="Draft a new configuration (does nothing until approved)"
)
async def create_config(body: FinanceConfigCreate, user: Perm("finance.manage"), session: DbSession) -> dict:
    return await _fin(session).create_draft(user, body.model_dump())


@router.delete("/finance/configs/{config_id}", status_code=204, summary="Delete a draft")
async def delete_config(config_id: UUID, user: Perm("finance.manage"), session: DbSession) -> Response:
    await _fin(session).delete_draft(user, config_id)
    return Response(status_code=204)


@router.post(
    "/finance/configs/{config_id}/approve", summary="Approve a draft: it becomes binding and immutable"
)
async def approve_config(
    config_id: UUID, body: ReasonBody, user: Perm("finance.approve"), session: DbSession
) -> dict:
    return await _fin(session).approve(user, config_id, body.reason)


@router.get(
    "/finance/summary", summary="Platform revenue, owner earnings, refunds and what is still undecided"
)
async def finance_summary(
    request: Request,
    _: Perm("finance.view"),
    session: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> dict:
    start, end, lo, hi = _range(request, session, date_from, date_to)
    fin = _fin(session)
    cfg = await active_config(session)
    flags = await platform_settings.get_all(session)
    gw = request.app.state.payment_gateway
    refunds = await RefundService(session, request.app.state.settings, gw).summary()
    approved = await any_approved(session)
    return {
        "range": {"date_from": start, "date_to": end},
        "active_config": None if cfg is None else {"id": cfg.id, "version": cfg.version, "effective_from": cfg.effective_from},
        "ledger": await fin.totals(lo, hi) if approved else None,
        "coverage": await fin.coverage(lo, hi),
        "refunds": refunds,
        "payouts": {
            "enabled": flags["payouts_enabled"],
            "automatic_gateway_payouts": False,
            "note": "Payout records are tracked here and marked paid after the transfer is made outside the "
            "system. RazorpayX / Route are not integrated, and nothing here assumes they are enabled.",
        },
        "decisions_needed": [
            d for d, missing in (
                ("Q7/Q8: approve a fee, tax and commission configuration", cfg is None),
                ("Q9: approve the refund and cancellation policy, then enable refunds", not flags["refunds_enabled"]),
                ("Q10: approve payout rules, then enable payouts", not flags["payouts_enabled"]),
            ) if missing
        ],
    }  # fmt: skip


@router.post(
    "/finance/accrue", summary="Write ledger entries for captured payments / processed refunds that have none"
)
async def accrue(user: Perm("finance.manage"), session: DbSession) -> dict:
    out = await _fin(session).accrue()
    audit.record(session, user.profile, "admin.ledger_accrued", "ledger", None, after=out)
    await session.commit()
    return out


@router.get("/finance/ledger", summary="Immutable ledger entries")
async def ledger(
    request: Request,
    _: Perm("finance.view"),
    session: DbSession,
    owner_id: UUID | None = None,
    kind: Literal["sale", "refund"] | None = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    lo = hi = None
    if date_from or date_to:
        _, _, lo, hi = _range(request, session, date_from or date_to, date_to or date_from)
    return await _fin(session).ledger_page(
        owner_id=owner_id, kind=kind, lo=lo, hi=hi, limit=limit, offset=offset
    )


@router.get(
    "/finance/owners/{owner_id}/balance", summary="What an owner has earned, been paid and can still be paid"
)
async def owner_balance(owner_id: UUID, _: Perm("finance.view"), session: DbSession) -> dict:
    return await _fin(session).owner_balance(owner_id)


@router.get("/payouts", summary="Payout records")
async def list_payouts(
    _: Perm("finance.view"),
    session: DbSession,
    owner_id: UUID | None = None,
    status_filter: Annotated[
        Literal["draft", "approved", "paid", "cancelled"] | None, Query(alias="status")
    ] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    return await _fin(session).list_payouts(
        owner_id=owner_id, status=status_filter, limit=limit, offset=offset
    )


@router.post("/payouts", status_code=201, summary="Create a payout record (disabled until Q10 is approved)")
async def create_payout(body: PayoutCreate, user: Perm("payouts.manage"), session: DbSession) -> dict:
    return await _fin(session).create_payout(
        user, body.owner_id, body.amount_paise, body.period_from, body.period_to, body.note
    )


@router.post("/payouts/{payout_id}/approve", summary="Approve a draft payout (a second administrator)")
async def approve_payout(payout_id: UUID, user: Perm("payouts.manage"), session: DbSession) -> dict:
    return await _fin(session).approve_payout(user, payout_id)


@router.post(
    "/payouts/{payout_id}/paid", summary="Record that the transfer was made, with its bank / UPI reference"
)
async def payout_paid(
    payout_id: UUID, body: PayoutPaid, user: Perm("payouts.manage"), session: DbSession
) -> dict:
    return await _fin(session).mark_paid(user, payout_id, body.method, body.reference)


@router.post("/payouts/{payout_id}/cancel", summary="Cancel an unpaid payout")
async def payout_cancel(
    payout_id: UUID, body: ReasonBody, user: Perm("payouts.manage"), session: DbSession
) -> dict:
    return await _fin(session).cancel_payout(user, payout_id, body.reason)


@router.post("/finance/reconciliation", status_code=201, summary="Run a reconciliation for a date range")
async def run_reconciliation(
    body: ReconcileRun, request: Request, user: Perm("finance.manage"), session: DbSession
) -> dict:
    return await ReconciliationService(
        session, request.app.state.settings, request.app.state.payment_gateway
    ).run(user, body.date_from, body.date_to)


@router.get("/finance/reconciliation", summary="Reconciliation runs")
async def list_runs(
    request: Request, _: Perm("finance.view"), session: DbSession, limit: Limit = 20, offset: Offset = 0
) -> dict:
    return await ReconciliationService(
        session, request.app.state.settings, request.app.state.payment_gateway
    ).list_runs(limit, offset)


@router.get("/finance/reconciliation/{run_id}", summary="One run with every mismatch")
async def get_run(run_id: UUID, request: Request, _: Perm("finance.view"), session: DbSession) -> dict:
    return await ReconciliationService(
        session, request.app.state.settings, request.app.state.payment_gateway
    ).get(run_id)


# ------------------------------------------------------------------ downloadable reports
def _csv_response(header: list[str], rows: list[list], name: str) -> Response:
    body = AdminService._csv(header, rows)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


async def _audited(session: DbSession, user, kind: str, rows: int, **filters) -> None:
    audit.record(session, user.profile, "admin.export", kind, None, rows=rows, filters=filters)
    await session.commit()


@router.get("/exports/refunds.csv", summary="Refund report")
async def export_refunds(
    request: Request,
    user: Perm("exports.download"),
    session: DbSession,
    status_filter: Annotated[RefundStatus | None, Query(alias="status")] = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> Response:
    lo = hi = None
    if date_from or date_to:
        _, _, lo, hi = _range(request, session, date_from or date_to, date_to or date_from)
    svc = _refunds(request, session)
    cap = request.app.state.settings.admin_export_max_rows
    page = await svc.list_page(
        status=status_filter, payment_id=None, booking_id=None, date_lo=lo, date_hi=hi, limit=cap, offset=0
    )
    rows = [
        [r["id"], r["booking_code"], r["venue_name"], r["razorpay_payment_id"], r["provider_refund_id"], r["amount_paise"],
         r["currency"], r["status"], r["source"], r["reason"], r["failure_reason"], r["created_at"].isoformat(),
         r["processed_at"].isoformat() if r["processed_at"] else ""]
        for r in page["items"]
    ]  # fmt: skip
    await _audited(
        session,
        user,
        "refunds",
        len(rows),
        status=status_filter,
        date_from=str(date_from),
        date_to=str(date_to),
    )
    return _csv_response(
        ["refund_id", "booking_code", "venue", "razorpay_payment_id", "razorpay_refund_id", "amount_paise", "currency",
         "status", "source", "reason", "failure_reason", "created_at_utc", "processed_at_utc"], rows, "zuruv-refunds.csv")  # fmt: skip


@router.get("/exports/ledger.csv", summary="Financial report: ledger entries")
async def export_ledger(
    request: Request,
    user: Perm("exports.download"),
    session: DbSession,
    owner_id: UUID | None = None,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> Response:
    lo = hi = None
    if date_from or date_to:
        _, _, lo, hi = _range(request, session, date_from or date_to, date_to or date_from)
    cap = request.app.state.settings.admin_export_max_rows
    page = await _fin(session).ledger_page(owner_id=owner_id, kind=None, lo=lo, hi=hi, limit=cap, offset=0)
    rows = [
        [e["id"], e["kind"], e["booking_code"], e["venue_name"], e["owner_name"], e["config_version"], e["gross_paise"],
         e["tax_paise"], e["owner_amount_paise"], e["platform_amount_paise"], e["fee_paise"], e["commission_paise"],
         e["discount_paise"], e["occurred_at"].isoformat()]
        for e in page["items"]
    ]  # fmt: skip
    await _audited(session, user, "ledger", len(rows), owner_id=str(owner_id) if owner_id else None)
    return _csv_response(
        ["entry_id", "kind", "booking_code", "venue", "owner", "config_version", "gross_paise", "tax_paise",
         "owner_amount_paise", "platform_amount_paise", "fee_paise", "commission_paise", "discount_paise",
         "occurred_at_utc"], rows, "zuruv-ledger.csv")  # fmt: skip


@router.get("/exports/payouts.csv", summary="Payout report")
async def export_payouts(
    request: Request, user: Perm("exports.download"), session: DbSession, owner_id: UUID | None = None
) -> Response:
    cap = request.app.state.settings.admin_export_max_rows
    page = await _fin(session).list_payouts(owner_id=owner_id, status=None, limit=cap, offset=0)
    rows = [
        [p["id"], p["owner_name"], p["amount_paise"], p["status"], p["period_from"], p["period_to"], p["method"],
         p["reference"], p["paid_at"].isoformat() if p["paid_at"] else "", p["created_at"].isoformat()]
        for p in page["items"]
    ]  # fmt: skip
    await _audited(session, user, "payouts", len(rows))
    return _csv_response(["payout_id", "owner", "amount_paise", "status", "period_from", "period_to", "method",
                          "reference", "paid_at_utc", "created_at_utc"], rows, "zuruv-payouts.csv")  # fmt: skip


@router.get("/exports/reconciliation/{run_id}.csv", summary="Reconciliation mismatch report")
async def export_reconciliation(
    run_id: UUID, request: Request, user: Perm("exports.download"), session: DbSession
) -> Response:
    run = await ReconciliationService(
        session, request.app.state.settings, request.app.state.payment_gateway
    ).get(run_id)
    rows = [
        [
            i["kind"],
            i["provider_payment_id"],
            i["payment_id"],
            i["expected_paise"],
            i["actual_paise"],
            i["detail"],
        ]
        for i in run["items"]
    ]
    await _audited(session, user, "reconciliation", len(rows), run_id=str(run_id))
    return _csv_response(["kind", "razorpay_payment_id", "payment_id", "expected_paise", "actual_paise", "detail"],
                         rows, f"zuruv-reconciliation-{str(run_id)[:8]}.csv")  # fmt: skip
