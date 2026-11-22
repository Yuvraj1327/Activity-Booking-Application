"""Builds the throwaway database used by the admin web Playwright suite (Step 8).

Test tooling only: it needs a Postgres SUPERUSER URL (`scripts/dev_pg.sh start`) and the test
helpers. It creates database `zuruv_e2e`, migrates it, and fills it through the REAL API with a
fake payment gateway (no Razorpay call), then back-dates rows so charts have a time axis.

    cd backend && python -m scripts.e2e_seed <out_dir>

Writes <out_dir>/users.json ({email: {id, role}}) and <out_dir>/db_url.txt.
"""

import json
import sys
import uuid
from pathlib import Path

from alembic import command
from tests.booking_helpers import API, book, future_day, iso, seed_world
from tests.conftest import (
    STUB_SQL,
    _admin_exec,
    alembic_config,
    auth_headers,
    make_auth_user,
    run,
    seed_profile,
    sql,
    with_database,
)  # fmt: skip
from tests.payment_helpers import create_order, payment_app, post_webhook, sign_checkout, webhook

SERVER = "postgresql://zt@127.0.0.1:54399/postgres"
DB_NAME = "zuruv_e2e"

OWNERS = [
    (
        "Priya Sharma",
        "priya@example.com",
        "Smash Arena Pvt Ltd",
        "Smash Arena Koramangala",
        "Badminton",
        60000,
    ),
    ("Rahul Verma", "rahul@example.com", "Greenfield Sports", "Greenfield Turf", "Football", 120000),
    ("Meera Iyer", "meera@example.com", "Blue Lagoon Aquatics", "Blue Lagoon Pool", "Swimming", 30000),
]
CUSTOMERS = [
    ("Aarav Mehta", "aarav@example.com"),
    ("Diya Nair", "diya@example.com"),
    ("Kabir Singh", "kabir@example.com"),
    ("Isha Kapoor", "isha@example.com"),
    ("Neel Joshi", "neel@example.com"),
]


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    run(_admin_exec(SERVER, f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)'))
    run(_admin_exec(SERVER, f'CREATE DATABASE "{DB_NAME}"'))
    db = with_database(SERVER, DB_NAME)
    run(_admin_exec(db, STUB_SQL.read_text()))
    command.upgrade(alembic_config(db), "head")

    users: dict[str, dict[str, str]] = {}
    admin = seed_profile(db, "admin", name="Ada Admin", email="admin@zuruv.test")
    users["admin@zuruv.test"] = {"id": str(admin), "role": "admin"}

    worlds = []
    for name, email, biz, venue, cat, price in OWNERS:
        w = seed_world(db, price=price)
        sql(
            db,
            "UPDATE public.profiles SET full_name=$1, email=$2, phone='+919800000001' WHERE id=$3",
            name,
            email,
            w["owner"],
        )
        sql(
            db,
            "UPDATE public.owner_profiles SET business_name=$1, business_email=$2, business_address='12 MG Road, Bengaluru' WHERE user_id=$3",
            biz,
            email,
            w["owner"],
        )
        sql(db, "UPDATE public.venues SET name=$1, address_line='MG Road' WHERE id=$2", venue, w["venue"])
        sql(
            db,
            "UPDATE public.categories SET name=$1 WHERE id IN (SELECT category_id FROM public.venue_categories WHERE venue_id=$2)",
            cat,
            w["venue"],
        )
        if not worlds:
            sql(
                db,
                "UPDATE public.cities SET name='Bengaluru' WHERE id=(SELECT city_id FROM public.venues WHERE id=$1)",
                w["venue"],
            )
        else:  # one shared city (names are unique)
            own = sql(db, "SELECT city_id FROM public.venues WHERE id=$1", w["venue"])[0]["city_id"]
            sql(
                db,
                "UPDATE public.venues SET city_id=(SELECT city_id FROM public.venues WHERE id=$1) WHERE id=$2",
                worlds[0]["venue"],
                w["venue"],
            )
            sql(db, "DELETE FROM public.cities WHERE id=$1", own)
        users[email] = {"id": str(w["owner"]), "role": "owner"}
        # seed_world also made one customer per world; the named customers below replace them.
        sql(db, "DELETE FROM public.profiles WHERE id=$1", w["customer"])
        worlds.append(w)

    custs = []
    for name, email in CUSTOMERS:
        uid = seed_profile(db, "customer", name=name, email=email)
        sql(
            db, "UPDATE public.profiles SET phone=$1 WHERE id=$2", f"+9198{uuid.uuid4().int % 10**8:08d}", uid
        )
        users[email] = {"id": str(uid), "role": "customer"}
        custs.append((uid, auth_headers(uid, email=email)))
    # A draft venue for Meera so the publication filter has something to show.
    sql(
        db,
        "INSERT INTO public.venues (owner_id, name, timezone, status) VALUES ($1,'Blue Lagoon Annex','Asia/Kolkata','draft')",
        worlds[2]["owner"],
    )

    def hold(env, w, h, day, hour):
        r = book(env.api, w, iso(future_day(day), hour), headers=h)
        assert r.status_code == 201, r.text
        return r.json()

    def pay(env, w, h, day, hour):
        b = hold(env, w, h, day, hour)
        order = create_order(env, b["id"], h).json()
        gp = env.gw.customer_pays(
            order["checkout"]["order_id"], method=("upi", "card", "netbanking")[hour % 3]
        )
        v = env.api.post(
            f"{API}/payments/verify",
            json={
                "razorpay_order_id": gp.order_id,
                "razorpay_payment_id": gp.id,
                "razorpay_signature": sign_checkout(gp.order_id or "", gp.id),
            },
            headers=h,
        )
        assert v.status_code == 200, v.text

    with payment_app(db, rate_limit_per_minute=0) as env:
        n = 0
        for wi, w in enumerate(worlds):
            for ci, (_uid, h) in enumerate(custs[:4]):
                for slot in range(2 + (wi + ci) % 2):
                    pay(env, w, h, 1 + (slot + ci) % 5, 7 + wi * 4 + slot * 2 + ci % 2)
                    n += 1
        # a failed payment, an abandoned hold, a cancelled hold
        b = hold(env, worlds[0], custs[0][1], 6, 20)
        order = create_order(env, b["id"], custs[0][1]).json()
        failed = env.gw.customer_pays(order["checkout"]["order_id"], status="failed")
        body, hdr = webhook("payment.failed", failed)
        assert post_webhook(env, body, hdr).json()["outcome"] == "applied"
        hold(env, worlds[1], custs[1][1], 6, 19)
        c = hold(env, worlds[2], custs[2][1], 6, 18)
        r = env.api.post(
            f"{API}/bookings/{c['id']}/cancel", json={"reason": "Plans changed"}, headers=custs[2][1]
        )
        assert r.status_code == 200, r.text
        # fresh sign-ups so the admin has real notifications
        for role, name, email, extra in (
            ("customer", "Zoya Khan", "zoya@example.com", {}),
            ("owner", "Arjun Rao", "arjun@example.com", {"business_name": "Rao Courts"}),
        ):
            uid = make_auth_user(db, email)
            r = env.api.post(
                f"{API}/auth/profile",
                json={"role": role, "full_name": name, **extra},
                headers=auth_headers(uid, email=email),
            )
            assert r.status_code == 201, r.text
            users[email] = {"id": str(uid), "role": role}

    # A second administrator with a deliberately narrow role, to prove permissions are enforced end to end.
    agent_role = sql(
        db,
        "INSERT INTO public.admin_roles (name, description, permissions) VALUES "
        "('Support agent', 'Tickets and the dashboard only', ARRAY['support.manage','dashboard.view']) RETURNING id",
    )[0]["id"]
    agent = seed_profile(db, "admin", name="Sam Support", email="limited@zuruv.test", grant=None)
    sql(db, "INSERT INTO public.admin_profiles (user_id, role_id) VALUES ($1,$2)", agent, agent_role)
    users["limited@zuruv.test"] = {"id": str(agent), "role": "admin"}
    # And one with NO role at all (the state of a freshly created administrator).
    bare = seed_profile(db, "admin", name="Nia NoRole", email="norole@zuruv.test", grant=None)
    users["norole@zuruv.test"] = {"id": str(bare), "role": "admin"}
    # A support ticket from a customer, and a KYC document waiting for review (no file is stored: e2e has no Storage).
    sql(
        db,
        "INSERT INTO public.support_tickets (user_id, kind, subject, message) VALUES ($1,'issue','Charged twice for one booking','I was charged twice for my badminton booking yesterday.')",
        uuid.UUID(users["aarav@example.com"]["id"]),
    )
    sql(
        db,
        "INSERT INTO public.owner_kyc_documents (owner_id, doc_type, storage_path, original_filename, content_type, byte_size) "
        "VALUES ($1,'identity',$2,'id.pdf','application/pdf',2048)",
        uuid.UUID(users["priya@example.com"]["id"]),
        f"{users['priya@example.com']['id']}/seed.pdf",
    )
    sql(
        db,
        "UPDATE public.owner_profiles SET kyc_status='pending' WHERE user_id=$1",
        uuid.UUID(users["priya@example.com"]["id"]),
    )

    sql(db, "UPDATE public.profiles SET status='suspended' WHERE email='neel@example.com'")

    # Spread history over the last ~4 weeks so the charts have a time axis (fixture data only).
    rows = sql(db, "SELECT id FROM public.bookings ORDER BY created_at")
    total = max(len(rows), 1)
    for i, r in enumerate(rows):
        d = 27 - (i * 27 // total)
        sql(
            db,
            "UPDATE public.bookings SET created_at = created_at - make_interval(days => $2) WHERE id=$1",
            r["id"],
            d,
        )
        sql(
            db,
            "UPDATE public.payments SET created_at = created_at - make_interval(days => $2), captured_at = captured_at - make_interval(days => $2), failed_at = failed_at - make_interval(days => $2) WHERE booking_id=$1",
            r["id"],
            d,
        )
    for i, r in enumerate(
        sql(
            db,
            "SELECT id FROM public.profiles WHERE role <> 'admin' AND email NOT IN ('zoya@example.com','arjun@example.com') ORDER BY email",
        )
    ):
        sql(
            db,
            "UPDATE public.profiles SET created_at = now() - make_interval(days => $2) WHERE id=$1",
            r["id"],
            28 - i * 3,
        )
    for i, r in enumerate(sql(db, "SELECT id FROM public.venues ORDER BY name")):
        sql(
            db,
            "UPDATE public.venues SET created_at = now() - make_interval(days => $2) WHERE id=$1",
            r["id"],
            25 - i * 4,
        )

    (out / "users.json").write_text(json.dumps(users, indent=2))
    (out / "db_url.txt").write_text(db)
    print(f"seeded {db}: {len(users)} users, {n} paid bookings")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
