"""Opening hours: regular weekly hours and special-date exceptions (Step 5).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12

Only OPENING HOURS are stored. Slot length, price rules and per-court schedules (the other
columns of the architecture's `schedule_rules`, section 7) are deliberately not here: they
depend on open questions Q1/Q2/Q17/N2/N23 and arrive with the booking engine (Step 6).

* schedule_rules: one row per open interval. A closed weekday simply has no rows.
  weekday 0 = Monday … 6 = Sunday. Times are LOCAL to the venue's time zone. Overnight
  intervals (closing after midnight) are not supported yet.
* schedule_exceptions: one row per special date. It REPLACES the regular hours for that date
  (precedence assumption for open question Q16). Either a closure or one custom interval.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UP = [
    """
CREATE TABLE public.schedule_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  weekday smallint NOT NULL,
  opens_at time NOT NULL,
  closes_at time NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_schedule_rules_weekday CHECK (weekday BETWEEN 0 AND 6),
  CONSTRAINT ck_schedule_rules_interval CHECK (opens_at < closes_at),
  CONSTRAINT uq_schedule_rules_start UNIQUE (venue_id, weekday, opens_at)
)
""",
    "CREATE INDEX ix_schedule_rules_venue ON public.schedule_rules (venue_id, weekday)",
    """
CREATE TABLE public.schedule_exceptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  on_date date NOT NULL,
  is_closed boolean NOT NULL,
  opens_at time,
  closes_at time,
  note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_schedule_exceptions_date UNIQUE (venue_id, on_date),
  CONSTRAINT ck_schedule_exceptions_hours CHECK (
    (is_closed AND opens_at IS NULL AND closes_at IS NULL)
    OR (NOT is_closed AND opens_at IS NOT NULL AND closes_at IS NOT NULL AND opens_at < closes_at)
  ),
  CONSTRAINT ck_schedule_exceptions_note CHECK (note IS NULL OR char_length(note) <= 200)
)
""",
    "CREATE INDEX ix_schedule_exceptions_venue_date ON public.schedule_exceptions (venue_id, on_date)",
    # updated_at triggers (function created in 0002)
    "CREATE TRIGGER trg_schedule_rules_updated BEFORE UPDATE ON public.schedule_rules "
    "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()",
    "CREATE TRIGGER trg_schedule_exceptions_updated BEFORE UPDATE ON public.schedule_exceptions "
    "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()",
    # Same security model as 0003/0004: RLS on, SELECT-only, writes only through the API.
    "ALTER TABLE public.schedule_rules ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.schedule_exceptions ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON public.schedule_rules, public.schedule_exceptions FROM anon, authenticated",
    "GRANT SELECT ON public.schedule_rules, public.schedule_exceptions TO authenticated",
    # Visible exactly when the venue is visible to the caller (venues RLS: own venues, or published).
    "CREATE POLICY schedule_rules_select ON public.schedule_rules FOR SELECT TO authenticated "
    "USING (EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id))",
    "CREATE POLICY schedule_exceptions_select ON public.schedule_exceptions FOR SELECT TO authenticated "
    "USING (EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id))",
]


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.schedule_exceptions CASCADE")
    op.execute("DROP TABLE IF EXISTS public.schedule_rules CASCADE")
