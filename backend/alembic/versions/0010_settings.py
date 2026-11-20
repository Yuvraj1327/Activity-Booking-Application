"""Mobile Settings: per-type notification toggles, language, interests, deletion request, support tickets.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-20

Extends existing tables instead of adding new ones wherever an existing table fits:

* `notification_preferences`  + booking / payment / promo switches (push + email already exist)
* `profiles`                  + `language`, `deletion_requested_at`
* `customer_profiles`         + `preferred_category_ids` (sports a customer is interested in)
* `support_tickets`           NEW: feedback, issue reports and support requests (nothing existing fits)
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

UP = [
    "ALTER TABLE public.notification_preferences "
    "ADD COLUMN booking_enabled boolean NOT NULL DEFAULT true, "
    "ADD COLUMN payment_enabled boolean NOT NULL DEFAULT true, "
    "ADD COLUMN promo_enabled boolean NOT NULL DEFAULT true",
    "ALTER TABLE public.profiles "
    "ADD COLUMN language text NOT NULL DEFAULT 'en', "
    "ADD COLUMN deletion_requested_at timestamptz",
    "ALTER TABLE public.profiles ADD CONSTRAINT ck_profiles_language CHECK (language IN ('en','hi'))",
    "ALTER TABLE public.customer_profiles "
    "ADD COLUMN preferred_category_ids uuid[] NOT NULL DEFAULT '{}'",
    "ALTER TABLE public.customer_profiles ADD CONSTRAINT ck_customer_profiles_interests "
    "CHECK (cardinality(preferred_category_ids) <= 20)",
    """
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
)
""",
    "CREATE INDEX ix_support_tickets_user_created ON public.support_tickets (user_id, created_at DESC)",
    "CREATE TRIGGER trg_support_tickets_updated BEFORE UPDATE ON public.support_tickets "
    "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()",
    "ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON public.support_tickets FROM anon, authenticated",
]


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.support_tickets CASCADE")
    op.execute("ALTER TABLE public.customer_profiles DROP CONSTRAINT IF EXISTS ck_customer_profiles_interests")
    op.execute("ALTER TABLE public.customer_profiles DROP COLUMN IF EXISTS preferred_category_ids")
    op.execute("ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS ck_profiles_language")
    op.execute("ALTER TABLE public.profiles DROP COLUMN IF EXISTS deletion_requested_at, DROP COLUMN IF EXISTS language")
    op.execute(
        "ALTER TABLE public.notification_preferences DROP COLUMN IF EXISTS promo_enabled, "
        "DROP COLUMN IF EXISTS payment_enabled, DROP COLUMN IF EXISTS booking_enabled"
    )
