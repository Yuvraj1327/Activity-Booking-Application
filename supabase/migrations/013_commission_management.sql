-- ============================================================================
-- ZURUV  013_commission_management
-- Alembic equivalent : revision 0012
-- Requires           : 012 (and all earlier files)
-- Safe to run        : once. Runs in one transaction; contains no DROP/TRUNCATE/DELETE of existing data.
-- Adds               : commission_rules + commission_rule_versions (append-only rule history: global /
--                      activity / venue), booking_commission_snapshots (immutable per-booking rate),
--                      commission columns on ledger_entries, finance_configs.commission_base.
-- Business decisions NOT made here (Q7-Q10): the commission base, tax/fee treatment, refund policy,
-- rounding and accrual milestone stay open. The ledger still needs an APPROVED finance configuration.
-- ============================================================================

BEGIN;

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
);

CREATE UNIQUE INDEX uq_commission_rules_global ON public.commission_rules ((true)) WHERE scope = 'global';

CREATE UNIQUE INDEX uq_commission_rules_category ON public.commission_rules (category_id) WHERE scope = 'activity';

CREATE UNIQUE INDEX uq_commission_rules_venue ON public.commission_rules (venue_id) WHERE scope = 'venue';

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
);

CREATE INDEX ix_crv_rule_effective ON public.commission_rule_versions (rule_id, effective_from DESC, version DESC);

CREATE INDEX ix_crv_created ON public.commission_rule_versions (created_at DESC);

CREATE INDEX ix_crv_created_by ON public.commission_rule_versions (created_by);

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
);

CREATE INDEX ix_bcs_rule ON public.booking_commission_snapshots (rule_id);

CREATE INDEX ix_bcs_scope ON public.booking_commission_snapshots (scope);

ALTER TABLE public.ledger_entries ADD COLUMN commission_bps integer, ADD COLUMN commission_scope text, ADD COLUMN commission_rule_id uuid REFERENCES public.commission_rules(id) ON DELETE RESTRICT, ADD COLUMN commission_rule_version integer, ADD COLUMN commission_base_paise bigint, ADD CONSTRAINT ck_ledger_commission_bps CHECK (commission_bps IS NULL OR commission_bps BETWEEN 0 AND 10000), ADD CONSTRAINT ck_ledger_commission_scope CHECK (commission_scope IS NULL OR commission_scope IN ('venue','activity','global','finance_config'));

CREATE INDEX ix_ledger_venue ON public.ledger_entries (venue_id, occurred_at DESC);

CREATE INDEX ix_ledger_commission_rule ON public.ledger_entries (commission_rule_id) WHERE commission_rule_id IS NOT NULL;

ALTER TABLE public.finance_configs ADD COLUMN commission_base text NOT NULL DEFAULT 'base', ADD CONSTRAINT ck_finance_commission_base CHECK (commission_base IN ('base','base_after_discount'));

CREATE TRIGGER trg_commission_rules_append_only BEFORE UPDATE OR DELETE ON public.commission_rules FOR EACH ROW EXECUTE FUNCTION public.forbid_modification();

CREATE TRIGGER trg_commission_rule_versions_append_only BEFORE UPDATE OR DELETE ON public.commission_rule_versions FOR EACH ROW EXECUTE FUNCTION public.forbid_modification();

CREATE TRIGGER trg_booking_commission_snapshots_append_only BEFORE UPDATE OR DELETE ON public.booking_commission_snapshots FOR EACH ROW EXECUTE FUNCTION public.forbid_modification();

ALTER TABLE public.commission_rules ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.commission_rules FROM anon, authenticated;

ALTER TABLE public.commission_rule_versions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.commission_rule_versions FROM anon, authenticated;

ALTER TABLE public.booking_commission_snapshots ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.booking_commission_snapshots FROM anon, authenticated;

UPDATE public.alembic_version SET version_num = '0012' WHERE version_num = '0011';

COMMIT;
