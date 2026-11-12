import os

import pytest

from alembic import command
from app.models import Base
from tests.conftest import (
    alembic_config,
    create_migrated_database,
    drop_database,
    require_server,
    run,
    sql,
    with_database,
)


@pytest.fixture
def fresh_db():
    server = require_server()
    url = create_migrated_database(server)
    yield url
    drop_database(server, url)
    os.environ.pop("ALEMBIC_DATABASE_URL", None)


def public_tables(url: str) -> set[str]:
    rows = sql(
        url, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"
    )
    return {r["tablename"] for r in rows}


def test_orm_models_match_migrated_schema(fresh_db):
    """Every ORM table and column exists in the migrated database (and vice versa for tables)."""
    assert {t.name for t in Base.metadata.sorted_tables} == public_tables(fresh_db)
    for table in Base.metadata.sorted_tables:
        cols = {
            r["column_name"]
            for r in sql(
                fresh_db,
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=$1",
                table.name,
            )
        }
        assert {c.name for c in table.columns} == cols, table.name


def test_downgrade_to_base_and_upgrade_again(fresh_db):
    cfg = alembic_config(fresh_db)
    assert len(public_tables(fresh_db)) == 14
    command.downgrade(cfg, "base")
    assert public_tables(fresh_db) == set()
    assert sql(fresh_db, "SELECT count(*) AS n FROM storage.buckets")[0]["n"] == 0
    assert (
        sql(fresh_db, "SELECT count(*) AS n FROM pg_policies WHERE schemaname IN ('public','storage')")[0][
            "n"
        ]
        == 0
    )
    command.upgrade(cfg, "head")
    assert len(public_tables(fresh_db)) == 14
    assert sql(fresh_db, "SELECT count(*) AS n FROM storage.buckets")[0]["n"] == 2


def test_upgrade_is_refused_without_supabase_auth_schema():
    server = require_server()
    import uuid

    from tests.conftest import _admin_exec

    name = f"zuruv_bare_{uuid.uuid4().hex[:8]}"
    run(_admin_exec(server, f'CREATE DATABASE "{name}"'))
    url = with_database(server, name)
    try:
        with pytest.raises(Exception, match="auth.users not found"):
            command.upgrade(alembic_config(url), "head")
    finally:
        drop_database(server, url)
        os.environ.pop("ALEMBIC_DATABASE_URL", None)
