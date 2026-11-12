from fastapi import APIRouter

from app.api.deps import DbSession, OwnerUser
from app.models import OwnerProfile
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import OwnerMe, OwnerUpdate, ProfileOut
from app.services.profiles import ProfileService

router = APIRouter(prefix="/owners", tags=["owners"])


def _out(user_profile: object, owner: OwnerProfile) -> OwnerMe:
    return OwnerMe(
        profile=ProfileOut.model_validate(user_profile),
        business_name=owner.business_name,
        business_phone=owner.business_phone,
        business_email=owner.business_email,
        business_address=owner.business_address,
    )


@router.get("/me", response_model=OwnerMe, summary="Own owner (business) profile")
async def get_owner(user: OwnerUser, session: DbSession) -> OwnerMe:
    owner = await ProfileRepository(session).get_owner(user.id)
    if owner is None:  # cannot happen through the API; guarded by the composite FK + registration
        from app.core.errors import NotFoundError

        raise NotFoundError("Owner profile not found.", code="PROFILE_NOT_FOUND")
    return _out(user.profile, owner)


@router.patch("/me", response_model=OwnerMe, summary="Update own owner profile")
async def update_owner(patch: OwnerUpdate, user: OwnerUser, session: DbSession) -> OwnerMe:
    return _out(user.profile, await ProfileService(session).update_owner(user.id, patch))
