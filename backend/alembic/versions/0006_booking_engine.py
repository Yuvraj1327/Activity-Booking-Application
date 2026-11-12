"""Booking engine: bookable resources, bookings, reserved slots, status history, blocks (Step 6).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-12

Follows architecture section 9. Unresolved business rules are NOT given defaults here:

* venue_resources gets `slot_minutes` and `slot_price_paise`, both set by the owner. While either
  is NULL the resource is "not configured" and produces no slots (open questions Q1, Q2, N2, Q17).
* booking_slots carries the double-booking guarantee: an EXCLUDE constraint makes two blocking
  rows for the same resource with overlapping time ranges impossible, whatever the application does.
* Hold length, fees, tax, commission and cancellation charges are not stored as rules; a booking
  keeps a price SNAPSHOT (jsonb) of what was applied at the time.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = (
    "'pending_payment','payment_failed','confirmed','expired','cancelled_by_customer',"
    "'cancelled_by_owner','completed','refund_pending','refunded'"
)

UP = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    # ---- resources become configurable
    "ALTER TABLE public.venue_resources ADD COLUMN slot_minutes integer, "
    "ADD COLUMN slot_price_paise bigint",
    "ALTER TABLE public.venue_resources ADD CONSTRAINT ck_venue_resources_slot_minutes "
    "CHECK (slot_minutes IS NULL OR slot_minutes BETWEEN 5 AND 720)",
    "ALTER TABLE public.venue_resources ADD CONSTRAINT ck_venue_resources_slot_price "
    "CHECK (slot_price_paise IS NULL OR slot_price_paise BETWEEN 0 AND 100000000)",
    # ---- bookings
    f"""
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
  price_snapshot jsonb NOT NULL DEFAULT '{{}}'::jsonb,
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
  CONSTRAINT ck_bookings_status CHECK (status IN ({STATUSES})),
  CONSTRAINT ck_bookings_payment_status CHECK (payment_status IN ('unpaid','pending','paid','failed','refunded')),
  CONSTRAINT ck_bookings_range CHECK (ends_at > starts_at),
  CONSTRAINT ck_bookings_duration CHECK (duration_minutes > 0
    AND duration_minutes * 60 = extract(epoch FROM (ends_at - starts_at))::int),
  CONSTRAINT ck_bookings_amounts CHECK (base_amount_paise >= 0 AND total_amount_paise >= 0),
  CONSTRAINT ck_bookings_hold CHECK (status <> 'pending_payment' OR expires_at IS NOT NULL),
  CONSTRAINT ck_bookings_code CHECK (char_length(booking_code) BETWEEN 6 AND 20),
  CONSTRAINT ck_bookings_reason CHECK (cancel_reason IS NULL OR char_length(cancel_reason) <= 300)
)
""",
    "CREATE UNIQUE INDEX uq_bookings_code ON public.bookings (booking_code)",
    "CREATE UNIQUE INDEX uq_bookings_idempotency ON public.bookings (customer_id, idempotency_key) "
    "WHERE idempotency_key IS NOT NULL",
    "CREATE INDEX ix_bookings_customer ON public.bookings (customer_id, starts_at DESC)",
    "CREATE INDEX ix_bookings_venue ON public.bookings (venue_id, starts_at DESC)",
    "CREATE INDEX ix_bookings_resource ON public.bookings (resource_id, starts_at)",
    "CREATE INDEX ix_bookings_status ON public.bookings (status)",
    "CREATE INDEX ix_bookings_holds ON public.bookings (expires_at) WHERE status = 'pending_payment'",
    "CREATE TRIGGER trg_bookings_updated BEFORE UPDATE ON public.bookings "
    "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()",
    # ---- reserved time: the double-booking guarantee
    """
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
)
""",
    "CREATE INDEX ix_booking_slots_booking ON public.booking_slots (booking_id)",
    "CREATE INDEX ix_booking_slots_resource_range ON public.booking_slots USING gist (resource_id, slot_range)",
    # ---- status history (append-only)
    """
CREATE TABLE public.booking_status_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE CASCADE,
  from_status text,
  to_status text NOT NULL,
  actor_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  actor_role text NOT NULL,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_bsh_to CHECK (to_status IN ("""
    + STATUSES
    + """)),
  CONSTRAINT ck_bsh_actor CHECK (actor_role IN ('customer','owner','admin','system'))
)
""",
    "CREATE INDEX ix_bsh_booking ON public.booking_status_history (booking_id, created_at)",
    """
CREATE FUNCTION public.booking_history_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'booking_status_history rows cannot be modified' USING ERRCODE = 'integrity_constraint_violation';
END $$
""",
    "CREATE TRIGGER trg_bsh_no_update BEFORE UPDATE ON public.booking_status_history "
    "FOR EACH ROW EXECUTE FUNCTION public.booking_history_append_only()",
    # ---- temporary unavailable periods set by the owner
    """
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
)
""",
    "CREATE INDEX ix_blocks_venue ON public.availability_blocks (venue_id)",
    # ---- same security model as earlier steps: RLS on, SELECT-only, writes only through the API
    "ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.booking_slots ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.booking_status_history ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE public.availability_blocks ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON public.bookings, public.booking_slots, public.booking_status_history, "
    "public.availability_blocks FROM anon, authenticated",
    "GRANT SELECT ON public.bookings, public.booking_slots, public.booking_status_history, "
    "public.availability_blocks TO authenticated",
    "CREATE POLICY bookings_select_own ON public.bookings FOR SELECT TO authenticated "
    "USING (customer_id = (SELECT auth.uid()))",
    "CREATE POLICY bookings_select_owner ON public.bookings FOR SELECT TO authenticated "
    "USING ((SELECT public.app_user_role()) = 'owner' AND EXISTS "
    "(SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = (SELECT auth.uid())))",
    "CREATE POLICY bookings_select_admin ON public.bookings FOR SELECT TO authenticated "
    "USING ((SELECT public.app_user_role()) = 'admin')",
    "CREATE POLICY booking_slots_select ON public.booking_slots FOR SELECT TO authenticated "
    "USING (EXISTS (SELECT 1 FROM public.bookings b WHERE b.id = booking_id))",
    "CREATE POLICY bsh_select ON public.booking_status_history FOR SELECT TO authenticated "
    "USING (EXISTS (SELECT 1 FROM public.bookings b WHERE b.id = booking_id))",
    "CREATE POLICY blocks_select_owner ON public.availability_blocks FOR SELECT TO authenticated "
    "USING ((SELECT public.app_user_role()) = 'owner' AND EXISTS "
    "(SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = (SELECT auth.uid())))",
    "CREATE POLICY blocks_select_admin ON public.availability_blocks FOR SELECT TO authenticated "
    "USING ((SELECT public.app_user_role()) = 'admin')",
]


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    for table in ("availability_blocks", "booking_status_history", "booking_slots", "bookings"):
        op.execute(f"DROP TABLE IF EXISTS public.{table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS public.booking_history_append_only()")
    op.execute("ALTER TABLE public.venue_resources DROP CONSTRAINT IF EXISTS ck_venue_resources_slot_price")
    op.execute("ALTER TABLE public.venue_resources DROP CONSTRAINT IF EXISTS ck_venue_resources_slot_minutes")
    op.execute("ALTER TABLE public.venue_resources DROP COLUMN IF EXISTS slot_price_paise, DROP COLUMN IF EXISTS slot_minutes")
