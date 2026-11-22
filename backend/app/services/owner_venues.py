"""Venue management for owners. Every query is scoped to the authenticated owner's id, so another
owner's venue is indistinguishable from a missing one (404, never 403: no existence leak)."""

import uuid
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import (
    Amenity,
    AuditLog,
    Category,
    City,
    ScheduleException,
    ScheduleRule,
    Venue,
    VenueAmenity,
    VenueCategory,
    VenueImage,
    VenueModerationEvent,
    VenueResource,
)
from app.schemas.catalog import AmenityOut, CategoryOut
from app.schemas.owner import (
    MAX_IMAGE_BYTES,
    MAX_IMAGES,
    DayHours,
    ImageOrder,
    ImagePatch,
    Interval,
    OwnerVenueCard,
    OwnerVenueCreate,
    OwnerVenueDetail,
    OwnerVenueImageOut,
    OwnerVenuePage,
    OwnerVenueUpdate,
    ScheduleOut,
    ScheduleReplace,
    SpecialDate,
)
from app.services import platform_settings
from app.services.schedule_guard import ensure_no_conflicts, has_bookings
from app.services.storage import StorageGateway
from app.services.venues import public_image_url

_IMAGE_TYPES = (
    (b"\xff\xd8\xff", "jpg", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
)


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """Detects the real format from the file's bytes (the client-declared type is not trusted)."""
    for magic, ext, ctype in _IMAGE_TYPES:
        if data.startswith(magic):
            return ext, ctype
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def _f(value: object) -> float | None:
    return float(value) if value is not None else None  # type: ignore[arg-type]


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class OwnerVenueService:
    def __init__(self, session: AsyncSession, settings: Settings, storage: StorageGateway) -> None:
        self.s = session
        self.settings = settings
        self.storage = storage

    # ------------------------------------------------------------------ helpers
    async def _owned(self, venue_id: UUID, owner_id: UUID, *, lock: bool = False) -> Venue:
        stmt = select(Venue).where(Venue.id == venue_id, Venue.owner_id == owner_id)
        if lock:
            stmt = stmt.with_for_update()  # waits for in-flight bookings on this venue
        venue = (await self.s.execute(stmt)).scalar_one_or_none()
        if venue is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        return venue

    async def _audit(self, owner_id: UUID, action: str, venue_id: UUID, **meta: object) -> None:
        self.s.add(
            AuditLog(
                actor_id=owner_id,
                actor_role="owner",
                action=action,
                entity_type="venue",
                entity_id=str(venue_id),
                metadata_=dict(meta),
            )
        )

    async def _check_city(self, city_id: UUID | None) -> None:
        if city_id is None:
            return
        found = await self.s.execute(select(City.id).where(City.id == city_id, City.is_active.is_(True)))
        if found.first() is None:
            raise ValidationFailedError("Choose a city from the list.", code="INVALID_CITY")

    async def _check_ids(
        self, model: type[Category] | type[Amenity], ids: list[UUID], code: str
    ) -> list[UUID]:
        unique = list(dict.fromkeys(ids))
        if not unique:
            return []
        rows = await self.s.execute(select(model.id).where(model.id.in_(unique), model.is_active.is_(True)))
        if len(rows.all()) != len(unique):
            raise ValidationFailedError("One or more selected options are not available.", code=code)
        return unique

    @staticmethod
    def _check_tz(tz: str) -> None:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
            raise ValidationFailedError("Unknown time zone.", code="INVALID_TIMEZONE") from exc

    async def _set_links(
        self, venue_id: UUID, category_ids: list[UUID] | None, amenity_ids: list[UUID] | None
    ) -> None:
        if category_ids is not None:
            await self.s.execute(delete(VenueCategory).where(VenueCategory.venue_id == venue_id))
            self.s.add_all(VenueCategory(venue_id=venue_id, category_id=c) for c in category_ids)
        if amenity_ids is not None:
            await self.s.execute(delete(VenueAmenity).where(VenueAmenity.venue_id == venue_id))
            self.s.add_all(VenueAmenity(venue_id=venue_id, amenity_id=a) for a in amenity_ids)

    async def _category_count(self, venue_id: UUID) -> int:
        q = select(func.count()).select_from(VenueCategory).where(VenueCategory.venue_id == venue_id)
        return int((await self.s.execute(q)).scalar_one())

    @staticmethod
    def _blockers(venue: Venue, category_count: int) -> list[str]:
        out = []
        if venue.city_id is None:
            out.append("Choose a city.")
        if venue.latitude is None or venue.longitude is None:
            out.append("Add the venue's latitude and longitude.")
        if category_count == 0:
            out.append("Choose at least one sport category.")
        return out

    # ------------------------------------------------------------------ views
    async def _images(self, venue_id: UUID) -> list[VenueImage]:
        q = (
            select(VenueImage)
            .where(VenueImage.venue_id == venue_id, VenueImage.status == "active")
            .order_by(VenueImage.sort_order, VenueImage.created_at)
        )
        return list((await self.s.scalars(q)).all())

    def _card(
        self, v: Venue, city_name: str | None, images: list[VenueImage], slugs: list[str]
    ) -> OwnerVenueCard:
        cover = next((i for i in images if i.is_cover), images[0] if images else None)
        return OwnerVenueCard(
            id=v.id,
            name=v.name,
            status=v.status,
            status_reason=v.status_reason if v.status in ("rejected", "suspended") else None,
            is_verified=v.is_verified,
            city_name=city_name,
            address_line=v.address_line,
            cover_image_url=public_image_url(self.settings, cover.storage_path) if cover else None,
            image_count=len(images),
            categories=slugs,
            starting_price_paise=v.starting_price_paise,
            currency=v.currency,
            rating_avg=_f(v.rating_avg),
            rating_count=v.rating_count,
            updated_at=v.updated_at,
        )

    async def detail(self, venue: Venue) -> OwnerVenueDetail:
        city = await self.s.get(City, venue.city_id) if venue.city_id else None
        images = await self._images(venue.id)
        cats = list(
            (
                await self.s.scalars(
                    select(Category)
                    .join(VenueCategory, VenueCategory.category_id == Category.id)
                    .where(VenueCategory.venue_id == venue.id)
                    .order_by(Category.sort_order, Category.name)
                )
            ).all()
        )
        ams = list(
            (
                await self.s.scalars(
                    select(Amenity)
                    .join(VenueAmenity, VenueAmenity.amenity_id == Amenity.id)
                    .where(VenueAmenity.venue_id == venue.id)
                    .order_by(Amenity.sort_order, Amenity.name)
                )
            ).all()
        )
        card = self._card(venue, city.name if city else None, images, [c.slug for c in cats])
        return OwnerVenueDetail(
            **card.model_dump(),
            description=venue.description,
            city_id=venue.city_id,
            state=city.state if city else None,
            postal_code=venue.postal_code,
            latitude=_f(venue.latitude),
            longitude=_f(venue.longitude),
            contact_phone=venue.contact_phone,
            timezone=venue.timezone,
            published_at=venue.published_at,
            category_details=[CategoryOut.model_validate(c) for c in cats],
            amenities=[AmenityOut.model_validate(a) for a in ams],
            images=[self._image_out(i) for i in images],
            publish_blockers=self._blockers(venue, len(cats)),
        )

    def _image_out(self, i: VenueImage) -> OwnerVenueImageOut:
        return OwnerVenueImageOut(
            id=i.id,
            url=public_image_url(self.settings, i.storage_path),
            alt_text=i.alt_text,
            is_cover=i.is_cover,
            sort_order=i.sort_order,
            width=i.width,
            height=i.height,
            byte_size=i.byte_size,
        )

    # ------------------------------------------------------------------ list / read
    async def list_venues(
        self, owner_id: UUID, q: str | None, status: str | None, limit: int, offset: int
    ) -> OwnerVenuePage:
        stmt = (
            select(Venue, City.name)
            .outerjoin(City, City.id == Venue.city_id)
            .where(Venue.owner_id == owner_id)
            .order_by(Venue.updated_at.desc(), Venue.id)
            .limit(limit + 1)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(Venue.status == status)
        if q:
            like = f"%{_escape_like(q.strip())}%"
            stmt = stmt.where(
                Venue.name.ilike(like, escape="\\")
                | Venue.address_line.ilike(like, escape="\\")
                | City.name.ilike(like, escape="\\")
            )
        rows = (await self.s.execute(stmt)).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        ids = [r[0].id for r in rows]
        images_by: dict[UUID, list[VenueImage]] = {i: [] for i in ids}
        slugs_by: dict[UUID, list[str]] = {i: [] for i in ids}
        if ids:
            imgs = await self.s.scalars(
                select(VenueImage)
                .where(VenueImage.venue_id.in_(ids), VenueImage.status == "active")
                .order_by(VenueImage.sort_order, VenueImage.created_at)
            )
            for img in imgs:
                images_by[img.venue_id].append(img)
            cat_rows = await self.s.execute(
                select(VenueCategory.venue_id, Category.slug)
                .join(Category, Category.id == VenueCategory.category_id)
                .where(VenueCategory.venue_id.in_(ids))
                .order_by(Category.sort_order)
            )
            for vid, slug in cat_rows.all():
                slugs_by[vid].append(slug)
        return OwnerVenuePage(
            items=[self._card(v, city, images_by[v.id], slugs_by[v.id]) for v, city in rows],
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    async def get(self, venue_id: UUID, owner_id: UUID) -> OwnerVenueDetail:
        return await self.detail(await self._owned(venue_id, owner_id))

    # ------------------------------------------------------------------ create / update
    async def create(self, owner_id: UUID, body: OwnerVenueCreate) -> OwnerVenueDetail:
        await self._check_city(body.city_id)
        self._check_tz(body.timezone)
        cats = await self._check_ids(Category, body.category_ids, "INVALID_CATEGORY")
        ams = await self._check_ids(Amenity, body.amenity_ids, "INVALID_AMENITY")
        venue = Venue(
            id=uuid.uuid4(),
            owner_id=owner_id,
            status="draft",
            **body.model_dump(exclude={"category_ids", "amenity_ids"}),
        )
        self.s.add(venue)
        await self.s.flush()
        await self._set_links(venue.id, cats, ams)
        await self._audit(owner_id, "venue.created", venue.id)
        await self.s.commit()
        await self.s.refresh(venue)
        return await self.detail(venue)

    async def update(self, venue_id: UUID, owner_id: UUID, patch: OwnerVenueUpdate) -> OwnerVenueDetail:
        venue = await self._owned(venue_id, owner_id, lock=True)
        data = patch.model_dump(exclude_unset=True)
        cats_in, ams_in = data.pop("category_ids", None), data.pop("amenity_ids", None)
        if "city_id" in data:
            await self._check_city(data["city_id"])
        if "timezone" in data:
            self._check_tz(data["timezone"])
        cats = await self._check_ids(Category, cats_in, "INVALID_CATEGORY") if cats_in is not None else None
        ams = await self._check_ids(Amenity, ams_in, "INVALID_AMENITY") if ams_in is not None else None
        for key, value in data.items():
            setattr(venue, key, value)
        if (venue.latitude is None) != (venue.longitude is None):
            raise ValidationFailedError(
                "latitude and longitude must be set together.", code="INVALID_LOCATION"
            )
        if venue.status == "published":
            # Check before touching the database: its constraint would otherwise surface as a 500.
            with self.s.no_autoflush:
                count = len(cats) if cats is not None else await self._category_count(venue.id)
            blockers = self._blockers(venue, count)
            if blockers:
                await self.s.rollback()
                raise ValidationFailedError(
                    "A published venue must keep its city, location and category. Unpublish it first.",
                    code="PUBLISHED_VENUE_INCOMPLETE",
                    details=blockers,
                )
        if cats is not None:
            await self._set_links(venue.id, cats, None)
        if ams is not None:
            await self._set_links(venue.id, None, ams)
        await self.s.flush()
        if "timezone" in data:  # moving the time zone moves every slot: same policy as hours (Q16)
            await ensure_no_conflicts(self.s, venue)
        await self._audit(
            owner_id,
            "venue.updated",
            venue.id,
            fields=sorted(data)
            + (["categories"] if cats is not None else [])
            + (["amenities"] if ams is not None else []),
        )
        await self.s.commit()
        await self.s.refresh(venue)
        return await self.detail(venue)

    def _moderation(
        self, venue: Venue, action: str, owner_id: UUID, from_status: str, reason: str | None = None
    ) -> None:
        self.s.add(
            VenueModerationEvent(
                venue_id=venue.id, action=action, from_status=from_status, to_status=venue.status,
                reason=reason, actor_id=owner_id, actor_role="owner",
            )
        )  # fmt: skip

    async def publish(self, venue_id: UUID, owner_id: UUID) -> OwnerVenueDetail:
        """Goes live directly, or is submitted for admin approval once that workflow is switched on (Q4).
        A suspended venue can never be re-published by its owner."""
        venue = await self._owned(venue_id, owner_id, lock=True)
        if venue.status == "suspended":
            raise ConflictError(
                "This venue was suspended by ZURUV. Contact support to have it reinstated.",
                code="VENUE_SUSPENDED",
            )
        if venue.status in ("published", "pending_review"):
            return await self.detail(venue)
        blockers = self._blockers(venue, await self._category_count(venue.id))
        if blockers:
            raise ValidationFailedError(
                "This venue is not ready to publish.", code="PUBLISH_REQUIREMENTS", details=blockers
            )
        old = venue.status
        now = datetime.now(UTC)
        if await platform_settings.get(self.s, "venue_approval_required"):
            venue.status = "pending_review"
            venue.submitted_at = now
            venue.status_reason = None
            self._moderation(venue, "submitted", owner_id, old)
            await self._audit(owner_id, "venue.submitted", venue.id)
        else:
            venue.status = "published"
            venue.published_at = now
            venue.status_reason = None
            await self._audit(owner_id, "venue.published", venue.id)
        await self.s.commit()
        await self.s.refresh(venue)
        return await self.detail(venue)

    async def unpublish(self, venue_id: UUID, owner_id: UUID) -> OwnerVenueDetail:
        venue = await self._owned(venue_id, owner_id, lock=True)
        if venue.status == "suspended":
            raise ConflictError("This venue was suspended by ZURUV.", code="VENUE_SUSPENDED")
        if venue.status in ("published", "pending_review"):
            old = venue.status
            venue.status = "draft"
            venue.published_at = None
            if old == "pending_review":
                self._moderation(venue, "withdrawn", owner_id, old)
            await self._audit(
                owner_id, "venue.unpublished" if old == "published" else "venue.withdrawn", venue.id
            )
            await self.s.commit()
            await self.s.refresh(venue)
        return await self.detail(venue)

    async def delete(self, venue_id: UUID, owner_id: UUID) -> None:
        """Hard delete. A venue that has any booking record cannot be deleted (409)."""
        venue = await self._owned(venue_id, owner_id, lock=True)
        if await has_bookings(self.s, venue_id=venue.id):
            raise ConflictError(
                "This venue has bookings and cannot be deleted. Unpublish it instead.",
                code="VENUE_HAS_BOOKINGS",
            )
        paths = [
            i.storage_path
            for i in (await self.s.scalars(select(VenueImage).where(VenueImage.venue_id == venue.id))).all()
        ]
        await self._audit(owner_id, "venue.deleted", venue.id, name=venue.name)
        await self.s.delete(venue)
        await self.s.commit()
        await self.storage.delete(paths)

    # ------------------------------------------------------------------ images
    async def add_image(
        self, venue_id: UUID, owner_id: UUID, data: bytes, alt_text: str | None
    ) -> OwnerVenueImageOut:
        venue = await self._owned(venue_id, owner_id)
        if not data:
            raise ValidationFailedError("The image file is empty.", code="INVALID_IMAGE")
        if len(data) > MAX_IMAGE_BYTES:
            raise ValidationFailedError("Images can be at most 5 MB.", code="IMAGE_TOO_LARGE")
        kind = sniff_image(data)
        if kind is None:
            raise ValidationFailedError("Upload a JPG, PNG or WebP image.", code="INVALID_IMAGE")
        existing = await self._images(venue.id)
        if len(existing) >= MAX_IMAGES:
            raise ValidationFailedError(
                f"A venue can have at most {MAX_IMAGES} images.", code="IMAGE_LIMIT_REACHED"
            )
        ext, content_type = kind
        path = f"{venue.id}/{uuid.uuid4()}.{ext}"
        await self.storage.upload(path, data, content_type)
        image = VenueImage(
            venue_id=venue.id,
            storage_path=path,
            status="active",
            is_cover=not existing,
            sort_order=(max((i.sort_order for i in existing), default=-1) + 1),
            alt_text=(alt_text or None),
            byte_size=len(data),
        )
        try:
            self.s.add(image)
            await self.s.flush()
            await self._audit(owner_id, "venue.image_added", venue.id, image_id=str(image.id))
            await self.s.commit()
        except Exception:
            await self.s.rollback()
            await self.storage.delete([path])
            raise
        return self._image_out(image)

    async def _image(self, venue_id: UUID, owner_id: UUID, image_id: UUID) -> VenueImage:
        await self._owned(venue_id, owner_id)
        image = (
            await self.s.execute(
                select(VenueImage).where(VenueImage.id == image_id, VenueImage.venue_id == venue_id)
            )
        ).scalar_one_or_none()
        if image is None:
            raise NotFoundError("Image not found.", code="IMAGE_NOT_FOUND")
        return image

    async def delete_image(self, venue_id: UUID, owner_id: UUID, image_id: UUID) -> None:
        image = await self._image(venue_id, owner_id, image_id)
        path, was_cover = image.storage_path, image.is_cover
        await self.s.delete(image)
        await self.s.flush()
        if was_cover:
            remaining = await self._images(venue_id)
            if remaining:
                remaining[0].is_cover = True
        await self._audit(owner_id, "venue.image_removed", venue_id, image_id=str(image_id))
        await self.s.commit()
        await self.storage.delete([path])

    async def patch_image(
        self, venue_id: UUID, owner_id: UUID, image_id: UUID, patch: ImagePatch
    ) -> OwnerVenueImageOut:
        image = await self._image(venue_id, owner_id, image_id)
        data = patch.model_dump(exclude_unset=True)
        if data.get("is_cover") is True:
            for other in await self._images(venue_id):
                if other.id != image.id and other.is_cover:
                    other.is_cover = False
            await self.s.flush()
        for key, value in data.items():
            setattr(image, key, value)
        await self.s.commit()
        return self._image_out(image)

    async def reorder_images(
        self, venue_id: UUID, owner_id: UUID, body: ImageOrder
    ) -> list[OwnerVenueImageOut]:
        await self._owned(venue_id, owner_id)
        images = await self._images(venue_id)
        if {i.id for i in images} != set(body.image_ids) or len(body.image_ids) != len(images):
            raise ValidationFailedError(
                "Send every image of this venue exactly once.", code="INVALID_IMAGE_ORDER"
            )
        by_id = {i.id: i for i in images}
        for position, image_id in enumerate(body.image_ids):
            by_id[image_id].sort_order = position
        await self.s.commit()
        return [self._image_out(by_id[i]) for i in body.image_ids]

    # ------------------------------------------------------------------ schedules
    async def get_schedule(self, venue_id: UUID, owner_id: UUID) -> ScheduleOut:
        venue = await self._owned(venue_id, owner_id)
        rules = (
            await self.s.scalars(
                select(ScheduleRule)
                .where(ScheduleRule.venue_id == venue.id)
                .order_by(ScheduleRule.weekday, ScheduleRule.opens_at)
            )
        ).all()
        exceptions = (
            await self.s.scalars(
                select(ScheduleException)
                .where(ScheduleException.venue_id == venue.id)
                .order_by(ScheduleException.on_date)
            )
        ).all()
        days: dict[int, list[Interval]] = {d: [] for d in range(7)}
        for r in rules:
            days[r.weekday].append(Interval(opens_at=r.opens_at, closes_at=r.closes_at))
        return ScheduleOut(
            venue_id=venue.id,
            timezone=venue.timezone,
            regular=[DayHours(weekday=d, intervals=days[d]) for d in range(7)],
            special=[
                SpecialDate(
                    on_date=e.on_date,
                    is_closed=e.is_closed,
                    opens_at=e.opens_at,
                    closes_at=e.closes_at,
                    note=e.note,
                )
                for e in exceptions
            ],
            slot_configuration=await self._slot_configuration(venue.id),
        )

    async def _slot_configuration(self, venue_id: UUID) -> dict[str, object]:
        rows = (
            await self.s.scalars(
                select(VenueResource)
                .where(VenueResource.venue_id == venue_id, VenueResource.is_active.is_(True))
                .order_by(VenueResource.sort_order, VenueResource.name)
            )
        ).all()
        ready = [r for r in rows if r.slot_minutes is not None and r.slot_price_paise is not None]
        if not ready:
            return {
                "status": "not_configured",
                "resources": len(rows),
                "message": "Add a court with a slot length and price to start taking bookings.",
            }
        return {
            "status": "configured",
            "resources": len(rows),
            "configured_resources": len(ready),
            "courts": [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "slot_minutes": r.slot_minutes,
                    "slot_price_paise": r.slot_price_paise,
                }
                for r in ready
            ],
        }

    async def replace_schedule(self, venue_id: UUID, owner_id: UUID, body: ScheduleReplace) -> ScheduleOut:
        venue = await self._owned(venue_id, owner_id, lock=True)
        if body.regular is not None:
            weekdays = [d.weekday for d in body.regular]
            if len(set(weekdays)) != len(weekdays):
                raise ValidationFailedError("Each weekday may appear once.", code="INVALID_SCHEDULE")
            for day in body.regular:
                ordered = sorted(day.intervals, key=lambda i: i.opens_at)
                for a, b in zip(ordered, ordered[1:], strict=False):
                    if b.opens_at < a.closes_at:
                        raise ValidationFailedError(
                            "Opening intervals on one day cannot overlap.", code="INVALID_SCHEDULE"
                        )
        if body.special is not None:
            dates = [d.on_date for d in body.special]
            if len(set(dates)) != len(dates):
                raise ValidationFailedError("Each special date may appear once.", code="INVALID_SCHEDULE")
        if body.regular is not None:
            await self.s.execute(delete(ScheduleRule).where(ScheduleRule.venue_id == venue.id))
            for day in body.regular:
                for iv in day.intervals:
                    self.s.add(
                        ScheduleRule(
                            venue_id=venue.id,
                            weekday=day.weekday,
                            opens_at=iv.opens_at,
                            closes_at=iv.closes_at,
                        )
                    )
        if body.special is not None:
            await self.s.execute(delete(ScheduleException).where(ScheduleException.venue_id == venue.id))
            for sp in body.special:
                self.s.add(
                    ScheduleException(
                        venue_id=venue.id,
                        on_date=sp.on_date,
                        is_closed=sp.is_closed,
                        opens_at=sp.opens_at,
                        closes_at=sp.closes_at,
                        note=sp.note,
                    )
                )
        await self.s.flush()
        await ensure_no_conflicts(self.s, venue)
        await self._audit(
            owner_id,
            "venue.schedule_replaced",
            venue.id,
            regular=body.regular is not None,
            special=body.special is not None,
        )
        await self.s.commit()
        return await self.get_schedule(venue.id, owner_id)
