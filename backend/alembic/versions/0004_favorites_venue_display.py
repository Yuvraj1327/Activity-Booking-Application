"""Favorites, plus the display fields the customer app needs on venues.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12

* favorites: customer <-> venue (architecture section 7, "Engagement").
* venues.rating_avg / rating_count: aggregates (architecture section 7). Reviews do not exist
  yet, so they stay NULL / 0 until the reviews step fills them.
* venues.starting_price_paise / currency: a display-only "from" price for listings. The real
  price model (schedule_rules, architecture section 7) is built with availability; this column
  is an interim, nullable value and will be derived from schedules then. Currency defaults to
  INR as an ASSUMPTION (open question N1).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UP = [
    "ALTER TABLE public.venues ADD COLUMN starting_price_paise bigint",
    "ALTER TABLE public.venues ADD COLUMN currency char(3) NOT NULL DEFAULT 'INR'",
    "ALTER TABLE public.venues ADD COLUMN rating_avg numeric(2, 1)",
    "ALTER TABLE public.venues ADD COLUMN rating_count integer NOT NULL DEFAULT 0",
    "ALTER TABLE public.venues ADD CONSTRAINT ck_venues_starting_price CHECK (starting_price_paise IS NULL OR starting_price_paise >= 0)",
    r"ALTER TABLE public.venues ADD CONSTRAINT ck_venues_currency CHECK (currency ~ '^[A-Z]{3}$')",
    "ALTER TABLE public.venues ADD CONSTRAINT ck_venues_rating_avg CHECK (rating_avg IS NULL OR rating_avg BETWEEN 0 AND 5)",
    "ALTER TABLE public.venues ADD CONSTRAINT ck_venues_rating_count CHECK (rating_count >= 0)",
    "ALTER TABLE public.venues ADD CONSTRAINT ck_venues_rating_consistent CHECK (rating_count = 0 OR rating_avg IS NOT NULL)",
    "CREATE INDEX ix_venues_published_rating ON public.venues (rating_count DESC, rating_avg DESC NULLS LAST) WHERE status = 'published'",
    """
CREATE TABLE public.favorites (
  customer_id uuid NOT NULL REFERENCES public.customer_profiles (user_id) ON DELETE CASCADE,
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_favorites PRIMARY KEY (customer_id, venue_id)
)
""",
    "CREATE INDEX ix_favorites_customer_created ON public.favorites (customer_id, created_at DESC)",
    "CREATE INDEX ix_favorites_venue_id ON public.favorites (venue_id)",
    # Same security model as 0003: RLS on, SELECT-only own rows, no client writes.
    "ALTER TABLE public.favorites ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON public.favorites FROM anon, authenticated",
    "GRANT SELECT ON public.favorites TO authenticated",
    "CREATE POLICY favorites_select_own ON public.favorites FOR SELECT TO authenticated "
    "USING (customer_id = (SELECT auth.uid()) AND (SELECT public.app_user_role()) = 'customer')",
]


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.favorites CASCADE")
    op.execute("DROP INDEX IF EXISTS public.ix_venues_published_rating")
    for constraint in (
        "ck_venues_rating_consistent",
        "ck_venues_rating_count",
        "ck_venues_rating_avg",
        "ck_venues_currency",
        "ck_venues_starting_price",
    ):
        op.execute(f"ALTER TABLE public.venues DROP CONSTRAINT IF EXISTS {constraint}")
    for column in ("rating_count", "rating_avg", "currency", "starting_price_paise"):
        op.execute(f"ALTER TABLE public.venues DROP COLUMN IF EXISTS {column}")
