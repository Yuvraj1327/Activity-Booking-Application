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

from sqlalchemy import Date, Numeric, String, and_, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import Settings
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.domain import booking_state as st
from app.domain import payment_state as pst
from app.models import (
    AuditLog,
    Booking,
    Category,
    City,
    CouponRedemption,
    Dispute,
    OwnerKycDocument,
    OwnerProfile,
    Payment,
    Payout,
    Profile,
    Refund,
    Venue,
    VenueCategory,
    VenueReport,
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
    CityShare,
    CustomerDetail,
    CustomerPage,
    CustomerRow,
    DashboardOut,
    DashboardPeriod,
    DashboardTotals,
    DateRange,
    Granularity,
    MoneyBreakdown,
    MoneyFigure,
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
    VenuePerformance,
    VenueRow,
)
from app.schemas.owner import Unavailable
from app.schemas.payment import AdminPaymentOut
from app.services import audit
from app.services.ledger import FinanceService, any_approved
from app.services.notifications import NotificationService
from app.services.payments import PaymentService
from app.utils.search import like_pattern

MAX_RANGE_DAYS = 366
CONFIRMED_SET = (st.CONFIRMED, st.COMPLETED)  # gross booking value: money for bookings that stand
CONFIRMED_ONLY = (st.CONFIRMED,)  # upcoming, paid-and-confirmed
COMPLETED_ONLY = (st.COMPLETED,)  # finished: never merged into "confirmed"
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
        self, actor: Profile, action: str, entity_type: str | None, entity_id: str | None, **meta: Any
    ) -> None:
        audit.record(self.s, actor, action, entity_type, entity_id, **meta)

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
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_ONLY)),
                    func.count(Booking.id).filter(Booking.status.in_(PENDING_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(COMPLETED_ONLY)),
                )
                .where(Booking.created_at >= lo, Booking.created_at < hi)
                .group_by(bucket)
            )
        ).all()
        by = {r[0]: r for r in rows}
        out: list[BookingBucket] = []
        for day in self._bucket_days(start, end, granularity):
            r = by.get(day)
            total, conf, pend, canc, comp = (
                (int(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5])) if r else (0, 0, 0, 0, 0)
            )
            out.append(
                BookingBucket(
                    bucket=day,
                    total=total,
                    confirmed=conf,
                    completed=comp,
                    pending=pend,
                    cancelled=canc,
                    other=total - conf - pend - canc - comp,
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
        refunded = int(
            await self.s.scalar(
                select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                    Refund.status == "processed", Refund.processed_at >= lo, Refund.processed_at < hi
                )
            )
            or 0
        )
        fin = FinanceService(self.s)
        platform: MoneyFigure | Unavailable
        owner: MoneyFigure | Unavailable
        tax: MoneyFigure | Unavailable
        if await any_approved(self.s):
            t = await fin.totals(lo, hi)
            cov = await fin.coverage(lo, hi)
            note = "From the ledger, under the finance configuration in force when each payment was captured."
            platform = MoneyFigure(amount_paise=t["platform"], note=note)
            owner = MoneyFigure(amount_paise=t["owner"], note=note)
            tax = MoneyFigure(amount_paise=t["tax"], note="Tax portion of payments (not revenue).")
            coverage: dict[str, Any] | None = cov
        else:
            platform = _unavailable(
                "Platform revenue", "Q7, Q8 (fees and commission): no approved configuration"
            )
            owner = _unavailable("Owner earnings", "Q7, Q8, Q10: no approved configuration")
            tax = _unavailable("Tax collected", "Q7 (tax rules): no approved configuration")
            coverage = None
        return MoneyBreakdown(
            gross_booking_value_paise=int(gross),
            successful_payment_paise=int(paid),
            platform_revenue=platform,
            owner_earnings=owner,
            tax_collected=tax,
            refunds=MoneyFigure(
                amount_paise=refunded, note="Refunds the gateway has processed in this period."
            ),
            ledger_coverage=coverage,
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
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_ONLY)),
                    func.count(Booking.id).filter(Booking.status.in_(COMPLETED_ONLY)),
                )
                .join(Booking, Booking.venue_id == Venue.id)
                .where(Booking.created_at >= lo, Booking.created_at < hi)
                .group_by(Venue.id, Venue.name)
                .order_by(func.count(Booking.id).desc(), Venue.name)
                .limit(limit)
            )
        ).all()
        return [
            TopVenue(venue_id=i, name=n, bookings=int(b), confirmed=int(c), completed=int(d))
            for i, n, b, c, d in rows
        ]

    # ------------------------------------------------------------------ sport / city / venue breakdowns
    async def sports_breakdown(self, start: date, end: date) -> tuple[list[CategoryShare], int]:
        """Bookings per sport. A venue can offer several sports, so each booking is split EQUALLY
        across them: the shares add up to the real total instead of over-counting. `tagged_bookings`
        is the unsplit count (a multi-sport venue's booking appears under each of its sports)."""
        lo, hi = self._bounds(start, end)
        n = (
            select(VenueCategory.venue_id.label("venue_id"), func.count().label("n"))
            .group_by(VenueCategory.venue_id)
            .subquery()
        )
        paid_amt = (
            select(func.coalesce(func.sum(Payment.amount_paise), 0))
            .where(Payment.booking_id == Booking.id, Payment.status.in_(PAID_SET))
            .correlate(Booking)
            .scalar_subquery()
        )
        weight = literal(1.0, Numeric) / n.c.n
        rows = (
            await self.s.execute(
                select(
                    Category.name,
                    func.sum(weight),
                    func.count(Booking.id),
                    func.count(func.distinct(Booking.venue_id)),
                    func.sum(cast(paid_amt, Numeric) / n.c.n),
                )
                .select_from(Booking)
                .join(VenueCategory, VenueCategory.venue_id == Booking.venue_id)
                .join(Category, Category.id == VenueCategory.category_id)
                .join(n, n.c.venue_id == Booking.venue_id)
                .where(Booking.created_at >= lo, Booking.created_at < hi)
                .group_by(Category.id, Category.name)
                .order_by(func.sum(weight).desc(), Category.name)
            )
        ).all()
        none = int(
            await self.s.scalar(
                select(func.count(Booking.id)).where(
                    Booking.created_at >= lo,
                    Booking.created_at < hi,
                    ~select(VenueCategory.venue_id)
                    .where(VenueCategory.venue_id == Booking.venue_id)
                    .exists(),
                )
            )
            or 0
        )
        shares = [
            CategoryShare(
                category=name, bookings=round(float(w), 2), tagged_bookings=int(t), venues=int(v),
                gross_paid_paise=int(round(float(g or 0))),
            )
            for name, w, t, v, g in rows
        ]  # fmt: skip
        return shares, none

    async def cities_breakdown(self, start: date, end: date) -> list[CityShare]:
        lo, hi = self._bounds(start, end)
        paid_amt = (
            select(func.coalesce(func.sum(Payment.amount_paise), 0))
            .where(Payment.booking_id == Booking.id, Payment.status.in_(PAID_SET))
            .correlate(Booking)
            .scalar_subquery()
        )
        venues = (
            select(Venue.city_id, func.count(Venue.id).label("c"))
            .where(Venue.status == "published")
            .group_by(Venue.city_id)
            .subquery()
        )
        rows = (
            await self.s.execute(
                select(
                    City.id,
                    func.coalesce(City.name, "No city"),
                    func.coalesce(func.max(venues.c.c), 0),
                    func.count(Booking.id),
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_ONLY)),
                    func.count(Booking.id).filter(Booking.status.in_(COMPLETED_ONLY)),
                    func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                    func.coalesce(func.sum(paid_amt), 0),
                )
                .select_from(Booking)
                .join(Venue, Venue.id == Booking.venue_id)
                .outerjoin(City, City.id == Venue.city_id)
                .outerjoin(venues, venues.c.city_id == Venue.city_id)
                .where(Booking.created_at >= lo, Booking.created_at < hi)
                .group_by(City.id, City.name)
                .order_by(func.count(Booking.id).desc(), City.name)
            )
        ).all()
        return [
            CityShare(city_id=i, city=n, venues=int(v), bookings=int(b), confirmed=int(c), completed=int(d),
                      cancelled=int(x), gross_paid_paise=int(g))
            for i, n, v, b, c, d, x, g in rows
        ]  # fmt: skip

    async def venues_performance(
        self, start: date, end: date, *, city_id: UUID | None, category_id: UUID | None, owner_id: UUID | None,
        sort: str, order: SortOrder, limit: int, offset: int,
    ) -> tuple[list[VenuePerformance], bool]:  # fmt: skip
        lo, hi = self._bounds(start, end)
        in_range = and_(Booking.created_at >= lo, Booking.created_at < hi)
        paid = (
            select(func.coalesce(func.sum(Payment.amount_paise), 0))
            .where(
                Payment.venue_id == Venue.id,
                Payment.status.in_(PAID_SET),
                Payment.created_at >= lo,
                Payment.created_at < hi,
            )
            .correlate(Venue)
            .scalar_subquery()
        )
        total = func.count(Booking.id).filter(in_range)
        canc = func.count(Booking.id).filter(in_range, Booking.status.in_(CANCELLED_SET))
        stmt = (
            select(
                Venue, City.name, total,
                func.count(Booking.id).filter(in_range, Booking.status.in_(CONFIRMED_ONLY)),
                func.count(Booking.id).filter(in_range, Booking.status.in_(COMPLETED_ONLY)),
                canc, paid,
            )
            .outerjoin(City, City.id == Venue.city_id)
            .outerjoin(Booking, Booking.venue_id == Venue.id)
            .group_by(Venue.id, City.name)
        )  # fmt: skip
        if city_id:
            stmt = stmt.where(Venue.city_id == city_id)
        if owner_id:
            stmt = stmt.where(Venue.owner_id == owner_id)
        if category_id:
            stmt = stmt.where(
                Venue.id.in_(select(VenueCategory.venue_id).where(VenueCategory.category_id == category_id))
            )
        cols = {"bookings": total, "revenue": paid, "cancellations": canc, "name": Venue.name}
        col = cols.get(sort, total)
        rows = (
            await self.s.execute(
                stmt.order_by(col.asc() if order == "asc" else col.desc(), Venue.name, Venue.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        out = []
        for v, city, t, c, d, x, g in rows[:limit]:
            t, c, d, x, g = int(t), int(c), int(d), int(x), int(g)
            out.append(
                VenuePerformance(
                    venue_id=v.id, name=v.name, city=city, status=v.status, bookings=t, confirmed=c, completed=d,
                    cancelled=x, cancellation_rate_percent=round(x * 100 / t, 1) if t else None, gross_paid_paise=g,
                    average_booking_paise=(g // max(c + d, 1)) if (c + d) else None,
                    rating_avg=float(v.rating_avg) if v.rating_avg is not None else None, rating_count=v.rating_count,
                )
            )  # fmt: skip
        return out, len(rows) > limit

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
        cats, uncategorised = await self.sports_breakdown(start, end)
        cities = await self.cities_breakdown(start, end)
        return PlatformAnalytics(
            range=self._range_out(start, end),
            granularity=granularity,
            new_customers=sum(s.customers for s in series),
            new_owners=sum(s.owners for s in series),
            new_venues=sum(s.venues_created for s in series),
            series=series,
            popular_categories=cats[:10],
            uncategorised_bookings=uncategorised,
            cities=cities,
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
                    count(Profile, Profile.role == "customer", Profile.status == "active"),
                    count(Profile, Profile.role == "owner", Profile.status == "active"),
                    count(Profile, Profile.role == "customer", Profile.status == "suspended"),
                    count(Profile, Profile.role == "owner", Profile.status == "suspended"),
                    count(Venue, Venue.status == "pending_review"),
                    count(VenueReport, VenueReport.status.in_(("open", "reviewing"))),
                )
            )
        ).one()
        in_range = and_(Booking.created_at >= lo, Booking.created_at < hi)
        p = (
            await self.s.execute(
                select(
                    func.count(Booking.id),
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_ONLY)),
                    func.count(Booking.id).filter(Booking.status.in_(PENDING_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(COMPLETED_ONLY)),
                ).where(in_range)
            )
        ).one()
        tx, failed_pay = (
            await self.s.execute(
                select(
                    func.count(Payment.id),
                    func.count(Payment.id).filter(Payment.status == pst.FAILED),
                ).where(Payment.created_at >= lo, Payment.created_at < hi)
            )
        ).one()
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
                active_customers=int(t[6]),
                active_owners=int(t[7]),
                suspended_customers=int(t[8]),
                suspended_owners=int(t[9]),
                pending_venue_approvals=int(t[10]),
                open_venue_reports=int(t[11]),
            ),
            period=DashboardPeriod(
                bookings=int(p[0]),
                confirmed=int(p[1]),
                completed=int(p[4]),
                pending=int(p[2]),
                cancelled=int(p[3]),
                transactions=int(tx),
                failed_payments=int(failed_pay),
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
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_ONLY)),
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
        pending_docs = int(
            await self.s.scalar(
                select(func.count()).where(
                    OwnerKycDocument.owner_id == owner_id, OwnerKycDocument.status == "pending"
                )
            )
            or 0
        )
        verified_venues = int(
            await self.s.scalar(
                select(func.count()).where(Venue.owner_id == owner_id, Venue.is_verified.is_(True))
            )
            or 0
        )
        paid_out = int(
            await self.s.scalar(
                select(func.coalesce(func.sum(Payout.amount_paise), 0)).where(
                    Payout.owner_id == owner_id, Payout.status == "paid"
                )
            )
            or 0
        )
        refunds = int(
            await self.s.scalar(
                select(func.coalesce(func.sum(Refund.amount_paise), 0))
                .join(Payment, Payment.id == Refund.payment_id)
                .join(Venue, Venue.id == Payment.venue_id)
                .where(Venue.owner_id == owner_id, Refund.status == "processed")
            )
            or 0
        )
        return OwnerDetail(
            kyc_status=own.kyc_status,
            kyc_reviewed_at=own.kyc_reviewed_at,
            kyc_note=own.kyc_note,
            pending_kyc_documents=pending_docs,
            verified_venues=verified_venues,
            payouts_paid_paise=paid_out,
            refunds_paise=refunds,
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
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_ONLY)),
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
            .where(Booking.customer_id == Profile.id, Booking.status.in_(CONFIRMED_ONLY))
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
                    func.count(Booking.id).filter(Booking.status.in_(CONFIRMED_ONLY)),
                    func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                    func.count(Booking.id).filter(Booking.status.in_(COMPLETED_ONLY)),
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
        refunded = int(
            await self.s.scalar(
                select(func.coalesce(func.sum(Refund.amount_paise), 0))
                .join(Payment, Payment.id == Refund.payment_id)
                .where(Payment.customer_id == customer_id, Refund.status == "processed")
            )
            or 0
        )
        open_dispute = bool(
            await self.s.scalar(
                select(func.count())
                .select_from(Dispute)
                .join(Booking, Booking.id == Dispute.booking_id)
                .where(Booking.customer_id == customer_id, Dispute.status.in_(("open", "investigating")))
            )
        )
        return CustomerDetail(
            completed_count=int(agg[3]),
            refunded_paise=refunded,
            deletion_requested_at=prof.deletion_requested_at,
            language=prof.language,
            has_open_dispute=open_dispute,
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
            before={"status": old},
            after={"status": new_status},
            reason=reason,
            **{"from": old, "to": new_status},
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
            .where(Booking.venue_id == Venue.id, Booking.status.in_(CONFIRMED_ONLY))
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
        reports = (
            select(func.count(VenueReport.id))
            .where(VenueReport.venue_id == Venue.id, VenueReport.status.in_(("open", "reviewing")))
            .correlate(Venue)
            .scalar_subquery()
        )
        stmt = (
            select(
                Venue,
                Profile.full_name,
                OwnerProfile.business_name,
                City.name,
                total,
                confirmed,
                cats,
                OwnerProfile.kyc_status,
                reports,
            )
            .join(OwnerProfile, OwnerProfile.user_id == Venue.owner_id)
            .join(Profile, Profile.id == Venue.owner_id)
            .outerjoin(City, City.id == Venue.city_id)
        )
        return stmt, total

    @staticmethod
    def _venue_row(row: Any) -> dict[str, Any]:
        v, owner_name, business, city, total, confirmed, cats, kyc, reports = row
        return {
            "is_verified": v.is_verified,
            "submitted_at": v.submitted_at,
            "status_reason": v.status_reason,
            "owner_kyc_status": kyc,
            "open_reports": int(reports),
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
        counts = (
            await self.s.execute(
                select(
                    func.count(Booking.id).filter(Booking.status.in_(COMPLETED_ONLY)),
                    func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                    func.count(Booking.id).filter(
                        Booking.status == st.CONFIRMED, Booking.starts_at > datetime.now(UTC)
                    ),
                ).where(Booking.venue_id == venue_id)
            )
        ).one()
        today = datetime.now(self.tz).date()
        first = (today.replace(day=1) - timedelta(days=150)).replace(day=1)
        lo, _ = self._bounds(first, first)
        _, hi = self._bounds(today, today)
        bucket = self._bucket(Booking.created_at, "month").label("b")
        paid_amt = (
            select(func.coalesce(func.sum(Payment.amount_paise), 0))
            .where(Payment.booking_id == Booking.id, Payment.status.in_(PAID_SET))
            .correlate(Booking)
            .scalar_subquery()
        )
        months = {
            b: (int(t), int(c), int(x), int(g))
            for b, t, c, x, g in (
                await self.s.execute(
                    select(
                        bucket,
                        func.count(Booking.id),
                        func.count(Booking.id).filter(Booking.status.in_(COMPLETED_ONLY)),
                        func.count(Booking.id).filter(Booking.status.in_(CANCELLED_SET)),
                        func.coalesce(func.sum(paid_amt), 0),
                    )
                    .where(Booking.venue_id == venue_id, Booking.created_at >= lo, Booking.created_at < hi)
                    .group_by(bucket)
                )
            ).all()
        }
        performance = []
        for m in self._bucket_days(first, today, "month"):
            t, c, x, g = months.get(m, (0, 0, 0, 0))
            performance.append(
                {"month": m.isoformat(), "bookings": t, "completed": c, "cancelled": x, "gross_paid_paise": g}
            )
        owner_earn: Any = _unavailable("Owner earnings", "Q7, Q8: no approved configuration")
        if await any_approved(self.s):
            tot = await FinanceService(self.s).totals(None, None, venue_id=venue_id)
            owner_earn = MoneyFigure(
                amount_paise=tot["owner"], note="Net of commission and refund reversals (ledger)."
            )
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
            verified_at=v.verified_at,
            completed_count=int(counts[0]),
            cancelled_count=int(counts[1]),
            future_confirmed_count=int(counts[2]),
            performance=performance,
            owner_earnings=owner_earn,
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
        category_id: UUID | None = None,
        city_id: UUID | None = None,
        refund_status: str | None = None,
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
        if city_id:
            stmt = stmt.where(Venue.city_id == city_id)
        if category_id:
            stmt = stmt.where(
                select(VenueCategory.venue_id)
                .where(VenueCategory.venue_id == Booking.venue_id, VenueCategory.category_id == category_id)
                .exists()
            )
        if refund_status:

            def has(*sts: str) -> Any:
                return (
                    select(Refund.id).where(Refund.booking_id == Booking.id, Refund.status.in_(sts)).exists()
                )

            if refund_status == "none":
                stmt = stmt.where(~select(Refund.id).where(Refund.booking_id == Booking.id).exists())
            elif refund_status == "awaiting":
                stmt = stmt.where(
                    Booking.status.in_((st.CANCELLED_CUSTOMER, st.CANCELLED_OWNER, st.CANCELLED_ADMIN)),
                    Booking.payment_status == "paid",
                    ~has("requested", "pending", "uncertain", "processed"),
                )
            elif refund_status == "pending":
                stmt = stmt.where(has("requested", "pending", "uncertain"))
            else:  # processed | failed
                stmt = stmt.where(has(refund_status))
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
        sports = (
            select(func.coalesce(func.array_agg(Category.name), []))
            .select_from(VenueCategory)
            .join(Category, Category.id == VenueCategory.category_id)
            .where(VenueCategory.venue_id == Booking.venue_id)
            .correlate(Booking)
            .scalar_subquery()
        )

        def refund_agg(*sts: str) -> Any:
            return (
                select(func.coalesce(func.sum(Refund.amount_paise), 0))
                .where(Refund.booking_id == Booking.id, Refund.status.in_(sts))
                .correlate(Booking)
                .scalar_subquery()
            )

        stmt = (
            select(
                Booking, Profile.full_name, Venue.owner_id, owner.c.full_name, pay_amount, pay_id, City.name, sports,
                refund_agg("processed"), refund_agg("requested", "pending", "uncertain"), refund_agg("failed"),
            )
            .join(Profile, Profile.id == Booking.customer_id)
            .join(Venue, Venue.id == Booking.venue_id)
            .join(owner, owner.c.id == Venue.owner_id)
            .outerjoin(City, City.id == Venue.city_id)
        )  # fmt: skip
        return stmt

    @staticmethod
    def _refund_status(b: Booking, processed: Any, in_flight: Any, failed: Any) -> str:
        if int(in_flight):
            return "pending"
        if int(processed):
            return "processed"
        if (
            b.status in (st.CANCELLED_CUSTOMER, st.CANCELLED_OWNER, st.CANCELLED_ADMIN)
            and b.payment_status == "paid"
        ):
            return "awaiting"  # cancelled and paid, no refund decided yet
        if int(failed):
            return "failed"
        return "none"

    def _booking_row(self, row: Any, now: datetime, svc: Any) -> AdminBookingRow:
        b, cust, owner_id, owner_name, pay_amount, pay_id, city, sports, processed, in_flight, failed = row
        base = svc._owner_out(b, cust, now).model_dump()
        refund_status = self._refund_status(b, processed, in_flight, failed)
        return AdminBookingRow(
            **base,
            customer_id=b.customer_id,
            owner_id=owner_id,
            owner_name=owner_name,
            payment_amount_paise=int(pay_amount) if pay_amount is not None else None,
            payment_id=pay_id,
            city=city,
            sports=sorted(sports or []),
            refund_status=refund_status,
            refunded_paise=int(processed),
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
        category_id: UUID | None = None,
        city_id: UUID | None = None,
        refund_status: str | None = None,
    ) -> AdminBookingRowPage:
        from app.services.availability import utcnow
        from app.services.bookings import BookingService

        svc = BookingService(self.s, self.settings)
        now = utcnow()
        await svc.settle_due(now=now)
        stmt = self._booking_filters(
            self._booking_base(),
            q=q, status=status, payment_status=payment_status, venue_id=venue_id, owner_id=owner_id,
            customer_id=customer_id, date_from=date_from, date_to=date_to, category_id=category_id,
            city_id=city_id, refund_status=refund_status,
        )  # fmt: skip
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
        from app.models import BookingStatusHistory
        from app.services.availability import utcnow
        from app.services.bookings import BookingService

        svc = BookingService(self.s, self.settings)
        now = utcnow()
        await svc.settle_due(now=now)
        row = (await self.s.execute(self._booking_base().where(Booking.id == booking_id))).first()
        if row is None:
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        out = self._booking_row(row, now, svc)
        b: Booking = row[0]
        history = await svc._history(booking_id)
        pay_rows = (
            await self.s.execute(
                select(Payment, Booking, Venue.name)
                .join(Booking, Booking.id == Payment.booking_id)
                .join(Venue, Venue.id == Payment.venue_id)
                .where(Payment.booking_id == booking_id)
            )
        ).all()
        cust = await self.s.get(Profile, b.customer_id)
        venue = await self.s.get(Venue, b.venue_id)
        owner_prof = await self.s.get(Profile, venue.owner_id) if venue else None
        owner_biz = await self.s.get(OwnerProfile, venue.owner_id) if venue else None
        city = await self.s.get(City, venue.city_id) if venue and venue.city_id else None
        # who did each step (names, not just ids)
        actors = {
            h.id: n
            for h, n in (
                await self.s.execute(
                    select(BookingStatusHistory, Profile.full_name)
                    .outerjoin(Profile, Profile.id == BookingStatusHistory.actor_id)
                    .where(BookingStatusHistory.booking_id == booking_id)
                )
            ).all()
        }
        timeline = [
            {
                "from_status": h.from_status, "to_status": h.to_status, "actor_role": h.actor_role,
                "actor_name": actors.get(hid), "reason": h.reason, "created_at": h.created_at,
            }
            for hid, h in (
                (x.id, x)
                for x in (
                    await self.s.scalars(
                        select(BookingStatusHistory)
                        .where(BookingStatusHistory.booking_id == booking_id)
                        .order_by(BookingStatusHistory.created_at, BookingStatusHistory.id)
                    )
                ).all()
            )
        ]  # fmt: skip
        refunds = await self._booking_refunds(booking_id, payments)
        disputes = [
            {"id": d.id, "subject": d.subject, "status": d.status, "priority": d.priority, "created_at": d.created_at,
             "resolution_type": d.resolution_type}
            for d in (await self.s.scalars(select(Dispute).where(Dispute.booking_id == booking_id).order_by(Dispute.created_at.desc()))).all()
        ]  # fmt: skip
        red = await self.s.scalar(select(CouponRedemption).where(CouponRedemption.booking_id == booking_id))
        coupon = None
        if red is not None:
            from app.models import Coupon

            c = await self.s.get(Coupon, red.coupon_id)
            coupon = {"code": c.code if c else None, "discount_paise": red.discount_paise}
        await self.s.commit()
        data = out.model_dump()
        data["history"] = [h.model_dump() for h in history]
        pays: Sequence[AdminPaymentOut] = [payments._admin_out(p, bk, vn) for p, bk, vn in pay_rows]
        return AdminBookingDetailOut(
            **data,
            payments=list(pays),
            customer={"id": b.customer_id, "full_name": cust.full_name if cust else None,
                      "email": cust.email if cust else None, "phone": cust.phone if cust else None,
                      "status": cust.status if cust else None},
            owner=None if owner_prof is None else {
                "id": owner_prof.id, "full_name": owner_prof.full_name, "email": owner_prof.email,
                "phone": owner_prof.phone, "business_name": owner_biz.business_name if owner_biz else None,
                "kyc_status": owner_biz.kyc_status if owner_biz else None, "status": owner_prof.status},
            venue=None if venue is None else {
                "id": venue.id, "name": venue.name, "address_line": venue.address_line, "city": city.name if city else None,
                "status": venue.status, "is_verified": venue.is_verified, "contact_phone": venue.contact_phone,
                "timezone": venue.timezone},
            price_snapshot=b.price_snapshot,
            refunds=refunds,
            disputes=disputes,
            coupon=coupon,
            timeline=timeline,
        )  # fmt: skip

    async def _booking_refunds(self, booking_id: UUID, payments: PaymentService) -> list[dict[str, Any]]:
        from app.services.refunds import RefundService

        svc = RefundService(self.s, self.settings, payments.gw)
        res = await svc.list_page(
            status=None,
            payment_id=None,
            booking_id=booking_id,
            date_lo=None,
            date_hi=None,
            limit=100,
            offset=0,
        )
        items: list[dict[str, Any]] = res["items"]
        return items

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
        owner_id: UUID | None = None,
        category_id: UUID | None = None,
        city_id: UUID | None = None,
        refund_status: str | None = None,
    ) -> str:
        stmt = self._booking_filters(
            self._booking_base(),
            q=None,
            status=status,
            payment_status=payment_status,
            venue_id=venue_id,
            owner_id=owner_id,
            customer_id=None,
            date_from=date_from,
            date_to=date_to,
            category_id=category_id,
            city_id=city_id,
            refund_status=refund_status,
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
            "city",
            "sports",
            "refund_status",
            "refunded_paise",
        ]
        out: list[list[object]] = []
        for r in rows[:cap]:
            b, cust, _owner_id, owner_name = r[0], r[1], r[2], r[3]
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
                    r[6],
                    "; ".join(sorted(r[7] or [])),
                    self._refund_status(b, r[8], r[9], r[10]),
                    int(r[8]),
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
        refunded = (
            select(func.coalesce(func.sum(Refund.amount_paise), 0))
            .where(Refund.payment_id == Payment.id, Refund.status == "processed")
            .correlate(Payment)
            .scalar_subquery()
        )
        in_flight = (
            select(func.coalesce(func.sum(Refund.amount_paise), 0))
            .where(Refund.payment_id == Payment.id, Refund.status.in_(("requested", "pending", "uncertain")))
            .correlate(Payment)
            .scalar_subquery()
        )
        stmt = (
            select(Payment, Booking.booking_code, Booking.venue_name, Profile.full_name, refunded, in_flight)
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
            "refunded_paise",
            "refund_in_progress_paise",
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
                int(done),
                int(pending),
            ]
            for p, code, venue, cust, done, pending in rows[:cap]
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
        self,
        action: str | None,
        entity_type: str | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        actor_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> AuditPage:
        stmt = select(AuditLog, Profile.full_name).outerjoin(Profile, Profile.id == AuditLog.actor_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if actor_id:
            stmt = stmt.where(AuditLog.actor_id == actor_id)
        if date_from or date_to:
            start, end = self.resolve_range(date_from or date_to, date_to or date_from)
            lo, hi = self._bounds(start, end)
            stmt = stmt.where(AuditLog.created_at >= lo, AuditLog.created_at < hi)
        rows = (
            await self.s.execute(
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
                    actor_name=name,
                    entity_type=a.entity_type,
                    entity_id=a.entity_id,
                    metadata=a.metadata_,
                    request_id=a.request_id,
                    created_at=a.created_at,
                )
                for a, name in rows[:limit]
            ],
            limit=limit,
            offset=offset,
            has_more=len(rows) > limit,
        )

    async def account_history(self, profile_id: UUID, limit: int, offset: int) -> AuditPage:
        """Everything done TO this account by an administrator: suspensions, reinstatements, KYC decisions."""
        stmt = (
            select(AuditLog, Profile.full_name)
            .outerjoin(Profile, Profile.id == AuditLog.actor_id)
            .where(
                or_(
                    and_(AuditLog.entity_type == "profile", AuditLog.entity_id == str(profile_id)),
                    and_(AuditLog.entity_type == "owner", AuditLog.entity_id == str(profile_id)),
                    AuditLog.metadata_["owner_id"].astext == str(profile_id),
                ),
                AuditLog.action.like("admin.%"),
            )
        )
        rows = (
            await self.s.execute(
                stmt.order_by(AuditLog.created_at.desc(), AuditLog.id).limit(limit + 1).offset(offset)
            )
        ).all()
        return AuditPage(
            items=[
                AuditRow(
                    id=a.id, action=a.action, actor_id=a.actor_id, actor_role=a.actor_role, actor_name=n,
                    entity_type=a.entity_type, entity_id=a.entity_id, metadata=a.metadata_,
                    request_id=a.request_id, created_at=a.created_at,
                )
                for a, n in rows[:limit]
            ],
            limit=limit, offset=offset, has_more=len(rows) > limit,
        )  # fmt: skip

    async def audit_actions(self) -> list[str]:
        return list(
            (await self.s.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action))).all()
        )


__all__ = ["AdminService", "csv_safe", "mask_phone"]
