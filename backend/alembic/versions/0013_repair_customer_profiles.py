"""Repair customer accounts that have a `profiles` row but no `customer_profiles` row.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-27

`bookings.customer_id` (and payments, reviews, favourites) reference `customer_profiles(user_id)`. The API
registers both rows together, but a customer profile created any other way (SQL editor, import, an early
build) has no `customer_profiles` row, so `POST /bookings` failed with `bookings_customer_id_fkey`.

This is data-only: it inserts the missing row for every `role = 'customer'` profile. It never touches
owners or admins, never updates or deletes an existing row, and keeps every constraint, foreign key and
RLS policy. Re-running it inserts nothing. The service also provisions the row on demand
(ProfileService.ensure_customer_profile), so accounts created after this migration are covered too.

Downgrade is a deliberate no-op: the inserted rows cannot be told apart from rows created by the API, and
deleting customer data on a downgrade would be harmful.

Read-only check before/after (expect 0 after):
  SELECT count(*) FROM public.profiles p WHERE p.role = 'customer'
    AND NOT EXISTS (SELECT 1 FROM public.customer_profiles c WHERE c.user_id = p.id);
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

REPAIR_SQL = """
INSERT INTO public.customer_profiles (user_id, role)
SELECT p.id, p.role
FROM public.profiles p
WHERE p.role = 'customer'
  AND NOT EXISTS (SELECT 1 FROM public.customer_profiles c WHERE c.user_id = p.id)
ON CONFLICT (user_id) DO NOTHING
"""


def upgrade() -> None:
    op.execute(REPAIR_SQL)


def downgrade() -> None:
    pass
