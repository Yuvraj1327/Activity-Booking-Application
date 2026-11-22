"""Support tickets, sports categories and CMS content (admin side)."""

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import (
    Booking,
    Category,
    CmsContent,
    Profile,
    SupportTicket,
    SupportTicketMessage,
    VenueCategory,
)
from app.services import audit
from app.services.notifications import NotificationService


# ====================================================================== support tickets
class SupportAdmin:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    @staticmethod
    def _row(
        t: SupportTicket, name: str, role: str, code: str | None, assignee: str | None
    ) -> dict[str, Any]:
        return {
            "id": t.id, "kind": t.kind, "subject": t.subject, "status": t.status, "priority": t.priority,
            "user_id": t.user_id, "user_name": name, "user_role": role, "booking_id": t.booking_id,
            "booking_code": code, "assigned_to": t.assigned_to, "assignee_name": assignee,
            "created_at": t.created_at, "updated_at": t.updated_at, "resolved_at": t.resolved_at,
        }  # fmt: skip

    def _base(self) -> Any:
        from sqlalchemy.orm import aliased

        asg = aliased(Profile)
        return (
            select(SupportTicket, Profile.full_name, Profile.role, Booking.booking_code, asg.full_name)
            .join(Profile, Profile.id == SupportTicket.user_id)
            .outerjoin(Booking, Booking.id == SupportTicket.booking_id)
            .outerjoin(asg, asg.id == SupportTicket.assigned_to)
        )

    async def list_all(
        self, status: str | None, priority: str | None, kind: str | None, q: str | None,
        assigned_to: UUID | None, limit: int, offset: int,
    ) -> dict[str, Any]:  # fmt: skip
        stmt = self._base()
        if status == "active":
            stmt = stmt.where(SupportTicket.status.in_(("open", "in_progress")))
        elif status:
            stmt = stmt.where(SupportTicket.status == status)
        if priority:
            stmt = stmt.where(SupportTicket.priority == priority)
        if kind:
            stmt = stmt.where(SupportTicket.kind == kind)
        if assigned_to:
            stmt = stmt.where(SupportTicket.assigned_to == assigned_to)
        if q and q.strip():
            pat = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(SupportTicket.subject.ilike(pat), Profile.full_name.ilike(pat), Profile.email.ilike(pat))
            )
        prio = func.array_position(["urgent", "high", "normal", "low"], SupportTicket.priority)
        rows = (
            await self.s.execute(
                stmt.order_by(prio, SupportTicket.created_at.desc(), SupportTicket.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        return {
            "items": [self._row(*r) for r in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    async def get(self, ticket_id: UUID) -> dict[str, Any]:
        row = (await self.s.execute(self._base().where(SupportTicket.id == ticket_id))).first()
        if row is None:
            raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
        t, *_ = row
        user = await self.s.get(Profile, t.user_id)
        booking = None
        if t.booking_id:
            b = await self.s.get(Booking, t.booking_id)
            if b is not None:
                booking = {"id": b.id, "booking_code": b.booking_code, "status": b.status, "payment_status": b.payment_status,
                           "venue_name": b.venue_name, "booking_date": b.booking_date, "total_amount_paise": b.total_amount_paise}  # fmt: skip
        msgs = (
            await self.s.execute(
                select(SupportTicketMessage, Profile.full_name)
                .outerjoin(Profile, Profile.id == SupportTicketMessage.author_id)
                .where(SupportTicketMessage.ticket_id == ticket_id)
                .order_by(SupportTicketMessage.created_at, SupportTicketMessage.id)
            )
        ).all()
        return {
            **self._row(*row),
            "message": t.message, "app_version": t.app_version, "platform": t.platform,
            "customer": {"id": user.id, "full_name": user.full_name, "email": user.email, "phone": user.phone,
                         "role": user.role, "status": user.status} if user else None,
            "booking": booking,
            "messages": [
                {"id": m.id, "kind": m.kind, "body": m.body, "author_role": m.author_role, "author_name": n,
                 "created_at": m.created_at}
                for m, n in msgs
            ],
        }  # fmt: skip

    def _event(self, t: SupportTicket, actor: CurrentUser, body: str) -> None:
        self.s.add(
            SupportTicketMessage(
                ticket_id=t.id, author_id=actor.id, author_role="admin", kind="event", body=body
            )
        )

    async def _lock(self, ticket_id: UUID) -> SupportTicket:
        t = await self.s.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id).with_for_update())
        if t is None:
            raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
        return t

    async def reply(self, actor: CurrentUser, ticket_id: UUID, body: str, internal: bool) -> dict[str, Any]:
        t = await self._lock(ticket_id)
        if t.status in ("resolved", "closed") and not internal:
            raise ConflictError("Reopen the ticket before replying to the customer.", code="TICKET_CLOSED")
        self.s.add(SupportTicketMessage(ticket_id=t.id, author_id=actor.id, author_role="admin",
                                        kind="note" if internal else "reply", body=body))  # fmt: skip
        before = {"status": t.status}
        if not internal and t.status == "open":
            t.status = "in_progress"
        audit.record(self.s, actor.profile, "admin.ticket_noted" if internal else "admin.ticket_replied", "support_ticket",
                     t.id, before=before, after={"status": t.status}, internal=internal)  # fmt: skip
        if not internal:
            await NotificationService(self.s).queue(
                user_id=t.user_id, type_="support.reply", title="ZURUV support replied", body=body[:200],
                dedupe_key=f"ticket:{t.id}:reply:{datetime.now(UTC).isoformat()}",
            )  # fmt: skip
        await self.s.commit()
        return await self.get(ticket_id)

    async def update(
        self, actor: CurrentUser, ticket_id: UUID, status: str | None, priority: str | None,
        assigned_to_me: bool | None, booking_id: UUID | None, set_booking: bool,
    ) -> dict[str, Any]:  # fmt: skip
        t = await self._lock(ticket_id)
        before = {
            "status": t.status,
            "priority": t.priority,
            "assigned_to": t.assigned_to,
            "booking_id": t.booking_id,
        }
        if status and status != t.status:
            self._event(t, actor, f"Status changed from {t.status} to {status}.")
            t.status = status
            t.resolved_at = datetime.now(UTC) if status in ("resolved", "closed") else None
        if priority and priority != t.priority:
            self._event(t, actor, f"Priority changed from {t.priority} to {priority}.")
            t.priority = priority
        if assigned_to_me is not None:
            t.assigned_to = actor.id if assigned_to_me else None
            self._event(t, actor, "Assigned to " + ("me." if assigned_to_me else "nobody."))
        if set_booking:
            if booking_id is not None and await self.s.get(Booking, booking_id) is None:
                raise ValidationFailedError("That booking does not exist.", code="BOOKING_NOT_FOUND")
            t.booking_id = booking_id
            self._event(t, actor, "Booking link " + ("set." if booking_id else "removed."))
        audit.record(self.s, actor.profile, "admin.ticket_updated", "support_ticket", t.id, before=before,
                     after={"status": t.status, "priority": t.priority, "assigned_to": t.assigned_to, "booking_id": t.booking_id})  # fmt: skip
        await self.s.commit()
        return await self.get(ticket_id)

    async def counts(self) -> dict[str, int]:
        rows = (
            await self.s.execute(select(SupportTicket.status, func.count()).group_by(SupportTicket.status))
        ).all()
        return {s: int(n) for s, n in rows}


# ====================================================================== categories
def slugify(name: str) -> str:
    base = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:80]


class CategoryAdmin:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    @staticmethod
    def out(c: Category, venues: int = 0, bookings: int = 0) -> dict[str, Any]:
        return {"id": c.id, "slug": c.slug, "name": c.name, "icon_key": c.icon_key, "sort_order": c.sort_order,
                "is_active": c.is_active, "venues": venues, "bookings": bookings, "updated_at": c.updated_at}  # fmt: skip

    async def list_all(self) -> list[dict[str, Any]]:
        v = dict(
            (
                await self.s.execute(
                    select(VenueCategory.category_id, func.count()).group_by(VenueCategory.category_id)
                )
            ).all()
        )
        b = dict(
            (
                await self.s.execute(
                    select(VenueCategory.category_id, func.count(Booking.id))
                    .join(Booking, Booking.venue_id == VenueCategory.venue_id)
                    .group_by(VenueCategory.category_id)
                )
            ).all()
        )
        rows = (await self.s.scalars(select(Category).order_by(Category.sort_order, Category.name))).all()
        return [self.out(c, int(v.get(c.id, 0)), int(b.get(c.id, 0))) for c in rows]

    async def create(
        self, actor: CurrentUser, name: str, slug: str | None, icon_key: str | None, sort_order: int
    ) -> dict[str, Any]:
        slug = slug or slugify(name)
        if not slug:
            raise ValidationFailedError("Give the sport a name with letters or digits.", code="INVALID_NAME")
        c = Category(name=name, slug=slug, icon_key=icon_key, sort_order=sort_order)
        self.s.add(c)
        try:
            await self.s.flush()
        except IntegrityError as exc:
            await self.s.rollback()
            raise ConflictError("A sport with that slug already exists.", code="CATEGORY_SLUG_TAKEN") from exc
        await self.s.refresh(c)
        audit.record(self.s, actor.profile, "admin.category_created", "category", c.id, after=self.out(c))
        await self.s.commit()
        return self.out(c)

    async def update(self, actor: CurrentUser, category_id: UUID, patch: dict[str, Any]) -> dict[str, Any]:
        c = await self.s.scalar(select(Category).where(Category.id == category_id).with_for_update())
        if c is None:
            raise NotFoundError("Sport not found.", code="CATEGORY_NOT_FOUND")
        before = self.out(c)
        for k, v in patch.items():
            setattr(c, k, v)
        await self.s.flush()
        await self.s.refresh(c)
        act = "admin.category_updated"
        if "is_active" in patch and patch["is_active"] != before["is_active"]:
            act = "admin.category_activated" if patch["is_active"] else "admin.category_deactivated"
        n = int(await self.s.scalar(select(func.count()).where(VenueCategory.category_id == c.id)) or 0)
        audit.record(
            self.s, actor.profile, act, "category", c.id, before=before, after=self.out(c), venues_affected=n
        )
        await self.s.commit()
        return self.out(c, n)


# ====================================================================== CMS
class CmsAdmin:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    @staticmethod
    def out(c: CmsContent, body: bool = True) -> dict[str, Any]:
        d = {"id": c.id, "kind": c.kind, "slug": c.slug, "audience": c.audience, "title": c.title,
             "sort_order": c.sort_order, "status": c.status, "published_at": c.published_at,
             "created_at": c.created_at, "updated_at": c.updated_at}  # fmt: skip
        if body:
            d["body"] = c.body
        return d

    @staticmethod
    def _snap(c: CmsContent) -> dict[str, Any]:
        return {"title": c.title, "status": c.status, "audience": c.audience, "sort_order": c.sort_order,
                "body_chars": len(c.body), "body_sha256": hashlib.sha256(c.body.encode()).hexdigest()[:16],
                "body_preview": c.body[:300]}  # fmt: skip

    async def list_all(
        self, kind: str | None, status: str | None, q: str | None, limit: int, offset: int
    ) -> dict[str, Any]:
        stmt = select(CmsContent)
        if kind:
            stmt = stmt.where(CmsContent.kind == kind)
        if status:
            stmt = stmt.where(CmsContent.status == status)
        if q and q.strip():
            stmt = stmt.where(
                or_(CmsContent.title.ilike(f"%{q.strip()}%"), CmsContent.slug.ilike(f"%{q.strip()}%"))
            )
        rows = (
            await self.s.scalars(
                stmt.order_by(CmsContent.kind, CmsContent.sort_order, CmsContent.title)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        return {
            "items": [self.out(c, body=False) for c in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    async def get(self, content_id: UUID) -> dict[str, Any]:
        c = await self.s.get(CmsContent, content_id)
        if c is None:
            raise NotFoundError("Content not found.", code="CONTENT_NOT_FOUND")
        return self.out(c)

    async def create(self, actor: CurrentUser, body: dict[str, Any]) -> dict[str, Any]:
        c = CmsContent(**body, updated_by=actor.id)
        self.s.add(c)
        try:
            await self.s.flush()
        except IntegrityError as exc:
            await self.s.rollback()
            raise ConflictError("Content with that slug already exists.", code="CONTENT_SLUG_TAKEN") from exc
        await self.s.refresh(c)
        audit.record(
            self.s, actor.profile, "admin.cms_created", "cms_content", c.id, after=self._snap(c), slug=c.slug
        )
        await self.s.commit()
        return self.out(c)

    async def update(self, actor: CurrentUser, content_id: UUID, patch: dict[str, Any]) -> dict[str, Any]:
        c = await self.s.scalar(select(CmsContent).where(CmsContent.id == content_id).with_for_update())
        if c is None:
            raise NotFoundError("Content not found.", code="CONTENT_NOT_FOUND")
        before = self._snap(c)
        for k, v in patch.items():
            setattr(c, k, v)
        c.updated_by = actor.id
        await self.s.flush()
        await self.s.refresh(c)
        audit.record(
            self.s,
            actor.profile,
            "admin.cms_updated",
            "cms_content",
            c.id,
            before=before,
            after=self._snap(c),
            slug=c.slug,
        )
        await self.s.commit()
        return self.out(c)

    async def set_published(self, actor: CurrentUser, content_id: UUID, publish: bool) -> dict[str, Any]:
        c = await self.s.scalar(select(CmsContent).where(CmsContent.id == content_id).with_for_update())
        if c is None:
            raise NotFoundError("Content not found.", code="CONTENT_NOT_FOUND")
        target = "published" if publish else "draft"
        if c.status == target:
            return self.out(c)
        before = self._snap(c)
        c.status = target
        c.published_at = datetime.now(UTC) if publish else None
        c.updated_by = actor.id
        await self.s.flush()
        await self.s.refresh(c)
        audit.record(self.s, actor.profile, "admin.cms_published" if publish else "admin.cms_unpublished", "cms_content",
                     c.id, before=before, after=self._snap(c), slug=c.slug)  # fmt: skip
        await self.s.commit()
        return self.out(c)

    # ---- public (what the apps display): published only
    async def public_list(self, kind: str | None, audience: str | None) -> list[dict[str, Any]]:
        stmt = select(CmsContent).where(CmsContent.status == "published")
        if kind:
            stmt = stmt.where(CmsContent.kind == kind)
        if audience:
            stmt = stmt.where(CmsContent.audience.in_(("all", audience)))
        rows = (
            await self.s.scalars(stmt.order_by(CmsContent.kind, CmsContent.sort_order, CmsContent.title))
        ).all()
        return [{"slug": c.slug, "kind": c.kind, "audience": c.audience, "title": c.title, "body": c.body,
                 "updated_at": c.updated_at} for c in rows]  # fmt: skip

    async def public_get(self, slug: str) -> dict[str, Any]:
        c = await self.s.scalar(
            select(CmsContent).where(CmsContent.slug == slug, CmsContent.status == "published")
        )
        if c is None:
            raise NotFoundError("Content not found.", code="CONTENT_NOT_FOUND")
        return {
            "slug": c.slug,
            "kind": c.kind,
            "audience": c.audience,
            "title": c.title,
            "body": c.body,
            "updated_at": c.updated_at,
        }
