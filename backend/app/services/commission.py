"""Commission management: versioned rules, resolution, immutable booking snapshots, reports.

Rule changes are only ever INSERTs of a new version. Nothing here updates or deletes a rule version,
a snapshot or a ledger entry (database triggers enforce it as well).
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.domain import commission as dom
from app.domain.finance_math import mul_bps
from app.models import (
    Booking,
    BookingCommissionSnapshot,
    Category,
    CommissionRule,
    CommissionRuleVersion,
    LedgerEntry,
    Payment,
    Profile,
    Venue,
    VenueCategory,
)
from app.services import audit

logger = logging.getLogger(__name__)
CLOCK_SKEW = timedelta(seconds=90)


def pct(bps: int | None) -> str | None:
    return None if bps is None else f"{bps / 100:.2f}".rstrip("0").rstrip(".") + "%"


class CommissionService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.s = session
        self.settings = settings
        self.priority = dom.DEFAULT_PRIORITY
        self.tiebreak: str | None = dom.DEFAULT_ACTIVITY_TIEBREAK
        cfg = settings
        if cfg is None:
            try:
                from app.core.config import get_settings

                cfg = get_settings()
            except Exception:  # no usable configuration: stay unresolved
                cfg = None
        if cfg is not None:
            self.tiebreak = cfg.commission_activity_tiebreak

    # ================================================================== resolution
    async def _candidates(
        self, venue_id: UUID, at: datetime, category_ids: list[UUID]
    ) -> list[dom.Candidate]:
        """Every rule that could apply to this venue, each with the version in force at `at`."""
        ranked = (
            select(
                CommissionRuleVersion,
                func.row_number()
                .over(
                    partition_by=CommissionRuleVersion.rule_id,
                    order_by=(
                        CommissionRuleVersion.effective_from.desc(),
                        CommissionRuleVersion.version.desc(),
                    ),
                )
                .label("rn"),
            )
            .where(CommissionRuleVersion.effective_from <= at)
            .subquery()
        )
        in_force = select(ranked).where(ranked.c.rn == 1).subquery()
        rows = (
            await self.s.execute(
                select(CommissionRule, in_force, Category.slug)
                .join(in_force, in_force.c.rule_id == CommissionRule.id)
                .outerjoin(Category, Category.id == CommissionRule.category_id)
                .where(
                    or_(
                        CommissionRule.scope == "global",
                        and_(CommissionRule.scope == "venue", CommissionRule.venue_id == venue_id),
                        and_(
                            CommissionRule.scope == "activity",
                            CommissionRule.category_id.in_(category_ids or [UUID(int=0)]),
                        ),
                    )
                )
            )
        ).all()
        return [
            dom.Candidate(
                scope=r[0].scope, rule_id=r[0].id, version_id=r[1], version=r.version, bps=r.commission_bps,
                is_active=r.is_active, category_id=r[0].category_id, category_slug=r.slug,
            )
            for r in rows
        ]  # fmt: skip

    async def _venue_categories(self, venue_id: UUID) -> list[tuple[UUID, str]]:
        rows = (
            await self.s.execute(
                select(Category.id, Category.slug)
                .join(VenueCategory, VenueCategory.category_id == Category.id)
                .where(VenueCategory.venue_id == venue_id)
                .order_by(Category.sort_order, Category.slug)
            )
        ).all()
        return [(r[0], r[1]) for r in rows]

    async def resolve(
        self, venue_id: UUID, at: datetime | None = None, category_id: UUID | None = None
    ) -> dict[str, Any]:
        """Which single rule applies to a booking at this venue created at `at`."""
        at = at or datetime.now(UTC)
        cats = await self._venue_categories(venue_id)
        cat_ids = [c[0] for c in cats]
        if category_id is not None:
            cat_ids = [category_id]  # explicit activity (preview): only that activity is considered
        cands = await self._candidates(venue_id, at, cat_ids)
        winner, ambiguous = dom.resolve(cands, self.priority, self.tiebreak)
        attributed = (
            winner.category_id
            if winner and winner.scope == "activity"
            else (category_id or (cats[0][0] if cats else None))
        )
        return {
            "at": at,
            "priority": list(self.priority),
            "ambiguous": ambiguous,
            "scope": winner.scope if winner else "none",
            "rule_id": winner.rule_id if winner else None,
            "rule_version_id": winner.version_id if winner else None,
            "rule_version": winner.version if winner else None,
            "commission_bps": winner.bps if winner else None,
            "category_id": attributed,
            "candidates": [
                {"scope": c.scope, "rule_id": str(c.rule_id), "version": c.version, "commission_bps": c.bps,
                 "is_active": c.is_active, "category_id": str(c.category_id) if c.category_id else None,
                 "selected": winner is not None and c.rule_id == winner.rule_id}
                for c in sorted(cands, key=lambda c: (list(self.priority).index(cast(dom.Scope, c.scope)), str(c.rule_id)))
            ],
        }  # fmt: skip

    # ================================================================== snapshots (immutable)
    async def snapshot_for_booking(
        self, booking: Booking, *, at: datetime | None = None, source: str = "booking_created"
    ) -> BookingCommissionSnapshot:
        """Store the commission that applies to this booking. The first write wins and is never changed:
        a retry, a webhook replay or a later rule edit all read the same row."""
        existing = await self.s.get(BookingCommissionSnapshot, booking.id)
        if existing is not None:
            return existing
        res = await self.resolve(booking.venue_id, at or datetime.now(UTC))
        values = {
            "booking_id": booking.id, "scope": res["scope"], "rule_id": res["rule_id"],
            "rule_version_id": res["rule_version_id"], "rule_version": res["rule_version"],
            "category_id": res["category_id"], "commission_bps": res["commission_bps"],
            "effective_at": res["at"], "source": source, "ambiguous": res["ambiguous"], "priority": res["priority"],
            "candidates": res["candidates"],
        }  # fmt: skip
        await self.s.execute(pg_insert(BookingCommissionSnapshot).values(**values).on_conflict_do_nothing())
        await self.s.flush()
        snap = await self.s.get(BookingCommissionSnapshot, booking.id)
        assert snap is not None
        return snap

    async def snapshot_for_new_booking(self, booking: Booking, at: datetime) -> None:
        """Called while a booking is being created. A failure here must never block the booking: the
        snapshot is then created at accrual time from the booking's creation instant (same result,
        because rules cannot be back-dated)."""
        try:
            async with self.s.begin_nested():
                await self.snapshot_for_booking(booking, at=at)
        except Exception:
            logger.exception("commission_snapshot_failed", extra={"booking_id": str(booking.id)})

    # ================================================================== rule management
    @staticmethod
    def _version_out(
        v: CommissionRuleVersion, *, effective_to: datetime | None = None, admin_name: str | None = None
    ) -> dict[str, Any]:
        return {
            "id": v.id, "rule_id": v.rule_id, "version": v.version, "commission_bps": v.commission_bps,
            "commission_pct": pct(v.commission_bps), "previous_bps": v.previous_bps,
            "previous_pct": pct(v.previous_bps), "is_active": v.is_active, "effective_from": v.effective_from,
            "effective_to": effective_to, "reason": v.reason, "changed_by": v.created_by,
            "changed_by_name": admin_name, "created_at": v.created_at,
        }  # fmt: skip

    async def _versions(self, rule_id: UUID) -> list[CommissionRuleVersion]:
        return list(
            (
                await self.s.scalars(
                    select(CommissionRuleVersion)
                    .where(CommissionRuleVersion.rule_id == rule_id)
                    .order_by(CommissionRuleVersion.version)
                )
            ).all()
        )

    @staticmethod
    def _in_force(versions: list[CommissionRuleVersion], at: datetime) -> CommissionRuleVersion | None:
        ok = [v for v in versions if v.effective_from <= at]
        return max(ok, key=lambda v: (v.effective_from, v.version)) if ok else None

    async def _rule_out(
        self,
        rule: CommissionRule,
        versions: list[CommissionRuleVersion],
        now: datetime,
        names: dict[UUID, str],
    ) -> dict[str, Any]:
        cur = self._in_force(versions, now)
        pending = sorted(
            (v for v in versions if v.effective_from > now), key=lambda v: (v.effective_from, v.version)
        )
        cat = await self.s.get(Category, rule.category_id) if rule.category_id else None
        ven = await self.s.get(Venue, rule.venue_id) if rule.venue_id else None
        return {
            "id": rule.id, "scope": rule.scope, "category_id": rule.category_id,
            "category_name": cat.name if cat else None, "venue_id": rule.venue_id,
            "venue_name": ven.name if ven else None, "created_at": rule.created_at,
            "current": self._version_out(cur, admin_name=names.get(cur.created_by)) if cur else None,
            "is_active_now": bool(cur and cur.is_active),
            "pending": [self._version_out(v, admin_name=names.get(v.created_by)) for v in pending],
            "latest_version": max((v.version for v in versions), default=0),
        }  # fmt: skip

    async def _names(self, ids: set[UUID]) -> dict[UUID, str]:
        if not ids:
            return {}
        rows = (await self.s.execute(select(Profile.id, Profile.full_name).where(Profile.id.in_(ids)))).all()
        return {r[0]: r[1] for r in rows}

    async def list_rules(
        self, scope: str | None = None, active_only: bool = False, q: str | None = None,
        _skip_ambiguity: bool = False,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        stmt = select(CommissionRule).order_by(CommissionRule.scope, CommissionRule.created_at)
        if scope:
            stmt = stmt.where(CommissionRule.scope == scope)
        rules = (await self.s.scalars(stmt)).all()
        vers: dict[UUID, list[CommissionRuleVersion]] = {}
        if rules:
            for v in (
                await self.s.scalars(
                    select(CommissionRuleVersion).where(
                        CommissionRuleVersion.rule_id.in_([r.id for r in rules])
                    )
                )
            ).all():
                vers.setdefault(v.rule_id, []).append(v)
        names = await self._names({v.created_by for vs in vers.values() for v in vs})
        out = [
            await self._rule_out(r, sorted(vers.get(r.id, []), key=lambda v: v.version), now, names)
            for r in rules
        ]
        if active_only:
            out = [r for r in out if r["is_active_now"]]
        if q:
            needle = q.lower()
            out = [
                r
                for r in out
                if needle in (r["venue_name"] or "").lower() or needle in (r["category_name"] or "").lower()
            ]
        glob = next((r for r in out if r["scope"] == "global"), None)
        return {
            "priority": list(self.priority),
            "priority_note": "The first scope with an active rule wins; exactly one rule applies per booking.",
            "activity_tiebreak": self.tiebreak,
            "ambiguous_venues": [] if _skip_ambiguity else await self.ambiguous_venues(),
            "global": glob, "items": [r for r in out if r["scope"] != "global"],
        }  # fmt: skip

    async def ambiguous_venues(self) -> list[dict[str, Any]]:
        """Venues whose sports carry DIFFERENT active activity rules and that have no active venue rule: new
        bookings there get no rate (and are not accrued) until the client approves a tie-break."""
        if self.tiebreak in ("lowest", "highest"):
            return []
        data = await self.list_rules(_skip_ambiguity=True)
        act = {r["category_id"]: r["current"]["commission_bps"] for r in data["items"]
               if r["scope"] == "activity" and r["is_active_now"]}  # fmt: skip
        ven = {r["venue_id"] for r in data["items"] if r["scope"] == "venue" and r["is_active_now"]}
        if len(act) < 2:
            return []
        rows = (
            await self.s.execute(
                select(Venue.id, Venue.name, VenueCategory.category_id)
                .join(VenueCategory, VenueCategory.venue_id == Venue.id)
                .where(VenueCategory.category_id.in_(list(act)))
            )
        ).all()
        per: dict[UUID, tuple[str, set[int]]] = {}
        for vid, name, cid in rows:
            per.setdefault(vid, (name, set()))[1].add(act[cid])
        return [{"venue_id": v, "venue_name": n, "percentages": sorted(b)} for v, (n, b) in per.items()
                if len(b) > 1 and v not in ven]  # fmt: skip

    async def get_rule(self, rule_id: UUID) -> dict[str, Any]:
        rule = await self.s.get(CommissionRule, rule_id)
        if rule is None:
            raise NotFoundError("Commission rule not found.", code="COMMISSION_RULE_NOT_FOUND")
        versions = await self._versions(rule_id)
        names = await self._names({v.created_by for v in versions})
        out = await self._rule_out(rule, versions, datetime.now(UTC), names)
        out["versions"] = [
            self._version_out(v, admin_name=names.get(v.created_by)) for v in reversed(versions)
        ]
        return out

    def _effective_from(self, requested: datetime | None, now: datetime) -> datetime:
        if requested is None:
            return now
        if requested.tzinfo is None:
            raise ValidationFailedError(
                "effective_from must include a time zone.", code="INVALID_EFFECTIVE_FROM"
            )
        if requested < now - CLOCK_SKEW:
            raise ValidationFailedError(
                "A commission change cannot be back-dated: it only applies to bookings made from its start time.",
                code="EFFECTIVE_FROM_IN_PAST",
            )
        return max(requested, now)

    async def create_rule(
        self,
        actor: CurrentUser,
        *,
        scope: str,
        category_id: UUID | None,
        venue_id: UUID | None,
        commission_bps: int,
        is_active: bool,
        effective_from: datetime | None,
        reason: str,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        eff = self._effective_from(effective_from, now)
        if scope == "activity":
            cat = await self.s.get(Category, category_id) if category_id else None
            if cat is None:
                raise NotFoundError("Activity (category) not found.", code="CATEGORY_NOT_FOUND")
        if scope == "venue" and (venue_id is None or await self.s.get(Venue, venue_id) is None):
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        rule = CommissionRule(scope=scope, category_id=category_id if scope == "activity" else None,
                              venue_id=venue_id if scope == "venue" else None, created_by=actor.id)  # fmt: skip
        try:
            async with self.s.begin_nested():
                self.s.add(rule)
                await self.s.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A rule already exists for this target. Add a new version to change it.",
                code="COMMISSION_RULE_EXISTS",
            ) from exc
        v = CommissionRuleVersion(rule_id=rule.id, version=1, commission_bps=commission_bps, previous_bps=None,
                                  is_active=is_active, effective_from=eff, reason=reason, created_by=actor.id)  # fmt: skip
        self.s.add(v)
        await self.s.flush()
        audit.record(self.s, actor.profile, "admin.commission_rule_created", "commission_rule", rule.id,
                     after={"scope": scope, "category_id": category_id, "venue_id": venue_id,
                            "commission_bps": commission_bps, "is_active": is_active, "effective_from": eff,
                            "version": 1}, reason=reason)  # fmt: skip
        await self.s.commit()
        return await self.get_rule(rule.id)

    async def add_version(
        self,
        actor: CurrentUser,
        rule_id: UUID,
        *,
        commission_bps: int | None,
        is_active: bool | None,
        effective_from: datetime | None,
        reason: str,
    ) -> dict[str, Any]:
        """Edit / activate / deactivate = append a new version. Earlier versions, snapshots and ledger entries stay as they are."""
        rule = await self.s.scalar(
            select(CommissionRule).where(CommissionRule.id == rule_id).with_for_update()
        )
        if rule is None:
            raise NotFoundError("Commission rule not found.", code="COMMISSION_RULE_NOT_FOUND")
        now = datetime.now(UTC)
        eff = self._effective_from(effective_from, now)
        versions = await self._versions(rule_id)
        last = versions[-1]
        new_bps = last.commission_bps if commission_bps is None else commission_bps
        new_active = last.is_active if is_active is None else is_active
        if new_bps == last.commission_bps and new_active == last.is_active:
            raise ValidationFailedError(
                "Nothing to change: the rule already has these values.", code="NO_CHANGE"
            )
        v = CommissionRuleVersion(rule_id=rule_id, version=last.version + 1, commission_bps=new_bps,
                                  previous_bps=last.commission_bps, is_active=new_active, effective_from=eff,
                                  reason=reason, created_by=actor.id)  # fmt: skip
        self.s.add(v)
        await self.s.flush()
        audit.record(self.s, actor.profile, "admin.commission_rule_changed", "commission_rule", rule_id,
                     before={"commission_bps": last.commission_bps, "is_active": last.is_active,
                             "version": last.version},
                     after={"commission_bps": new_bps, "is_active": new_active, "version": v.version,
                            "effective_from": eff, "scope": rule.scope}, reason=reason)  # fmt: skip
        await self.s.commit()
        return await self.get_rule(rule_id)

    async def active_summary(self) -> dict[str, Any]:
        data = await self.list_rules()
        now = datetime.now(UTC)
        glob = data["global"]
        return {
            "priority": data["priority"], "priority_note": data["priority_note"], "at": now,
            "global": None if glob is None or glob["current"] is None else {
                "rule_id": glob["id"], "commission_bps": glob["current"]["commission_bps"],
                "commission_pct": glob["current"]["commission_pct"], "is_active": glob["current"]["is_active"],
                "effective_from": glob["current"]["effective_from"], "version": glob["current"]["version"],
                "pending": glob["pending"]},
            "activity_rules": [r for r in data["items"] if r["scope"] == "activity" and r["is_active_now"]],
            "venue_rules": [r for r in data["items"] if r["scope"] == "venue" and r["is_active_now"]],
        }  # fmt: skip

    # ================================================================== history
    async def history(
        self,
        *,
        scope: str | None,
        venue_id: UUID | None,
        category_id: UUID | None,
        lo: datetime | None,
        hi: datetime | None,
        limit: int,
        offset: int,
        owner_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Every version of every rule, newest first, with the percentage it replaced and the end of its life
        (the start of the next version of the same rule). Filter by scope, venue, activity and the date it was made."""
        nxt = (
            func.lead(CommissionRuleVersion.effective_from)
            .over(
                partition_by=CommissionRuleVersion.rule_id,
                order_by=(CommissionRuleVersion.effective_from, CommissionRuleVersion.version),
            )
            .label("effective_to")
        )
        inner = select(CommissionRuleVersion, nxt).subquery()
        v = inner.c
        stmt = (
            select(inner, CommissionRule.scope, CommissionRule.category_id, CommissionRule.venue_id,
                   Category.name.label("category_name"), Venue.name.label("venue_name"),
                   Profile.full_name.label("admin_name"))
            .join(CommissionRule, CommissionRule.id == v.rule_id)
            .outerjoin(Category, Category.id == CommissionRule.category_id)
            .outerjoin(Venue, Venue.id == CommissionRule.venue_id)
            .outerjoin(Profile, Profile.id == v.created_by)
        )  # fmt: skip
        if scope:
            stmt = stmt.where(CommissionRule.scope == scope)
        if venue_id:
            stmt = stmt.where(CommissionRule.venue_id == venue_id)
        if category_id:
            stmt = stmt.where(CommissionRule.category_id == category_id)
        if lo:
            stmt = stmt.where(v.created_at >= lo)
        if hi:
            stmt = stmt.where(v.created_at < hi)
        if owner_id is not None:  # owner view: global + activities of their venues + their venues
            vids = select(Venue.id).where(Venue.owner_id == owner_id)
            cids = select(VenueCategory.category_id).where(VenueCategory.venue_id.in_(vids))
            stmt = stmt.where(
                or_(
                    CommissionRule.scope == "global",
                    CommissionRule.venue_id.in_(vids),
                    CommissionRule.category_id.in_(cids),
                )
            )
        rows = (
            await self.s.execute(
                stmt.order_by(v.created_at.desc(), v.version.desc()).limit(limit + 1).offset(offset)
            )
        ).all()
        items = []
        for r in rows[:limit]:
            items.append({
                "id": r.id, "rule_id": r.rule_id, "scope": r.scope, "category_id": r.category_id,
                "category_name": r.category_name, "venue_id": r.venue_id, "venue_name": r.venue_name,
                "version": r.version, "previous_bps": r.previous_bps, "previous_pct": pct(r.previous_bps),
                "commission_bps": r.commission_bps, "commission_pct": pct(r.commission_bps),
                "is_active": r.is_active, "effective_from": r.effective_from, "effective_to": r.effective_to,
                "reason": r.reason, "changed_by": r.created_by, "changed_by_name": r.admin_name,
                "created_at": r.created_at,
            })  # fmt: skip
        return {"items": items, "limit": limit, "offset": offset, "has_more": len(rows) > limit}

    # ================================================================== booking detail
    async def booking_detail(self, booking_id: UUID, owner_id: UUID | None = None) -> dict[str, Any]:
        row = (
            await self.s.execute(
                select(Booking, Venue.owner_id)
                .join(Venue, Venue.id == Booking.venue_id)
                .where(Booking.id == booking_id)
            )
        ).first()
        if row is None or (owner_id is not None and row[1] != owner_id):
            raise NotFoundError("Booking not found.", code="BOOKING_NOT_FOUND")
        b = row[0]
        snap = await self.s.get(BookingCommissionSnapshot, booking_id)
        entries = (
            await self.s.scalars(
                select(LedgerEntry)
                .where(LedgerEntry.booking_id == booking_id)
                .order_by(LedgerEntry.occurred_at, LedgerEntry.id)
            )
        ).all()
        sale = next((e for e in entries if e.kind == "sale"), None)
        def net(f: str) -> int:
            return int(sum(getattr(e, f) for e in entries))

        cat = await self.s.get(Category, snap.category_id) if snap and snap.category_id else None
        return {
            "booking_id": b.id, "booking_code": b.booking_code, "venue_id": b.venue_id, "venue_name": b.venue_name,
            "payment_status": b.payment_status, "status": b.status,
            "snapshot": None if snap is None else {
                "scope": snap.scope, "ambiguous": snap.ambiguous, "rule_id": snap.rule_id, "rule_version": snap.rule_version,
                "commission_bps": snap.commission_bps, "commission_pct": pct(snap.commission_bps),
                "category_id": snap.category_id, "category_name": cat.name if cat else None,
                "effective_at": snap.effective_at, "resolved_at": snap.resolved_at, "source": snap.source,
                "priority": snap.priority, "candidates": snap.candidates},
            "calculation": None if sale is None else {
                "gross_paise": sale.gross_paise, "commission_base_paise": sale.commission_base_paise,
                "commission_bps": sale.commission_bps, "commission_pct": pct(sale.commission_bps),
                "commission_scope": sale.commission_scope, "commission_rule_id": sale.commission_rule_id,
                "commission_rule_version": sale.commission_rule_version,
                "commission_paise": sale.commission_paise, "owner_net_paise": sale.owner_amount_paise,
                "tax_paise": sale.tax_paise, "fee_paise": sale.fee_paise, "discount_paise": sale.discount_paise,
                "finance_config_version": sale.config_version, "occurred_at": sale.occurred_at},
            "net": {"gross_paise": net("gross_paise"), "commission_paise": net("commission_paise"),
                    "owner_net_paise": net("owner_amount_paise"), "platform_paise": net("platform_amount_paise"),
                    "refunded_paise": -sum(e.gross_paise for e in entries if e.kind == "refund")},
            "entries": [{"id": e.id, "kind": e.kind, "gross_paise": e.gross_paise, "commission_paise": e.commission_paise,
                         "owner_amount_paise": e.owner_amount_paise, "occurred_at": e.occurred_at} for e in entries],
            "note": None if sale is not None else "No ledger entry yet: it is written after the payment is captured "
            "under an approved finance configuration.",
        }  # fmt: skip

    # ================================================================== calculation preview
    async def calculate(
        self, *, venue_id: UUID, category_id: UUID | None, base_paise: int, at: datetime | None
    ) -> dict[str, Any]:
        """What the commission would be for an amount, using the rules in force at `at` (default now). Read-only."""
        if await self.s.get(Venue, venue_id) is None:
            raise NotFoundError("Venue not found.", code="VENUE_NOT_FOUND")
        res = await self.resolve(venue_id, at or datetime.now(UTC), category_id)
        bps = res["commission_bps"]
        c = None if bps is None else mul_bps(base_paise, bps)
        return {**res, "base_paise": base_paise, "commission_paise": c,
                "owner_net_paise": None if c is None else base_paise - c,
                "rounding": "half-up to the paisa", "note": None if bps is not None else
                "No commission rule applies; the approved finance configuration's percentage is used when a payment is accrued."}  # fmt: skip

    # ================================================================== reports
    def ledger_filters(
        self, lo: datetime | None, hi: datetime | None, venue_id: UUID | None, category_id: UUID | None,
        owner_id: UUID | None,
    ) -> list[Any]:
        conds: list[Any] = []
        if lo:
            conds.append(LedgerEntry.occurred_at >= lo)
        if hi:
            conds.append(LedgerEntry.occurred_at < hi)
        if venue_id:
            conds.append(LedgerEntry.venue_id == venue_id)
        if owner_id:
            conds.append(LedgerEntry.owner_id == owner_id)
        if category_id:
            conds.append(BookingCommissionSnapshot.category_id == category_id)
        return conds

    async def report(
        self,
        lo: datetime | None,
        hi: datetime | None,
        *,
        venue_id: UUID | None = None,
        category_id: UUID | None = None,
        owner_id: UUID | None = None,
    ) -> dict[str, Any]:
        conds = self.ledger_filters(lo, hi, venue_id, category_id, owner_id)
        L = LedgerEntry
        base = (
            select()
            .select_from(L)
            .outerjoin(BookingCommissionSnapshot, BookingCommissionSnapshot.booking_id == L.booking_id)
        )

        def sums(*extra: Any) -> Any:
            return base.add_columns(
                func.coalesce(func.sum(L.gross_paise).filter(L.kind == "sale"), 0),
                func.coalesce(-func.sum(L.gross_paise).filter(L.kind == "refund"), 0),
                func.coalesce(func.sum(L.gross_paise), 0),
                func.coalesce(func.sum(L.commission_paise).filter(L.kind == "sale"), 0),
                func.coalesce(-func.sum(L.commission_paise).filter(L.kind == "refund"), 0),
                func.coalesce(func.sum(L.commission_paise), 0),
                func.coalesce(func.sum(L.owner_amount_paise), 0),
                func.coalesce(func.sum(L.platform_amount_paise), 0),
                func.coalesce(func.sum(L.tax_paise), 0),
                func.count(func.distinct(L.booking_id)).filter(L.kind == "sale"),
                *extra,
            ).where(*conds)

        def pack(r: Any) -> dict[str, int]:
            keys = (
                "sales_gross_paise",
                "refunded_gross_paise",
                "net_gross_paise",
                "commission_accrued_paise",
                "commission_reversed_paise",
                "net_commission_paise",
                "owner_net_paise",
                "platform_net_paise",
                "tax_paise",
                "bookings",
            )
            return {k: int(r[i]) for i, k in enumerate(keys)}

        totals = pack((await self.s.execute(sums())).one())

        by_activity = []
        stmt = (
            sums(BookingCommissionSnapshot.category_id, Category.name)
            .outerjoin(Category, Category.id == BookingCommissionSnapshot.category_id)
            .group_by(BookingCommissionSnapshot.category_id, Category.name)
            .order_by(func.sum(L.commission_paise).desc())
        )
        for r in (await self.s.execute(stmt)).all():
            by_activity.append({"category_id": r[10], "category_name": r[11] or "No activity", **pack(r)})
        stmt = (
            sums(L.venue_id, Venue.name)
            .join(Venue, Venue.id == L.venue_id)
            .group_by(L.venue_id, Venue.name)
            .order_by(func.sum(L.commission_paise).desc())
        )
        by_venue = [
            {"venue_id": r[10], "venue_name": r[11], **pack(r)} for r in (await self.s.execute(stmt)).all()
        ]
        tzname = self.settings.admin_report_timezone if self.settings else "Asia/Kolkata"
        day = func.date(func.timezone(tzname, L.occurred_at)).label("day")
        stmt = sums(day).group_by(day).order_by(day)
        by_day = [{"date": r[10], **pack(r)} for r in (await self.s.execute(stmt)).all()]
        scope_col = func.coalesce(L.commission_scope, "legacy")
        stmt = sums(scope_col).group_by(scope_col)
        by_scope = [{"scope": r[10], **pack(r)} for r in (await self.s.execute(stmt)).all()]
        return {"totals": totals, "by_activity": by_activity, "by_venue": by_venue, "by_day": by_day,
                "by_scope": by_scope, "reconciliation": await self.reconcile(lo, hi, venue_id=venue_id, owner_id=owner_id)}  # fmt: skip

    async def reconcile(
        self,
        lo: datetime | None,
        hi: datetime | None,
        *,
        venue_id: UUID | None = None,
        owner_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Internal consistency checks that must hold for the commission totals to be trusted."""
        L = LedgerEntry
        lc: list[Any] = []
        if lo:
            lc.append(L.occurred_at >= lo)
        if hi:
            lc.append(L.occurred_at < hi)
        if venue_id:
            lc.append(L.venue_id == venue_id)
        if owner_id:
            lc.append(L.owner_id == owner_id)
        checks: list[dict[str, Any]] = []

        async def count(stmt: Any) -> int:
            return int(await self.s.scalar(stmt) or 0)

        # 1. every sale entry equals the captured payment it came from
        n = await count(
            select(func.count())
            .select_from(L)
            .join(Payment, Payment.id == L.payment_id)
            .where(L.kind == "sale", L.gross_paise != Payment.amount_paise, *lc)
        )
        checks.append(
            {
                "key": "sale_equals_payment",
                "label": "Ledger sale amount equals the captured payment",
                "mismatches": n,
                "ok": n == 0,
            }
        )
        # 2. refunds in the ledger equal the processed refund
        from app.models import Refund

        n = await count(
            select(func.count())
            .select_from(L)
            .join(Refund, Refund.id == L.refund_id)
            .where(L.kind == "refund", -L.gross_paise != Refund.amount_paise, *lc)
        )
        checks.append(
            {
                "key": "refund_equals_refund",
                "label": "Ledger refund amount equals the processed refund",
                "mismatches": n,
                "ok": n == 0,
            }
        )
        # 3. recompute commission from base x percentage (integer, half-up)
        n = await count(
            select(func.count())
            .select_from(L)
            .where(
                L.kind == "sale",
                L.commission_bps.is_not(None),
                L.commission_base_paise.is_not(None),
                L.commission_paise != func.div(L.commission_base_paise * L.commission_bps * 2 + 10000, 20000),
                *lc,
            )
        )
        checks.append(
            {
                "key": "commission_recomputes",
                "label": "Commission equals base × percentage (half-up)",
                "mismatches": n,
                "ok": n == 0,
            }
        )
        # 4. commission on the entry equals the booking's immutable snapshot
        n = await count(
            select(func.count())
            .select_from(L)
            .join(BookingCommissionSnapshot, BookingCommissionSnapshot.booking_id == L.booking_id)
            .where(
                L.commission_scope != "finance_config",
                L.commission_scope.is_not(None),
                or_(
                    L.commission_bps != BookingCommissionSnapshot.commission_bps,
                    L.commission_rule_id != BookingCommissionSnapshot.rule_id,
                ),
                *lc,
            )
        )
        checks.append(
            {
                "key": "entry_matches_snapshot",
                "label": "Ledger commission matches the booking's snapshot",
                "mismatches": n,
                "ok": n == 0,
            }
        )
        # 5. no booking has more than one sale entry (duplicate webhooks / retries)
        dup = (
            select(L.booking_id)
            .where(L.kind == "sale", *lc)
            .group_by(L.booking_id)
            .having(func.count() > 1)
            .subquery()
        )
        n = await count(select(func.count()).select_from(dup))
        checks.append(
            {
                "key": "no_duplicate_sales",
                "label": "At most one sale entry per booking",
                "mismatches": n,
                "ok": n == 0,
            }
        )
        # 6. captured payments still waiting for a ledger entry
        pc: list[Any] = [
            Payment.captured_at.is_not(None),
            ~select(L.id).where(L.entry_key == func.concat("sale:", Payment.id)).exists(),
        ]
        from app.domain import payment_state as pst

        pc.append(Payment.status.in_(tuple(pst.PAID)))
        if lo:
            pc.append(Payment.captured_at >= lo)
        if hi:
            pc.append(Payment.captured_at < hi)
        if venue_id:
            pc.append(Payment.venue_id == venue_id)
        if owner_id:
            pc.append(Payment.venue_id.in_(select(Venue.id).where(Venue.owner_id == owner_id)))
        n = await count(select(func.count()).select_from(Payment).where(*pc))
        checks.append(
            {
                "key": "uncovered_payments",
                "label": "Captured payments not yet in the ledger (run accrual)",
                "mismatches": n,
                "ok": n == 0,
                "informational": True,
            }
        )
        return {"ok": all(c["ok"] for c in checks if not c.get("informational")), "checks": checks}

    async def owner_name(self, owner_id: UUID) -> str | None:
        return await self.s.scalar(select(Profile.full_name).where(Profile.id == owner_id))

    # ================================================================== owner earnings (their own venues only)
    async def owner_earnings(
        self,
        owner_id: UUID,
        *,
        venue_id: UUID | None,
        lo: datetime | None,
        hi: datetime | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        """Booking-by-booking explanation of what the owner earns: customer paid -> court charge -> commission
        (percentage, rule, version) -> other deductions -> net payable. Read from the immutable ledger only.
        'Net payable' is an accounting figure: it does NOT mean money has been transferred."""
        from app.services.ledger import any_approved

        if not await any_approved(self.s):
            return {"available": False, "currency": "INR",
                    "reason": "Commission and net earnings appear once an approved fee and commission "
                              "configuration exists (open questions Q7, Q8).",
                    "totals": None, "items": [], "limit": limit, "offset": offset, "has_more": False}  # fmt: skip
        L = LedgerEntry
        conds: list[Any] = [L.owner_id == owner_id]
        if venue_id:
            conds.append(L.venue_id == venue_id)
        if lo:
            conds.append(L.occurred_at >= lo)
        if hi:
            conds.append(L.occurred_at < hi)
        tot = (
            await self.s.execute(
                select(
                    func.coalesce(func.sum(L.gross_paise).filter(L.kind == "sale"), 0),
                    func.coalesce(func.sum(L.commission_paise).filter(L.kind == "sale"), 0),
                    func.coalesce(func.sum(L.owner_amount_paise).filter(L.kind == "sale"), 0),
                    func.coalesce(-func.sum(L.gross_paise).filter(L.kind == "refund"), 0),
                    func.coalesce(-func.sum(L.commission_paise).filter(L.kind == "refund"), 0),
                    func.coalesce(-func.sum(L.owner_amount_paise).filter(L.kind == "refund"), 0),
                    func.coalesce(func.sum(L.owner_amount_paise), 0),
                    func.count().filter(L.kind == "sale"),
                ).where(*conds)
            )
        ).one()
        refunds = (
            select(L.booking_id.label("bid"), func.sum(-L.gross_paise).label("refunded"),
                   func.sum(-L.commission_paise).label("c_rev"), func.sum(-L.owner_amount_paise).label("o_rev"))
            .where(L.kind == "refund").group_by(L.booking_id).subquery()
        )  # fmt: skip
        rows = (
            await self.s.execute(
                select(L, Booking, Venue.name, refunds.c.refunded, refunds.c.c_rev, refunds.c.o_rev)
                .join(Booking, Booking.id == L.booking_id)
                .join(Venue, Venue.id == L.venue_id)
                .outerjoin(refunds, refunds.c.bid == L.booking_id)
                .where(L.kind == "sale", *conds)
                .order_by(L.occurred_at.desc(), L.id)
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        items = []
        for e, b, vname, refunded, c_rev, o_rev in rows[:limit]:
            snap = b.price_snapshot or {}
            court = int(snap.get("base_amount_paise", b.base_amount_paise))
            other = (
                court - e.commission_paise - e.owner_amount_paise
            )  # owner-borne discount, only when configured
            items.append({
                "booking_id": e.booking_id, "booking_code": b.booking_code, "venue_id": e.venue_id,
                "venue_name": vname, "resource_name": b.resource_name, "accrued_at": e.occurred_at,
                "customer_paid_paise": e.gross_paise, "court_charge_paise": court,
                "platform_fee_paise": e.fee_paise, "tax_paise": e.tax_paise, "discount_paise": e.discount_paise,
                "commission_base_paise": e.commission_base_paise, "commission_bps": e.commission_bps,
                "commission_pct": pct(e.commission_bps), "commission_paise": e.commission_paise,
                "other_deductions_paise": other, "net_payable_paise": e.owner_amount_paise,
                "refunded_paise": int(refunded or 0), "commission_reversed_paise": int(c_rev or 0),
                "net_after_refunds_paise": e.owner_amount_paise - int(o_rev or 0),
                "formula": (f"{pct(e.commission_bps)} of the commission base ({e.commission_base_paise} paise), "
                            "rounded half-up to the paisa" if e.commission_bps is not None and e.commission_base_paise is not None
                            else "Calculated before commission details were recorded."),
            })  # fmt: skip
        return {
            "available": True, "currency": "INR",
            "note": "Net payable is what ZURUV owes you for these bookings. It is a record, not a transfer: "
                    "payouts are handled separately.",
            "totals": {"customer_paid_paise": int(tot[0]), "commission_paise": int(tot[1]),
                       "net_payable_paise": int(tot[2]), "refunded_paise": int(tot[3]),
                       "commission_reversed_paise": int(tot[4]), "net_after_refunds_paise": int(tot[6]),
                       "bookings": int(tot[7])},
            "items": items, "limit": limit, "offset": offset, "has_more": len(rows) > limit,
        }  # fmt: skip

    async def owner_current_rates(self, owner_id: UUID) -> list[dict[str, Any]]:
        """The percentage that applies to a NEW booking at each of the owner's venues right now."""
        venues = (
            await self.s.execute(
                select(Venue.id, Venue.name).where(Venue.owner_id == owner_id).order_by(Venue.name)
            )
        ).all()
        out = []
        for vid, name in venues:
            r = await self.resolve(vid)
            sel = next((c for c in r["candidates"] if c["selected"]), None)
            out.append({"venue_id": vid, "venue_name": name, "scope": r["scope"],
                        "commission_bps": r["commission_bps"], "commission_pct": pct(r["commission_bps"]),
                        "rule_version": r["rule_version"], "selected": sel})  # fmt: skip
        return out
