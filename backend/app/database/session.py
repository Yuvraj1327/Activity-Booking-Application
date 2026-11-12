"""Async SQLAlchemy engine and session management.

The engine is created lazily and only when DATABASE_URL is configured. Nothing here
connects to the database at import time or at application start.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.errors import ServiceUnavailableError

logger = logging.getLogger(__name__)


def to_async_url(url: str) -> str:
    """Normalise a Supabase/Postgres URL to the asyncpg driver."""
    parsed = make_url(url)
    if parsed.drivername in ("postgres", "postgresql"):
        parsed = parsed.set(drivername="postgresql+asyncpg")
    return parsed.render_as_string(hide_password=False)


def to_sync_url(url: str) -> str:
    """Return the URL with the asyncpg driver (Alembic runs async too); kept for clarity."""
    return to_async_url(url)


def create_engine_from_settings(settings: Settings) -> AsyncEngine | None:
    if settings.database_url is None:
        return None
    url = to_async_url(settings.database_url.get_secret_value())
    connect_args: dict[str, Any] = {
        "timeout": settings.db_connect_timeout,
        "statement_cache_size": settings.db_statement_cache_size,
        "server_settings": {"application_name": "zuruv-api"},
    }
    kwargs: dict[str, Any] = {"connect_args": connect_args, "pool_pre_ping": True}
    if settings.db_use_nullpool:
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=1800,
        )
    return create_async_engine(url, **kwargs)


class Database:
    """Holds the engine and session factory for the application's lifetime."""

    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine | None = create_engine_from_settings(settings)
        self.sessionmaker: async_sessionmaker[AsyncSession] | None = (
            async_sessionmaker(self.engine, expire_on_commit=False) if self.engine else None
        )

    @property
    def configured(self) -> bool:
        return self.engine is not None

    async def dispose(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()

    async def session(self) -> AsyncIterator[AsyncSession]:
        if self.sessionmaker is None:
            raise ServiceUnavailableError("Database is not configured.", code="DATABASE_NOT_CONFIGURED")
        async with self.sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
