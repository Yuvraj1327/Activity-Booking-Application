"""Financial reconciliation: our records against each other, and against Razorpay when it is reachable.

A run never changes money or payment state. It only records what does not match, so a human can
decide. When the gateway cannot be reached (or is not configured) the run says so and reports the
internal checks only: it never pretends a gateway comparison happened.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import Settings
from app.core.errors import NotFoundError, ServiceUnavailableError, ValidationFailedError
from app.domain import payment_state as pst
from app.gateways.razorpay import PaymentGateway
from app.models import LedgerEntry, Payment, ReconciliationItem, ReconciliationRun, Refund
from app.services import audit
from app.services.ledger import active_config

logger = logging.getLogger(__name__)
MAX_DAYS = 93
MAX_REFUND_CHECKS = 200


def _bounds(settings: Settings, start: date, end: date) -> tuple[datetime, datetime]:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(settings.admin_report_timezone)
    lo = datetime.combine(start, datetime.min.time(), tzinfo=tz).astimezone(UTC)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=tz).astimezone(UTC)
    return lo, hi


class ReconciliationService:
    def __init__(self, session: AsyncSession, settings: Settings, gateway: PaymentGateway) -> None:
        self.s = session
        self.settings = settings
        self.gw = gateway

    async def run(self, actor: CurrentUser, start: date, end: date) -> dict[str, Any]:
        if start > end:
            raise ValidationFailedError("date_from must not be after date_to.", code="INVALID_RANGE")
        if (end - start).days + 1 > MAX_DAYS:
            raise ValidationFailedError(f"At most {MAX_DAYS} days per run.", code="RANGE_TOO_LARGE")
        lo, hi = _bounds(self.settings, start, end)
        items: list[dict[str, Any]] = []
        summary: dict[str, Any] = {}

        pays = (
            await self.s.scalars(select(Payment).where(Payment.created_at >= lo, Payment.created_at < hi))
        ).all()
        paid = [p for p in pays if p.status in pst.PAID]
        summary["db_payments"] = len(pays)
        summary["db_captured"] = len(paid)
        summary["db_captured_paise"] = sum(p.amount_paise for p in paid)

        # ---- internal: ledger vs payments, refunds vs payment status
        ledger_sums = dict(
            (
                await self.s.execute(
                    select(LedgerEntry.payment_id, func.sum(LedgerEntry.gross_paise))
                    .where(LedgerEntry.payment_id.in_([p.id for p in paid] or [UUID(int=0)]))
                    .group_by(LedgerEntry.payment_id)
                )
            ).all()
        )
        refund_sums = dict(
            (
                await self.s.execute(
                    select(Refund.payment_id, func.sum(Refund.amount_paise))
                    .where(
                        Refund.status == "processed",
                        Refund.payment_id.in_([p.id for p in paid] or [UUID(int=0)]),
                    )
                    .group_by(Refund.payment_id)
                )
            ).all()
        )
        for p in paid:
            refunded = int(refund_sums.get(p.id, 0))
            if p.status == pst.REFUNDED and refunded != p.amount_paise:
                items.append(
                    self._item(
                        "refund_mismatch",
                        p,
                        p.amount_paise,
                        refunded,
                        "Payment is marked refunded but processed refunds differ.",
                    )
                )
            if p.status == pst.PARTIALLY_REFUNDED and not (0 < refunded < p.amount_paise):
                items.append(
                    self._item(
                        "refund_mismatch",
                        p,
                        None,
                        refunded,
                        "Payment is marked partially refunded but refunds do not match.",
                    )
                )
            cfg = await active_config(self.s, p.captured_at) if p.captured_at else None
            if p.id not in ledger_sums:
                if cfg is not None:
                    items.append(
                        self._item(
                            "ledger_missing",
                            p,
                            p.amount_paise,
                            None,
                            "Captured under an approved configuration but not in the ledger. Run accrual.",
                        )
                    )
            elif int(ledger_sums[p.id]) != p.amount_paise - refunded:
                items.append(
                    self._item(
                        "ledger_mismatch",
                        p,
                        p.amount_paise - refunded,
                        int(ledger_sums[p.id]),
                        "Ledger total differs from amount paid minus processed refunds (run accrual if refunds are new).",
                    )
                )
        stuck_cut = datetime.now(UTC) - timedelta(days=1)
        for r in (
            await self.s.scalars(
                select(Refund).where(
                    Refund.status.in_(("requested", "pending", "uncertain")), Refund.created_at < stuck_cut
                )
            )
        ).all():
            items.append(
                {"kind": "refund_stuck", "payment_id": r.payment_id, "refund_id": r.id, "provider_payment_id": None,
                 "expected_paise": r.amount_paise, "actual_paise": None,
                 "detail": f"Refund has been '{r.status}' for more than a day."}
            )  # fmt: skip

        # ---- gateway comparison
        gateway_checked, note = False, None
        if not self.gw.configured:
            note = "Razorpay is not configured on the server: only internal checks were run."
        else:
            try:
                gps = await self.gw.list_payments_between(int(lo.timestamp()), int(hi.timestamp()) - 1)
                gateway_checked = True
            except ServiceUnavailableError:
                note = "Razorpay could not be reached: only internal checks were run."
        if gateway_checked:
            by_pid = {p.provider_payment_id: p for p in pays if p.provider_payment_id}
            g_captured = {g.id: g for g in gps if g.status in ("captured", "refunded")}
            summary["gateway_captured"] = len(g_captured)
            summary["gateway_captured_paise"] = sum(g.amount_paise for g in g_captured.values())
            for gid, g in g_captured.items():
                p = by_pid.get(gid)
                if p is None:
                    items.append({"kind": "missing_in_database", "payment_id": None, "refund_id": None, "provider_payment_id": gid,
                                  "expected_paise": None, "actual_paise": g.amount_paise,
                                  "detail": "Captured at Razorpay but no matching payment record."})  # fmt: skip
                elif g.amount_paise != p.amount_paise:
                    items.append(
                        self._item(
                            "amount_mismatch",
                            p,
                            p.amount_paise,
                            g.amount_paise,
                            "Amount differs from Razorpay.",
                        )
                    )
                elif p.status not in pst.PAID:
                    items.append(
                        self._item(
                            "status_mismatch",
                            p,
                            p.amount_paise,
                            g.amount_paise,
                            f"Razorpay says captured; we have '{p.status}'.",
                        )
                    )
            for p in paid:
                if p.provider_payment_id and p.provider_payment_id not in g_captured:
                    items.append(
                        self._item(
                            "missing_in_gateway",
                            p,
                            p.amount_paise,
                            None,
                            "Recorded as captured but Razorpay does not list it as captured.",
                        )
                    )
            # refunds: compare processed totals for payments that have refunds on our side
            with_refunds = [p for p in paid if p.id in refund_sums][:MAX_REFUND_CHECKS]
            for p in with_refunds:
                try:
                    grs = await self.gw.fetch_payment_refunds(p.provider_payment_id or "")
                except ServiceUnavailableError:
                    note = (note or "") + " Some refund checks were skipped (gateway error)."
                    break
                g_total = sum(r.amount_paise for r in grs if r.status == "processed")
                if g_total != int(refund_sums[p.id]):
                    items.append(
                        self._item(
                            "refund_mismatch",
                            p,
                            int(refund_sums[p.id]),
                            g_total,
                            "Processed refund total differs from Razorpay.",
                        )
                    )
            summary["refund_payments_checked"] = len(with_refunds)

        run = ReconciliationRun(
            period_from=start, period_to=end, gateway_checked=gateway_checked, gateway_note=note,
            summary=summary, mismatch_count=len(items), run_by=actor.id,
        )  # fmt: skip
        self.s.add(run)
        await self.s.flush()
        for it in items:
            self.s.add(ReconciliationItem(run_id=run.id, **it))
        audit.record(self.s, actor.profile, "admin.reconciliation_run", "reconciliation_run", run.id,
                     after={"mismatches": len(items), "gateway_checked": gateway_checked},
                     period_from=start, period_to=end)  # fmt: skip
        await self.s.commit()
        return await self.get(run.id)

    @staticmethod
    def _item(kind: str, p: Payment, expected: int | None, actual: int | None, detail: str) -> dict[str, Any]:
        return {"kind": kind, "payment_id": p.id, "refund_id": None, "provider_payment_id": p.provider_payment_id,
                "expected_paise": expected, "actual_paise": actual, "detail": detail}  # fmt: skip

    @staticmethod
    def _run_out(r: ReconciliationRun) -> dict[str, Any]:
        return {"id": r.id, "period_from": r.period_from, "period_to": r.period_to, "gateway_checked": r.gateway_checked,
                "gateway_note": r.gateway_note, "summary": r.summary, "mismatch_count": r.mismatch_count,
                "created_at": r.created_at}  # fmt: skip

    async def get(self, run_id: UUID) -> dict[str, Any]:
        r = await self.s.get(ReconciliationRun, run_id)
        if r is None:
            raise NotFoundError("Reconciliation run not found.", code="RUN_NOT_FOUND")
        items = (
            await self.s.scalars(
                select(ReconciliationItem)
                .where(ReconciliationItem.run_id == run_id)
                .order_by(ReconciliationItem.kind, ReconciliationItem.created_at)
            )
        ).all()
        return {
            **self._run_out(r),
            "items": [
                {"id": i.id, "kind": i.kind, "payment_id": i.payment_id, "refund_id": i.refund_id,
                 "provider_payment_id": i.provider_payment_id, "expected_paise": i.expected_paise,
                 "actual_paise": i.actual_paise, "detail": i.detail}
                for i in items
            ],
        }  # fmt: skip

    async def list_runs(self, limit: int, offset: int) -> dict[str, Any]:
        rows = (
            await self.s.scalars(
                select(ReconciliationRun)
                .order_by(ReconciliationRun.created_at.desc())
                .limit(limit + 1)
                .offset(offset)
            )
        ).all()
        return {
            "items": [self._run_out(r) for r in rows[:limit]],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }
