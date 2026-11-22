from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile, status

from app.api.deps import DbSession, OwnerUser
from app.core.errors import ValidationFailedError
from app.schemas.catalog import Limit
from app.schemas.owner import (
    MAX_IMAGE_BYTES,
    ImageOrder,
    ImagePatch,
    OwnerVenueCreate,
    OwnerVenueDetail,
    OwnerVenueImageOut,
    OwnerVenuePage,
    OwnerVenueUpdate,
    ScheduleOut,
    ScheduleReplace,
)
from app.services.owner_venues import OwnerVenueService

router = APIRouter(prefix="/owners/venues", tags=["owner-venues"])


def _svc(request: Request, session: DbSession) -> OwnerVenueService:
    return OwnerVenueService(session, request.app.state.settings, request.app.state.storage)


@router.get("", response_model=OwnerVenuePage, summary="Own venues (search, filter by status)")
async def list_venues(
    request: Request,
    user: OwnerUser,
    session: DbSession,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", pattern="^(draft|pending_review|published|rejected|suspended|archived)$"),
    ] = None,
    limit: Limit = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> OwnerVenuePage:
    return await _svc(request, session).list_venues(user.id, q, status_filter, limit, offset)


@router.post(
    "", response_model=OwnerVenueDetail, status_code=status.HTTP_201_CREATED, summary="Create a draft venue"
)
async def create_venue(
    body: OwnerVenueCreate, request: Request, user: OwnerUser, session: DbSession
) -> OwnerVenueDetail:
    return await _svc(request, session).create(user.id, body)


@router.get("/{venue_id}", response_model=OwnerVenueDetail, summary="Own venue, for editing")
async def get_venue(
    venue_id: UUID, request: Request, user: OwnerUser, session: DbSession
) -> OwnerVenueDetail:
    return await _svc(request, session).get(venue_id, user.id)


@router.patch("/{venue_id}", response_model=OwnerVenueDetail, summary="Update own venue")
async def update_venue(
    venue_id: UUID, body: OwnerVenueUpdate, request: Request, user: OwnerUser, session: DbSession
) -> OwnerVenueDetail:
    return await _svc(request, session).update(venue_id, user.id, body)


@router.delete("/{venue_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete own venue")
async def delete_venue(venue_id: UUID, request: Request, user: OwnerUser, session: DbSession) -> Response:
    await _svc(request, session).delete(venue_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{venue_id}/publish",
    response_model=OwnerVenueDetail,
    summary="Publish, or submit for admin approval when that workflow is on (Q4)",
)
async def publish(venue_id: UUID, request: Request, user: OwnerUser, session: DbSession) -> OwnerVenueDetail:
    return await _svc(request, session).publish(venue_id, user.id)


@router.post(
    "/{venue_id}/unpublish",
    response_model=OwnerVenueDetail,
    summary="Take the listing offline (back to draft)",
)
async def unpublish(
    venue_id: UUID, request: Request, user: OwnerUser, session: DbSession
) -> OwnerVenueDetail:
    return await _svc(request, session).unpublish(venue_id, user.id)


# ------------------------------------------------------------------ images
@router.post(
    "/{venue_id}/images",
    response_model=OwnerVenueImageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image (multipart). The backend validates it and stores it in Supabase Storage",
)
async def upload_image(
    venue_id: UUID,
    request: Request,
    user: OwnerUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
    alt_text: Annotated[str | None, Form(max_length=200)] = None,
) -> OwnerVenueImageOut:
    data = await file.read(MAX_IMAGE_BYTES + 1)  # never buffer more than the limit
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationFailedError("Images can be at most 5 MB.", code="IMAGE_TOO_LARGE")
    return await _svc(request, session).add_image(venue_id, user.id, data, alt_text)


@router.put("/{venue_id}/images/order", response_model=list[OwnerVenueImageOut], summary="Reorder images")
async def reorder_images(
    venue_id: UUID, body: ImageOrder, request: Request, user: OwnerUser, session: DbSession
) -> list[OwnerVenueImageOut]:
    return await _svc(request, session).reorder_images(venue_id, user.id, body)


@router.patch(
    "/{venue_id}/images/{image_id}",
    response_model=OwnerVenueImageOut,
    summary="Set cover, caption or position",
)
async def patch_image(
    venue_id: UUID, image_id: UUID, body: ImagePatch, request: Request, user: OwnerUser, session: DbSession
) -> OwnerVenueImageOut:
    return await _svc(request, session).patch_image(venue_id, user.id, image_id, body)


@router.delete(
    "/{venue_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an image"
)
async def delete_image(
    venue_id: UUID, image_id: UUID, request: Request, user: OwnerUser, session: DbSession
) -> Response:
    await _svc(request, session).delete_image(venue_id, user.id, image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ schedules
@router.get("/{venue_id}/schedules", response_model=ScheduleOut, summary="Regular and special opening hours")
async def get_schedule(venue_id: UUID, request: Request, user: OwnerUser, session: DbSession) -> ScheduleOut:
    return await _svc(request, session).get_schedule(venue_id, user.id)


@router.put(
    "/{venue_id}/schedules", response_model=ScheduleOut, summary="Replace regular and/or special hours"
)
async def put_schedule(
    venue_id: UUID, body: ScheduleReplace, request: Request, user: OwnerUser, session: DbSession
) -> ScheduleOut:
    return await _svc(request, session).replace_schedule(venue_id, user.id, body)
