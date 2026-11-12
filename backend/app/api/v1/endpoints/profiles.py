from fastapi import APIRouter

from app.api.deps import AnyUser, DbSession
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services.profiles import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileOut, summary="Own base profile (any role)")
async def get_my_profile(user: AnyUser) -> ProfileOut:
    return ProfileOut.model_validate(user.profile)


@router.patch("/me", response_model=ProfileOut, summary="Update own base profile")
async def update_my_profile(patch: ProfileUpdate, user: AnyUser, session: DbSession) -> ProfileOut:
    return ProfileOut.model_validate(await ProfileService(session).update_profile(user.id, patch))
