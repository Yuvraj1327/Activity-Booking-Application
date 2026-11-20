from fastapi import APIRouter

from app.api.deps import CustomerUser, DbSession
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import CustomerMe, CustomerUpdate, ProfileOut
from app.services.profiles import ProfileService

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/me", response_model=CustomerMe, summary="Own customer profile")
async def get_customer(user: CustomerUser, session: DbSession) -> CustomerMe:
    customer = await ProfileRepository(session).get_customer(user.id)
    return CustomerMe(
        profile=ProfileOut.model_validate(user.profile),
        preferred_city_id=customer.preferred_city_id if customer else None,
        preferred_category_ids=customer.preferred_category_ids if customer else [],
    )


@router.patch("/me", response_model=CustomerMe, summary="Update own customer profile")
async def update_customer(patch: CustomerUpdate, user: CustomerUser, session: DbSession) -> CustomerMe:
    customer = await ProfileService(session).update_customer(user.id, patch)
    return CustomerMe(
        profile=ProfileOut.model_validate(user.profile),
        preferred_city_id=customer.preferred_city_id,
        preferred_category_ids=customer.preferred_category_ids,
    )
