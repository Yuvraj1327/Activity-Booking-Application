-- ============================================================================
-- ZURUV  003_venues_and_catalog
-- Alembic equivalent : revisions 0001 (catalogue, venues, images), 0002 (triggers), 0004 (price/rating columns)
-- Requires           : 002
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- ============================================================================

BEGIN;

CREATE TABLE public.categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL,
  name text NOT NULL,
  icon_key text,
  sort_order integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_categories_slug UNIQUE (slug),
  CONSTRAINT ck_categories_slug CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 60),
  CONSTRAINT ck_categories_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 80)
);

CREATE TABLE public.amenities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL,
  name text NOT NULL,
  icon_key text,
  sort_order integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_amenities_slug UNIQUE (slug),
  CONSTRAINT ck_amenities_slug CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND char_length(slug) <= 60),
  CONSTRAINT ck_amenities_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 80)
);

CREATE TRIGGER trg_categories_set_updated_at BEFORE UPDATE ON public.categories FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_amenities_set_updated_at BEFORE UPDATE ON public.amenities FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

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
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_venues_status CHECK (status IN ('draft', 'published', 'archived')),
  CONSTRAINT ck_venues_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 160),
  CONSTRAINT ck_venues_description CHECK (description IS NULL OR char_length(description) <= 5000),
  CONSTRAINT ck_venues_latitude CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CONSTRAINT ck_venues_longitude CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
  CONSTRAINT ck_venues_coordinates_pair CHECK ((latitude IS NULL) = (longitude IS NULL)),
  CONSTRAINT ck_venues_contact_phone CHECK (contact_phone IS NULL OR contact_phone ~ '^\+[1-9][0-9]{6,14}$'),
  CONSTRAINT ck_venues_timezone CHECK (char_length(timezone) BETWEEN 1 AND 64),
  CONSTRAINT ck_venues_published_has_location CHECK (
    status <> 'published' OR (city_id IS NOT NULL AND latitude IS NOT NULL)
  )
);

CREATE INDEX ix_venues_owner_id ON public.venues (owner_id);

CREATE INDEX ix_venues_city_published ON public.venues (city_id) WHERE status = 'published';

-- Revision 0004: display columns (starting price, currency, rating aggregates).
ALTER TABLE public.venues ADD COLUMN starting_price_paise bigint;

ALTER TABLE public.venues ADD COLUMN currency char(3) NOT NULL DEFAULT 'INR';

ALTER TABLE public.venues ADD COLUMN rating_avg numeric(2, 1);

ALTER TABLE public.venues ADD COLUMN rating_count integer NOT NULL DEFAULT 0;

ALTER TABLE public.venues ADD CONSTRAINT ck_venues_starting_price CHECK (starting_price_paise IS NULL OR starting_price_paise >= 0);

ALTER TABLE public.venues ADD CONSTRAINT ck_venues_currency CHECK (currency ~ '^[A-Z]{3}$');

ALTER TABLE public.venues ADD CONSTRAINT ck_venues_rating_avg CHECK (rating_avg IS NULL OR rating_avg BETWEEN 0 AND 5);

ALTER TABLE public.venues ADD CONSTRAINT ck_venues_rating_count CHECK (rating_count >= 0);

ALTER TABLE public.venues ADD CONSTRAINT ck_venues_rating_consistent CHECK (rating_count = 0 OR rating_avg IS NOT NULL);

CREATE INDEX ix_venues_published_rating ON public.venues (rating_count DESC, rating_avg DESC NULLS LAST) WHERE status = 'published';

CREATE TRIGGER trg_venues_set_updated_at BEFORE UPDATE ON public.venues FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TABLE public.venue_categories (
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  category_id uuid NOT NULL REFERENCES public.categories (id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_venue_categories PRIMARY KEY (venue_id, category_id)
);

CREATE INDEX ix_venue_categories_category_id ON public.venue_categories (category_id);

CREATE TABLE public.venue_amenities (
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  amenity_id uuid NOT NULL REFERENCES public.amenities (id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_venue_amenities PRIMARY KEY (venue_id, amenity_id)
);

CREATE INDEX ix_venue_amenities_amenity_id ON public.venue_amenities (amenity_id);

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
);

CREATE INDEX ix_venue_images_venue_sort ON public.venue_images (venue_id, sort_order);

CREATE UNIQUE INDEX uq_venue_images_one_cover ON public.venue_images (venue_id) WHERE is_cover;

COMMIT;
