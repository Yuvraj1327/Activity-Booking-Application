"""Supabase Storage configuration and access restrictions.

Runs against the LOCAL STUB of storage.buckets / storage.objects (see
supabase/local/supabase_stub.sql): it proves our policies, not Supabase's Storage service.
Bucket-level size/MIME limits are configuration that the real Storage service enforces;
here we only assert they are set."""

import uuid

import asyncpg
import pytest

from tests.conftest import run, seed_profile, sql
from tests.rls_helpers import session_as

DENIED = asyncpg.InsufficientPrivilegeError
INSERT = "INSERT INTO storage.objects (bucket_id, name, owner) VALUES ($1, $2, $3)"


@pytest.fixture
def users(clean_db):
    return (
        clean_db,
        seed_profile(clean_db, "customer"),
        seed_profile(clean_db, "owner"),
        seed_profile(clean_db, "customer", status="suspended"),
    )


def test_buckets_are_configured(clean_db):
    rows = {r["id"]: r for r in sql(clean_db, "SELECT * FROM storage.buckets")}
    assert set(rows) == {"venue-images", "profile-images"}
    assert rows["venue-images"]["public"] is True
    assert rows["profile-images"]["public"] is False
    for bucket in rows.values():
        assert bucket["allowed_mime_types"] == ["image/jpeg", "image/png", "image/webp"]
    assert rows["venue-images"]["file_size_limit"] == 5 * 1024 * 1024
    assert rows["profile-images"]["file_size_limit"] == 2 * 1024 * 1024


def test_user_can_manage_only_files_in_own_folder(users):
    url, a, b, _ = users

    async def scenario():
        async with session_as(url, a) as c:
            await c.execute(INSERT, "profile-images", f"{a}/avatar_1.webp", a)
            assert await c.fetchval("SELECT count(*) FROM storage.objects") == 1
            assert (
                await c.execute(
                    "UPDATE storage.objects SET metadata = '{}'::jsonb WHERE name = $1", f"{a}/avatar_1.webp"
                )
                == "UPDATE 1"
            )
            assert (
                await c.execute("DELETE FROM storage.objects WHERE name = $1", f"{a}/avatar_1.webp")
                == "DELETE 1"
            )

    run(scenario())


@pytest.mark.parametrize(
    "path",
    [
        "{other}/steal.webp",  # someone else's folder
        "{me}/../{other}/x.webp",  # traversal
        "{me}/sub/x.webp",  # nesting
        "x.webp",  # no folder
        "{me}/x.exe",  # extension not allowed
        "{me}/",  # folder marker
        "{me}x/x.webp",  # prefix trick
    ],
)
def test_cannot_write_outside_own_folder(users, path):
    url, a, b, _ = users
    name = path.format(me=a, other=b)

    async def scenario():
        async with session_as(url, a) as c:
            with pytest.raises(DENIED, match="row-level security"):
                await c.execute(INSERT, "profile-images", name, a)

    run(scenario())


def test_cannot_overwrite_or_read_other_users_files(users):
    url, a, b, _ = users
    sql(url, INSERT, "profile-images", f"{b}/avatar.webp", b)

    async def scenario():
        async with session_as(url, a) as c:
            assert await c.fetchval("SELECT count(*) FROM storage.objects") == 0  # cannot even see it
            assert (
                await c.execute(
                    "UPDATE storage.objects SET name = $1 WHERE name = $2", f"{a}/x.webp", f"{b}/avatar.webp"
                )
                == "UPDATE 0"
            )
            assert (
                await c.execute("DELETE FROM storage.objects WHERE name = $1", f"{b}/avatar.webp")
                == "DELETE 0"
            )
        async with session_as(url, a) as c:  # cannot move own file into someone else's folder
            await c.execute(INSERT, "profile-images", f"{a}/mine.webp", a)
            with pytest.raises(DENIED):
                await c.execute(
                    "UPDATE storage.objects SET name = $1 WHERE name = $2",
                    f"{b}/avatar.webp",
                    f"{a}/mine.webp",
                )

    run(scenario())
    assert sql(url, "SELECT count(*) AS n FROM storage.objects")[0]["n"] == 1  # b's file untouched


def test_venue_images_bucket_is_not_writable_by_clients(users):
    url, a, owner, _ = users
    sql(url, INSERT, "venue-images", f"{uuid.uuid4()}/1.webp", None)

    async def scenario():
        for role, uid in (("authenticated", owner), ("authenticated", a), ("anon", None)):
            async with session_as(url, uid, role=role) as c:
                with pytest.raises(DENIED):
                    await c.execute(INSERT, "venue-images", f"{uuid.uuid4()}/2.webp", uid)
            async with session_as(url, uid, role=role) as c:
                assert (
                    await c.execute("DELETE FROM storage.objects WHERE bucket_id = 'venue-images'")
                    == "DELETE 0"
                )
                assert (
                    await c.execute(
                        "UPDATE storage.objects SET name = name || 'x' WHERE bucket_id = 'venue-images'"
                    )
                    == "UPDATE 0"
                )

    run(scenario())
    assert sql(url, "SELECT count(*) AS n FROM storage.objects")[0]["n"] == 1


def test_anon_cannot_access_profile_images(users):
    url, a, *_ = users
    sql(url, INSERT, "profile-images", f"{a}/avatar.webp", a)

    async def scenario():
        async with session_as(url, role="anon") as c:
            assert (
                await c.fetchval("SELECT count(*) FROM storage.objects WHERE bucket_id = 'profile-images'")
                == 0
            )
        async with session_as(url, role="anon") as c:
            with pytest.raises(DENIED):
                await c.execute(INSERT, "profile-images", f"{a}/x.webp", a)

    run(scenario())


def test_suspended_user_cannot_upload(users):
    url, _, _, suspended = users

    async def scenario():
        async with session_as(url, suspended) as c:
            with pytest.raises(DENIED):
                await c.execute(INSERT, "profile-images", f"{suspended}/x.webp", suspended)

    run(scenario())
