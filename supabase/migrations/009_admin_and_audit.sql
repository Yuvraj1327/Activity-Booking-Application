-- ============================================================================
-- ZURUV  009_admin_and_audit
-- Alembic equivalent : revisions 0001 (audit_logs), 0002 (append-only trigger), 0008 (admin report indexes)
-- Requires           : 005 and 002
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- ============================================================================

BEGIN;

-- Append-only audit log. Admin accounts themselves are created by the operator script
-- backend/scripts/create_admin.py, never through the public API.
CREATE TABLE public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id uuid REFERENCES public.profiles (id) ON DELETE SET NULL,
  actor_role text,
  action text NOT NULL,
  entity_type text,
  entity_id text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  request_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_audit_logs_actor_role CHECK (actor_role IS NULL OR actor_role IN ('customer', 'owner', 'admin', 'system')),
  CONSTRAINT ck_audit_logs_action CHECK (char_length(action) BETWEEN 1 AND 100),
  CONSTRAINT ck_audit_logs_metadata CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX ix_audit_logs_created_at ON public.audit_logs (created_at DESC);

CREATE INDEX ix_audit_logs_actor_id ON public.audit_logs (actor_id);

CREATE INDEX ix_audit_logs_entity ON public.audit_logs (entity_type, entity_id);

CREATE FUNCTION public.audit_logs_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE'
     AND NEW.actor_id IS NULL
     AND (to_jsonb(NEW) - 'actor_id') = (to_jsonb(OLD) - 'actor_id') THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'audit_logs is append-only' USING ERRCODE = 'insufficient_privilege';
END
$$;

CREATE TRIGGER trg_audit_logs_append_only BEFORE UPDATE OR DELETE ON public.audit_logs FOR EACH ROW EXECUTE FUNCTION public.audit_logs_append_only();

-- Revision 0008: indexes for admin dashboards and lists.
CREATE INDEX IF NOT EXISTS ix_bookings_created_at ON public.bookings (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_profiles_role_created ON public.profiles (role, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_venues_created_at ON public.venues (created_at DESC);

COMMIT;
