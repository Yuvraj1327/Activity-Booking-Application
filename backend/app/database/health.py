"""Database connectivity check used by GET /health."""

import asyncio
import logging
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text

from app.database.session import Database

logger = logging.getLogger(__name__)

DatabaseState = Literal["not_configured", "ok", "unavailable"]


class DatabaseHealth(BaseModel):
    status: DatabaseState
    latency_ms: float | None = None


async def check_database(db: Database, timeout_seconds: float) -> DatabaseHealth:
    """Never reports "ok" unless a real `SELECT 1` succeeded."""
    if db.engine is None:
        return DatabaseHealth(status="not_configured")

    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        async with asyncio.timeout(timeout_seconds):
            async with db.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any failure means unavailable
        logger.warning("database_health_failed", extra={"error_type": type(exc).__name__})
        return DatabaseHealth(status="unavailable")
    return DatabaseHealth(status="ok", latency_ms=round((loop.time() - started) * 1000, 2))
