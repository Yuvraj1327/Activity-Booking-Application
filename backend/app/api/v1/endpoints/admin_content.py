"""Admin: support tickets, sports categories, coupons, CMS. Plus the public read of published content."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, DbSession, require_permission
from app.schemas.admin_ops import (
    CategoryCreate,
    CategoryUpdate,
    CmsCreate,
    CmsUpdate,
    CouponBody,
    CouponPatch,
    TicketReply,
    TicketUpdate,
)
from app.schemas.catalog import Limit
from app.services.admin_content import CategoryAdmin, CmsAdmin, SupportAdmin
from app.services.coupons import CouponService

router = APIRouter(prefix="/admin", tags=["admin-content"])
public_router = APIRouter(tags=["content"])
Offset = Annotated[int, Query(ge=0, le=100_000)]
Status = Literal["open", "in_progress", "resolved", "closed"]
Priority = Literal["low", "normal", "high", "urgent"]


# ------------------------------------------------------------------ support
@router.get("/support/tickets", summary="Support tickets, feedback and issue reports")
async def list_tickets(
    _: Annotated[CurrentUser, Depends(require_permission("support.manage"))],
    session: DbSession,
    status_filter: Annotated[Status | Literal["active"] | None, Query(alias="status")] = None,
    priority: Priority | None = None,
    kind: Literal["support", "feedback", "issue"] | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    assigned_to: UUID | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    svc = SupportAdmin(session)
    return {
        **await svc.list_all(status_filter, priority, kind, q, assigned_to, limit, offset),
        "counts": await svc.counts(),
    }


@router.get("/support/tickets/{ticket_id}", summary="Ticket with customer, related booking and full history")
async def get_ticket(
    ticket_id: UUID,
    _: Annotated[CurrentUser, Depends(require_permission("support.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await SupportAdmin(session).get(ticket_id)


@router.post(
    "/support/tickets/{ticket_id}/messages", summary="Reply to the customer, or leave an internal note"
)
async def reply_ticket(
    ticket_id: UUID,
    body: TicketReply,
    user: Annotated[CurrentUser, Depends(require_permission("support.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await SupportAdmin(session).reply(user, ticket_id, body.body, body.internal)


@router.patch("/support/tickets/{ticket_id}", summary="Change status, priority, assignee or linked booking")
async def update_ticket(
    ticket_id: UUID,
    body: TicketUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("support.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await SupportAdmin(session).update(
        user,
        ticket_id,
        body.status,
        body.priority,
        body.assigned_to_me,
        body.booking_id,
        "booking_id" in body.model_fields_set,
    )


# ------------------------------------------------------------------ categories
@router.get("/categories", summary="All sports categories, including inactive ones")
async def list_categories(
    _: Annotated[CurrentUser, Depends(require_permission("categories.manage"))], session: DbSession
) -> dict[str, Any]:
    return {"items": await CategoryAdmin(session).list_all()}


@router.post("/categories", status_code=201, summary="Create a sports category")
async def create_category(
    body: CategoryCreate,
    user: Annotated[CurrentUser, Depends(require_permission("categories.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CategoryAdmin(session).create(user, body.name, body.slug, body.icon_key, body.sort_order)


@router.patch("/categories/{category_id}", summary="Edit, activate or deactivate (never deleted)")
async def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("categories.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CategoryAdmin(session).update(user, category_id, body.model_dump(exclude_unset=True))


# ------------------------------------------------------------------ coupons
@router.get("/coupons", summary="Coupons")
async def list_coupons(
    _: Annotated[CurrentUser, Depends(require_permission("coupons.manage"))],
    session: DbSession,
    active: bool | None = None,
    q: Annotated[str | None, Query(max_length=40)] = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    return await CouponService(session).list_all(active, q, limit, offset)


@router.post("/coupons", status_code=201, summary="Create a coupon")
async def create_coupon(
    body: CouponBody,
    user: Annotated[CurrentUser, Depends(require_permission("coupons.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CouponService(session).create(user, body.model_dump())


@router.get("/coupons/{coupon_id}", summary="One coupon with its redemption count")
async def get_coupon(
    coupon_id: UUID,
    _: Annotated[CurrentUser, Depends(require_permission("coupons.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CouponService(session).get(coupon_id)


@router.patch("/coupons/{coupon_id}", summary="Edit limits and validity, activate or deactivate")
async def update_coupon(
    coupon_id: UUID,
    body: CouponPatch,
    user: Annotated[CurrentUser, Depends(require_permission("coupons.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CouponService(session).update(user, coupon_id, body.model_dump(exclude_unset=True))


@router.get("/coupons/{coupon_id}/redemptions", summary="Redemption history")
async def coupon_redemptions(
    coupon_id: UUID,
    _: Annotated[CurrentUser, Depends(require_permission("coupons.manage"))],
    session: DbSession,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict[str, Any]:
    return await CouponService(session).redemptions(coupon_id, limit, offset)


# ------------------------------------------------------------------ CMS
@router.get("/cms", summary="Content entries (pages and FAQs)")
async def list_cms(
    _: Annotated[CurrentUser, Depends(require_permission("cms.manage"))],
    session: DbSession,
    kind: Literal["page", "faq"] | None = None,
    status_filter: Annotated[Literal["draft", "published"] | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> dict[str, Any]:
    return await CmsAdmin(session).list_all(kind, status_filter, q, limit, offset)


@router.post("/cms", status_code=201, summary="Create content (draft)")
async def create_cms(
    body: CmsCreate,
    user: Annotated[CurrentUser, Depends(require_permission("cms.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CmsAdmin(session).create(user, body.model_dump())


@router.get("/cms/{content_id}", summary="One entry with its body")
async def get_cms(
    content_id: UUID, _: Annotated[CurrentUser, Depends(require_permission("cms.manage"))], session: DbSession
) -> dict[str, Any]:
    return await CmsAdmin(session).get(content_id)


@router.patch("/cms/{content_id}", summary="Edit content")
async def update_cms(
    content_id: UUID,
    body: CmsUpdate,
    user: Annotated[CurrentUser, Depends(require_permission("cms.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CmsAdmin(session).update(user, content_id, body.model_dump(exclude_unset=True))


@router.post("/cms/{content_id}/publish", summary="Publish: the apps show it immediately")
async def publish_cms(
    content_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("cms.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CmsAdmin(session).set_published(user, content_id, True)


@router.post("/cms/{content_id}/unpublish", summary="Unpublish: the apps stop showing it")
async def unpublish_cms(
    content_id: UUID,
    user: Annotated[CurrentUser, Depends(require_permission("cms.manage"))],
    session: DbSession,
) -> dict[str, Any]:
    return await CmsAdmin(session).set_published(user, content_id, False)


# ------------------------------------------------------------------ public read (what the apps display)
def _cache(response: Response) -> None:
    response.headers["Cache-Control"] = "public, max-age=60"


@public_router.get("/content", summary="Published pages and FAQs")
async def public_content(
    response: Response,
    session: DbSession,
    kind: Literal["page", "faq"] | None = None,
    audience: Literal["customer", "owner"] | None = None,
) -> dict[str, Any]:
    _cache(response)
    return {"items": await CmsAdmin(session).public_list(kind, audience)}


@public_router.get("/content/{slug}", summary="One published entry")
async def public_content_item(slug: str, response: Response, session: DbSession) -> dict[str, Any]:
    _cache(response)
    return await CmsAdmin(session).public_get(slug)
