"""Owner-managed courts (resources) and temporary unavailable periods."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models import AuditLog, AvailabilityBlock, Venue, VenueResource
from app.schemas.booking import BlockCreate, BlockOut, ResourceCreate, ResourceOut, ResourceUpdate
from app.services.availability import is_configured
from app.services.schedule_guard import ensure_no_conflicts, has_bookings

MAX_RESOURCES = 50


def resource_out(r: VenueResource) -> ResourceOut:
    return ResourceOut(
        id=r.id,
        venue_id=r.venue_id,
        name=r.name,
        slot_minutes=r.slot_minutes,
        slot_price_paise=r.slot_price_paise,
        sort_order=r.sort_order,
        is_active=r.is_active,
        configured=is_configured(r),
    )


def block_out(b: AvailabilityBlock) -> BlockOut:
    assert b.block_range.lower is not None and b.block_range.upper is not None
    return BlockOut(
        id=b.id,
        venue_id=b.venue_id,
        resource_id=b.resource_id,
        starts_at=b.block_range.lower,
        ends_at=b.block_range.upper,
        reason=b.reason,
    )


class OwnerResourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    async def _venue(self, venue_id: UUID, owner_id: UUID) -> Venue:
        """Exclusive row lock: bookings being created for this venue wait for this change."""
        venue = await self.s.scalar(
            select(Venue).where(Venue.id == venue_id, Venue.owner_id == owner_id).with_for_update()
        )
        if venue is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        return venue

    async def _resource(self, venue_id: UUID, resource_id: UUID) -> VenueResource:
        res = await self.s.scalar(
            select(VenueResource).where(VenueResource.id == resource_id, VenueResource.venue_id == venue_id)
        )
        if res is None:
            raise NotFoundError("Court not found.", code="RESOURCE_NOT_FOUND")
        return res

    def _audit(self, owner_id: UUID, action: str, entity: str, entity_id: UUID, **meta: object) -> None:
        self.s.add(
            AuditLog(
                actor_id=owner_id,
                actor_role="owner",
                action=action,
                entity_type=entity,
                entity_id=str(entity_id),
                metadata_=dict(meta),
            )
        )

    async def list_resources(self, venue_id: UUID, owner_id: UUID) -> list[ResourceOut]:
        await self._owned_readonly(venue_id, owner_id)
        rows = await self.s.scalars(
            select(VenueResource)
            .where(VenueResource.venue_id == venue_id)
            .order_by(VenueResource.sort_order, VenueResource.name)
        )
        return [resource_out(r) for r in rows]

    async def _owned_readonly(self, venue_id: UUID, owner_id: UUID) -> Venue:
        venue = await self.s.scalar(select(Venue).where(Venue.id == venue_id, Venue.owner_id == owner_id))
        if venue is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        return venue

    async def create_resource(self, venue_id: UUID, owner_id: UUID, body: ResourceCreate) -> ResourceOut:
        await self._venue(venue_id, owner_id)
        count = len(
            (await self.s.scalars(select(VenueResource.id).where(VenueResource.venue_id == venue_id))).all()
        )
        if count >= MAX_RESOURCES:
            raise ConflictError(
                f"A venue can have at most {MAX_RESOURCES} courts.", code="TOO_MANY_RESOURCES"
            )
        res = VenueResource(venue_id=venue_id, **body.model_dump())
        self.s.add(res)
        await self.s.flush()
        self._audit(owner_id, "resource.created", "venue_resource", res.id, venue_id=str(venue_id))
        await self.s.commit()
        return resource_out(res)

    async def update_resource(
        self, venue_id: UUID, owner_id: UUID, resource_id: UUID, patch: ResourceUpdate
    ) -> ResourceOut:
        venue = await self._venue(venue_id, owner_id)
        res = await self._resource(venue_id, resource_id)
        data = patch.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(res, key, value)
        await self.s.flush()
        if {"slot_minutes", "is_active"} & data.keys():
            await ensure_no_conflicts(self.s, venue)
        self._audit(owner_id, "resource.updated", "venue_resource", res.id, fields=sorted(data))
        await self.s.commit()
        return resource_out(res)

    async def delete_resource(self, venue_id: UUID, owner_id: UUID, resource_id: UUID) -> None:
        await self._venue(venue_id, owner_id)
        res = await self._resource(venue_id, resource_id)
        if await has_bookings(self.s, resource_id=res.id):
            raise ConflictError(
                "This court has bookings. Deactivate it instead of deleting it.", code="RESOURCE_HAS_BOOKINGS"
            )
        await self.s.delete(res)
        self._audit(owner_id, "resource.deleted", "venue_resource", resource_id, venue_id=str(venue_id))
        await self.s.commit()

    # ------------------------------------------------------------------ blocks
    async def list_blocks(self, venue_id: UUID, owner_id: UUID) -> list[BlockOut]:
        await self._owned_readonly(venue_id, owner_id)
        rows = await self.s.scalars(
            select(AvailabilityBlock)
            .where(AvailabilityBlock.venue_id == venue_id)
            .order_by(AvailabilityBlock.created_at)
        )
        return [block_out(b) for b in rows]

    async def create_block(self, venue_id: UUID, owner_id: UUID, body: BlockCreate) -> BlockOut:
        venue = await self._venue(venue_id, owner_id)
        if body.resource_id is not None:
            await self._resource(venue_id, body.resource_id)
        block = AvailabilityBlock(
            venue_id=venue_id,
            resource_id=body.resource_id,
            block_range=Range(body.starts_at, body.ends_at, bounds="[)"),
            reason=body.reason,
            created_by=owner_id,
        )
        self.s.add(block)
        await self.s.flush()
        await ensure_no_conflicts(self.s, venue)
        self._audit(owner_id, "block.created", "availability_block", block.id, venue_id=str(venue_id))
        await self.s.commit()
        return block_out(block)

    async def delete_block(self, venue_id: UUID, owner_id: UUID, block_id: UUID) -> None:
        await self._venue(venue_id, owner_id)
        block = await self.s.scalar(
            select(AvailabilityBlock).where(
                AvailabilityBlock.id == block_id, AvailabilityBlock.venue_id == venue_id
            )
        )
        if block is None:
            raise NotFoundError("Block not found.", code="BLOCK_NOT_FOUND")
        await self.s.delete(block)
        self._audit(owner_id, "block.deleted", "availability_block", block_id, venue_id=str(venue_id))
        await self.s.commit()
