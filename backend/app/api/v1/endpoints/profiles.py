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
