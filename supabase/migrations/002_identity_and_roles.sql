-- ============================================================================
-- ZURUV  002_identity_and_roles
-- Alembic equivalent : revisions 0001 (profiles, customer/owner profiles, cities), 0002 (triggers), 0003 (app_user_role)
-- Requires           : 001
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- Note             : cities is created here (not in 003) because customer_profiles.preferred_city_id
--                    references it. It is catalogue data and is exposed read-only in 010.
-- ============================================================================

BEGIN;

-- Shared helper used by every table with an updated_at column.
CREATE FUNCTION public.set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$;

-- Identity: one profiles row per auth.users row; role is customer | owner | admin.
CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE RESTRICT,
  role text NOT NULL,
  status text NOT NULL DEFAULT 'active',
  full_name text NOT NULL,
  email text,
  phone text,
  avatar_path text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_profiles_role CHECK (role IN ('customer', 'owner', 'admin')),
  CONSTRAINT ck_profiles_status CHECK (status IN ('active', 'suspended')),
  CONSTRAINT ck_profiles_full_name CHECK (char_length(btrim(full_name)) BETWEEN 1 AND 120),
  CONSTRAINT ck_profiles_email CHECK (email IS NULL OR char_length(email) <= 320),
  CONSTRAINT ck_profiles_phone CHECK (phone IS NULL OR phone ~ '^\+[1-9][0-9]{6,14}$'),
  CONSTRAINT ck_profiles_avatar_path CHECK (
    avatar_path IS NULL OR (avatar_path LIKE id::text || '/%' AND char_length(avatar_path) <= 300)
  ),
  CONSTRAINT uq_profiles_id_role UNIQUE (id, role)
);

CREATE INDEX ix_profiles_role ON public.profiles (role);

CREATE INDEX ix_profiles_status ON public.profiles (status) WHERE status <> 'active';

CREATE INDEX ix_profiles_lower_email ON public.profiles (lower(email));

-- Cities (referenced by customer_profiles).
CREATE TABLE public.cities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  state text,
  country_code char(2) NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_cities_name CHECK (char_length(btrim(name)) BETWEEN 1 AND 120),
  CONSTRAINT ck_cities_country_code CHECK (country_code ~ '^[A-Z]{2}$')
);

CREATE UNIQUE INDEX uq_cities_name_state_country ON public.cities (lower(name), lower(coalesce(state, '')), country_code);

CREATE TABLE public.customer_profiles (
  user_id uuid PRIMARY KEY,
  role text NOT NULL DEFAULT 'customer',
  preferred_city_id uuid REFERENCES public.cities (id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_customer_profiles_role CHECK (role = 'customer'),
  CONSTRAINT fk_customer_profiles_user_id_profiles
    FOREIGN KEY (user_id, role) REFERENCES public.profiles (id, role) ON DELETE CASCADE
);

CREATE TABLE public.owner_profiles (
  user_id uuid PRIMARY KEY,
  role text NOT NULL DEFAULT 'owner',
  business_name text NOT NULL,
  business_phone text,
  business_email text,
  business_address text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_owner_profiles_role CHECK (role = 'owner'),
  CONSTRAINT ck_owner_profiles_business_name CHECK (char_length(btrim(business_name)) BETWEEN 1 AND 160),
  CONSTRAINT ck_owner_profiles_business_phone CHECK (business_phone IS NULL OR business_phone ~ '^\+[1-9][0-9]{6,14}$'),
  CONSTRAINT ck_owner_profiles_business_email CHECK (business_email IS NULL OR char_length(business_email) <= 320),
  CONSTRAINT ck_owner_profiles_business_address CHECK (business_address IS NULL OR char_length(business_address) <= 500),
  CONSTRAINT fk_owner_profiles_user_id_profiles
    FOREIGN KEY (user_id, role) REFERENCES public.profiles (id, role) ON DELETE CASCADE
);

-- Triggers: updated_at, and the role is immutable once set.
CREATE TRIGGER trg_profiles_set_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_customer_profiles_set_updated_at BEFORE UPDATE ON public.customer_profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_owner_profiles_set_updated_at BEFORE UPDATE ON public.owner_profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_cities_set_updated_at BEFORE UPDATE ON public.cities FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE FUNCTION public.prevent_role_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.role IS DISTINCT FROM OLD.role THEN
    RAISE EXCEPTION 'profiles.role is immutable' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$;

CREATE TRIGGER trg_profiles_prevent_role_change BEFORE UPDATE OF role ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.prevent_role_change();

-- Role lookup used by every RLS policy (SECURITY DEFINER; returns NULL for suspended users).
CREATE FUNCTION public.app_user_role() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
  SELECT p.role FROM public.profiles p
  WHERE p.id = (SELECT auth.uid()) AND p.status = 'active'
$$;

REVOKE ALL ON FUNCTION public.app_user_role() FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.app_user_role() TO anon, authenticated, service_role;

COMMIT;
