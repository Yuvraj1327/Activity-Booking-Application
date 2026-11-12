"""Identity, catalogue, venues, notifications and audit tables.

Revision ID: 0001
Revises:
Create Date: 2026-11-12

Design notes (see docs/DATABASE_SCHEMA.md):
* One role per account (profiles.role), enforced for the role tables by a composite FK.
* Role/status live here, never in JWT metadata (decision D-11).
* Money tables, bookings, payments etc. are NOT created here (later steps).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = "created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()"
_PHONE = r"'^\+[1-9][0-9]{6,14}$'"

UP = [
    # Guard: this schema FKs to auth.users, which only exists on Supabase (or the local stub).
    r"""
DO $$
BEGIN
  IF to_regclass('auth.users') IS NULL THEN
    RAISE EXCEPTION 'auth.users not found. Run against a Supabase database, or load supabase/local/supabase_stub.sql into a LOCAL test database first.';
  END IF;
END
$$
""",
    # ---- identity -------------------------------------------------------------------
    rf"""
CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE RESTRICT,
  role text NOT NULL,
  status text NOT NULL DEFAULT 'active',
  full_name text NOT NULL,
  email text,
  phone text,
  avatar_path text,
  {_TS},
  CONSTRAINT ck_profiles_role CHECK (role IN ('customer', 'owner', 'admin')),
  CONSTRAINT ck_profiles_status CHECK (status IN ('active', 'suspended')),
  CONSTRAINT ck_profiles_full_name CHECK (char_length(btrim(full_name)) BETWEEN 1 AND 120),
  CONSTRAINT ck_profiles_email CHECK (email IS NULL OR char_length(email) <= 320),
  CONSTRAINT ck_profiles_phone CHECK (phone IS NULL OR phone ~ {_PHONE}),
  CONSTRAINT ck_profiles_avatar_path CHECK (
    avatar_path IS NULL OR (avatar_path LIKE id::text || '/%' AND char_length(avatar_path) <= 300)
  ),
  CONSTRAINT uq_profiles_id_role UNIQUE (id, role)
)
""",
    "CREATE INDEX ix_profiles_role ON public.profiles (role)",
    "CREATE INDEX ix_profiles_status ON public.profiles (status) WHERE status <> 'active'",
    "CREATE INDEX ix_profiles_lower_email ON public.profiles (lower(email))",
    # ---- reference data ---------------------------------------------------------------
    rf"""
CREATE TABLE public.cities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  state text,
  country_code char(2) NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  {_TS},
  CONSTRAINT ck_cities_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
  CONSTRAINT ck_cities_country_code CHECK (country_code ~ '^[A-Z]{{2}}$')
)
""",
    "CREATE UNIQUE INDEX uq_cities_name_state_country ON public.cities "
    "(lower(name), lower(coalesce(state, '')), country_code)",
    rf"""
CREATE TABLE public.categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL,
  name text NOT NULL,
  icon_key text,
  sort_order integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  {_TS},
  CONSTRAINT uq_categories_slug UNIQUE (slug),
  CONSTRAINT ck_categories_slug CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 60),
  CONSTRAINT ck_categories_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 80)
)
""",
    rf"""
CREATE TABLE public.amenities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL,
  name text NOT NULL,
  icon_key text,
  sort_order integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  {_TS},
  CONSTRAINT uq_amenities_slug UNIQUE (slug),
  CONSTRAINT ck_amenities_slug CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 60),
  CONSTRAINT ck_amenities_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 80)
)
""",
    # ---- role extension tables (composite FK pins profiles.role) ------------------------
    rf"""
CREATE TABLE public.customer_profiles (
  user_id uuid PRIMARY KEY,
  role text NOT NULL DEFAULT 'customer',
  preferred_city_id uuid REFERENCES public.cities (id) ON DELETE SET NULL,
  {_TS},
  CONSTRAINT ck_customer_profiles_role CHECK (role = 'customer'),
  CONSTRAINT fk_customer_profiles_user_id_profiles
    FOREIGN KEY (user_id, role) REFERENCES public.profiles (id, role) ON DELETE CASCADE
)
""",
    rf"""
CREATE TABLE public.owner_profiles (
  user_id uuid PRIMARY KEY,
  role text NOT NULL DEFAULT 'owner',
  business_name text NOT NULL,
  business_phone text,
  business_email text,
  business_address text,
  {_TS},
  CONSTRAINT ck_owner_profiles_role CHECK (role = 'owner'),
  CONSTRAINT ck_owner_profiles_business_name CHECK (char_length(btrim(business_name)) BETWEEN 1 AND 160),
  CONSTRAINT ck_owner_profiles_business_phone CHECK (business_phone IS NULL OR business_phone ~ {_PHONE}),
  CONSTRAINT ck_owner_profiles_business_email CHECK (business_email IS NULL OR char_length(business_email) <= 320),
  CONSTRAINT ck_owner_profiles_business_address CHECK (business_address IS NULL OR char_length(business_address) <= 500),
  CONSTRAINT fk_owner_profiles_user_id_profiles
    FOREIGN KEY (user_id, role) REFERENCES public.profiles (id, role) ON DELETE CASCADE
)
""",
    # ---- venues -------------------------------------------------------------------------
    rf"""
CREATE TABLE public.venues (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL REFERENCES public.owner_profiles (user_id) ON DELETE RESTRICT,
  city_id uuid REFERENCES public.cities (id) ON DELETE RESTRICT,
  name text NOT NULL,
  description text,
  address_line text,
  postal_code text,
  latitude numeric(9, 6),
  longitude numeric(9, 6),
  google_place_id text,
  contact_phone text,
  timezone text NOT NULL,
  status text NOT NULL DEFAULT 'draft',
  published_at timestamptz,
  {_TS},
  CONSTRAINT ck_venues_status CHECK (status IN ('draft', 'published', 'archived')),
  CONSTRAINT ck_venues_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 160),
  CONSTRAINT ck_venues_description CHECK (description IS NULL OR char_length(description) <= 5000),
  CONSTRAINT ck_venues_latitude CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CONSTRAINT ck_venues_longitude CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
  CONSTRAINT ck_venues_coordinates_pair CHECK ((latitude IS NULL) = (longitude IS NULL)),
  CONSTRAINT ck_venues_contact_phone CHECK (contact_phone IS NULL OR contact_phone ~ {_PHONE}),
  CONSTRAINT ck_venues_timezone CHECK (char_length(timezone) BETWEEN 1 AND 64),
  CONSTRAINT ck_venues_published_has_location CHECK (
    status <> 'published' OR (city_id IS NOT NULL AND latitude IS NOT NULL)
  )
)
""",
    "CREATE INDEX ix_venues_owner_id ON public.venues (owner_id)",
    "CREATE INDEX ix_venues_city_published ON public.venues (city_id) WHERE status = 'published'",
    rf"""
CREATE TABLE public.venue_categories (
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  category_id uuid NOT NULL REFERENCES public.categories (id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_venue_categories PRIMARY KEY (venue_id, category_id)
)
""",
    "CREATE INDEX ix_venue_categories_category_id ON public.venue_categories (category_id)",
    rf"""
CREATE TABLE public.venue_amenities (
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  amenity_id uuid NOT NULL REFERENCES public.amenities (id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_venue_amenities PRIMARY KEY (venue_id, amenity_id)
)
""",
    "CREATE INDEX ix_venue_amenities_amenity_id ON public.venue_amenities (amenity_id)",
    r"""
CREATE TABLE public.venue_images (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  storage_path text NOT NULL,
  status text NOT NULL DEFAULT 'pending',
  is_cover boolean NOT NULL DEFAULT false,
  sort_order integer NOT NULL DEFAULT 0,
  alt_text text,
  width integer,
  height integer,
  byte_size bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_venue_images_storage_path UNIQUE (storage_path),
  CONSTRAINT ck_venue_images_status CHECK (status IN ('pending', 'active')),
  CONSTRAINT ck_venue_images_sort_order CHECK (sort_order >= 0),
  CONSTRAINT ck_venue_images_alt_text CHECK (alt_text IS NULL OR char_length(alt_text) <= 200),
  CONSTRAINT ck_venue_images_width CHECK (width IS NULL OR width > 0),
  CONSTRAINT ck_venue_images_height CHECK (height IS NULL OR height > 0),
  CONSTRAINT ck_venue_images_byte_size CHECK (byte_size IS NULL OR byte_size > 0),
  CONSTRAINT ck_venue_images_cover_active CHECK (NOT is_cover OR status = 'active'),
  CONSTRAINT ck_venue_images_path_in_venue_folder CHECK (storage_path LIKE venue_id::text || '/%')
)
""",
    "CREATE INDEX ix_venue_images_venue_sort ON public.venue_images (venue_id, sort_order)",
    "CREATE UNIQUE INDEX uq_venue_images_one_cover ON public.venue_images (venue_id) WHERE is_cover",
    # Bookable unit. Q1/Q2/Q17/N2/N23 are unanswered: this stays structural (no price, no capacity).
    rf"""
CREATE TABLE public.venue_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  name text NOT NULL,
  sort_order integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  {_TS},
  CONSTRAINT ck_venue_resources_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 80),
  CONSTRAINT ck_venue_resources_sort_order CHECK (sort_order >= 0)
)
""",
    "CREATE UNIQUE INDEX uq_venue_resources_venue_name ON public.venue_resources (venue_id, lower(name))",
    # ---- engagement / system --------------------------------------------------------------
    r"""
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
)
""",
    "CREATE INDEX ix_notifications_user_created ON public.notifications (user_id, created_at DESC)",
    "CREATE INDEX ix_notifications_user_unread ON public.notifications (user_id) WHERE read_at IS NULL",
    r"""
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
)
""",
    "CREATE INDEX ix_audit_logs_created_at ON public.audit_logs (created_at DESC)",
    "CREATE INDEX ix_audit_logs_actor_id ON public.audit_logs (actor_id)",
    "CREATE INDEX ix_audit_logs_entity ON public.audit_logs (entity_type, entity_id)",
]

DOWN_TABLES = [
    "audit_logs",
    "notifications",
    "venue_resources",
    "venue_images",
    "venue_amenities",
    "venue_categories",
    "venues",
    "owner_profiles",
    "customer_profiles",
    "amenities",
    "categories",
    "cities",
    "profiles",
]


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    for table in DOWN_TABLES:
        op.execute(f"DROP TABLE IF EXISTS public.{table} CASCADE")
