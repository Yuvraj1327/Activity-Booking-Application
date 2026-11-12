"""Step 8: admin console reads, aggregation, account status changes and CSV exports.

Rules this module keeps:
* Read-only except `change_status` (suspend / reactivate), which is audited and refuses admins.
* Aggregation happens in SQL (GROUP BY / date_trunc); nothing here loads whole tables.
* Money figures that need an unapproved business rule are `Unavailable`, never computed.
* Exports contain no e-mail, phone or address and neutralise spreadsheet formulas.
"""

import csv
import io
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Date, String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.logging import request_id_ctx
from app.domain import booking_state as st
from app.domain import payment_state as pst
from app.models import (
    AuditLog,
    Booking,
    Category,
    City,
    OwnerProfile,
    Payment,
    Profile,
    Venue,
    VenueCategory,
    VenueResource,
)
from app.schemas.admin import (
    ActivityItem,
    AdminBookingDetailOut,
    AdminBookingRow,
    AdminBookingRowPage,
    AuditPage,
    AuditRow,
    BookingAnalytics,
    BookingBrief,
    BookingBucket,
    CategoryShare,
    CustomerDetail,
    CustomerPage,
    CustomerRow,
    DashboardOut,
    DashboardPeriod,
    DashboardTotals,
    DateRange,
    Granularity,
    MoneyBreakdown,
    OwnerDetail,
    OwnerPage,
    OwnerRow,
    PaymentBucket,
    PlatformAnalytics,
    RegistrationBucket,
    RegistrationRow,
    RevenueAnalytics,
    StatusChangeOut,
    StatusShare,
    TopVenue,
    VenueBrief,
    VenueDetail,
    VenuePage,
    VenueRow,
)
from app.schemas.owner import Unavailable
from app.schemas.payment import AdminPaymentOut
from app.services.notifications import NotificationService
from app.services.payments import PaymentService
from app.utils.search import like_pattern

MAX_RANGE_DAYS = 366
CONFIRMED_SET = (st.CONFIRMED, st.COMPLETED)
PENDING_SET = (st.PENDING,)
CANCELLED_SET = tuple(sorted(st.CANCELLED))
PAID_SET = tuple(sorted(pst.PAID))
OPEN_SET = (pst.CREATED, pst.PENDING, pst.AUTHORIZED)

SortOrder = Literal["asc", "desc"]


def _unavailable(what: str, depends_on: str) -> Unavailable:
    return Unavailable(
        depends_on=depends_on,
        message=f"{what} is not available: the rule is not approved yet. No figure is estimated.",
    )


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return "•" * max(len(phone) - 4, 0) + phone[-4:]


def csv_safe(value: object) -> str:
    """Neutralise spreadsheet formula injection ( =, +, -, @, tab, CR at the start of a cell)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


class AdminService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.s = session
        self.settings = settings
        try:
            self.tz = ZoneInfo(settings.admin_report_timezone)
        except Exception as exc:  # misconfiguration: fail loudly at first use
            raise ValidationFailedError("Invalid report time zone.", code="INVALID_TIMEZONE") from exc

    # ================================================================== helpers
    def resolve_range(self, date_from: date | None, date_to: date | None) -> tuple[date, date]:
        today = datetime.now(self.tz).date()
        end = date_to or today
        start = date_from or (end - timedelta(days=29))
        if start > end:
            raise ValidationFailedError("date_from must not be after date_to.", code="INVALID_RANGE")
        if (end - start).days + 1 > MAX_RANGE_DAYS:
            raise ValidationFailedError(
                f"The date range may cover at most {MAX_RANGE_DAYS} days.", code="RANGE_TOO_LARGE"
            )
        return start, end

    def _bounds(self, start: date, end: date) -> tuple[datetime, datetime]:
        lo = datetime.combine(start, datetime.min.time(), tzinfo=self.tz).astimezone(UTC)
        hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=self.tz).astimezone(UTC)
        return lo, hi

    def _range_out(self, start: date, end: date) -> DateRange:
        return DateRange(date_from=start, date_to=end, timezone=self.settings.admin_report_timezone)

    def _bucket(self, column: Any, granularity: Granularity) -> ColumnElement[date]:
        local = func.timezone(self.settings.admin_report_timezone, column)
        return cast(func.date_trunc(granularity, local), Date)

    @staticmethod
    def _bucket_start(day: date, granularity: Granularity) -> date:
        if granularity == "week":
            return day - timedelta(days=day.weekday())
        if granularity == "month":
            return day.replace(day=1)
        return day

    def _bucket_days(self, start: date, end: date, granularity: Granularity) -> list[date]:
        out: list[date] = []
        cur = self._bucket_start(start, granularity)
        while cur <= end:
            out.append(cur)
            if granularity == "day":
                cur += timedelta(days=1)
            elif granularity == "week":
                cur += timedelta(days=7)
            else:
                cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        return out

    async def _audit(
        self, actor: Profile, action: str, entity_type: str | None, entity_id: str | None, **meta: object
    ) -> None:
        self.s.add(
            AuditLog(
                actor_id=actor.id,
                actor_role=actor.role,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata_=dict(meta),
                request_id=request_id_ctx.get(),
            )
        )

    # ================================================================== analytics
    async def booking_analytics(
        self, date_from: date | None, date_to: date | None, granularity: Granularity
    ) -> BookingAnalytics:
        start, end = self.resolve_range(date_from, date_to)
        series = await self._booking_series(start, end, granularity)
        dist = await self._status_distribution(start, end)
        return BookingAnalytics(
            range=self._range_out(start, end),
            granularity=granularity,
            total=sum(b.total for b in series),
            series=series,
            status_distribution=dist,
        )

    async def _booking_series(self, start: date, end: date, granularity: Granularity) -> list[BookingBucket]:
        lo, hi = self._bounds(start, end)
        bucket = self._bucket(Booking.created_at, granularity).label("b")
        rows = (
            await self.s.execute(
                select(
                    bucket,
                    func.count(Booking.id),
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(PENDING_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                )
                .where(Booking.created_at >= lo, Booking.created_at < hi)
                .group_by(bucket)
            )
        ).all()
        by = {r[0]: r for r in rows}
        out: list[BookingBucket] = []
        for day in self._bucket_days(start, end, granularity):
            r = by.get(day)
            total, conf, pend, canc = (int(r[1]), int(r[2]), int(r[3]), int(r[4])) if r else (0, 0, 0, 0)
            out.append(
                BookingBucket(
                    bucket=day,
                    total=total,
                    confirmed=conf,
                    pending=pend,
                    cancelled=canc,
                    other=total - conf - pend - canc,
                )
            )
        return out

    async def _status_distribution(self, start: date, end: date) -> list[StatusShare]:
        lo, hi = self._bounds(start, end)
        rows = (
            await self.s.execute(
                select(Booking.status, func.count(Booking.id))
                .where(Booking.created_at >= lo, Booking.created_at < hi)
                .group_by(Booking.status)
                .order_by(func.count(Booking.id).desc(), Booking.status)
            )
        ).all()
        return [StatusShare(status=s, count=int(c)) for s, c in rows]

    async def _money(self, start: date, end: date) -> MoneyBreakdown:
        lo, hi = self._bounds(start, end)
        gross = (
            await self.s.execute(
                select(func.coalesce(func.sum(Booking.total_amount_paise), 0)).where(
                    Booking.created_at >= lo, Booking.created_at < hi, Booking.status.in_(CONFIRMED_SET)
                )
            )
        ).scalar_one()
        paid = (
            await self.s.execute(
                select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
                    Payment.created_at >= lo, Payment.created_at < hi, Payment.status.in_(PAID_SET)
                )
            )
        ).scalar_one()
        return MoneyBreakdown(
            gross_booking_value_paise=int(gross),
            successful_payment_paise=int(paid),
            platform_revenue=_unavailable("Platform revenue", "Q7, Q8 (fees and commission)"),
            owner_earnings=_unavailable("Owner earnings", "Q7, Q8, Q10 (fees, commission, payouts)"),
            refunds=_unavailable("Refund totals", "Q9 (cancellation and refund policy)"),
        )

    async def _payment_series(self, start: date, end: date, granularity: Granularity) -> list[PaymentBucket]:
        lo, hi = self._bounds(start, end)
        bucket = self._bucket(Payment.created_at, granularity).label("b")
        rows = (
            await self.s.execute(
                select(
                    bucket,
                    func.count(Payment.id).filter(Payment.status.in_(PAID_SET)),
                    func.coalesce(func.sum(Payment.amount_paise).filter(Payment.status.in_(PAID_SET)), 0),
                    func.count(Payment.id).filter(Payment.status == pst.FAILED),
                    func.count(Payment.id).filter(Payment.status.in_(OPEN_SET)),
                )
                .where(Payment.created_at >= lo, Payment.created_at < hi)
                .group_by(bucket)
            )
        ).all()
        by = {r[0]: r for r in rows}
        out: list[PaymentBucket] = []
        for day in self._bucket_days(start, end, granularity):
            r = by.get(day)
            out.append(
                PaymentBucket(
                    bucket=day,
                    captured_count=int(r[1]) if r else 0,
                    captured_paise=int(r[2]) if r else 0,
                    failed_count=int(r[3]) if r else 0,
                    open_count=int(r[4]) if r else 0,
                )
            )
        return out

    async def revenue_analytics(
        self, date_from: date | None, date_to: date | None, granularity: Granularity
    ) -> RevenueAnalytics:
        start, end = self.resolve_range(date_from, date_to)
        series = await self._payment_series(start, end, granularity)
        captured = sum(p.captured_count for p in series)
        failed = sum(p.failed_count for p in series)
        open_ = sum(p.open_count for p in series)
        decided = captured + failed
        return RevenueAnalytics(
            range=self._range_out(start, end),
            granularity=granularity,
            transactions_total=captured + failed + open_,
            captured_count=captured,
            failed_count=failed,
            open_count=open_,
            # Share of decided attempts that were paid. None when nothing was decided.
            success_rate_percent=round(captured * 100 / decided, 1) if decided else None,
            money=await self._money(start, end),
            series=series,
        )

    async def _top_venues(self, start: date, end: date, limit: int = 5) -> list[TopVenue]:
        lo, hi = self._bounds(start, end)
        rows = (
            await self.s.execute(
                select(
                    Venue.id,
                    Venue.name,
                    func.count(Booking.id),
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_SET)),
                )
                .join(Booking, Booking.venue_id == Venue.id)
                .where(Booking.created_at >= lo, Booking.created_at < hi)
                .group_by(Venue.id, Venue.name)
                .order_by(func.count(Booking.id).desc(), Venue.name)
                .limit(limit)
            )
        ).all()
        return [TopVenue(venue_id=i, name=n, bookings=int(b), confirmed=int(c)) for i, n, b, c in rows]

    async def platform_analytics(
        self, date_from: date | None, date_to: date | None, granularity: Granularity
    ) -> PlatformAnalytics:
        start, end = self.resolve_range(date_from, date_to)
        lo, hi = self._bounds(start, end)
        pb = self._bucket(Profile.created_at, granularity).label("b")
        prof = {
            (b, role): int(n)
            for b, role, n in (
                await self.s.execute(
                    select(pb, Profile.role, func.count(Profile.id))
                    .where(Profile.created_at >= lo, Profile.created_at < hi, Profile.role != "admin")
                    .group_by(pb, Profile.role)
                )
            ).all()
        }
        vb = self._bucket(Venue.created_at, granularity).label("b")
        ven = {
            b: int(n)
            for b, n in (
                await self.s.execute(
                    select(vb, func.count(Venue.id))
                    .where(Venue.created_at >= lo, Venue.created_at < hi)
                    .group_by(vb)
                )
            ).all()
        }
        series = [
            RegistrationBucket(
                bucket=d,
                customers=prof.get((d, "customer"), 0),
                owners=prof.get((d, "owner"), 0),
                venues_created=ven.get(d, 0),
            )
            for d in self._bucket_days(start, end, granularity)
        ]
        cats = (
            await self.s.execute(
                select(Category.name, func.count(Booking.id))
                .select_from(Booking)
                .join(VenueCategory, VenueCategory.venue_id == Booking.venue_id)
                .join(Category, Category.id == VenueCategory.category_id)
                .where(Booking.created_at >= lo, Booking.created_at < hi)
                .group_by(Category.name)
                .order_by(func.count(Booking.id).desc(), Category.name)
                .limit(10)
            )
        ).all()
        return PlatformAnalytics(
            range=self._range_out(start, end),
            granularity=granularity,
            new_customers=sum(s.customers for s in series),
            new_owners=sum(s.owners for s in series),
            new_venues=sum(s.venues_created for s in series),
            series=series,
            popular_categories=[CategoryShare(category=n, bookings=int(c)) for n, c in cats],
            top_venues=await self._top_venues(start, end, 10),
        )

    # ================================================================== dashboard
    async def dashboard(self, date_from: date | None, date_to: date | None) -> DashboardOut:
        start, end = self.resolve_range(date_from, date_to)
        lo, hi = self._bounds(start, end)
        granularity: Granularity = "day" if (end - start).days < 92 else "week"

        def count(model: Any, *where: Any) -> Any:
            return select(func.count(model.id)).where(*where).scalar_subquery()

        t = (
            await self.s.execute(
                select(
                    count(Profile, Profile.role == "customer"),
                    count(Profile, Profile.role == "owner"),
                    count(Venue),
                    count(Venue, Venue.status == "published"),
                    count(Booking),
                    count(Payment),
                )
            )
        ).one()
        in_range = and_(Booking.created_at >= lo, Booking.created_at < hi)
        p = (
            await self.s.execute(
                select(
                    func.count(Booking.id),
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(PENDING_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                ).where(in_range)
            )
        ).one()
        tx = (
            await self.s.execute(
                select(func.count(Payment.id)).where(Payment.created_at >= lo, Payment.created_at < hi)
            )
        ).scalar_one()
        regs = dict(
            (
                await self.s.execute(
                    select(Profile.role, func.count(Profile.id))
                    .where(Profile.created_at >= lo, Profile.created_at < hi)
                    .group_by(Profile.role)
                )
            ).all()
        )
        recent_b = await self._recent_bookings(5)
        recent_r = (
            await self.s.execute(
                select(Profile.id, Profile.full_name, Profile.role, Profile.created_at)
                .where(Profile.role != "admin")
                .order_by(Profile.created_at.desc(), Profile.id)
                .limit(5)
            )
        ).all()
        return DashboardOut(
            range=self._range_out(start, end),
            totals=DashboardTotals(
                customers=int(t[0]),
                owners=int(t[1]),
                venues=int(t[2]),
                published_venues=int(t[3]),
                bookings=int(t[4]),
                payments=int(t[5]),
            ),
            period=DashboardPeriod(
                bookings=int(p[0]),
                confirmed=int(p[1]),
                pending=int(p[2]),
                cancelled=int(p[3]),
                transactions=int(tx),
                money=await self._money(start, end),
                new_customers=int(regs.get("customer", 0)),
                new_owners=int(regs.get("owner", 0)),
            ),
            booking_trend=await self._booking_series(start, end, granularity),
            revenue_trend=await self._payment_series(start, end, granularity),
            recent_bookings=recent_b,
            recent_registrations=[
                RegistrationRow(id=i, full_name=n, role=r, created_at=c) for i, n, r, c in recent_r
            ],
            popular_venues=await self._top_venues(start, end, 5),
            activity=await self._activity(10),
        )

    async def _recent_bookings(self, limit: int) -> list[BookingBrief]:
        rows = (
            await self.s.execute(
                select(Booking, Profile.full_name)
                .join(Profile, Profile.id == Booking.customer_id)
                .order_by(Booking.created_at.desc(), Booking.id)
                .limit(limit)
            )
        ).all()
        return [self._brief(b, n) for b, n in rows]

    @staticmethod
    def _brief(b: Booking, customer_name: str) -> BookingBrief:
        return BookingBrief(
            id=b.id,
            booking_code=b.booking_code,
            venue_name=b.venue_name,
            customer_name=customer_name,
            booking_date=b.booking_date,
            status=b.status,
            payment_status=b.payment_status,
            total_amount_paise=b.total_amount_paise,
            currency=b.currency,
            created_at=b.created_at,
        )

    async def activity(self, limit: int) -> list[ActivityItem]:
        return await self._activity(limit)

    async def _activity(self, limit: int) -> list[ActivityItem]:
        """Latest platform events from tables that already record them (no extra event store)."""
        from app.models import BookingStatusHistory

        items: list[ActivityItem] = []
        bs = (
            await self.s.execute(
                select(BookingStatusHistory, Booking.booking_code, Booking.venue_name)
                .join(Booking, Booking.id == BookingStatusHistory.booking_id)
                .order_by(BookingStatusHistory.created_at.desc())
                .limit(limit)
            )
        ).all()
        for h, code, venue in bs:
            items.append(
                ActivityItem(
                    kind="booking",
                    title=f"Booking {code} is now {h.to_status.replace('_', ' ')}",
                    detail=venue,
                    created_at=h.created_at,
                    entity_id=str(h.booking_id),
                )
            )
        aud = (
            await self.s.scalars(
                select(AuditLog)
                .where(AuditLog.action.in_(("profile.registered", "admin.account_status_changed")))
                .order_by(AuditLog.created_at.desc())
                .limit(limit)
            )
        ).all()
        for a in aud:
            if a.action == "profile.registered":
                title = f"New {a.metadata_.get('role', 'user')} registered"
                detail = None
            else:
                title = f"Account {a.metadata_.get('to', 'status')} by admin"
                detail = str(a.metadata_.get("target_role") or "")
            items.append(
                ActivityItem(
                    kind="account", title=title, detail=detail, created_at=a.created_at, entity_id=a.entity_id
                )
            )
        pays = (
            await self.s.execute(
                select(Payment, Booking.booking_code)
                .join(Booking, Booking.id == Payment.booking_id)
                .where(Payment.status.in_((pst.CAPTURED, pst.FAILED)))
                .order_by(Payment.updated_at.desc())
                .limit(limit)
            )
        ).all()
        for pay, code in pays:
            items.append(
                ActivityItem(
                    kind="payment",
                    title=f"Payment {pay.status} for {code}",
                    detail=None,
                    created_at=pay.updated_at,
                    entity_id=str(pay.id),
                )
            )
        items.sort(key=lambda i: i.created_at, reverse=True)
        return items[:limit]

    # ================================================================== owners / customers
    @staticmethod
    def _order(column_map: dict[str, Any], sort: str, order: SortOrder, tie: Any) -> list[Any]:
        col = column_map.get(sort, column_map["created_at"])
        return [col.asc() if order == "asc" else col.desc(), tie]

    async def list_owners(
        self, q: str | None, status: str | None, sort: str, order: SortOrder, limit: int, offset: int
    ) -> OwnerPage:
        venues = (
            select(func.count(Venue.id))
            .where(Venue.owner_id == Profile.id)
            .correlate(Profile)
            .scalar_subquery()
        )
        published = (
            select(func.count(Venue.id))
            .where(Venue.owner_id == Profile.id, Venue.status == "published")
            .correlate(Profile)
            .scalar_subquery()
        )
        bookings = (
            select(func.count(Booking.id))
            .join(Venue, Venue.id == Booking.venue_id)
            .where(Venue.owner_id == Profile.id)
            .correlate(Profile)
            .scalar_subquery()
        )
        stmt = (
            select(Profile, OwnerProfile.business_name, venues, published, bookings)
            .join(OwnerProfile, OwnerProfile.user_id == Profile.id)
            .where(Profile.role == "owner")
        )
        if status:
            stmt = stmt.where(Profile.status == status)
        if q and q.strip():
            pat = like_pattern(q)
            stmt = stmt.where(
                or_(
                    Profile.full_name.ilike(pat, escape="\\"),
                    Profile.email.ilike(pat, escape="\\"),
                    OwnerProfile.business_name.ilike(pat, escape="\\"),
                )
            )
        cols = {
            "created_at": Profile.created_at,
            "name": Profile.full_name,
            "venues": venues,
            "bookings": bookings,
        }
        rows = (
            await self.s.execute(
                stmt.order_by(*self._order(cols, sort, order, Profile.id)).limit(limit + 1).offset(offset)
            )
        ).all()
        items = [
            OwnerRow(
                id=p.id,
                full_name=p.full_name,
                email=p.email,
                phone_masked=mask_phone(p.phone),
                business_name=bn,
                status=p.status,
                created_at=p.created_at,
                venues_count=int(v),
                published_venues_count=int(pub),
                bookings_count=int(b),
            )
            for p, bn, v, pub, b in rows[:limit]
        ]
        return OwnerPage(items=items, limit=limit, offset=offset, has_more=len(rows) > limit)

    async def get_owner(self, owner_id: UUID) -> OwnerDetail:
        row = (
            await self.s.execute(
                select(Profile, OwnerProfile)
                .join(OwnerProfile, OwnerProfile.user_id == Profile.id)
                .where(Profile.id == owner_id, Profile.role == "owner")
            )
        ).first()
        if row is None:
            raise NotFoundError("Owner not found.", code="OWNER_NOT_FOUND")
        prof, own = row
        venues = await self._venue_briefs(owner_id)
        agg = (
            await self.s.execute(
                select(
                    func.count(Booking.id),
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_SET)),
                )
                .join(Venue, Venue.id == Booking.venue_id)
                .where(Venue.owner_id == owner_id)
            )
        ).one()
        gross = (
            await self.s.execute(
                select(func.coalesce(func.sum(Payment.amount_paise), 0))
                .join(Venue, Venue.id == Payment.venue_id)
                .where(Venue.owner_id == owner_id, Payment.status.in_(PAID_SET))
            )
        ).scalar_one()
        recent = (
            await self.s.execute(
                select(Booking, Profile.full_name)
                .join(Profile, Profile.id == Booking.customer_id)
                .join(Venue, Venue.id == Booking.venue_id)
                .where(Venue.owner_id == owner_id)
                .order_by(Booking.created_at.desc(), Booking.id)
                .limit(10)
            )
        ).all()
        return OwnerDetail(
            id=prof.id,
            full_name=prof.full_name,
            email=prof.email,
            phone=prof.phone,
            business_name=own.business_name,
            business_phone=own.business_phone,
            business_email=own.business_email,
            business_address=own.business_address,
            status=prof.status,
            created_at=prof.created_at,
            venues=venues,
            bookings_count=int(agg[0]),
            confirmed_count=int(agg[1]),
            gross_paid_paise=int(gross),
            recent_bookings=[self._brief(b, n) for b, n in recent],
        )

    async def _venue_briefs(self, owner_id: UUID) -> list[VenueBrief]:
        rows = (
            await self.s.execute(
                select(
                    Venue,
                    City.name,
                    func.count(Booking.id),
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_SET)),
                )
                .outerjoin(City, City.id == Venue.city_id)
                .outerjoin(Booking, Booking.venue_id == Venue.id)
                .where(Venue.owner_id == owner_id)
                .group_by(Venue.id, City.name)
                .order_by(Venue.created_at.desc(), Venue.id)
            )
        ).all()
        return [
            VenueBrief(
                id=v.id,
                name=v.name,
                status=v.status,
                city=c,
                created_at=v.created_at,
                bookings_count=int(n),
                confirmed_count=int(cf),
            )
            for v, c, n, cf in rows
        ]

    async def list_customers(
        self, q: str | None, status: str | None, sort: str, order: SortOrder, limit: int, offset: int
    ) -> CustomerPage:
        total = (
            select(func.count(Booking.id))
            .where(Booking.customer_id == Profile.id)
            .correlate(Profile)
            .scalar_subquery()
        )
        confirmed = (
            select(func.count(Booking.id))
            .where(Booking.customer_id == Profile.id, Booking.status.in_(CONFIRMED_SET))
            .correlate(Profile)
            .scalar_subquery()
        )
        stmt = select(Profile, total, confirmed).where(Profile.role == "customer")
        if status:
            stmt = stmt.where(Profile.status == status)
        if q and q.strip():
            pat = like_pattern(q)
            stmt = stmt.where(
                or_(Profile.full_name.ilike(pat, escape="\\"), Profile.email.ilike(pat, escape="\\"))
            )
        cols = {"created_at": Profile.created_at, "name": Profile.full_name, "bookings": total}
        rows = (
            await self.s.execute(
                stmt.order_by(*self._order(cols, sort, order, Profile.id)).limit(limit + 1).offset(offset)
            )
        ).all()
        items = [
            CustomerRow(
                id=p.id,
                full_name=p.full_name,
                email=p.email,
                phone_masked=mask_phone(p.phone),
                status=p.status,
                created_at=p.created_at,
                bookings_count=int(t),
                confirmed_count=int(c),
            )
            for p, t, c in rows[:limit]
        ]
        return CustomerPage(items=items, limit=limit, offset=offset, has_more=len(rows) > limit)

    async def get_customer(self, customer_id: UUID) -> CustomerDetail:
        prof = (
            await self.s.scalars(select(Profile).where(Profile.id == customer_id, Profile.role == "customer"))
        ).first()
        if prof is None:
            raise NotFoundError("Customer not found.", code="CUSTOMER_NOT_FOUND")
        agg = (
            await self.s.execute(
                select(
                    func.count(Booking.id),
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                ).where(Booking.customer_id == customer_id)
            )
        ).one()
        gross = (
            await self.s.execute(
                select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
                    Payment.customer_id == customer_id, Payment.status.in_(PAID_SET)
                )
            )
        ).scalar_one()
        rows = (
            await self.s.scalars(
                select(Booking)
                .where(Booking.customer_id == customer_id)
                .order_by(Booking.created_at.desc(), Booking.id)
                .limit(50)
            )
        ).all()
        return CustomerDetail(
            id=prof.id,
            full_name=prof.full_name,
            email=prof.email,
            phone=prof.phone,
            status=prof.status,
            created_at=prof.created_at,
            bookings_count=int(agg[0]),
            confirmed_count=int(agg[1]),
            cancelled_count=int(agg[2]),
            gross_paid_paise=int(gross),
            bookings=[self._brief(b, prof.full_name) for b in rows],
        )

    # ------------------------------------------------------------------ status change (audited)
    async def change_status(
        self, actor: Profile, target_id: UUID, expected_role: str, new_status: str, reason: str
    ) -> StatusChangeOut:
        if target_id == actor.id:
            raise PermissionDeniedError("You cannot change your own account.", code="ADMIN_ACCOUNT_PROTECTED")
        target = (
            await self.s.scalars(select(Profile).where(Profile.id == target_id).with_for_update())
        ).first()
        if target is None or target.role != expected_role:
            # A customer id sent to the owner route (or vice versa) is simply not found.
            if target is not None and target.role == "admin":
                raise PermissionDeniedError(
                    "Admin accounts cannot be changed here.", code="ADMIN_ACCOUNT_PROTECTED"
                )
            raise NotFoundError(
                f"{expected_role.title()} not found.", code=f"{expected_role.upper()}_NOT_FOUND"
            )
        if target.status == new_status:
            return StatusChangeOut(id=target.id, role=target.role, status=target.status, changed=False)
        old = target.status
        target.status = new_status
        await self._audit(
            actor,
            "admin.account_status_changed",
            "profile",
            str(target.id),
            target_role=target.role,
            **{"from": old, "to": new_status},
            reason=reason,
        )
        await self._notify_admins(
            type_="admin.account_status",
            title=f"{target.role.title()} account {new_status}",
            body=f"{target.full_name}: {reason}"[:1000],
            dedupe=f"acct-status:{target.id}:{new_status}:{datetime.now(UTC).isoformat()}",
        )
        await self.s.commit()
        return StatusChangeOut(id=target.id, role=target.role, status=new_status, changed=True)

    async def _notify_admins(self, *, type_: str, title: str, body: str, dedupe: str) -> None:
        admins = (
            await self.s.scalars(
                select(Profile.id).where(Profile.role == "admin", Profile.status == "active")
            )
        ).all()
        notes = NotificationService(self.s)
        for admin_id in admins:
            await notes.queue(user_id=admin_id, type_=type_, title=title, body=body, dedupe_key=dedupe)

    # ================================================================== venues
    def _venue_stmt(self) -> Any:
        total = (
            select(func.count(Booking.id))
            .where(Booking.venue_id == Venue.id)
            .correlate(Venue)
            .scalar_subquery()
        )
        confirmed = (
            select(func.count(Booking.id))
            .where(Booking.venue_id == Venue.id, Booking.status.in_(CONFIRMED_SET))
            .correlate(Venue)
            .scalar_subquery()
        )
        cats = (
            select(func.coalesce(func.array_agg(Category.name), []))
            .select_from(VenueCategory)
            .join(Category, Category.id == VenueCategory.category_id)
            .where(VenueCategory.venue_id == Venue.id)
            .correlate(Venue)
            .scalar_subquery()
        )
        stmt = (
            select(Venue, Profile.full_name, OwnerProfile.business_name, City.name, total, confirmed, cats)
            .join(OwnerProfile, OwnerProfile.user_id == Venue.owner_id)
            .join(Profile, Profile.id == Venue.owner_id)
            .outerjoin(City, City.id == Venue.city_id)
        )
        return stmt, total

    @staticmethod
    def _venue_row(row: Any) -> dict[str, Any]:
        v, owner_name, business, city, total, confirmed, cats = row
        return {
            "id": v.id,
            "name": v.name,
            "owner_id": v.owner_id,
            "owner_name": owner_name,
            "business_name": business,
            "categories": sorted(cats or []),
            "city": city,
            "address_line": v.address_line,
            "status": v.status,
            "created_at": v.created_at,
            "published_at": v.published_at,
            "bookings_count": int(total),
            "confirmed_count": int(confirmed),
        }

    async def list_venues(
        self,
        q: str | None,
        status: str | None,
        city_id: UUID | None,
        category_id: UUID | None,
        owner_id: UUID | None,
        sort: str,
        order: SortOrder,
        limit: int,
        offset: int,
    ) -> VenuePage:
        stmt, total = self._venue_stmt()
        if status:
            stmt = stmt.where(Venue.status == status)
        if city_id:
            stmt = stmt.where(Venue.city_id == city_id)
        if owner_id:
            stmt = stmt.where(Venue.owner_id == owner_id)
        if category_id:
            stmt = stmt.where(
                Venue.id.in_(select(VenueCategory.venue_id).where(VenueCategory.category_id == category_id))
            )
        if q and q.strip():
            pat = like_pattern(q)
            stmt = stmt.where(
                or_(
                    Venue.name.ilike(pat, escape="\\"),
                    Profile.full_name.ilike(pat, escape="\\"),
                    OwnerProfile.business_name.ilike(pat, escape="\\"),
                    City.name.ilike(pat, escape="\\"),
                )
            )
        cols = {"created_at": Venue.created_at, "name": Venue.name, "bookings": total}
        rows = (
            await self.s.execute(
                stmt.order_by(*self._order(cols, sort, order, Venue.id)).limit(limit + 1).offset(offset)
            )
        ).all()
        return VenuePage(
            items=[VenueRow(**self._venue_row(r)) for r in rows[:limit]],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    async def get_venue(self, venue_id: UUID) -> VenueDetail:
        stmt, _ = self._venue_stmt()
        row = (await self.s.execute(stmt.where(Venue.id == venue_id))).first()
        if row is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        v = row[0]
        res = (
            await self.s.execute(
                select(
                    func.count(VenueResource.id), func.count(VenueResource.id).filter(VenueResource.is_active)
                ).where(VenueResource.venue_id == venue_id)
            )
        ).one()
        gross = (
            await self.s.execute(
                select(func.coalesce(func.sum(Payment.amount_paise), 0)).where(
                    Payment.venue_id == venue_id, Payment.status.in_(PAID_SET)
                )
            )
        ).scalar_one()
        return VenueDetail(
            **self._venue_row(row),
            description=v.description,
            contact_phone=v.contact_phone,
            timezone=v.timezone,
            resources_count=int(res[0]),
            active_resources_count=int(res[1]),
            gross_paid_paise=int(gross),
            rating_avg=float(v.rating_avg) if v.rating_avg is not None else None,
            rating_count=v.rating_count,
        )

    # ================================================================== bookings
    def _booking_filters(
        self,
        stmt: Any,
        *,
        q: str | None,
        status: str | None,
        payment_status: str | None,
        venue_id: UUID | None,
        owner_id: UUID | None,
        customer_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
    ) -> Any:
        if status:
            stmt = stmt.where(Booking.status == status)
        if payment_status:
            stmt = stmt.where(Booking.payment_status == payment_status)
        if venue_id:
            stmt = stmt.where(Booking.venue_id == venue_id)
        if owner_id:
            stmt = stmt.where(Venue.owner_id == owner_id)
        if customer_id:
            stmt = stmt.where(Booking.customer_id == customer_id)
        if date_from:
            stmt = stmt.where(Booking.booking_date >= date_from)
        if date_to:
            stmt = stmt.where(Booking.booking_date <= date_to)
        if q and q.strip():
            pat = like_pattern(q)
            stmt = stmt.where(
                or_(
                    Booking.booking_code.ilike(pat, escape="\\"),
                    cast(Booking.id, String).ilike(pat, escape="\\"),
                    Profile.full_name.ilike(pat, escape="\\"),
                    Booking.venue_name.ilike(pat, escape="\\"),
                )
            )
        return stmt

    def _booking_base(self) -> Any:
        owner = Profile.__table__.alias("owner_profile")
        pay_amount = (
            select(Payment.amount_paise)
            .where(Payment.booking_id == Booking.id)
            .correlate(Booking)
            .scalar_subquery()
        )
        pay_id = (
            select(Payment.id).where(Payment.booking_id == Booking.id).correlate(Booking).scalar_subquery()
        )
        stmt = (
            select(Booking, Profile.full_name, Venue.owner_id, owner.c.full_name, pay_amount, pay_id)
            .join(Profile, Profile.id == Booking.customer_id)
            .join(Venue, Venue.id == Booking.venue_id)
            .join(owner, owner.c.id == Venue.owner_id)
        )
        return stmt

    def _booking_row(self, row: Any, now: datetime, svc: Any) -> AdminBookingRow:
        b, cust, owner_id, owner_name, pay_amount, pay_id = row
        base = svc._owner_out(b, cust, now).model_dump()
        return AdminBookingRow(
            **base,
            customer_id=b.customer_id,
            owner_id=owner_id,
            owner_name=owner_name,
            payment_amount_paise=int(pay_amount) if pay_amount is not None else None,
            payment_id=pay_id,
        )

    async def list_bookings(
        self,
        *,
        q: str | None,
        status: str | None,
        payment_status: str | None,
        venue_id: UUID | None,
        owner_id: UUID | None,
        customer_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
        limit: int,
        offset: int,
    ) -> AdminBookingRowPage:
        from app.services.availability import utcnow
        from app.services.bookings import BookingService

        svc = BookingService(self.s, self.settings)
        now = utcnow()
        await svc.settle_due(now=now)
        stmt = self._booking_filters(
            self._booking_base(),
            q=q,
            status=status,
            payment_status=payment_status,
            venue_id=venue_id,
            owner_id=owner_id,
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
        )
        rows = (
            await self.s.execute(
                stmt.order_by(Booking.created_at.desc(), Booking.id).limit(limit + 1).offset(offset)
            )
        ).all()
        await self.s.commit()
        return AdminBookingRowPage(
            items=[self._booking_row(r, now, svc) for r in rows[:limit]],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    async def get_booking(self, booking_id: UUID, payments: PaymentService) -> AdminBookingDetailOut:
        from app.services.availability import utcnow
        from app.services.bookings import BookingService

        svc = BookingService(self.s, self.settings)
        now = utcnow()
        await svc.settle_due(now=now)
        row = (await self.s.execute(self._booking_base().where(Booking.id == booking_id))).first()
        if row is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        out = self._booking_row(row, now, svc)
        history = await svc._history(booking_id)
        pay_rows = (
            await self.s.execute(
                select(Payment, Booking, Venue.name)
                .join(Booking, Booking.id == Payment.booking_id)
                .join(Venue, Venue.id == Payment.venue_id)
                .where(Payment.booking_id == booking_id)
            )
        ).all()
        await self.s.commit()
        data = out.model_dump()
        data["history"] = [h.model_dump() for h in history]
        pays: Sequence[AdminPaymentOut] = [payments._admin_out(p, b, vn) for p, b, vn in pay_rows]
        return AdminBookingDetailOut(**data, payments=list(pays))

    # ================================================================== exports (CSV)
    async def export_bookings(
        self,
        actor: Profile,
        *,
        status: str | None,
        payment_status: str | None,
        venue_id: UUID | None,
        date_from: date | None,
        date_to: date | None,
    ) -> str:
        stmt = self._booking_filters(
            self._booking_base(),
            q=None,
            status=status,
            payment_status=payment_status,
            venue_id=venue_id,
            owner_id=None,
            customer_id=None,
            date_from=date_from,
            date_to=date_to,
        )
        cap = self.settings.admin_export_max_rows
        rows = (
            await self.s.execute(stmt.order_by(Booking.created_at.desc(), Booking.id).limit(cap + 1))
        ).all()
        truncated = len(rows) > cap
        header = [
            "booking_code",
            "booking_id",
            "customer_id",
            "customer_name",
            "venue",
            "owner_name",
            "booking_date",
            "start_local",
            "end_local",
            "duration_minutes",
            "total_amount_paise",
            "currency",
            "payment_status",
            "booking_status",
            "created_at_utc",
        ]
        out: list[list[object]] = []
        for b, cust, _owner_id, owner_name, _pa, _pi in rows[:cap]:
            tz = ZoneInfo(b.timezone)
            out.append(
                [
                    b.booking_code,
                    b.id,
                    b.customer_id,
                    cust,
                    b.venue_name,
                    owner_name,
                    b.booking_date,
                    b.starts_at.astimezone(tz).strftime("%H:%M"),
                    b.ends_at.astimezone(tz).strftime("%H:%M"),
                    b.duration_minutes,
                    b.total_amount_paise,
                    b.currency,
                    b.payment_status,
                    b.status,
                    b.created_at.astimezone(UTC).isoformat(timespec="seconds"),
                ]
            )
        await self._audit(
            actor,
            "admin.export",
            "bookings",
            None,
            rows=len(out),
            truncated=truncated,
            filters={
                "status": status,
                "payment_status": payment_status,
                "venue_id": str(venue_id) if venue_id else None,
                "date_from": str(date_from) if date_from else None,
                "date_to": str(date_to) if date_to else None,
            },
        )
        await self.s.commit()
        return self._csv(header, out)

    async def export_payments(
        self, actor: Profile, *, status: str | None, date_from: date | None, date_to: date | None
    ) -> str:
        stmt = (
            select(Payment, Booking.booking_code, Booking.venue_name, Profile.full_name)
            .join(Booking, Booking.id == Payment.booking_id)
            .join(Profile, Profile.id == Payment.customer_id)
        )
        if status:
            stmt = stmt.where(Payment.status == status)
        if date_from or date_to:
            start, end = (date_from or date_to), (date_to or date_from)
            assert start is not None and end is not None
            lo, hi = self._bounds(min(start, end), max(start, end))
            stmt = stmt.where(Payment.created_at >= lo, Payment.created_at < hi)
        cap = self.settings.admin_export_max_rows
        rows = (
            await self.s.execute(stmt.order_by(Payment.created_at.desc(), Payment.id).limit(cap + 1))
        ).all()
        header = [
            "payment_id",
            "booking_code",
            "customer_id",
            "customer_name",
            "venue",
            "amount_paise",
            "currency",
            "method",
            "status",
            "razorpay_order_id",
            "razorpay_payment_id",
            "review_required",
            "created_at_utc",
            "captured_at_utc",
        ]
        out = [
            [
                p.id,
                code,
                p.customer_id,
                cust,
                venue,
                p.amount_paise,
                p.currency,
                p.method,
                p.status,
                p.provider_order_id,
                p.provider_payment_id,
                p.review_required,
                p.created_at.astimezone(UTC).isoformat(timespec="seconds"),
                p.captured_at.astimezone(UTC).isoformat(timespec="seconds") if p.captured_at else "",
            ]
            for p, code, venue, cust in rows[:cap]
        ]
        await self._audit(
            actor,
            "admin.export",
            "payments",
            None,
            rows=len(out),
            truncated=len(rows) > cap,
            filters={
                "status": status,
                "date_from": str(date_from) if date_from else None,
                "date_to": str(date_to) if date_to else None,
            },
        )
        await self.s.commit()
        return self._csv(header, out)

    async def export_people(self, actor: Profile, role: Literal["customer", "owner"]) -> str:
        """Customer / owner report. Deliberately no e-mail, phone or address columns."""
        bookings = (
            select(func.count(Booking.id))
            .where(Booking.customer_id == Profile.id)
            .correlate(Profile)
            .scalar_subquery()
            if role == "customer"
            else select(func.count(Booking.id))
            .join(Venue, Venue.id == Booking.venue_id)
            .where(Venue.owner_id == Profile.id)
            .correlate(Profile)
            .scalar_subquery()
        )
        cap = self.settings.admin_export_max_rows
        rows = (
            await self.s.execute(
                select(Profile.id, Profile.full_name, Profile.status, Profile.created_at, bookings)
                .where(Profile.role == role)
                .order_by(Profile.created_at.desc(), Profile.id)
                .limit(cap + 1)
            )
        ).all()
        header = ["id", "name", "status", "registered_at_utc", "bookings_count"]
        out = [[i, n, s, c.astimezone(UTC).isoformat(timespec="seconds"), b] for i, n, s, c, b in rows[:cap]]
        await self._audit(actor, "admin.export", f"{role}s", None, rows=len(out), truncated=len(rows) > cap)
        await self.s.commit()
        return self._csv(header, out)

    @staticmethod
    def _csv(header: list[str], rows: Sequence[Sequence[object]]) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\r\n")
        w.writerow(header)
        for r in rows:
            w.writerow([csv_safe(c) for c in r])
        return buf.getvalue()

    # ================================================================== audit log
    async def list_audit(
        self, action: str | None, entity_type: str | None, limit: int, offset: int
    ) -> AuditPage:
        stmt = select(AuditLog)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        rows = (
            await self.s.scalars(
                stmt.order_by(AuditLog.created_at.desc(), AuditLog.id).limit(limit + 1).offset(offset)
            )
        ).all()
        return AuditPage(
            items=[
                AuditRow(
                    id=a.id,
                    action=a.action,
                    actor_id=a.actor_id,
                    actor_role=a.actor_role,
                    entity_type=a.entity_type,
                    entity_id=a.entity_id,
                    metadata=a.metadata_,
                    created_at=a.created_at,
                )
                for a in rows[:limit]
            ],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )


__all__ = ["AdminService", "csv_safe", "mask_phone"]
