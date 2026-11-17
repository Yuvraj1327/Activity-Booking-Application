-- ============================================================================
-- ZURUV  005_bookings
-- Alembic equivalent : revision 0006 (booking engine)
-- Requires           : 004 (and 002/003 for customers and venues)
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- Double booking    : prevented by the ex_booking_slots_no_overlap GiST exclusion constraint,
--                    not only by application code.
-- ============================================================================

BEGIN;

CREATE TABLE public.bookings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_code text NOT NULL,
  customer_id uuid NOT NULL REFERENCES public.customer_profiles(user_id) ON DELETE RESTRICT,
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE RESTRICT,
  resource_id uuid NOT NULL REFERENCES public.venue_resources(id) ON DELETE RESTRICT,
  status text NOT NULL,
  payment_status text NOT NULL DEFAULT 'unpaid',
  booking_date date NOT NULL,
  starts_at timestamptz NOT NULL,
  ends_at timestamptz NOT NULL,
  duration_minutes integer NOT NULL,
  base_amount_paise bigint NOT NULL,
  total_amount_paise bigint NOT NULL,
  currency text NOT NULL DEFAULT 'INR',
  price_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
  venue_name text NOT NULL,
  resource_name text NOT NULL,
  timezone text NOT NULL,
  expires_at timestamptz,
  idempotency_key text,
  request_hash text,
  confirmed_at timestamptz,
  cancelled_at timestamptz,
  cancelled_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  cancel_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_bookings_status CHECK (status IN ('pending_payment','payment_failed','confirmed','expired','cancelled_by_customer','cancelled_by_owner','completed','refund_pending','refunded')),
  CONSTRAINT ck_bookings_payment_status CHECK (payment_status IN ('unpaid','pending','paid','failed','refunded')),
  CONSTRAINT ck_bookings_range CHECK (ends_at > starts_at),
  CONSTRAINT ck_bookings_duration CHECK (duration_minutes > 0
    AND duration_minutes * 60 = extract(epoch FROM (ends_at - starts_at))::int),
  CONSTRAINT ck_bookings_amounts CHECK (base_amount_paise >= 0 AND total_amount_paise >= 0),
  CONSTRAINT ck_bookings_hold CHECK (status <> 'pending_payment' OR expires_at IS NOT NULL),
  CONSTRAINT ck_bookings_code CHECK (char_length(booking_code) BETWEEN 6 AND 20),
  CONSTRAINT ck_bookings_reason CHECK (cancel_reason IS NULL OR char_length(cancel_reason) <= 300)
);

CREATE UNIQUE INDEX uq_bookings_code ON public.bookings (booking_code);

CREATE UNIQUE INDEX uq_bookings_idempotency ON public.bookings (customer_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE INDEX ix_bookings_customer ON public.bookings (customer_id, starts_at DESC);

CREATE INDEX ix_bookings_venue ON public.bookings (venue_id, starts_at DESC);

CREATE INDEX ix_bookings_resource ON public.bookings (resource_id, starts_at);

CREATE INDEX ix_bookings_status ON public.bookings (status);

CREATE INDEX ix_bookings_holds ON public.bookings (expires_at) WHERE status = 'pending_payment';

CREATE TRIGGER trg_bookings_updated BEFORE UPDATE ON public.bookings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.booking_slots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE CASCADE,
  resource_id uuid NOT NULL REFERENCES public.venue_resources(id) ON DELETE RESTRICT,
  slot_range tstzrange NOT NULL,
  is_blocking boolean NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_booking_slots_range CHECK (
    NOT isempty(slot_range) AND lower_inf(slot_range) = false AND upper_inf(slot_range) = false),
  CONSTRAINT ex_booking_slots_no_overlap EXCLUDE USING gist
    (resource_id WITH =, slot_range WITH &&) WHERE (is_blocking)
);

CREATE INDEX ix_booking_slots_booking ON public.booking_slots (booking_id);

CREATE INDEX ix_booking_slots_resource_range ON public.booking_slots USING gist (resource_id, slot_range);

CREATE TABLE public.booking_status_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE CASCADE,
  from_status text,
  to_status text NOT NULL,
  actor_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  actor_role text NOT NULL,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_bsh_to CHECK (to_status IN ('pending_payment','payment_failed','confirmed','expired','cancelled_by_customer','cancelled_by_owner','completed','refund_pending','refunded')),
  CONSTRAINT ck_bsh_actor CHECK (actor_role IN ('customer','owner','admin','system'))
);

CREATE INDEX ix_bsh_booking ON public.booking_status_history (booking_id, created_at);

CREATE FUNCTION public.booking_history_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'booking_status_history rows cannot be modified' USING ERRCODE = 'integrity_constraint_violation';
END $$;

CREATE TRIGGER trg_bsh_no_update BEFORE UPDATE ON public.booking_status_history FOR EACH ROW EXECUTE FUNCTION public.booking_history_append_only();

COMMIT;
