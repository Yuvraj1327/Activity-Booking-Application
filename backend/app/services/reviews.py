"""Reviews and owner replies. Rules and their status: see migration 0009 and OPEN_QUESTIONS (Q15, N14)."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.domain import booking_state as st
from app.models import Booking, Profile, Review, ReviewResponse, Venue
from app.schemas.review import (
    OwnerReviewOut,
    OwnerReviewPage,
    RatingSummary,
    ReplyOut,
    ReviewOut,
    ReviewPage,
)
from app.services.bookings import BookingService
from app.services.notifications import NotificationService


def reviewer_name(full_name: str | None) -> str:
    """'Priya Sharma' -> 'Priya S.'  (a customer's full name is never shown to other users)."""
    parts = (full_name or "").split()
    if not parts:
        return "Customer"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0].upper()}."


class ReviewService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.s = session
        self.settings = settings

    # ------------------------------------------------------------------ customer
    async def create(
        self, customer_id: UUID, booking_id: UUID, rating: int, comment: str | None
    ) -> ReviewOut:
        await BookingService(self.s, self.settings).settle_due(customer_id=customer_id)
        booking = await self.s.scalar(
            select(Booking).where(Booking.id == booking_id, Booking.customer_id == customer_id)
        )
        if booking is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        if booking.status != st.COMPLETED:
            raise ConflictError(
                "You can review a booking after it has taken place.", code="BOOKING_NOT_REVIEWABLE"
            )
        review = Review(
            booking_id=booking.id,
            venue_id=booking.venue_id,
            customer_id=customer_id,
            rating=rating,
            comment=comment,
        )
        try:
            async with self.s.begin_nested():
                self.s.add(review)
                await self.s.flush()
        except IntegrityError as exc:
            raise ConflictError("This booking has already been reviewed.", code="REVIEW_EXISTS") from exc
        await self.s.refresh(review)
        venue = await self.s.get(Venue, booking.venue_id)
        if venue is not None:
            await NotificationService(self.s).queue(
                user_id=venue.owner_id,
                type_="review.created",
                title="New review",
                body=f"{rating} star review for {venue.name}",
                dedupe_key=f"review:{review.id}",
                booking_id=booking.id,
            )
        await self.s.commit()
        profile = await self.s.get(Profile, customer_id)
        return ReviewOut(
            id=review.id,
            rating=review.rating,
            comment=review.comment,
            reviewer_name=reviewer_name(profile.full_name if profile else None),
            created_at=review.created_at,
        )

    async def mine(self, customer_id: UUID, booking_id: UUID) -> ReviewOut:
        rows = await self._rows(
            Review.booking_id == booking_id, Review.customer_id == customer_id, limit=1, offset=0
        )
        if not rows:
            raise NotFoundError("No review for this booking.", code="REVIEW_NOT_FOUND")
        return self._out(rows[0])

    # ------------------------------------------------------------------ venue (any signed-in user)
    async def venue_reviews(self, venue_id: UUID, limit: int, offset: int) -> ReviewPage:
        venue = await self.s.scalar(select(Venue).where(Venue.id == venue_id, Venue.status == "published"))
        if venue is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        rows = await self._rows(Review.venue_id == venue_id, limit=limit + 1, offset=offset)
        return ReviewPage(
            items=[self._out(r) for r in rows[:limit]],
            summary=await self._summary(Review.venue_id == venue_id),
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    # ------------------------------------------------------------------ owner
    async def owner_reviews(
        self, owner_id: UUID, rating: int | None, venue_id: UUID | None, limit: int, offset: int
    ) -> OwnerReviewPage:
        scope: list[Any] = [Venue.owner_id == owner_id]
        if venue_id is not None:
            scope.append(Review.venue_id == venue_id)
        summary = await self._summary(*scope)
        if rating is not None:
            scope.append(Review.rating == rating)
        rows = await self._rows(*scope, limit=limit + 1, offset=offset)
        items = [
            OwnerReviewOut(
                **self._out(r).model_dump(),
                venue_id=r.venue_id,
                venue_name=r.venue_name,
                booking_code=r.booking_code,
            )
            for r in rows[:limit]
        ]
        return OwnerReviewPage(
            items=items, summary=summary, limit=limit, offset=offset, has_more=len(rows) > limit
        )

    async def reply(self, owner_id: UUID, review_id: UUID, body: str) -> OwnerReviewOut:
        review = await self.s.scalar(
            select(Review)
            .join(Venue, Venue.id == Review.venue_id)
            .where(Review.id == review_id, Venue.owner_id == owner_id)
        )
        if review is None:  # someone else's review looks exactly like a missing one
            raise NotFoundError("Review not found.", code="REVIEW_NOT_FOUND")
        try:
            async with self.s.begin_nested():
                self.s.add(ReviewResponse(review_id=review.id, owner_id=owner_id, body=body))
                await self.s.flush()
        except IntegrityError as exc:
            raise ConflictError("You have already replied to this review.", code="REPLY_EXISTS") from exc
        venue = await self.s.get(Venue, review.venue_id)
        await NotificationService(self.s).queue(
            user_id=review.customer_id,
            type_="review.reply",
            title="The venue replied to your review",
            body=f"{venue.name if venue else 'The venue'} responded.",
            dedupe_key=f"review-reply:{review.id}",
            booking_id=review.booking_id,
        )
        await self.s.commit()
        rows = await self._rows(Review.id == review_id, Venue.owner_id == owner_id, limit=1, offset=0)
        r = rows[0]
        return OwnerReviewOut(
            **self._out(r).model_dump(),
            venue_id=r.venue_id,
            venue_name=r.venue_name,
            booking_code=r.booking_code,
        )

    # ------------------------------------------------------------------ helpers
    async def _rows(self, *where: Any, limit: int, offset: int) -> list[Any]:
        stmt = (
            select(
                Review.id,
                Review.rating,
                Review.comment,
                Review.created_at,
                Review.venue_id,
                Venue.name.label("venue_name"),
                Booking.booking_code,
                Profile.full_name.label("customer_name"),
                ReviewResponse.body.label("reply_body"),
                ReviewResponse.created_at.label("reply_at"),
            )
            .join(Venue, Venue.id == Review.venue_id)
            .join(Booking, Booking.id == Review.booking_id)
            .join(Profile, Profile.id == Review.customer_id)
            .outerjoin(ReviewResponse, ReviewResponse.review_id == Review.id)
            .where(*where)
            .order_by(Review.created_at.desc(), Review.id)
            .limit(limit)
            .offset(offset)
        )
        return list((await self.s.execute(stmt)).all())

    @staticmethod
    def _out(r: Any) -> ReviewOut:
        return ReviewOut(
            id=r.id,
            rating=r.rating,
            comment=r.comment,
            reviewer_name=reviewer_name(r.customer_name),
            created_at=r.created_at,
            reply=ReplyOut(body=r.reply_body, created_at=r.reply_at) if r.reply_body is not None else None,
        )

    async def _summary(self, *where: Any) -> RatingSummary:
        rows = (
            await self.s.execute(
                select(Review.rating, func.count())
                .join(Venue, Venue.id == Review.venue_id)
                .where(*where)
                .group_by(Review.rating)
            )
        ).all()
        dist = {str(i): 0 for i in range(1, 6)}
        for rating, n in rows:
            dist[str(rating)] = n
        count = sum(dist.values())
        avg = round(sum(int(k) * v for k, v in dist.items()) / count, 1) if count else None
        return RatingSummary(average=avg, count=count, distribution=dist)
