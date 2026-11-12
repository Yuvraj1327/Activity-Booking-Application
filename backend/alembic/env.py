"""Alembic environment (async). Alembic is the only migration tool (decision D-13).

URL precedence: ALEMBIC_DATABASE_URL, then DATABASE_URL. For Supabase use a direct or
session-mode connection for migrations, not the transaction pooler.
"""

import asyncio
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import get_settings
from app.database.session import to_async_url
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    settings = get_settings()
    secret = settings.alembic_database_url or settings.database_url
    if secret is None:
        sys.exit(
            "ERROR: no database configured. Set ALEMBIC_DATABASE_URL or DATABASE_URL "
            "in backend/.env (see backend/.env.example)."
        )
    return to_async_url(secret.get_secret_value())


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(
        _database_url(),
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},
    )
    async with engine.connect() as connection:
        await connection.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
