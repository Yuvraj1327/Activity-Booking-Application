"""Database-level guarantees, tested with direct SQL (no API in the way)."""

import uuid

import asyncpg
import pytest

from tests.conftest import make_auth_user, run, seed_profile, sql


def fails(url: str, query: str, exc: type[Exception], *args: object) -> None:
    with pytest.raises(exc):
        sql(url, query, *args)


CHECK = asyncpg.CheckViolationError
UNIQUE = asyncpg.UniqueViolationError
FK = asyncpg.ForeignKeyViolationError


def new_user(url: str) -> uuid.UUID:
    return make_auth_user(url, f"{uuid.uuid4().hex[:6]}@example.com")


def insert_profile(url: str, uid: uuid.UUID, **over: object) -> None:
    cols = {"role": "customer", "status": "active", "full_name": "Name", **over}
    names = ", ".join(cols)
    marks = ", ".join(f"${i + 2}" for i in range(len(cols)))
    sql(url, f"INSERT INTO public.profiles (id, {names}) VALUES ($1, {marks})", uid, *cols.values())


@pytest.mark.parametrize(
    "over",
    [
        {"role": "superadmin"},
        {"status": "deleted"},
        {"full_name": "   "},
        {"full_name": "x" * 121},
        {"phone": "9876543210"},
        {"phone": "+0123456789"},
        {"avatar_path": "other/x.png"},
    ],
)
def test_profile_check_constraints(clean_db, over):
    fails_user = new_user(clean_db)
    with pytest.raises(CHECK):
        insert_profile(clean_db, fails_user, **over)


def test_profile_requires_auth_user(clean_db):
    with pytest.raises(FK):
        insert_profile(clean_db, uuid.uuid4())


def test_profile_primary_key_is_unique(clean_db):
    uid = new_user(clean_db)
    insert_profile(clean_db, uid)
    with pytest.raises(UNIQUE):
        insert_profile(clean_db, uid)


def test_role_is_immutable(clean_db):
    uid = seed_profile(clean_db, "customer")
    with pytest.raises(CHECK, match="immutable"):
        sql(clean_db, "UPDATE public.profiles SET role='admin' WHERE id=$1", uid)
    assert sql(clean_db, "SELECT role FROM public.profiles WHERE id=$1", uid)[0]["role"] == "customer"


def test_updated_at_trigger(clean_db):
    uid = seed_profile(clean_db, "customer")
    before = sql(clean_db, "SELECT updated_at FROM public.profiles WHERE id=$1", uid)[0]["updated_at"]
    sql(clean_db, "SELECT pg_sleep(0.05)")
    sql(clean_db, "UPDATE public.profiles SET full_name='Changed' WHERE id=$1", uid)
    after = sql(clean_db, "SELECT updated_at FROM public.profiles WHERE id=$1", uid)[0]["updated_at"]
    assert after > before


def test_role_tables_are_pinned_to_the_matching_role(clean_db):
    owner = seed_profile(clean_db, "owner")
    customer = seed_profile(clean_db, "customer")
    with pytest.raises(FK):  # an owner cannot get a customer_profiles row
        sql(clean_db, "INSERT INTO public.customer_profiles (user_id) VALUES ($1)", owner)
    with pytest.raises(FK):  # a customer cannot get an owner_profiles row
        sql(clean_db, "INSERT INTO public.owner_profiles (user_id, business_name) VALUES ($1, 'x')", customer)
    with pytest.raises(CHECK):  # and the role column cannot be faked
        sql(clean_db, "INSERT INTO public.customer_profiles (user_id, role) VALUES ($1, 'owner')", owner)


def test_owner_profile_checks_and_cascade(clean_db):
    uid = seed_profile(clean_db, "owner")
    with pytest.raises(CHECK):
        sql(clean_db, "UPDATE public.owner_profiles SET business_name='' WHERE user_id=$1", uid)
    with pytest.raises(CHECK):
        sql(clean_db, "UPDATE public.owner_profiles SET business_phone='123' WHERE user_id=$1", uid)
    sql(clean_db, "DELETE FROM public.profiles WHERE id=$1", uid)
    assert sql(clean_db, "SELECT count(*) AS n FROM public.owner_profiles")[0]["n"] == 0


def test_cities_categories_amenities(clean_db):
    sql(clean_db, "INSERT INTO public.cities (name, state, country_code) VALUES ('Pune','MH','IN')")
    with pytest.raises(UNIQUE):  # case-insensitive
        sql(clean_db, "INSERT INTO public.cities (name, state, country_code) VALUES ('PUNE','mh','IN')")
    with pytest.raises(CHECK):  # must be upper-case ISO alpha-2
        sql(clean_db, "INSERT INTO public.cities (name, country_code) VALUES ('X','in')")
    with pytest.raises(asyncpg.StringDataRightTruncationError):
        sql(clean_db, "INSERT INTO public.cities (name, country_code) VALUES ('X','india')")
    sql(clean_db, "INSERT INTO public.categories (slug, name) VALUES ('table-tennis','Table Tennis')")
    with pytest.raises(UNIQUE):
        sql(clean_db, "INSERT INTO public.categories (slug, name) VALUES ('table-tennis','Dup')")
    for bad in ("Table Tennis", "-x", "x-", "a--b", ""):
        with pytest.raises(CHECK):
            sql(clean_db, "INSERT INTO public.amenities (slug, name) VALUES ($1,'x')", bad)


def seed_venue(url: str, owner: uuid.UUID, status: str = "draft", name: str = "Arena") -> uuid.UUID:
    city = sql(
        url,
        "INSERT INTO public.cities (name, country_code) VALUES ($1,'IN') RETURNING id",
        f"C{uuid.uuid4().hex[:6]}",
    )[0]["id"]
    return sql(
        url,
        "INSERT INTO public.venues (owner_id, city_id, name, latitude, longitude, timezone, status) "
        "VALUES ($1,$2,$3,12.97,77.59,'Asia/Kolkata',$4) RETURNING id",
        owner, city, name, status,
    )[0]["id"]  # fmt: skip


def test_venue_constraints(clean_db):
    owner = seed_profile(clean_db, "owner")
    customer = seed_profile(clean_db, "customer")
    base = "INSERT INTO public.venues (owner_id, name, timezone{c}) VALUES ($1, 'V', 'Asia/Kolkata'{v})"

    sql(clean_db, base.format(c="", v=""), owner)  # draft with no location is fine
    with pytest.raises(FK):  # only an owner profile can own a venue
        sql(clean_db, base.format(c="", v=""), customer)
    with pytest.raises(CHECK):
        sql(clean_db, base.format(c=", status", v=", 'live'"), owner)
    with pytest.raises(CHECK):
        sql(clean_db, base.format(c=", latitude, longitude", v=", 91, 10"), owner)
    with pytest.raises(CHECK):
        sql(clean_db, base.format(c=", latitude, longitude", v=", 10, 181"), owner)
    with pytest.raises(CHECK):  # latitude without longitude
        sql(clean_db, base.format(c=", latitude", v=", 10"), owner)
    with pytest.raises(CHECK):  # cannot publish a venue that has no city/location
        sql(clean_db, base.format(c=", status", v=", 'published'"), owner)
    seed_venue(clean_db, owner, "published")  # with location it can


def test_owner_with_venues_cannot_be_deleted(clean_db):
    owner = seed_profile(clean_db, "owner")
    seed_venue(clean_db, owner)
    with pytest.raises(FK):
        sql(clean_db, "DELETE FROM public.owner_profiles WHERE user_id=$1", owner)


def test_venue_links_and_cascade(clean_db):
    owner = seed_profile(clean_db, "owner")
    venue = seed_venue(clean_db, owner)
    cat = sql(
        clean_db, "INSERT INTO public.categories (slug,name) VALUES ('football','Football') RETURNING id"
    )[0]["id"]
    sql(clean_db, "INSERT INTO public.venue_categories VALUES ($1,$2)", venue, cat)
    with pytest.raises(UNIQUE):
        sql(clean_db, "INSERT INTO public.venue_categories VALUES ($1,$2)", venue, cat)
    with pytest.raises(FK):
        sql(clean_db, "INSERT INTO public.venue_amenities VALUES ($1,$2)", venue, uuid.uuid4())
    sql(clean_db, "DELETE FROM public.venues WHERE id=$1", venue)
    assert sql(clean_db, "SELECT count(*) AS n FROM public.venue_categories")[0]["n"] == 0


def test_venue_images_constraints(clean_db):
    owner = seed_profile(clean_db, "owner")
    venue = seed_venue(clean_db, owner)
    other = seed_venue(clean_db, owner, name="Other")
    ins = "INSERT INTO public.venue_images (venue_id, storage_path, status, is_cover) VALUES ($1,$2,$3,$4)"
    sql(clean_db, ins, venue, f"{venue}/a.webp", "active", True)
    with pytest.raises(UNIQUE):  # only one cover per venue
        sql(clean_db, ins, venue, f"{venue}/b.webp", "active", True)
    with pytest.raises(CHECK):  # path must sit in the venue's own folder
        sql(clean_db, ins, venue, f"{other}/c.webp", "active", False)
    with pytest.raises(CHECK):  # a pending image cannot be the cover
        sql(clean_db, ins, other, f"{other}/d.webp", "pending", True)
    with pytest.raises(CHECK):
        sql(clean_db, ins, other, f"{other}/e.webp", "archived", False)
    with pytest.raises(UNIQUE):
        sql(clean_db, ins, venue, f"{venue}/a.webp", "active", False)


def test_venue_resources_unique_name_per_venue(clean_db):
    owner = seed_profile(clean_db, "owner")
    v1, v2 = seed_venue(clean_db, owner), seed_venue(clean_db, owner, name="B")
    ins = "INSERT INTO public.venue_resources (venue_id, name) VALUES ($1,$2)"
    sql(clean_db, ins, v1, "Court 1")
    with pytest.raises(UNIQUE):
        sql(clean_db, ins, v1, "court 1")
    sql(clean_db, ins, v2, "Court 1")  # same name in another venue is fine
    with pytest.raises(CHECK):
        sql(clean_db, ins, v1, " ")


def test_notifications_constraints(clean_db):
    uid = seed_profile(clean_db, "customer")
    ins = "INSERT INTO public.notifications (user_id, type, title, data) VALUES ($1,$2,$3,$4::jsonb)"
    sql(clean_db, ins, uid, "welcome", "Hi", "{}")
    with pytest.raises(CHECK):
        sql(clean_db, ins, uid, "welcome", "Hi", "[1]")
    with pytest.raises(CHECK):
        sql(clean_db, ins, uid, "", "Hi", "{}")
    with pytest.raises(FK):
        sql(clean_db, ins, uuid.uuid4(), "welcome", "Hi", "{}")


def test_audit_log_is_append_only(clean_db):
    uid = seed_profile(clean_db, "admin")
    log = sql(
        clean_db,
        "INSERT INTO public.audit_logs (actor_id, actor_role, action) VALUES ($1,'admin','x') RETURNING id",
        uid,
    )[0]["id"]
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        sql(clean_db, "UPDATE public.audit_logs SET action='tampered' WHERE id=$1", log)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        sql(clean_db, "DELETE FROM public.audit_logs WHERE id=$1", log)
    with pytest.raises(CHECK):
        sql(clean_db, "INSERT INTO public.audit_logs (action, actor_role) VALUES ('x','hacker')")
    # deleting the actor keeps the log, with the actor nulled (the one allowed change)
    sql(clean_db, "DELETE FROM public.profiles WHERE id=$1", uid)
    row = sql(clean_db, "SELECT actor_id, action FROM public.audit_logs WHERE id=$1", log)[0]
    assert row["actor_id"] is None and row["action"] == "x"


def test_run_helper_is_importable():
    assert run  # keeps the import used for type checkers
