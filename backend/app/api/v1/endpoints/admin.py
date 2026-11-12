from fastapi import APIRouter

from app.api.deps import AdminUser
from app.schemas.profile import ProfileOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me", response_model=ProfileOut, summary="Verify the caller is an authorised admin")
async def admin_me(user: AdminUser) -> ProfileOut:
    """Used by the admin web to confirm access server-side. Admin modules arrive in Step 8."""
    return ProfileOut.model_validate(user.profile)
