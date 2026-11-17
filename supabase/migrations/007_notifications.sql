-- ============================================================================
-- ZURUV  007_notifications
-- Alembic equivalent : revisions 0001 (notifications), 0007 (push/dedupe columns, device tokens, preferences, e-mail log)
-- Requires           : 006 (notifications reference bookings and payments)
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- ============================================================================

BEGIN;

CREATE TABLE public.notifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.profiles (id) ON DELETE CASCADE,
  type text NOT NULL,
  title text NOT NULL,
  body text,
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  read_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_notifications_type CHECK (char_length(type) BETWEEN 1 AND 60),
  CONSTRAINT ck_notifications_title CHECK (char_length(btrim(title)) BETWEEN 1 AND 160),
  CONSTRAINT ck_notifications_body CHECK (body IS NULL OR char_length(body) <= 1000),
  CONSTRAINT ck_notifications_data CHECK (jsonb_typeof(data) = 'object')
);

CREATE INDEX ix_notifications_user_created ON public.notifications (user_id, created_at DESC);

CREATE INDEX ix_notifications_user_unread ON public.notifications (user_id) WHERE read_at IS NULL;

-- Revision 0007: booking/payment links, de-duplication, push delivery state.
ALTER TABLE public.notifications ADD COLUMN booking_id uuid REFERENCES public.bookings(id) ON DELETE SET NULL, ADD COLUMN payment_id uuid REFERENCES public.payments(id) ON DELETE SET NULL, ADD COLUMN dedupe_key text, ADD COLUMN push_status text NOT NULL DEFAULT 'skipped', ADD COLUMN push_attempts integer NOT NULL DEFAULT 0, ADD COLUMN push_sent_at timestamptz;

ALTER TABLE public.notifications ADD CONSTRAINT ck_notifications_push_status CHECK (push_status IN ('pending','sent','failed','skipped'));

CREATE UNIQUE INDEX uq_notifications_dedupe ON public.notifications (user_id, dedupe_key) WHERE dedupe_key IS NOT NULL;

CREATE INDEX ix_notifications_push_pending ON public.notifications (created_at) WHERE push_status = 'pending';

CREATE TABLE public.user_device_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  token text NOT NULL,
  platform text NOT NULL,
  app text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_device_tokens_platform CHECK (platform IN ('android','ios','web')),
  CONSTRAINT ck_device_tokens_app CHECK (app IN ('customer','owner','admin')),
  CONSTRAINT ck_device_tokens_token CHECK (char_length(token) BETWEEN 20 AND 4096)
);

CREATE UNIQUE INDEX uq_device_tokens_token ON public.user_device_tokens (token);

CREATE INDEX ix_device_tokens_user ON public.user_device_tokens (user_id);

CREATE TRIGGER trg_device_tokens_updated BEFORE UPDATE ON public.user_device_tokens FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.notification_preferences (
  user_id uuid PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  push_enabled boolean NOT NULL DEFAULT true,
  email_enabled boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_notification_preferences_updated BEFORE UPDATE ON public.notification_preferences FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.email_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  to_email text NOT NULL,
  template text NOT NULL,
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  dedupe_key text NOT NULL,
  status text NOT NULL DEFAULT 'queued',
  attempts integer NOT NULL DEFAULT 0,
  provider_message_id text,
  last_error text,
  booking_id uuid REFERENCES public.bookings(id) ON DELETE SET NULL,
  payment_id uuid REFERENCES public.payments(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  CONSTRAINT ck_email_deliveries_status CHECK (status IN ('queued','sent','failed','skipped')),
  CONSTRAINT ck_email_deliveries_context CHECK (jsonb_typeof(context) = 'object')
);

CREATE UNIQUE INDEX uq_email_deliveries_dedupe ON public.email_deliveries (dedupe_key);

CREATE INDEX ix_email_deliveries_queue ON public.email_deliveries (created_at) WHERE status = 'queued';

CREATE TRIGGER trg_email_deliveries_updated BEFORE UPDATE ON public.email_deliveries FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMIT;
