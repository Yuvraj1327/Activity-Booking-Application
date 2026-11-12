"""Triggers: updated_at, immutable role, append-only audit log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPDATED_AT_TABLES = [
    "profiles",
    "customer_profiles",
    "owner_profiles",
    "cities",
    "categories",
    "amenities",
    "venues",
    "venue_resources",
]


def upgrade() -> None:
    op.execute(
        """
CREATE FUNCTION public.set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$
"""
    )
    for table in UPDATED_AT_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_set_updated_at BEFORE UPDATE ON public.{table} "
            "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
        )

    # A role can never change after creation: privilege escalation by UPDATE is impossible
    # even for a buggy API path. Admins are created as admins (scripts/create_admin.py).
    op.execute(
        """
CREATE FUNCTION public.prevent_role_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.role IS DISTINCT FROM OLD.role THEN
    RAISE EXCEPTION 'profiles.role is immutable' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$
"""
    )
    op.execute(
        "CREATE TRIGGER trg_profiles_prevent_role_change BEFORE UPDATE OF role ON public.profiles "
        "FOR EACH ROW EXECUTE FUNCTION public.prevent_role_change()"
    )

    # Audit log is append-only. The one permitted change is the FK action that nulls actor_id
    # when a profile is removed.
    op.execute(
        """
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
$$
"""
    )
    op.execute(
        "CREATE TRIGGER trg_audit_logs_append_only BEFORE UPDATE OR DELETE ON public.audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION public.audit_logs_append_only()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON public.audit_logs")
    op.execute("DROP FUNCTION IF EXISTS public.audit_logs_append_only()")
    op.execute("DROP TRIGGER IF EXISTS trg_profiles_prevent_role_change ON public.profiles")
    op.execute("DROP FUNCTION IF EXISTS public.prevent_role_change()")
    for table in UPDATED_AT_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_set_updated_at ON public.{table}")
    op.execute("DROP FUNCTION IF EXISTS public.set_updated_at()")
