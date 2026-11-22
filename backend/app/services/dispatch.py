"""Post-commit delivery and the lightweight in-process housekeeping loop (no Redis / Celery).

Why this is enough for now: notifications and emails are written to the database in the same
transaction as the business change (an outbox). Delivery happens right after the response via a
FastAPI background task, and a single asyncio loop in each API process retries anything left over
and reconciles payments the gateway confirmed while we were not looking. Several API instances are
safe: every claim uses FOR UPDATE SKIP LOCKED. When volume or latency demands it, this loop can be
replaced by a real worker without touching the callers.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from fastapi import FastAPI

from app.services.bookings import BookingService
from app.services.ledger import FinanceService, any_approved
from app.services.notifications import dispatch_all
from app.services.payments import PaymentService
from app.services.refunds import RefundService

logger = logging.getLogger(__name__)


async def dispatch_in_background(app: FastAPI) -> None:
    """Called after the response is sent. Failures are logged and never raised."""
    db = app.state.db
    if not db.configured:
        return
    try:
        async for session in db.session():
            await dispatch_all(session, app.state.push_sender, app.state.email_sender)
    except Exception:
        logger.exception("background_dispatch_failed")


async def sweep_once(app: FastAPI) -> None:
    db = app.state.db
    if not db.configured:
        return
    status = {"last_run_at": datetime.now(UTC), "last_ok": True}
    app.state.sweep_status = status
    async for session in db.session():
        try:
            await BookingService(session, app.state.settings).settle_due()
            await session.commit()
            await PaymentService(session, app.state.settings, app.state.payment_gateway).reconcile_open()
            if app.state.payment_gateway.configured:
                await RefundService(session, app.state.settings, app.state.payment_gateway).reconcile_stuck()
            if await any_approved(session):  # keeps the ledger current; a no-op until a rule is approved
                await FinanceService(session).accrue()
        except Exception:
            logger.exception("sweep_failed")
            status["last_ok"] = False
            await session.rollback()
    await dispatch_in_background(app)


async def sweep_loop(app: FastAPI, interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        with contextlib.suppress(Exception):
            await sweep_once(app)
