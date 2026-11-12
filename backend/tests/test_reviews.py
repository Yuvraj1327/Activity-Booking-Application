"""Step 10: customer reviews and owner replies, and the venue rating aggregate."""

import threading
import uuid

import pytest

from tests.booking_helpers import API, new_customer, seed_world
from tests.conftest import auth_headers, seed_profile, sql
from tests.payment_helpers import hold_booking, make_admin, paid_booking, payment_app, rows


def finish(db: str, booking_id: str) -> None:
    """Move a paid booking into the past so it settles as `completed` (the real settle path runs on read)."""
    bid = uuid.UUID(booking_id)
    sql(
        db,
        "UPDATE public.booking_slots SET slot_range = tstzrange(now() - interval '3 hours', now() - interval '2 hours') "
        "WHERE booking_id=$1",
        bid,
    )
    sql(
        db,
        "UPDATE public.bookings SET starts_at = now() - interval '3 hours', ends_at = now() - interval '2 hours' WHERE id=$1",
        bid,
    )


def completed_booking(env, db, w, hour=9):
    b, _, _ = paid_booking(env, w, hour)
    finish(db, b["id"])
    return b


def test_only_completed_bookings_can_be_reviewed(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        held = hold_booking(env, w, hour=10)
        r = env.api.post(f"{API}/bookings/{held['id']}/review", json={"rating": 5}, headers=w["customer_h"])
        assert (r.status_code, r.json()["code"]) == (409, "BOOKING_NOT_REVIEWABLE")
        paid, _, _ = paid_booking(env, w, hour=12)  # confirmed but in the future
        r = env.api.post(f"{API}/bookings/{paid['id']}/review", json={"rating": 5}, headers=w["customer_h"])
        assert (r.status_code, r.json()["code"]) == (409, "BOOKING_NOT_REVIEWABLE")
        assert rows(clean_db, "SELECT count(*) AS n FROM public.reviews")[0]["n"] == 0


def test_review_updates_the_venue_aggregate_and_is_one_per_booking(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = completed_booking(env, clean_db, w)
        r = env.api.post(
            f"{API}/bookings/{b['id']}/review",
            json={"rating": 4, "comment": "  Great court  "},
            headers=w["customer_h"],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["rating"] == 4 and body["comment"] == "Great court"
        assert body["reviewer_name"] == "Cathy C."  # never the full name

        v = rows(clean_db, "SELECT rating_avg, rating_count FROM public.venues")[0]
        assert (float(v["rating_avg"]), v["rating_count"]) == (4.0, 1)

        again = env.api.post(f"{API}/bookings/{b['id']}/review", json={"rating": 1}, headers=w["customer_h"])
        assert (again.status_code, again.json()["code"]) == (409, "REVIEW_EXISTS")
        assert rows(clean_db, "SELECT count(*) AS n FROM public.reviews")[0]["n"] == 1

        mine = env.api.get(f"{API}/bookings/{b['id']}/review", headers=w["customer_h"])
        assert mine.status_code == 200 and mine.json()["rating"] == 4

        listing = env.api.get(f"{API}/venues/{w['venue']}/reviews", headers=w["customer_h"]).json()
        assert [i["rating"] for i in listing["items"]] == [4]
        assert listing["summary"] == {
            "average": 4.0,
            "count": 1,
            "distribution": {"1": 0, "2": 0, "3": 0, "4": 1, "5": 0},
        }
        # the owner was told once
        notes = rows(clean_db, "SELECT type FROM public.notifications WHERE user_id=$1", w["owner"])
        assert [n["type"] for n in notes].count("review.created") == 1


def test_review_input_is_validated(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = completed_booking(env, clean_db, w)
        url = f"{API}/bookings/{b['id']}/review"
        for bad in (
            {"rating": 0},
            {"rating": 6},
            {"rating": "5"},
            {},
            {"rating": 5, "comment": "x" * 1001},
            {"rating": 5, "venue_id": str(w["venue"])},
            {"rating": 5, "customer_id": str(w["customer"])},
        ):
            assert env.api.post(url, json=bad, headers=w["customer_h"]).status_code == 422, bad
        assert rows(clean_db, "SELECT count(*) AS n FROM public.reviews")[0]["n"] == 0


def test_a_customer_cannot_review_someone_elses_booking(clean_db):
    w = seed_world(clean_db)
    _, other_h = new_customer(clean_db, "Intruder")
    with payment_app(clean_db) as env:
        b = completed_booking(env, clean_db, w)
        r = env.api.post(f"{API}/bookings/{b['id']}/review", json={"rating": 1}, headers=other_h)
        assert r.status_code == 404
        assert (
            env.api.post(
                f"{API}/bookings/{b['id']}/review", json={"rating": 1}, headers=w["owner_h"]
            ).status_code
            == 403
        )
        assert rows(clean_db, "SELECT count(*) AS n FROM public.reviews")[0]["n"] == 0


def test_owner_sees_only_own_reviews_and_can_reply_once(clean_db):
    w = seed_world(clean_db)
    other_owner_h = auth_headers(seed_profile(clean_db, "owner", name="Other Owner"))
    with payment_app(clean_db) as env:
        b = completed_booking(env, clean_db, w)
        review = env.api.post(
            f"{API}/bookings/{b['id']}/review",
            json={"rating": 5, "comment": "Superb"},
            headers=w["customer_h"],
        ).json()

        mine = env.api.get(f"{API}/owners/reviews", headers=w["owner_h"]).json()
        assert [i["id"] for i in mine["items"]] == [review["id"]]
        assert (
            mine["items"][0]["venue_name"] == "Ace Arena"
            and mine["items"][0]["booking_code"] == b["booking_code"]
        )
        assert (
            env.api.get(f"{API}/owners/reviews", params={"rating": 3}, headers=w["owner_h"]).json()["items"]
            == []
        )
        assert env.api.get(f"{API}/owners/reviews", headers=other_owner_h).json()["items"] == []

        # another owner cannot reply to it; it looks like a missing review
        r = env.api.post(
            f"{API}/owners/reviews/{review['id']}/reply", json={"body": "hi"}, headers=other_owner_h
        )
        assert r.status_code == 404
        assert (
            env.api.post(
                f"{API}/owners/reviews/{review['id']}/reply", json={"body": "hi"}, headers=w["customer_h"]
            ).status_code
            == 403
        )

        ok = env.api.post(
            f"{API}/owners/reviews/{review['id']}/reply",
            json={"body": "  Thank you!  "},
            headers=w["owner_h"],
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["reply"]["body"] == "Thank you!"
        dup = env.api.post(
            f"{API}/owners/reviews/{review['id']}/reply", json={"body": "again"}, headers=w["owner_h"]
        )
        assert (dup.status_code, dup.json()["code"]) == (409, "REPLY_EXISTS")
        assert (
            env.api.post(
                f"{API}/owners/reviews/{review['id']}/reply", json={"body": "  "}, headers=w["owner_h"]
            ).status_code
            == 422
        )

        public = env.api.get(f"{API}/venues/{w['venue']}/reviews", headers=w["customer_h"]).json()
        assert public["items"][0]["reply"]["body"] == "Thank you!"
        # the customer is told about the reply
        notes = rows(clean_db, "SELECT type FROM public.notifications WHERE user_id=$1", w["customer"])
        assert "review.reply" in [n["type"] for n in notes]


def test_reviews_and_replies_cannot_be_edited_or_deleted_even_in_the_database(clean_db):
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = completed_booking(env, clean_db, w)
        env.api.post(f"{API}/bookings/{b['id']}/review", json={"rating": 3}, headers=w["customer_h"])
    for statement in ("UPDATE public.reviews SET rating = 5", "DELETE FROM public.reviews"):
        with pytest.raises(Exception, match="cannot be changed or deleted"):
            sql(clean_db, statement)


def test_reviews_are_not_readable_by_clients_directly(clean_db):
    """RLS is on and no grants exist: the API is the only way to read reviews."""
    assert rows(
        clean_db,
        "SELECT relrowsecurity FROM pg_class WHERE relname IN ('reviews','review_responses')",
    ) == [{"relrowsecurity": True}, {"relrowsecurity": True}] or all(
        r["relrowsecurity"]
        for r in rows(
            clean_db, "SELECT relrowsecurity FROM pg_class WHERE relname IN ('reviews','review_responses')"
        )
    )
    grants = rows(
        clean_db,
        "SELECT count(*) AS n FROM information_schema.role_table_grants WHERE table_name IN ('reviews','review_responses') "
        "AND grantee IN ('anon','authenticated')",
    )
    assert grants[0]["n"] == 0


def test_two_different_customers_average_correctly_and_concurrently(clean_db):
    w = seed_world(clean_db)
    cust2, cust2_h = new_customer(clean_db, "Second Person")
    with payment_app(clean_db) as env:
        b1 = completed_booking(env, clean_db, w, hour=9)
        w2 = dict(w, customer=cust2, customer_h=cust2_h)
        b2 = completed_booking(env, clean_db, w2, hour=13)
        results: list[int] = []

        def post(booking, headers, rating):
            results.append(
                env.api.post(
                    f"{API}/bookings/{booking['id']}/review", json={"rating": rating}, headers=headers
                ).status_code
            )

        threads = [
            threading.Thread(target=post, args=(b1, w["customer_h"], 5)),
            threading.Thread(target=post, args=(b2, cust2_h, 2)),
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert results == [201, 201] or sorted(results) == [201, 201]
        v = rows(clean_db, "SELECT rating_avg, rating_count FROM public.venues")[0]
        assert (float(v["rating_avg"]), v["rating_count"]) == (3.5, 2)  # no lost update


def test_admin_cannot_post_reviews_and_unknown_venue_is_404(clean_db):
    admin_h = make_admin(clean_db)
    w = seed_world(clean_db)
    with payment_app(clean_db) as env:
        b = completed_booking(env, clean_db, w)
        assert (
            env.api.post(f"{API}/bookings/{b['id']}/review", json={"rating": 5}, headers=admin_h).status_code
            == 403
        )
        r = env.api.get(f"{API}/venues/00000000-0000-0000-0000-000000000000/reviews", headers=admin_h)
        assert r.status_code == 404
