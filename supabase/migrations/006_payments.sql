-- ============================================================================
-- ZURUV  006_payments
-- Alembic equivalent : revision 0007 (payments, payment_events)
-- Requires           : 005
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- Refunds           : the application has no separate refunds table (refund policy is an open
--                    business question, Q9). Refund state is recorded as payments.status
--                    'refunded'/'partially_refunded' and bookings.status 'refund_pending'/'refunded'.
-- ============================================================================

BEGIN;

CREATE TABLE public.payments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
  customer_id uuid NOT NULL REFERENCES public.customer_profiles(user_id) ON DELETE RESTRICT,
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE RESTRICT,
  provider text NOT NULL DEFAULT 'razorpay',
  provider_order_id text NOT NULL,
  provider_payment_id text,
  amount_paise bigint NOT NULL,
  currency text NOT NULL,
  status text NOT NULL DEFAULT 'created',
  method text,
  failure_code text,
  failure_reason text,
  review_required boolean NOT NULL DEFAULT false,
  review_reason text,
  gateway_refs jsonb NOT NULL DEFAULT '{}'::jsonb,
  captured_at timestamptz,
  failed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_payments_status CHECK (status IN ('created','pending','authorized','captured','failed','refunded','partially_refunded')),
  CONSTRAINT ck_payments_amount CHECK (amount_paise > 0),
  CONSTRAINT ck_payments_provider CHECK (provider IN ('razorpay')),
  CONSTRAINT ck_payments_captured CHECK (
    status NOT IN ('captured','refunded','partially_refunded') OR provider_payment_id IS NOT NULL),
  CONSTRAINT ck_payments_refs CHECK (jsonb_typeof(gateway_refs) = 'object'),
  CONSTRAINT ck_payments_review CHECK (NOT review_required OR review_reason IS NOT NULL)
);

CREATE UNIQUE INDEX uq_payments_booking ON public.payments (booking_id);

CREATE UNIQUE INDEX uq_payments_order ON public.payments (provider, provider_order_id);

CREATE UNIQUE INDEX uq_payments_provider_payment ON public.payments (provider, provider_payment_id) WHERE provider_payment_id IS NOT NULL;

CREATE INDEX ix_payments_customer ON public.payments (customer_id, created_at DESC);

CREATE INDEX ix_payments_venue ON public.payments (venue_id, created_at DESC);

CREATE INDEX ix_payments_status ON public.payments (status, created_at);

CREATE INDEX ix_payments_review ON public.payments (created_at) WHERE review_required;

CREATE TRIGGER trg_payments_updated BEFORE UPDATE ON public.payments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.payment_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id uuid REFERENCES public.payments(id) ON DELETE CASCADE,
  provider_event_id text,
  event_type text NOT NULL,
  source text NOT NULL,
  provider_order_id text,
  provider_payment_id text,
  outcome text NOT NULL,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_payment_events_source CHECK (source IN ('webhook','verify','reconcile','system')),
  CONSTRAINT ck_payment_events_outcome CHECK (outcome IN ('applied','duplicate','ignored','rejected')),
  CONSTRAINT ck_payment_events_detail CHECK (jsonb_typeof(detail) = 'object')
);

CREATE UNIQUE INDEX uq_payment_events_provider_event ON public.payment_events (provider_event_id) WHERE provider_event_id IS NOT NULL;

CREATE INDEX ix_payment_events_payment ON public.payment_events (payment_id, created_at);

CREATE INDEX ix_payment_events_outcome ON public.payment_events (outcome, created_at DESC);

CREATE FUNCTION public.payment_events_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'payment_events rows cannot be modified' USING ERRCODE = 'integrity_constraint_violation';
END $$;

CREATE TRIGGER trg_payment_events_no_update BEFORE UPDATE ON public.payment_events FOR EACH ROW EXECUTE FUNCTION public.payment_events_append_only();

COMMIT;
