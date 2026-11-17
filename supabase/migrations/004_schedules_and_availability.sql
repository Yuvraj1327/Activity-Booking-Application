-- ============================================================================
-- ZURUV  004_schedules_and_availability
-- Alembic equivalent : revisions 0001 (venue_resources), 0005 (schedules), 0006 (slot columns, availability_blocks)
-- Requires           : 003
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- ============================================================================

BEGIN;

-- Courts / bookable resources of a venue.
CREATE TABLE public.venue_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  name text NOT NULL,
  sort_order integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_venue_resources_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 80),
  CONSTRAINT ck_venue_resources_sort_order CHECK (sort_order >= 0)
);

CREATE UNIQUE INDEX uq_venue_resources_venue_name ON public.venue_resources (venue_id, lower(name));

-- Revision 0006: slot length and price per court.
ALTER TABLE public.venue_resources ADD COLUMN slot_minutes integer, ADD COLUMN slot_price_paise bigint;

ALTER TABLE public.venue_resources ADD CONSTRAINT ck_venue_resources_slot_minutes CHECK (slot_minutes IS NULL OR slot_minutes BETWEEN 5 AND 720);

ALTER TABLE public.venue_resources ADD CONSTRAINT ck_venue_resources_slot_price CHECK (slot_price_paise IS NULL OR slot_price_paise BETWEEN 0 AND 100000000);

CREATE TRIGGER trg_venue_resources_set_updated_at BEFORE UPDATE ON public.venue_resources FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Weekly opening hours and date exceptions.
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
);

CREATE INDEX ix_schedule_rules_venue ON public.schedule_rules (venue_id, weekday);

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
);

CREATE INDEX ix_schedule_exceptions_venue_date ON public.schedule_exceptions (venue_id, on_date);

CREATE TRIGGER trg_schedule_rules_updated BEFORE UPDATE ON public.schedule_rules FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_schedule_exceptions_updated BEFORE UPDATE ON public.schedule_exceptions FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- Owner/admin blocks on a court or whole venue.
CREATE TABLE public.availability_blocks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE CASCADE,
  resource_id uuid REFERENCES public.venue_resources(id) ON DELETE CASCADE,
  block_range tstzrange NOT NULL,
  reason text,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_blocks_range CHECK (
    NOT isempty(block_range) AND lower_inf(block_range) = false AND upper_inf(block_range) = false),
  CONSTRAINT ck_blocks_reason CHECK (reason IS NULL OR char_length(reason) <= 200)
);

CREATE INDEX ix_blocks_venue ON public.availability_blocks (venue_id);

COMMIT;
