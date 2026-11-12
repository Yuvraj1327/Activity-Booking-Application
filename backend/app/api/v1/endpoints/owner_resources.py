"""Owner: courts (resources) and temporary unavailable periods."""

from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.deps import DbSession, OwnerUser
from app.schemas.booking import BlockCreate, BlockOut, ResourceCreate, ResourceOut, ResourceUpdate
from app.services.owner_resources import OwnerResourceService

router = APIRouter(prefix="/owners/venues/{venue_id}", tags=["owner-courts"])


@router.get("/resources", response_model=list[ResourceOut], summary="Courts of a venue")
async def list_resources(venue_id: UUID, user: OwnerUser, session: DbSession) -> list[ResourceOut]:
    return await OwnerResourceService(session).list_resources(venue_id, user.id)


@router.post(
    "/resources", response_model=ResourceOut, status_code=status.HTTP_201_CREATED, summary="Add a court"
)
async def create_resource(
    venue_id: UUID, body: ResourceCreate, user: OwnerUser, session: DbSession
) -> ResourceOut:
    return await OwnerResourceService(session).create_resource(venue_id, user.id, body)


@router.patch(
    "/resources/{resource_id}",
    response_model=ResourceOut,
    summary="Edit a court (409 SCHEDULE_CONFLICT if it would break future bookings)",
)
async def update_resource(
    venue_id: UUID, resource_id: UUID, body: ResourceUpdate, user: OwnerUser, session: DbSession
) -> ResourceOut:
    return await OwnerResourceService(session).update_resource(venue_id, user.id, resource_id, body)


@router.delete(
    "/resources/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a court that has never been booked",
)
async def delete_resource(venue_id: UUID, resource_id: UUID, user: OwnerUser, session: DbSession) -> Response:
    await OwnerResourceService(session).delete_resource(venue_id, user.id, resource_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/blocks", response_model=list[BlockOut], summary="Temporary unavailable periods")
async def list_blocks(venue_id: UUID, user: OwnerUser, session: DbSession) -> list[BlockOut]:
    return await OwnerResourceService(session).list_blocks(venue_id, user.id)


@router.post(
    "/blocks",
    response_model=BlockOut,
    status_code=status.HTTP_201_CREATED,
    summary="Block a period (409 SCHEDULE_CONFLICT if bookings exist in it)",
)
async def create_block(venue_id: UUID, body: BlockCreate, user: OwnerUser, session: DbSession) -> BlockOut:
    return await OwnerResourceService(session).create_block(venue_id, user.id, body)


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a block")
async def delete_block(venue_id: UUID, block_id: UUID, user: OwnerUser, session: DbSession) -> Response:
    await OwnerResourceService(session).delete_block(venue_id, user.id, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
