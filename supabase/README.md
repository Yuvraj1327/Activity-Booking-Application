# ZURUV database package for Supabase

Plain PostgreSQL files that build the complete ZURUV database in a Supabase project, so you can run them in the **Supabase SQL Editor** with no tooling. They are generated from, and kept equal to, the Alembic migrations.

> **Source of truth:** `backend/alembic/versions/` (revisions 0001 → 0009). These SQL files are an equivalent, hand-runnable copy of Alembic head. Never edit them on their own: change Alembic first, then update the SQL and run `supabase/verify_sync.sh` (below).

## Files and execution order

Run them **in this order, each one once, on a fresh project**:

| # | File | Creates |
|---|---|---|
| 1 | `migrations/001_extensions.sql` | Pre-flight checks (Supabase `auth`/`storage` present; refuses to run if ZURUV is already installed), `btree_gist` extension |
| 2 | `migrations/002_identity_and_roles.sql` | `profiles` (role `customer`/`owner`/`admin`, status `active`/`suspended`), `customer_profiles`, `owner_profiles`, `cities`; `set_updated_at()`, role-immutability trigger, `app_user_role()` |
| 3 | `migrations/003_venues_and_catalog.sql` | `categories`, `amenities`, `venues` (with price/rating columns), `venue_categories`, `venue_amenities`, `venue_images` |
| 4 | `migrations/004_schedules_and_availability.sql` | `venue_resources` (courts, slot length/price), `schedule_rules`, `schedule_exceptions`, `availability_blocks` |
| 5 | `migrations/005_bookings.sql` | `bookings`, `booking_slots` (GiST exclusion constraint = no double booking), `booking_status_history` (append-only) |
| 6 | `migrations/006_payments.sql` | `payments`, `payment_events` (append-only, de-duplicated webhook ledger) |
| 7 | `migrations/007_notifications.sql` | `notifications`, `user_device_tokens`, `notification_preferences`, `email_deliveries` |
| 8 | `migrations/008_reviews_and_favorites.sql` | `favorites`, `reviews`, `review_responses`, rating-aggregate trigger, immutability triggers |
| 9 | `migrations/009_admin_and_audit.sql` | `audit_logs` (append-only) and the admin dashboard indexes |
| 10 | `migrations/010_rls_storage_policies.sql` | Row Level Security on all 27 tables, API-role grants, 34 table policies, Storage buckets + policies, Alembic version stamp (`0009`) |
| 11 | `seed.sql` | Reference data only: 12 categories, 12 amenities, 10 cities (optional but the apps need categories/cities to be useful) |

27 application tables in total (the 28th table in the database is `alembic_version`).

### What is *not* in the schema, on purpose
- **No refunds table.** The application has none: refund policy is an open business question (Q9, `docs/OPEN_QUESTIONS.md`). Refund state exists only as `payments.status` (`refunded`, `partially_refunded`) and `bookings.status` (`refund_pending`, `refunded`). No "transactions" table either: `payments` + `payment_events` are the transaction ledger.
- **No write policies for `anon`/`authenticated`.** The mobile apps and the admin site never write to the database directly; every write goes through the FastAPI backend, which connects as the database owner. The API roles may only `SELECT`, through the policies below.
- **No admin-creation SQL.** Admins are created by the operator script (see step 5).

## Run it in the Supabase SQL Editor

1. Create a new Supabase project (empty database). Open **SQL Editor → New query**.
2. For each file in the table above, in order: open the file, copy its whole contents, paste into a new query, click **Run**, and wait for **Success** before the next one. Each file runs inside its own transaction (`BEGIN … COMMIT`), so a failed file changes nothing; fix the error and run **that file** again, then continue.
3. Run `seed.sql` the same way (safe to repeat).
4. Check (SQL Editor):

   ```sql
   select count(*) from pg_tables where schemaname = 'public';                   -- 28
   select count(*) from pg_tables where schemaname='public' and not rowsecurity
     and tablename <> 'alembic_version';                                         -- 0
   select id, public from storage.buckets order by id;                            -- profile-images (false), venue-images (true)
   select version_num from public.alembic_version;                                -- 0009
   ```
5. Create the first admin (needs the backend checkout; it never needs the service-role key): create the user in **Authentication → Users → Add user**, then from `backend/` with `DATABASE_URL` set to the project's direct/session connection string:
   `python -m scripts.create_admin --email <admin-email> --name "<Name>"`.
6. Configure the backend (`DATABASE_URL`, `SUPABASE_URL`, …) as in `docs/MANUAL_DEPLOYMENT_GUIDE.md`.

### Using Alembic instead
Both routes give the same database. Use **either** the SQL files **or** `alembic upgrade head`, not both. The SQL files stamp `alembic_version = 0009`, so after running them `alembic upgrade head` does nothing and future Alembic migrations apply normally.

## Safety
- **Fresh databases only.** `001` aborts with a clear message if `public.profiles` already exists. The files contain no `DROP`, `TRUNCATE` or `DELETE`, and no `UPDATE` of existing rows. `010` runs `REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated` (identical to Alembic revision 0003): on a project where you had already created other tables in `public` and relied on the default Supabase API grants, those grants are removed. That is intended for ZURUV and never deletes data.
- No credentials, keys or secrets appear in any file.
- Do **not** run `local/supabase_stub.sql` on Supabase; it is for local test databases only.

## Security model (010)
| Role | What the Supabase data API allows |
|---|---|
| `anon` | `SELECT` only on active `cities`, `categories`, `amenities`; published `venues` and their categories, amenities, active images, active courts |
| `authenticated` customer | the above + own profile, own favourites, own bookings, own payments, own notifications and notification preferences, schedules of visible venues |
| `authenticated` owner | the public data + own profile and own venues (any status), their images/courts/blocks, bookings and payments of own venues, own notifications |
| `authenticated` admin | `SELECT` on profiles, customer/owner profiles, venues, bookings, availability blocks, payments, audit logs |
| none of them | `payment_events`, `user_device_tokens`, `email_deliveries`, `reviews`, `review_responses`: RLS on, no grants, no policy (backend only) |

Role checks use `public.app_user_role()` (reads `profiles`; returns `NULL` for suspended users, so suspension also cuts data-API access). Storage: `venue-images` is a public-read bucket (5 MB; JPEG/PNG/WebP) written only by the backend with the service-role key; `profile-images` is private (2 MB; JPEG/PNG/WebP) and each signed-in user can read/write/delete only objects under their own `<uid>/` folder.

## How this was verified (and what was not)
Executed on a local PostgreSQL 16 prepared with `local/supabase_stub.sql`:
- All ten files ran in order with no errors; `seed.sql` ran twice (idempotent: 12 / 12 / 10 rows).
- `pg_dump --schema-only` of the SQL-built database is **identical** to one built by `alembic upgrade head` (tables, columns, constraints, indexes, triggers, functions, RLS flags, policies, grants, storage policies): 28 tables, 38 policies (34 table + 4 storage), 22 triggers, 90 indexes, 168 constraints in both. Re-check any time with `supabase/verify_sync.sh`.
- The complete backend test suite (346 tests, including the RLS, migration, ORM-vs-schema, booking-concurrency and payment tests) passed against a database built **only from these SQL files**.
- Re-running `001` is refused; re-running `002` fails without changes.

**Not verified:** a run on a real hosted Supabase project (the stub only approximates `auth`, `storage` and the API roles); in particular creating policies on `storage.objects` from the SQL Editor depends on your project's permissions. If that statement in `010` is rejected, create the four `profile_images_*` policies in **Storage → Policies** with the same expressions, then run the remaining part of the file. The SQL Editor's size/timeouts and the Supabase "destructive query" warning were not exercised.

## Keeping it in sync
1. Add the Alembic revision and its tests as usual.
2. Mirror the change in the matching file here (a new table → the file for its topic; its RLS/grants/policies → `010`), and bump the stamp in `010`.
3. `scripts/dev_pg.sh start && supabase/verify_sync.sh` must print `IN SYNC`.
