"""Coupons: validation and discount calculation happen here, on the server, never in the app.

A coupon is checked when a price is quoted AND again, under a row lock, when the booking is created,
so two customers cannot both take the last redemption. A redemption counts against the limits only
while its booking stands: an expired hold, or an unpaid booking that was cancelled, frees it again.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.domain import booking_state as bst
from app.domain.finance_math import mul_bps
from app.domain.pricing import MIN_PAYABLE_PAISE
from app.models import Booking, Coupon, CouponRedemption, Profile, Venue, VenueCategory
from app.services import audit


def coupon_out(c: Coupon, redeemed: int | None = None) -> dict[str, Any]:
    return {
        "id": c.id, "code": c.code, "description": c.description, "discount_type": c.discount_type,
        "percent_bps": c.percent_bps, "fixed_paise": c.fixed_paise, "max_discount_paise": c.max_discount_paise,
        "min_booking_paise": c.min_booking_paise, "valid_from": c.valid_from, "valid_until": c.valid_until,
        "usage_limit_total": c.usage_limit_total, "usage_limit_per_user": c.usage_limit_per_user,
        "first_booking_only": c.first_booking_only, "eligible_category_ids": c.eligible_category_ids,
        "eligible_city_ids": c.eligible_city_ids, "eligible_venue_ids": c.eligible_venue_ids,
        "is_active": c.is_active, "created_at": c.created_at, "updated_at": c.updated_at, "redeemed": redeemed,
    }  # fmt: skip


def _standing() -> ColumnElement[bool]:
    """Bookings whose redemption still counts."""
    unpaid = ("unpaid", "pending", "failed")
    cancelled = (bst.CANCELLED_CUSTOMER, bst.CANCELLED_OWNER, bst.CANCELLED_ADMIN)
    return ~(
        (Booking.status == bst.EXPIRED) | (Booking.status.in_(cancelled) & Booking.payment_status.in_(unpaid))
    )


class CouponService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    # ================================================================== customer-facing evaluation
    async def evaluate(
        self,
        customer_id: UUID,
        code: str,
        venue: Venue,
        base_amount_paise: int,
        fees_and_tax_paise: int,
        *,
        lock: bool,
    ) -> tuple[Coupon, int]:
        """Returns (coupon, discount_paise) or raises a specific validation error."""
        code = code.strip().upper()
        stmt = select(Coupon).where(Coupon.code == code)
        c = await self.s.scalar(stmt.with_for_update() if lock else stmt)
        if c is None:
            raise ValidationFailedError("That coupon code is not valid.", code="COUPON_NOT_FOUND")
        now = datetime.now(UTC)
        if not c.is_active:
            raise ValidationFailedError("This coupon is no longer active.", code="COUPON_INACTIVE")
        if c.valid_from and now < c.valid_from:
            raise ValidationFailedError("This coupon is not valid yet.", code="COUPON_NOT_STARTED")
        if c.valid_until and now >= c.valid_until:
            raise ValidationFailedError("This coupon has expired.", code="COUPON_EXPIRED")
        if base_amount_paise < c.min_booking_paise:
            raise ValidationFailedError(
                f"This coupon needs a booking of at least {c.min_booking_paise / 100:.2f}.",
                code="COUPON_MIN_AMOUNT",
            )
        if c.eligible_venue_ids and venue.id not in c.eligible_venue_ids:
            raise ValidationFailedError(
                "This coupon does not apply to this venue.", code="COUPON_NOT_ELIGIBLE"
            )
        if c.eligible_city_ids and venue.city_id not in c.eligible_city_ids:
            raise ValidationFailedError(
                "This coupon does not apply in this city.", code="COUPON_NOT_ELIGIBLE"
            )
        if c.eligible_category_ids:
            hit = await self.s.scalar(
                select(func.count()).where(
                    VenueCategory.venue_id == venue.id, VenueCategory.category_id.in_(c.eligible_category_ids)
                )
            )
            if not hit:
                raise ValidationFailedError(
                    "This coupon does not apply to this sport.", code="COUPON_NOT_ELIGIBLE"
                )
        used_total, used_by_user = (
            await self.s.execute(
                select(
                    func.count(CouponRedemption.id),
                    func.count(CouponRedemption.id).filter(CouponRedemption.customer_id == customer_id),
                )
                .join(Booking, Booking.id == CouponRedemption.booking_id)
                .where(CouponRedemption.coupon_id == c.id, _standing())
            )
        ).one()
        if c.usage_limit_total is not None and used_total >= c.usage_limit_total:
            raise ValidationFailedError("This coupon has been fully redeemed.", code="COUPON_EXHAUSTED")
        if c.usage_limit_per_user is not None and used_by_user >= c.usage_limit_per_user:
            raise ValidationFailedError(
                "You have already used this coupon the maximum number of times.", code="COUPON_USER_LIMIT"
            )
        if c.first_booking_only:
            prior = await self.s.scalar(
                select(func.count()).where(
                    Booking.customer_id == customer_id,
                    Booking.payment_status.in_(("paid", "partially_refunded", "refunded")),
                )
            )
            if prior:
                raise ValidationFailedError(
                    "This coupon is only for a first booking.", code="COUPON_FIRST_ONLY"
                )
        raw = (
            mul_bps(base_amount_paise, c.percent_bps or 0)
            if c.discount_type == "percent"
            else int(c.fixed_paise or 0)
        )
        if c.max_discount_paise is not None:
            raw = min(raw, c.max_discount_paise)
        # Never discount a booking below the gateway's minimum payable amount.
        discount = min(raw, base_amount_paise + fees_and_tax_paise - MIN_PAYABLE_PAISE)
        if discount <= 0:
            raise ValidationFailedError(
                "This coupon cannot be applied to this booking.", code="COUPON_NOT_APPLICABLE"
            )
        return c, discount

    def redeem(self, coupon: Coupon, booking: Booking, discount: int) -> None:
        self.s.add(
            CouponRedemption(
                coupon_id=coupon.id,
                booking_id=booking.id,
                customer_id=booking.customer_id,
                discount_paise=discount,
            )
        )

    # ================================================================== admin
    async def _counts(self, ids: list[UUID]) -> dict[UUID, int]:
        if not ids:
            return {}
        rows = (
            await self.s.execute(
                select(CouponRedemption.coupon_id, func.count())
                .join(Booking, Booking.id == CouponRedemption.booking_id)
                .where(CouponRedemption.coupon_id.in_(ids), _standing())
                .group_by(CouponRedemption.coupon_id)
            )
        ).all()
        return {i: int(n) for i, n in rows}

    async def list_all(self, active: bool | None, q: str | None, limit: int, offset: int) -> dict[str, Any]:
        stmt = select(Coupon)
        if active is not None:
            stmt = stmt.where(Coupon.is_active == active)
        if q and q.strip():
            stmt = stmt.where(Coupon.code.ilike(f"%{q.strip().upper()}%"))
        rows = (
            await self.s.scalars(
                stmt.order_by(Coupon.created_at.desc(), Coupon.id).limit(limit + 1).offset(offset)
            )
        ).all()
        counts = await self._counts([c.id for c in rows[:limit]])
        return {
            "items": [coupon_out(c, counts.get(c.id, 0)) for c in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    async def get(self, coupon_id: UUID) -> dict[str, Any]:
        c = await self.s.get(Coupon, coupon_id)
        if c is None:
            raise NotFoundError("Coupon not found.", code="COUPON_NOT_FOUND")
        return coupon_out(c, (await self._counts([c.id])).get(c.id, 0))

    async def create(self, actor: CurrentUser, body: dict[str, Any]) -> dict[str, Any]:
        c = Coupon(**body, created_by=actor.id)
        self.s.add(c)
        try:
            await self.s.flush()
        except IntegrityError as exc:
            await self.s.rollback()
            raise ConflictError("A coupon with that code exists.", code="COUPON_CODE_TAKEN") from exc
        await self.s.refresh(c)
        audit.record(self.s, actor.profile, "admin.coupon_created", "coupon", c.id, after=coupon_out(c))
        await self.s.commit()
        return coupon_out(c, 0)

    async def update(self, actor: CurrentUser, coupon_id: UUID, patch: dict[str, Any]) -> dict[str, Any]:
        c = await self.s.scalar(select(Coupon).where(Coupon.id == coupon_id).with_for_update())
        if c is None:
            raise NotFoundError("Coupon not found.", code="COUPON_NOT_FOUND")
        before = coupon_out(c)
        for k, v in patch.items():
            setattr(c, k, v)
        if c.valid_from and c.valid_until and c.valid_from >= c.valid_until:
            await self.s.rollback()
            raise ValidationFailedError("valid_from must be before valid_until.", code="INVALID_RANGE")
        try:
            await self.s.flush()
        except IntegrityError as exc:
            await self.s.rollback()
            raise ValidationFailedError("Those values are not allowed.", code="INVALID_COUPON") from exc
        await self.s.refresh(c)
        action = (
            "admin.coupon_activated"
            if patch.get("is_active") is True and not before["is_active"]
            else (
                "admin.coupon_deactivated"
                if patch.get("is_active") is False and before["is_active"]
                else "admin.coupon_updated"
            )
        )
        audit.record(self.s, actor.profile, action, "coupon", c.id, before=before, after=coupon_out(c))
        await self.s.commit()
        return coupon_out(c, (await self._counts([c.id])).get(c.id, 0))

    async def redemptions(self, coupon_id: UUID, limit: int, offset: int) -> dict[str, Any]:
        if await self.s.get(Coupon, coupon_id) is None:
            raise NotFoundError("Coupon not found.", code="COUPON_NOT_FOUND")
        rows = (
            await self.s.execute(
                select(
                    CouponRedemption,
                    Booking.booking_code,
                    Booking.status,
                    Booking.payment_status,
                    Profile.full_name,
                )
                .join(Booking, Booking.id == CouponRedemption.booking_id)
                .join(Profile, Profile.id == CouponRedemption.customer_id)
                .where(CouponRedemption.coupon_id == coupon_id)
                .order_by(CouponRedemption.created_at.desc(), CouponRedemption.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        return {
            "items": [
                {"id": r.id, "booking_id": r.booking_id, "booking_code": code, "booking_status": bs,
                 "payment_status": ps, "customer_id": r.customer_id, "customer_name": name,
                 "discount_paise": r.discount_paise, "created_at": r.created_at}
                for r, code, bs, ps, name in rows[:limit]
            ],
            "limit": limit, "offset": offset, "has_more": len(rows) > limit,
        }  # fmt: skip
