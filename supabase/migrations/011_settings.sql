-- ============================================================================
-- ZURUV  011_settings
-- Alembic equivalent : revision 0010
-- Requires           : 010 (and all earlier files)
-- Safe to run        : once. Runs in one transaction; contains no DROP/TRUNCATE/DELETE of existing data.
-- Adds               : notification type switches, profile language + deletion request,
--                      customer sport interests, support_tickets (feedback / issue reports)
-- ============================================================================

BEGIN;

ALTER TABLE public.notification_preferences ADD COLUMN booking_enabled boolean NOT NULL DEFAULT true, ADD COLUMN payment_enabled boolean NOT NULL DEFAULT true, ADD COLUMN promo_enabled boolean NOT NULL DEFAULT true;

ALTER TABLE public.profiles ADD COLUMN language text NOT NULL DEFAULT 'en', ADD COLUMN deletion_requested_at timestamptz;

ALTER TABLE public.profiles ADD CONSTRAINT ck_profiles_language CHECK (language IN ('en','hi'));

ALTER TABLE public.customer_profiles ADD COLUMN preferred_category_ids uuid[] NOT NULL DEFAULT '{}';

ALTER TABLE public.customer_profiles ADD CONSTRAINT ck_customer_profiles_interests CHECK (cardinality(preferred_category_ids) <= 20);

CREATE TABLE public.support_tickets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  kind text NOT NULL,
  subject text NOT NULL,
  message text NOT NULL,
  app_version text,
  platform text,
  status text NOT NULL DEFAULT 'open',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_support_tickets_kind CHECK (kind IN ('support','feedback','issue')),
  CONSTRAINT ck_support_tickets_status CHECK (status IN ('open','closed')),
  CONSTRAINT ck_support_tickets_subject CHECK (char_length(btrim(subject)) BETWEEN 3 AND 120),
  CONSTRAINT ck_support_tickets_message CHECK (char_length(btrim(message)) BETWEEN 10 AND 2000)
);

CREATE INDEX ix_support_tickets_user_created ON public.support_tickets (user_id, created_at DESC);

CREATE TRIGGER trg_support_tickets_updated BEFORE UPDATE ON public.support_tickets FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.support_tickets FROM anon, authenticated;

-- Keep the Alembic marker in step (010 recorded 0009).
UPDATE public.alembic_version SET version_num = '0010' WHERE version_num = '0009';

COMMIT;
