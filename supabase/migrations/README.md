# supabase/migrations

**Reserved. Intentionally empty in Stage 2.**

Decision D-13 in `docs/SYSTEM_ARCHITECTURE.md` makes **Alembic the only schema
migration tool** (`backend/alembic/versions/`). Two migration histories against one
database would drift, so the application schema **and its Row Level Security
policies are written as Alembic migrations** in Stage 3.

This folder exists because the Supabase CLI expects it. Use it only for objects that
Alembic cannot own, such as Supabase-managed storage policies, and only after the
decision is recorded in an ADR. Anything placed here must be idempotent and must
not create application tables.

RLS rule for Stage 3 (docs/SYSTEM_ARCHITECTURE.md section 8.3): RLS is enabled on
every application table with **no policies for `anon` or `authenticated`**, so the
Supabase data API cannot read or write application data.
