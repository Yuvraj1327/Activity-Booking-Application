"""Indexes for admin dashboards and lists (Step 9 performance review). Indexes only.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-12

The admin console filters bookings by creation date and lists owners/customers by registration
date. Neither access path had an index, so those queries would scan whole tables as data grows.
No table, column, constraint or business rule changes.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_created_at ON public.bookings (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_profiles_role_created ON public.profiles (role, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_venues_created_at ON public.venues (created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_venues_created_at")
    op.execute("DROP INDEX IF EXISTS public.ix_profiles_role_created")
    op.execute("DROP INDEX IF EXISTS public.ix_bookings_created_at")
