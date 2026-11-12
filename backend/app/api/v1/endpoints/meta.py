from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.schemas.common import VersionResponse

router = APIRouter(tags=["meta"])


@router.get("/version", response_model=VersionResponse, summary="API version")
async def version(settings: Annotated[Settings, Depends(get_app_settings)]) -> VersionResponse:
    return VersionResponse(name=settings.app_name, version=settings.app_version, api_version="v1")
