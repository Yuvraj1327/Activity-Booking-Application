from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import AnyUser, DbSession
from app.schemas.profile import ProfileOut, ProfileUpdate, SupportTicketCreate, SupportTicketOut
from app.services.profiles import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileOut, summary="Own base profile (any role)")
async def get_my_profile(user: AnyUser) -> ProfileOut:
    return ProfileOut.model_validate(user.profile)


@router.patch("/me", response_model=ProfileOut, summary="Update own base profile")
async def update_my_profile(patch: ProfileUpdate, user: AnyUser, session: DbSession) -> ProfileOut:
    return ProfileOut.model_validate(await ProfileService(session).update_profile(user.id, patch))


@router.post("/me/deletion-request", response_model=ProfileOut, summary="Request deletion of my account")
async def request_deletion(user: AnyUser, session: DbSession) -> ProfileOut:
    return ProfileOut.model_validate(await ProfileService(session).request_deletion(user.id))


@router.delete("/me/deletion-request", response_model=ProfileOut, summary="Cancel my deletion request")
async def cancel_deletion(user: AnyUser, session: DbSession) -> ProfileOut:
    return ProfileOut.model_validate(await ProfileService(session).cancel_deletion(user.id))


support_router = APIRouter(prefix="/support", tags=["support"])


@support_router.post(
    "/tickets", response_model=SupportTicketOut, status_code=201, summary="Send support, feedback or an issue"
)
async def create_ticket(body: SupportTicketCreate, user: AnyUser, session: DbSession) -> SupportTicketOut:
    return SupportTicketOut.model_validate(await ProfileService(session).create_ticket(user.id, body))


@support_router.get("/tickets", response_model=list[SupportTicketOut], summary="My support messages")
async def my_tickets(user: AnyUser, session: DbSession) -> list[SupportTicketOut]:
    return [SupportTicketOut.model_validate(t) for t in await ProfileService(session).list_tickets(user.id)]


@support_router.get(
    "/tickets/{ticket_id}/messages", summary="Replies from the ZURUV team on one of my messages"
)
async def ticket_replies(ticket_id: UUID, user: AnyUser, session: DbSession) -> dict[str, Any]:
    from sqlalchemy import select

    from app.core.errors import NotFoundError
    from app.models import SupportTicket, SupportTicketMessage

    t = await session.scalar(
        select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user.id)
    )
    if t is None:
        raise NotFoundError("Message not found.", code="TICKET_NOT_FOUND")
    rows = (
        await session.scalars(
            select(SupportTicketMessage)
            .where(SupportTicketMessage.ticket_id == ticket_id, SupportTicketMessage.kind == "reply")
            .order_by(SupportTicketMessage.created_at)
        )
    ).all()
    return {
        "items": [
            {"id": m.id, "body": m.body, "from_team": m.author_role == "admin", "created_at": m.created_at}
            for m in rows
        ]
    }
