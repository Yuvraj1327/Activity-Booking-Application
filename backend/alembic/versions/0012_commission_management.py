"""Commission management: versioned rules, immutable per-booking snapshots, commission columns on the ledger.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-27

Design (see docs/COMMISSION_MANAGEMENT.md):
  commission_rules          identity of a rule: scope global / activity (category) / venue. One row per target.
  commission_rule_versions  append-only. Every create / edit / activate / deactivate is a NEW version row with
                            its own effective_from, previous percentage, reason and admin. A rule's state at any
                            instant is the version with the greatest effective_from <= that instant.
  booking_commission_snapshots  append-only. The rate resolved when a booking is created. Later rule edits never
                            touch it, and the ledger accrues from it.
  ledger_entries            gains the commission rate / rule / version actually used (nullable for pre-existing rows).
  finance_configs           gains `commission_base` (which amount the percentage is applied to). Defaults to the
                            behaviour that already existed ('base': the slot price before discounts, fees and tax).

Which base, tax / fee treatment, refund policy, rounding and accrual milestone are still business decisions
(Q7-Q10): nothing here approves them. The ledger still needs an APPROVED finance configuration.
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

NEW_TABLES = ["commission_rules", "commission_rule_versions", "booking_commission_snapshots"]
APPEND_ONLY = NEW_TABLES

STATEMENTS = [
    # ------------------------------------------------------------------ rule identity
    """
CREATE TABLE public.commission_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scope text NOT NULL,
  category_id uuid REFERENCES public.categories(id) ON DELETE RESTRICT,
  venue_id uuid REFERENCES public.venues(id) ON DELETE RESTRICT,
  created_by uuid REFERENCES public.profiles(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_commission_rules_scope CHECK (scope IN ('global','activity','venue')),
  CONSTRAINT ck_commission_rules_target CHECK (
    (scope = 'global' AND category_id IS NULL AND venue_id IS NULL) OR
    (scope = 'activity' AND category_id IS NOT NULL AND venue_id IS NULL) OR
    (scope = 'venue' AND venue_id IS NOT NULL AND category_id IS NULL))
)
""",
    "CREATE UNIQUE INDEX uq_commission_rules_global ON public.commission_rules ((true)) WHERE scope = 'global'",
    "CREATE UNIQUE INDEX uq_commission_rules_category ON public.commission_rules (category_id) WHERE scope = 'activity'",
    "CREATE UNIQUE INDEX uq_commission_rules_venue ON public.commission_rules (venue_id) WHERE scope = 'venue'",
    # ------------------------------------------------------------------ rule versions (history)
    """
CREATE TABLE public.commission_rule_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id uuid NOT NULL REFERENCES public.commission_rules(id) ON DELETE RESTRICT,
  version integer NOT NULL,
  commission_bps integer NOT NULL,
  previous_bps integer,
  is_active boolean NOT NULL,
  effective_from timestamptz NOT NULL,
  reason text NOT NULL,
  created_by uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_commission_rule_versions UNIQUE (rule_id, version),
  CONSTRAINT ck_crv_version CHECK (version >= 1),
  CONSTRAINT ck_crv_bps CHECK (commission_bps BETWEEN 0 AND 10000),
  CONSTRAINT ck_crv_prev CHECK (previous_bps IS NULL OR previous_bps BETWEEN 0 AND 10000),
  CONSTRAINT ck_crv_reason CHECK (char_length(btrim(reason)) BETWEEN 3 AND 500)
)
""",
    "CREATE INDEX ix_crv_rule_effective ON public.commission_rule_versions (rule_id, effective_from DESC, version DESC)",
    "CREATE INDEX ix_crv_created ON public.commission_rule_versions (created_at DESC)",
    "CREATE INDEX ix_crv_created_by ON public.commission_rule_versions (created_by)",
    # ------------------------------------------------------------------ booking snapshots
    """
CREATE TABLE public.booking_commission_snapshots (
  booking_id uuid PRIMARY KEY REFERENCES public.bookings(id) ON DELETE RESTRICT,
  scope text NOT NULL,
  rule_id uuid REFERENCES public.commission_rules(id) ON DELETE RESTRICT,
  rule_version_id uuid REFERENCES public.commission_rule_versions(id) ON DELETE RESTRICT,
  rule_version integer,
  category_id uuid REFERENCES public.categories(id) ON DELETE RESTRICT,
  commission_bps integer,
  effective_at timestamptz NOT NULL,
  resolved_at timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL DEFAULT 'booking_created',
  ambiguous boolean NOT NULL DEFAULT false,
  priority text[] NOT NULL,
  candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
  CONSTRAINT ck_bcs_scope CHECK (scope IN ('venue','activity','global','none')),
  CONSTRAINT ck_bcs_bps CHECK (commission_bps IS NULL OR commission_bps BETWEEN 0 AND 10000),
  CONSTRAINT ck_bcs_source CHECK (source IN ('booking_created','accrual_backfill')),
  CONSTRAINT ck_bcs_ambiguous CHECK (NOT ambiguous OR scope = 'none'),
  CONSTRAINT ck_bcs_consistent CHECK (
    (scope = 'none' AND rule_id IS NULL AND rule_version_id IS NULL AND commission_bps IS NULL) OR
    (scope <> 'none' AND rule_id IS NOT NULL AND rule_version_id IS NOT NULL AND commission_bps IS NOT NULL
       AND rule_version IS NOT NULL)),
  CONSTRAINT ck_bcs_candidates CHECK (jsonb_typeof(candidates) = 'array')
)
""",
    "CREATE INDEX ix_bcs_rule ON public.booking_commission_snapshots (rule_id)",
    "CREATE INDEX ix_bcs_scope ON public.booking_commission_snapshots (scope)",
    # ------------------------------------------------------------------ ledger: which commission was used
    "ALTER TABLE public.ledger_entries "
    "ADD COLUMN commission_bps integer, "
    "ADD COLUMN commission_scope text, "
    "ADD COLUMN commission_rule_id uuid REFERENCES public.commission_rules(id) ON DELETE RESTRICT, "
    "ADD COLUMN commission_rule_version integer, "
    "ADD COLUMN commission_base_paise bigint, "
    "ADD CONSTRAINT ck_ledger_commission_bps CHECK (commission_bps IS NULL OR commission_bps BETWEEN 0 AND 10000), "
    "ADD CONSTRAINT ck_ledger_commission_scope CHECK "
    "(commission_scope IS NULL OR commission_scope IN ('venue','activity','global','finance_config'))",
    "CREATE INDEX ix_ledger_venue ON public.ledger_entries (venue_id, occurred_at DESC)",
    "CREATE INDEX ix_ledger_commission_rule ON public.ledger_entries (commission_rule_id) "
    "WHERE commission_rule_id IS NOT NULL",
    # ------------------------------------------------------------------ finance config: commission base
    "ALTER TABLE public.finance_configs ADD COLUMN commission_base text NOT NULL DEFAULT 'base', "
    "ADD CONSTRAINT ck_finance_commission_base CHECK (commission_base IN ('base','base_after_discount'))",
]


def _tail() -> list[str]:
    out: list[str] = []
    for t in APPEND_ONLY:
        out.append(
            f"CREATE TRIGGER trg_{t}_append_only BEFORE UPDATE OR DELETE ON public.{t} "
            "FOR EACH ROW EXECUTE FUNCTION public.forbid_modification()"
        )
    for t in NEW_TABLES:
        out.append(f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY")
        out.append(f"REVOKE ALL ON public.{t} FROM anon, authenticated")
    return out


ALL_STATEMENTS = STATEMENTS + _tail()


def upgrade() -> None:
    for statement in ALL_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("ALTER TABLE public.finance_configs DROP CONSTRAINT IF EXISTS ck_finance_commission_base")
    op.execute("ALTER TABLE public.finance_configs DROP COLUMN IF EXISTS commission_base")
    op.execute("DROP INDEX IF EXISTS public.ix_ledger_commission_rule")
    op.execute("DROP INDEX IF EXISTS public.ix_ledger_venue")
    op.execute(
        "ALTER TABLE public.ledger_entries DROP CONSTRAINT IF EXISTS ck_ledger_commission_scope, "
        "DROP CONSTRAINT IF EXISTS ck_ledger_commission_bps, DROP COLUMN IF EXISTS commission_base_paise, "
        "DROP COLUMN IF EXISTS commission_rule_version, DROP COLUMN IF EXISTS commission_rule_id, "
        "DROP COLUMN IF EXISTS commission_scope, DROP COLUMN IF EXISTS commission_bps"
    )
    for t in reversed(NEW_TABLES):
        op.execute(f"DROP TABLE IF EXISTS public.{t} CASCADE")
