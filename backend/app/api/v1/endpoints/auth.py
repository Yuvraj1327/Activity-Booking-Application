from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import DbSession, get_token_claims, token_user_id
from app.core.security import TokenClaims
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import MeResponse, ProfileCreate, ProfileOut
from app.services.profiles import ProfileService
from app.utils.phone import normalize_claim_phone

router = APIRouter(prefix="/auth", tags=["auth"])

Claims = Annotated[TokenClaims, Depends(get_token_claims)]


@router.get("/me", response_model=MeResponse, summary="Who am I (token identity + profile if any)")
async def me(claims: Claims, session: DbSession) -> MeResponse:
    """Works for a signed-in user without a profile yet (`has_profile: false`), so a client
    can decide between the registration form and the app. Suspended accounts are returned
    with `status: suspended` so the client can explain; every other endpoint refuses them."""
    profile = await ProfileRepository(session).get_profile(token_user_id(claims))
    return MeResponse(
        user_id=token_user_id(claims),
        email=claims.email,
        phone=normalize_claim_phone(claims.phone),
        has_profile=profile is not None,
        profile=ProfileOut.model_validate(profile) if profile else None,
    )


@router.post(
    "/profile",
    response_model=ProfileOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create the profile for the signed-in user (customer or owner)",
    responses={
        200: {"description": "Profile already existed with the same role"},
        409: {"description": "Different role"},
    },
)
async def create_profile(
    payload: ProfileCreate, claims: Claims, session: DbSession, response: Response
) -> ProfileOut:
    profile, created = await ProfileService(session).register(claims, payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return ProfileOut.model_validate(profile)
