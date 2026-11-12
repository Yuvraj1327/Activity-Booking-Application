"""Customer reviews and owner replies (Step 10).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-12

Rules implemented (the conservative reading of requirements R-050..R-052; Q15 and N14 still need
the client's confirmation, see docs/OPEN_QUESTIONS.md):

* only the customer of a COMPLETED booking can review it, once (UNIQUE booking_id), rating 1-5;
* a review cannot be edited or deleted through the API; the owner of the venue can reply once
  (UNIQUE review_id);
* `venues.rating_avg` / `rating_count` are maintained by a trigger, so the displayed aggregate always
  equals the stored reviews. The venue row is locked first so concurrent reviews cannot lose an update.

Clients never read these tables directly (RLS on, no grants): reads go through the API.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UP = [
    """
CREATE TABLE public.reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE RESTRICT,
  customer_id uuid NOT NULL REFERENCES public.customer_profiles(user_id) ON DELETE RESTRICT,
  rating smallint NOT NULL,
  comment text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_reviews_booking UNIQUE (booking_id),
  CONSTRAINT ck_reviews_rating CHECK (rating BETWEEN 1 AND 5),
  CONSTRAINT ck_reviews_comment CHECK (comment IS NULL OR char_length(comment) BETWEEN 1 AND 1000)
)
""",
    """
CREATE TABLE public.review_responses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id uuid NOT NULL REFERENCES public.reviews(id) ON DELETE RESTRICT,
  owner_id uuid NOT NULL REFERENCES public.owner_profiles(user_id) ON DELETE RESTRICT,
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_review_responses_review UNIQUE (review_id),
  CONSTRAINT ck_review_responses_body CHECK (char_length(body) BETWEEN 1 AND 1000)
)
""",
    "CREATE INDEX ix_reviews_venue_created ON public.reviews (venue_id, created_at DESC)",
    "CREATE INDEX ix_reviews_customer ON public.reviews (customer_id)",
    """
CREATE FUNCTION public.refresh_venue_rating() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM public.venues WHERE id = NEW.venue_id FOR UPDATE;
  UPDATE public.venues v
     SET rating_count = s.c, rating_avg = s.a
    FROM (SELECT count(*)::int AS c, round(avg(rating)::numeric, 1) AS a
            FROM public.reviews WHERE venue_id = NEW.venue_id) s
   WHERE v.id = NEW.venue_id;
  RETURN NEW;
END
$$
""",
    "CREATE TRIGGER trg_reviews_rating AFTER INSERT ON public.reviews "
    "FOR EACH ROW EXECUTE FUNCTION public.refresh_venue_rating()",
    # reviews and replies are not editable or deletable (no approved rule allows it)
    """
CREATE FUNCTION public.reviews_are_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'reviews and replies cannot be changed or deleted' USING ERRCODE = '23000';
END
$$
""",
    "CREATE TRIGGER trg_reviews_immutable BEFORE UPDATE OR DELETE ON public.reviews "
    "FOR EACH ROW EXECUTE FUNCTION public.reviews_are_immutable()",
    "CREATE TRIGGER trg_review_responses_immutable BEFORE UPDATE OR DELETE ON public.review_responses "
    "FOR EACH ROW EXECUTE FUNCTION public.reviews_are_immutable()",
    "ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.review_responses ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON public.reviews, public.review_responses FROM anon, authenticated",
]


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.review_responses CASCADE")
    op.execute("DROP TABLE IF EXISTS public.reviews CASCADE")
    op.execute("DROP FUNCTION IF EXISTS public.reviews_are_immutable()")
    op.execute("DROP FUNCTION IF EXISTS public.refresh_venue_rating()")
