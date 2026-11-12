"""Owner dashboard, notifications and the honest 'not available yet' business endpoints."""

from datetime import date
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.models import Notification, Venue, VenueImage
from app.schemas.owner import (
    AnalyticsOut,
    BookingOverview,
    DashboardOut,
    DashboardVenue,
    NotificationOut,
    NotificationPage,
    Unavailable,
)
from app.services.bookings import BookingService
from app.services.venues import public_image_url

STEP_6 = "Step 6 (availability and booking engine)"
STEP_7 = "Step 7 (payments)"
STEP_REVIEWS = "Reviews feature (no reviews table yet)"

_GROUP_PREFIXES: dict[str, tuple[str, ...]] = {
    "bookings": ("booking.",),
    "payments": ("payment.", "payout."),
    "reviews": ("review.",),
}


def unavailable(depends_on: str, what: str) -> Unavailable:
    return Unavailable(depends_on=depends_on, message=f"{what} will appear once {depends_on} is built.")


def notification_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        type=n.type,
        title=n.title,
        body=n.body,
        data=n.data,
        is_read=n.read_at is not None,
        created_at=n.created_at,
        booking_id=n.booking_id,
        payment_id=n.payment_id,
    )


class OwnerBusinessService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.s = session
        self.settings = settings

    async def _performance(self, owner_id: UUID) -> list[DashboardVenue]:
        cover = (
            select(VenueImage.storage_path)
            .where(VenueImage.venue_id == Venue.id, VenueImage.status == "active")
            .order_by(VenueImage.is_cover.desc(), VenueImage.sort_order)
            .limit(1)
            .correlate(Venue)
            .scalar_subquery()
        )
        rows = await self.s.execute(
            select(Venue, cover.label("cover"))
            .where(Venue.owner_id == owner_id)
            .order_by(Venue.rating_count.desc(), Venue.name)
        )
        return [
            DashboardVenue(
                venue_id=v.id,
                name=v.name,
                status=v.status,
                rating_avg=float(v.rating_avg) if v.rating_avg is not None else None,
                rating_count=v.rating_count,
                cover_image_url=public_image_url(self.settings, path),
                starting_price_paise=v.starting_price_paise,
                currency=v.currency,
            )
            for v, path in rows.all()
        ]

    async def dashboard(self, owner_id: UUID) -> DashboardOut:
        performance = await self._performance(owner_id)
        counts = {"published": 0, "draft": 0, "archived": 0}
        for v in performance:
            counts[v.status] += 1
        rated = [v for v in performance if v.rating_avg is not None and v.rating_count > 0]
        total_ratings = sum(v.rating_count for v in rated)
        average = (
            round(
                sum(v.rating_avg * v.rating_count for v in rated if v.rating_avg is not None) / total_ratings,
                1,
            )
            if total_ratings
            else None
        )
        recent = (
            await self.s.scalars(
                select(Notification)
                .where(Notification.user_id == owner_id)
                .order_by(Notification.created_at.desc())
                .limit(10)
            )
        ).all()
        counts_b = await BookingService(self.s, self.settings).owner_counts(owner_id)
        return DashboardOut(
            venues_total=len(performance),
            venues_published=counts["published"],
            venues_draft=counts["draft"],
            venues_archived=counts["archived"],
            average_rating=average,
            ratings_count=total_ratings,
            venue_performance=performance,
            recent_activity=[notification_out(n) for n in recent],
            total_bookings=counts_b["total"],
            booking_overview=BookingOverview(
                upcoming=counts_b["upcoming"],
                completed=counts_b["completed"],
                cancelled=counts_b["cancelled"],
            ),
            total_revenue=unavailable(STEP_7, "Revenue"),
            monthly_revenue=unavailable(STEP_7, "Monthly revenue"),
            average_utilization=unavailable(STEP_6, "Utilization"),
        )

    async def analytics(self, owner_id: UUID, date_from: date, date_to: date) -> AnalyticsOut:
        return AnalyticsOut(
            date_from=date_from,
            date_to=date_to,
            venue_performance=await self._performance(owner_id),
            total_bookings=unavailable(STEP_6, "Booking totals"),
            revenue=unavailable(STEP_7, "Revenue"),
            utilization=unavailable(STEP_6, "Utilization"),
            booking_trends=unavailable(STEP_6, "Booking trends"),
            popular_time_slots=unavailable(STEP_6, "Popular time slots"),
        )

    # ------------------------------------------------------------------ notifications
    async def notifications(
        self, owner_id: UUID, group: str, unread_only: bool, limit: int, offset: int
    ) -> NotificationPage:
        stmt = select(Notification).where(Notification.user_id == owner_id)
        if group in _GROUP_PREFIXES:
            from sqlalchemy import or_

            stmt = stmt.where(or_(*[Notification.type.like(f"{p}%") for p in _GROUP_PREFIXES[group]]))
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        rows = list(
            (
                await self.s.scalars(
                    stmt.order_by(Notification.created_at.desc(), Notification.id)
                    .limit(limit + 1)
                    .offset(offset)
                )
            ).all()
        )
        unread = (
            await self.s.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == owner_id, Notification.read_at.is_(None))
            )
        ).scalar_one()
        return NotificationPage(
            items=[notification_out(n) for n in rows[:limit]],
            unread_count=int(unread),
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    async def mark_read(self, owner_id: UUID, notification_id: UUID) -> None:
        found = (
            await self.s.execute(
                select(Notification.id).where(
                    Notification.id == notification_id, Notification.user_id == owner_id
                )
            )
        ).first()
        if found is None:
            raise NotFoundError("Notification not found.", code="NOTIFICATION_NOT_FOUND")
        await self.s.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == owner_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=func.now())
        )
        await self.s.commit()

    async def mark_all_read(self, owner_id: UUID) -> None:
        await self.s.execute(
            update(Notification)
            .where(Notification.user_id == owner_id, Notification.read_at.is_(None))
            .values(read_at=func.now())
        )
        await self.s.commit()
