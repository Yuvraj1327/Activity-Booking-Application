"""Finance configuration (versioned), the immutable ledger, owner balances and payouts.

Nothing here invents a rule: with no APPROVED configuration there are no ledger entries, owner
earnings are "not available", and no payout can be created. The ledger is append-only (database
trigger); a refund adds a negative entry, a sale is never edited.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.domain import payment_state as pst
from app.domain.finance_math import Rules, reversal, split_sale
from app.models import (
    Booking,
    FinanceConfig,
    LedgerEntry,
    OwnerProfile,
    Payment,
    Payout,
    Profile,
    Refund,
    Venue,
)
from app.services import audit, platform_settings

logger = logging.getLogger(__name__)


def rules_of(c: FinanceConfig) -> Rules:
    return Rules(
        c.platform_fee_bps, c.platform_fee_fixed_paise, c.tax_rate_bps, c.tax_on, c.commission_bps,
        c.discount_borne_by,
    )  # fmt: skip


def config_out(c: FinanceConfig) -> dict[str, Any]:
    return {
        "id": c.id, "version": c.version, "status": c.status, "platform_fee_bps": c.platform_fee_bps,
        "platform_fee_fixed_paise": c.platform_fee_fixed_paise, "tax_rate_bps": c.tax_rate_bps,
        "tax_on": c.tax_on, "commission_bps": c.commission_bps, "discount_borne_by": c.discount_borne_by,
        "notes": c.notes, "created_at": c.created_at, "approved_at": c.approved_at,
        "effective_from": c.effective_from, "retired_at": c.retired_at,
    }  # fmt: skip


async def active_config(session: AsyncSession, at: datetime | None = None) -> FinanceConfig | None:
    """The approved configuration in force at `at` (default now), or None: then NOTHING is computed."""
    at = at or datetime.now(UTC)
    return await session.scalar(
        select(FinanceConfig)
        .where(FinanceConfig.status.in_(("approved", "retired")), FinanceConfig.effective_from <= at)
        .order_by(FinanceConfig.effective_from.desc())
        .limit(1)
    )


async def any_approved(session: AsyncSession) -> bool:
    return bool(await session.scalar(select(func.count()).where(FinanceConfig.status != "draft")))


class FinanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    # ================================================================== configuration
    async def list_configs(self) -> list[dict[str, Any]]:
        rows = (await self.s.scalars(select(FinanceConfig).order_by(FinanceConfig.version.desc()))).all()
        return [config_out(c) for c in rows]

    async def create_draft(self, actor: CurrentUser, body: dict[str, Any]) -> dict[str, Any]:
        c = FinanceConfig(**body, created_by=actor.id)
        self.s.add(c)
        await self.s.flush()
        await self.s.refresh(c)
        audit.record(
            self.s, actor.profile, "admin.finance_config_drafted", "finance_config", c.id, after=config_out(c)
        )
        await self.s.commit()
        return config_out(c)

    async def delete_draft(self, actor: CurrentUser, config_id: UUID) -> None:
        c = await self.s.scalar(select(FinanceConfig).where(FinanceConfig.id == config_id).with_for_update())
        if c is None:
            raise NotFoundError("Configuration not found.", code="CONFIG_NOT_FOUND")
        if c.status != "draft":
            raise ConflictError("Only a draft can be deleted.", code="CONFIG_NOT_DRAFT")
        audit.record(
            self.s,
            actor.profile,
            "admin.finance_config_deleted",
            "finance_config",
            c.id,
            before=config_out(c),
        )
        await self.s.delete(c)
        await self.s.commit()

    async def approve(self, actor: CurrentUser, config_id: UUID, reason: str) -> dict[str, Any]:
        """Approval makes the rules binding from now on. It cannot be undone or edited: supersede it."""
        c = await self.s.scalar(select(FinanceConfig).where(FinanceConfig.id == config_id).with_for_update())
        if c is None:
            raise NotFoundError("Configuration not found.", code="CONFIG_NOT_FOUND")
        if c.status != "draft":
            raise ConflictError("This configuration is already approved.", code="CONFIG_NOT_DRAFT")
        if c.created_by == actor.id:
            raise ConflictError(
                "A different administrator must approve a configuration you drafted (four-eyes rule).",
                code="APPROVER_MUST_DIFFER",
            )
        now = datetime.now(UTC)
        prev = await active_config(self.s, now)
        before = config_out(c)
        c.status = "approved"
        c.approved_by = actor.id
        c.approved_at = now
        c.effective_from = now
        if prev is not None and prev.status == "approved":
            prev.status = "retired"
            prev.retired_at = now
        await self.s.flush()
        audit.record(self.s, actor.profile, "admin.finance_config_approved", "finance_config", c.id,
                     before=before, after=config_out(c), reason=reason,
                     superseded_version=prev.version if prev else None)  # fmt: skip
        await self.s.commit()
        return config_out(c)

    # ================================================================== accrual
    async def accrue(self, limit: int = 1000) -> dict[str, int]:
        """Write ledger entries for captured payments and processed refunds that have none yet.
        Idempotent: each entry has a unique key, so running it twice changes nothing."""
        sales = refunds = skipped = 0
        pays = (
            await self.s.execute(
                select(Payment, Booking, Venue.owner_id)
                .join(Booking, Booking.id == Payment.booking_id)
                .join(Venue, Venue.id == Payment.venue_id)
                .where(
                    Payment.status.in_(tuple(pst.PAID)),
                    Payment.captured_at.is_not(None),
                    ~select(LedgerEntry.id)
                    .where(LedgerEntry.entry_key == func.concat("sale:", Payment.id))
                    .exists(),
                )
                .order_by(Payment.captured_at)
                .limit(limit)
            )
        ).all()
        for p, b, owner_id in pays:
            cfg = await active_config(self.s, p.captured_at)
            if cfg is None:
                skipped += 1
                continue
            snap = b.price_snapshot or {}
            try:
                sp = split_sale(
                    p.amount_paise, int(snap.get("base_amount_paise", b.base_amount_paise)),
                    int(snap.get("fees_paise", 0)), int(snap.get("tax_paise", 0)),
                    int(snap.get("discount_paise", 0)), rules_of(cfg),
                )  # fmt: skip
            except ValueError:
                logger.warning("ledger_price_mismatch", extra={"payment_id": str(p.id)})
                skipped += 1
                continue
            if await self._insert(
                LedgerEntry(
                    entry_key=f"sale:{p.id}",
                    kind="sale",
                    owner_id=owner_id,
                    venue_id=p.venue_id,
                    booking_id=p.booking_id,
                    payment_id=p.id,
                    config_id=cfg.id,
                    config_version=cfg.version,
                    gross_paise=sp.gross,
                    tax_paise=sp.tax,
                    owner_amount_paise=sp.owner,
                    platform_amount_paise=sp.platform,
                    fee_paise=sp.fee,
                    commission_paise=sp.commission,
                    discount_paise=sp.discount,
                    occurred_at=p.captured_at,
                )
            ):
                sales += 1
        refs = (
            await self.s.scalars(
                select(Refund)
                .where(
                    Refund.status == "processed",
                    ~select(LedgerEntry.id)
                    .where(LedgerEntry.entry_key == func.concat("refund:", Refund.id))
                    .exists(),
                )
                .order_by(Refund.processed_at, Refund.id)
                .limit(limit)
            )
        ).all()
        for r in refs:
            sale = await self.s.scalar(
                select(LedgerEntry).where(LedgerEntry.entry_key == f"sale:{r.payment_id}")
            )
            if sale is None:
                skipped += 1
                continue
            earlier = int(
                await self.s.scalar(
                    select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                        Refund.payment_id == r.payment_id,
                        Refund.status == "processed",
                        (Refund.processed_at < r.processed_at)
                        | ((Refund.processed_at == r.processed_at) & (Refund.id < r.id)),
                    )
                )
                or 0
            )
            o1, t1, p1 = reversal(sale.gross_paise, sale.owner_amount_paise, sale.tax_paise, earlier)
            o2, t2, p2 = reversal(
                sale.gross_paise, sale.owner_amount_paise, sale.tax_paise, earlier + r.amount_paise
            )
            ratio_fee = (sale.fee_paise * (earlier + r.amount_paise)) // max(sale.gross_paise, 1) - (
                sale.fee_paise * earlier
            ) // max(sale.gross_paise, 1)
            ratio_com = (sale.commission_paise * (earlier + r.amount_paise)) // max(sale.gross_paise, 1) - (
                sale.commission_paise * earlier
            ) // max(sale.gross_paise, 1)
            if await self._insert(
                LedgerEntry(
                    entry_key=f"refund:{r.id}",
                    kind="refund",
                    owner_id=sale.owner_id,
                    venue_id=sale.venue_id,
                    booking_id=sale.booking_id,
                    payment_id=sale.payment_id,
                    refund_id=r.id,
                    config_id=sale.config_id,
                    config_version=sale.config_version,
                    gross_paise=-r.amount_paise,
                    tax_paise=-(t2 - t1),
                    owner_amount_paise=-(o2 - o1),
                    platform_amount_paise=-(p2 - p1),
                    fee_paise=-ratio_fee,
                    commission_paise=-ratio_com,
                    discount_paise=0,
                    occurred_at=r.processed_at or datetime.now(UTC),
                )
            ):
                refunds += 1
        await self.s.commit()
        return {"sales": sales, "refunds": refunds, "skipped_no_rule_or_no_sale": skipped}

    async def _insert(self, e: LedgerEntry) -> bool:
        try:
            async with self.s.begin_nested():
                self.s.add(e)
                await self.s.flush()
            return True
        except IntegrityError:
            return False

    # ================================================================== reads
    async def totals(
        self,
        lo: datetime | None,
        hi: datetime | None,
        *,
        owner_id: UUID | None = None,
        venue_id: UUID | None = None,
    ) -> dict[str, int]:
        stmt = select(
            func.coalesce(func.sum(LedgerEntry.gross_paise), 0),
            func.coalesce(func.sum(LedgerEntry.owner_amount_paise), 0),
            func.coalesce(func.sum(LedgerEntry.platform_amount_paise), 0),
            func.coalesce(func.sum(LedgerEntry.tax_paise), 0),
            func.coalesce(func.sum(LedgerEntry.gross_paise).filter(LedgerEntry.kind == "sale"), 0),
            func.coalesce(-func.sum(LedgerEntry.gross_paise).filter(LedgerEntry.kind == "refund"), 0),
            func.count(),
        )
        if lo:
            stmt = stmt.where(LedgerEntry.occurred_at >= lo)
        if hi:
            stmt = stmt.where(LedgerEntry.occurred_at < hi)
        if owner_id:
            stmt = stmt.where(LedgerEntry.owner_id == owner_id)
        if venue_id:
            stmt = stmt.where(LedgerEntry.venue_id == venue_id)
        g, o, p, t, sales, refunds, n = (await self.s.execute(stmt)).one()
        return {"net_gross": int(g), "owner": int(o), "platform": int(p), "tax": int(t),
                "sales": int(sales), "refunds": int(refunds), "entries": int(n)}  # fmt: skip

    async def coverage(self, lo: datetime | None, hi: datetime | None) -> dict[str, int]:
        stmt = select(func.count()).where(
            Payment.status.in_(tuple(pst.PAID)), Payment.captured_at.is_not(None)
        )
        if lo:
            stmt = stmt.where(Payment.captured_at >= lo)
        if hi:
            stmt = stmt.where(Payment.captured_at < hi)
        total = int(await self.s.scalar(stmt) or 0)
        covered = int(
            await self.s.scalar(
                stmt.where(
                    select(LedgerEntry.id)
                    .where(LedgerEntry.entry_key == func.concat("sale:", Payment.id))
                    .exists()
                )
            )
            or 0
        )
        return {
            "captured_payments": total,
            "with_ledger_entry": covered,
            "without_ledger_entry": total - covered,
        }

    async def ledger_page(
        self,
        *,
        owner_id: UUID | None,
        kind: str | None,
        lo: datetime | None,
        hi: datetime | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        stmt = (
            select(LedgerEntry, Booking.booking_code, Venue.name, Profile.full_name)
            .join(Booking, Booking.id == LedgerEntry.booking_id)
            .join(Venue, Venue.id == LedgerEntry.venue_id)
            .join(Profile, Profile.id == LedgerEntry.owner_id)
        )
        if owner_id:
            stmt = stmt.where(LedgerEntry.owner_id == owner_id)
        if kind:
            stmt = stmt.where(LedgerEntry.kind == kind)
        if lo:
            stmt = stmt.where(LedgerEntry.occurred_at >= lo)
        if hi:
            stmt = stmt.where(LedgerEntry.occurred_at < hi)
        rows = (
            await self.s.execute(
                stmt.order_by(LedgerEntry.occurred_at.desc(), LedgerEntry.id).limit(limit + 1).offset(offset)
            )
        ).all()
        return {
            "items": [
                {"id": e.id, "kind": e.kind, "booking_id": e.booking_id, "booking_code": code, "venue_name": v,
                 "owner_id": e.owner_id, "owner_name": o, "payment_id": e.payment_id, "refund_id": e.refund_id,
                 "config_version": e.config_version, "gross_paise": e.gross_paise, "tax_paise": e.tax_paise,
                 "owner_amount_paise": e.owner_amount_paise, "platform_amount_paise": e.platform_amount_paise,
                 "fee_paise": e.fee_paise, "commission_paise": e.commission_paise, "discount_paise": e.discount_paise,
                 "occurred_at": e.occurred_at}
                for e, code, v, o in rows[:limit]
            ],
            "limit": limit, "offset": offset, "has_more": len(rows) > limit,
        }  # fmt: skip

    # ================================================================== owner balance and payouts
    async def owner_balance(self, owner_id: UUID) -> dict[str, Any]:
        if not await any_approved(self.s):
            return {"available": False, "reason": "No approved finance configuration yet (Q7, Q8)."}
        earned = int(
            await self.s.scalar(
                select(func.coalesce(func.sum(LedgerEntry.owner_amount_paise), 0)).where(
                    LedgerEntry.owner_id == owner_id
                )
            )
            or 0
        )
        rows = dict(
            (
                await self.s.execute(
                    select(Payout.status, func.coalesce(func.sum(Payout.amount_paise), 0))
                    .where(Payout.owner_id == owner_id)
                    .group_by(Payout.status)
                )
            ).all()
        )
        committed = sum(int(rows.get(s, 0)) for s in ("draft", "approved", "paid"))
        return {
            "available": True, "earned_paise": earned, "paid_paise": int(rows.get("paid", 0)),
            "reserved_paise": int(rows.get("draft", 0)) + int(rows.get("approved", 0)),
            "payable_paise": earned - committed,
        }  # fmt: skip

    @staticmethod
    def payout_out(p: Payout, owner_name: str | None = None) -> dict[str, Any]:
        return {
            "id": p.id, "owner_id": p.owner_id, "owner_name": owner_name, "amount_paise": p.amount_paise,
            "currency": p.currency, "status": p.status, "period_from": p.period_from, "period_to": p.period_to,
            "method": p.method, "reference": p.reference, "note": p.note, "approved_at": p.approved_at,
            "paid_at": p.paid_at, "cancel_reason": p.cancel_reason, "created_at": p.created_at,
        }  # fmt: skip

    async def _guard_payouts(self) -> None:
        if not await platform_settings.get(self.s, "payouts_enabled"):
            raise ConflictError(
                "Payouts are switched off until the payout rules (Q10) are approved and an administrator "
                "with settings permission enables them. Automatic gateway payouts are not integrated.",
                code="PAYOUTS_DISABLED",
            )

    async def create_payout(
        self,
        actor: CurrentUser,
        owner_id: UUID,
        amount: int,
        period_from: Any,
        period_to: Any,
        note: str | None,
    ) -> dict[str, Any]:
        await self._guard_payouts()
        owner = await self.s.scalar(
            select(OwnerProfile).where(OwnerProfile.user_id == owner_id).with_for_update()
        )
        if owner is None:
            raise NotFoundError("Owner not found.", code="OWNER_NOT_FOUND")
        if await platform_settings.get(self.s, "payout_requires_kyc") and owner.kyc_status != "verified":
            raise ConflictError("The owner's KYC is not verified.", code="OWNER_KYC_REQUIRED")
        prof = await self.s.get(Profile, owner_id)
        if prof is None or prof.status != "active":
            raise ConflictError("The owner's account is not active.", code="OWNER_NOT_ACTIVE")
        bal = await self.owner_balance(owner_id)
        if not bal["available"]:
            raise ConflictError(bal["reason"], code="FINANCE_NOT_APPROVED")
        if amount > bal["payable_paise"]:
            raise ValidationFailedError(
                f"The amount exceeds the payable balance of {bal['payable_paise']} paise.",
                code="AMOUNT_EXCEEDS_BALANCE",
            )
        if period_from and period_to and period_from > period_to:
            raise ValidationFailedError("period_from must not be after period_to.", code="INVALID_RANGE")
        p = Payout(owner_id=owner_id, amount_paise=amount, period_from=period_from, period_to=period_to,
                   note=note, created_by=actor.id)  # fmt: skip
        self.s.add(p)
        await self.s.flush()
        audit.record(self.s, actor.profile, "admin.payout_created", "payout", p.id, before={"payable_paise": bal["payable_paise"]},
                     after={"status": "draft", "amount_paise": amount}, owner_id=str(owner_id))  # fmt: skip
        await self.s.commit()
        return self.payout_out(p, prof.full_name)

    async def _payout(self, payout_id: UUID) -> Payout:
        p = await self.s.scalar(select(Payout).where(Payout.id == payout_id).with_for_update())
        if p is None:
            raise NotFoundError("Payout not found.", code="PAYOUT_NOT_FOUND")
        return p

    async def approve_payout(self, actor: CurrentUser, payout_id: UUID) -> dict[str, Any]:
        await self._guard_payouts()
        p = await self._payout(payout_id)
        if p.status != "draft":
            raise ConflictError("Only a draft payout can be approved.", code="PAYOUT_NOT_DRAFT")
        if p.created_by == actor.id:
            raise ConflictError(
                "A different administrator must approve this payout.", code="APPROVER_MUST_DIFFER"
            )
        p.status, p.approved_by, p.approved_at = "approved", actor.id, datetime.now(UTC)
        audit.record(self.s, actor.profile, "admin.payout_approved", "payout", p.id, before={"status": "draft"},
                     after={"status": "approved"}, amount_paise=p.amount_paise)  # fmt: skip
        await self.s.commit()
        return self.payout_out(p)

    async def mark_paid(
        self, actor: CurrentUser, payout_id: UUID, method: str, reference: str
    ) -> dict[str, Any]:
        """RECORDS that money was sent outside this system (bank / UPI). No gateway payout is made."""
        await self._guard_payouts()
        p = await self._payout(payout_id)
        if p.status != "approved":
            raise ConflictError("Only an approved payout can be marked paid.", code="PAYOUT_NOT_APPROVED")
        p.status, p.method, p.reference = "paid", method, reference
        p.paid_by, p.paid_at = actor.id, datetime.now(UTC)
        audit.record(self.s, actor.profile, "admin.payout_paid", "payout", p.id, before={"status": "approved"},
                     after={"status": "paid", "method": method, "reference": reference})  # fmt: skip
        await self.s.commit()
        return self.payout_out(p)

    async def cancel_payout(self, actor: CurrentUser, payout_id: UUID, reason: str) -> dict[str, Any]:
        p = await self._payout(payout_id)
        if p.status not in ("draft", "approved"):
            raise ConflictError(
                "A paid or cancelled payout cannot be cancelled.", code="PAYOUT_NOT_CANCELLABLE"
            )
        before = p.status
        p.status, p.cancel_reason = "cancelled", reason
        audit.record(self.s, actor.profile, "admin.payout_cancelled", "payout", p.id, before={"status": before},
                     after={"status": "cancelled"}, reason=reason)  # fmt: skip
        await self.s.commit()
        return self.payout_out(p)

    async def list_payouts(
        self, *, owner_id: UUID | None, status: str | None, limit: int, offset: int
    ) -> dict[str, Any]:
        stmt = select(Payout, Profile.full_name).join(Profile, Profile.id == Payout.owner_id)
        if owner_id:
            stmt = stmt.where(Payout.owner_id == owner_id)
        if status:
            stmt = stmt.where(Payout.status == status)
        rows = (
            await self.s.execute(
                stmt.order_by(Payout.created_at.desc(), Payout.id).limit(limit + 1).offset(offset)
            )
        ).all()
        return {
            "items": [self.payout_out(p, n) for p, n in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }
