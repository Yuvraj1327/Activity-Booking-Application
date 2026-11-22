"""Admin: venue approval / verification / suspension, venue reports, owner KYC review."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import CurrentUser, DbSession, require_permission
from app.schemas.admin_ops import (
    KycDocDecision,
    KycOwnerDecision,
    ReportResolve,
    VenueDecision,
    VenueReasonRequired,
)
from app.schemas.catalog import Limit
from app.services.kyc import KycService
from app.services.venue_moderation import VenueModeration

router = APIRouter(prefix="/admin", tags=["admin-moderation"])
Offset = Annotated[int, Query(ge=0, le=100_000)]


def _mod(request: Request, session: DbSession) -> VenueModeration:
    return VenueModeration(session, request.app.state.settings)


def _kyc(request: Request, session: DbSession) -> KycService:
    return KycService(session, request.app.state.settings, request.app.state.storage)


# ------------------------------------------------------------------ venues
@router.post("/venues/{venue_id}/approve", summary="Approve a venue that is waiting for review")
async def approve_venue(
    venue_id: UUID,
    body: VenueDecision,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("venues.moderate"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _mod(request, session).transition(user, venue_id, "approve", body.reason)


@router.post("/venues/{venue_id}/reject", summary="Reject a venue (reason required)")
async def reject_venue(
    venue_id: UUID,
    body: VenueReasonRequired,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("venues.moderate"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _mod(request, session).transition(user, venue_id, "reject", body.reason)


@router.post(
    "/venues/{venue_id}/suspend", summary="Suspend a live venue (reason required; bookings untouched)"
)
async def suspend_venue(
    venue_id: UUID,
    body: VenueReasonRequired,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("venues.moderate"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _mod(request, session).transition(user, venue_id, "suspend", body.reason)


@router.post("/venues/{venue_id}/reinstate", summary="Reinstate a suspended venue")
async def reinstate_venue(
    venue_id: UUID,
    body: VenueDecision,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("venues.moderate"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _mod(request, session).transition(user, venue_id, "reinstate", body.reason)


@router.post("/venues/{venue_id}/verify", summary="Mark a venue as verified")
async def verify_venue(
    venue_id: UUID,
    body: VenueDecision,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("venues.moderate"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _mod(request, session).set_verified(user, venue_id, True, body.reason)


@router.post("/venues/{venue_id}/unverify", summary="Remove verification (reason required)")
async def unverify_venue(
    venue_id: UUID,
    body: VenueReasonRequired,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("venues.moderate"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _mod(request, session).set_verified(user, venue_id, False, body.reason)


@router.get("/venues/{venue_id}/history", summary="Approval / verification / suspension history")
async def venue_history(
    venue_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("venues.view"))],
    session: DbSession,
) -> dict[str, Any]:
    return {"items": await _mod(request, session).history(venue_id)}


# ------------------------------------------------------------------ reports
@router.get("/venue-reports", summary="Reported venues")
async def list_reports(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("venues.view"))],
    session: DbSession,
    status_filter: Annotated[
        Literal["open", "reviewing", "dismissed", "action_taken"] | None, Query(alias="status")
    ] = None,
    venue_id: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    return await _mod(request, session).list_reports(status_filter, venue_id, limit, offset)


@router.get("/venue-reports/{report_id}", summary="Report details")
async def get_report(
    report_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("venues.view"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _mod(request, session).get_report(report_id)


@router.patch("/venue-reports/{report_id}", summary="Review or close a report")
async def resolve_report(
    report_id: UUID,
    body: ReportResolve,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("venues.moderate"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _mod(request, session).resolve_report(user, report_id, body.status, body.note)


# ------------------------------------------------------------------ KYC
@router.get("/kyc/queue", summary="Owners with documents waiting for review")
async def kyc_queue(
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("kyc.review"))],
    session: DbSession,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    return await _kyc(request, session).queue(limit, offset)


@router.get("/owners/{owner_id}/kyc", summary="Owner verification status and submitted documents")
async def owner_kyc(
    owner_id: UUID,
    request: Request,
    _: Annotated[CurrentUser, Depends(require_permission("kyc.review"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _kyc(request, session).admin_view(owner_id)


@router.get("/kyc/documents/{doc_id}/file", summary="View a KYC document (streamed, every view is audited)")
async def kyc_file(
    doc_id: UUID,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("kyc.review"))],
    session: DbSession,
) -> Response:
    data, content_type, filename = await _kyc(request, session).read_file(user, doc_id)
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post(
    "/kyc/documents/{doc_id}/review", summary="Approve or reject one document (rejection needs a reason)"
)
async def review_doc(
    doc_id: UUID,
    body: KycDocDecision,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("kyc.review"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _kyc(request, session).review_document(user, doc_id, body.decision, body.reason)


@router.post("/owners/{owner_id}/kyc/decision", summary="Verify or reject the owner's KYC as a whole")
async def owner_kyc_decision(
    owner_id: UUID,
    body: KycOwnerDecision,
    request: Request,
    user: Annotated[CurrentUser, Depends(require_permission("kyc.review"))],
    session: DbSession,
) -> dict[str, Any]:
    return await _kyc(request, session).decide_owner(user, owner_id, body.decision, body.reason)
