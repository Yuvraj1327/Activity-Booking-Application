-- ============================================================================
-- ZURUV  001_extensions
-- Alembic equivalent : revision 0001 pre-flight check, 0006 (btree_gist)
-- Requires           : a Supabase project (auth + storage schemas)
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- ============================================================================

BEGIN;

-- Pre-flight 1: this must be a Supabase database (or a LOCAL test database prepared with
-- supabase/local/supabase_stub.sql). Same check as Alembic revision 0001.
DO $$
BEGIN
  IF to_regclass('auth.users') IS NULL THEN
    RAISE EXCEPTION 'auth.users not found. Run against a Supabase database, or load supabase/local/supabase_stub.sql into a LOCAL test database first.';
  END IF;
  IF to_regclass('storage.buckets') IS NULL OR to_regclass('storage.objects') IS NULL THEN
    RAISE EXCEPTION 'Supabase Storage tables (storage.buckets / storage.objects) not found.';
  END IF;
END
$$;

-- Pre-flight 2: refuse to run on a database that already has the ZURUV schema, so a second
-- run can never collide with, or alter, existing data. (Use Alembic for later upgrades.)
DO $$
BEGIN
  IF to_regclass('public.profiles') IS NOT NULL THEN
    RAISE EXCEPTION 'public.profiles already exists: the ZURUV schema is already installed. Nothing was changed. Do not re-run these files; use Alembic (backend/alembic) for upgrades.';
  END IF;
END
$$;

-- Needed by the booking no-overlap exclusion constraint (uuid WITH = inside a GiST index).
-- gen_random_uuid() is built into PostgreSQL 13+, so no pgcrypto/uuid-ossp is required.
CREATE EXTENSION IF NOT EXISTS btree_gist;

COMMIT;
