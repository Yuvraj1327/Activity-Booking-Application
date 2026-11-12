# Step 3 report — Authentication and database foundation

Date: 2026-11-12. Read with: DATABASE_SCHEMA.md, AUTHENTICATION_FLOW.md, ROLE_PERMISSION_MATRIX.md, STORAGE_CONFIGURATION.md, API_DOCUMENTATION.md.

## Headline: what is and is not verified

| Area | Status | Evidence |
|---|---|---|
| Schema, constraints, triggers, RLS, storage policies | **Verified on a local PostgreSQL 16 + Supabase stub** | 151 backend tests pass; migrations upgrade, downgrade to base and upgrade again |
| Migrations applied to **your Supabase development database** | **NOT done** | No Supabase credentials were provided |
| JWT verification, RBAC, profile APIs | **Verified** with tokens signed in the tests (HS256) against the real FastAPI app + migrated database | tests below |
| Verification of **real Supabase tokens** (JWKS / project secret), real sign-up, e-mail verification, Google, Apple, phone OTP, TOTP | **NOT tested** | needs your project; code paths and dashboard steps are documented |
| Admin web | Builds, lints, type-checks; unauthenticated visitors are redirected to `/login` (fail closed) | no sign-in could be tested without Supabase |
| Flutter authentication (both apps) | **NOT compiled or run** | no Flutter SDK / pub.dev access here; tests are written but unexecuted |

## 1. Database tables created (13)
`profiles`, `customer_profiles`, `owner_profiles`, `cities`, `categories`, `amenities`, `venues`, `venue_categories`, `venue_amenities`, `venue_images`, `venue_resources`, `notifications`, `audit_logs` (+ Alembic's `alembic_version`). Not created on purpose: `user_roles`, `user_sessions`, `account_status`, `admin_profiles` (see decisions D-27/D-28 in DATABASE_SCHEMA.md).

## 2. Migration status
Revisions `0001` (tables), `0002` (triggers), `0003` (RLS, grants, storage). Applied and round-tripped on a throwaway local database. **Not applied to Supabase.** To apply: set `ALEMBIC_DATABASE_URL` (direct or session connection) and run `alembic upgrade head` from `backend/`. The migration refuses to run if `auth.users` does not exist.

## 3. Authentication methods
E-mail + password with verification, password reset, session persistence/restoration, logout: implemented in both apps (unexecuted). Google, Apple, phone OTP: implemented behind flags, hidden until configured (phone needs an SMS provider, open question N24). Admin: e-mail + password + TOTP. Backend token verification: tested.

## 4. API endpoints
`GET /health`, `GET /api/v1/version`, `GET /auth/me`, `POST /auth/profile`, `GET|PATCH /profiles/me`, `GET|PATCH /customers/me`, `GET|PATCH /owners/me`, `GET /admin/me`. Reusable dependencies: `get_current_user`, `require_customer`, `require_owner`, `require_admin` (+ MFA).

## 5. RLS policies (20 `SELECT` policies on public tables, 4 on `storage.objects`)
Own-row reads, published venues, active catalogue, owner-own drafts, admin read-all, no insert/update/delete policies anywhere. Write grants revoked from `anon` and `authenticated`.

## 6. Storage buckets
`venue-images` (public, 5 MiB, jpeg/png/webp, backend-write-only) and `profile-images` (private, 2 MiB, jpeg/png/webp, own-folder-only). Limits are my assumptions.

## 7. Permission matrix
See ROLE_PERMISSION_MATRIX.md.

## 8. App status
- **Customer app:** login, register (with e-mail confirmation screen), forgot/reset password, complete-profile, phone OTP, splash/suspended/error screens, Riverpod state, GoRouter guard, role validation (an owner account is signed out with an explanation), logout. **Unverified.**
- **Owner app:** same, plus business name at registration and owner-role validation. **Unverified.**
- **Admin web:** login, TOTP enrol/verify, protected routes, server-side role check via the API, unauthorized page, logout. Builds; sign-in untested.

## 9. Test results (this environment)

| Check | Result |
|---|---|
| `pytest` with a local Postgres | **151 passed** |
| `pytest` without a database | 36 passed, **115 skipped** (reported as skipped, never as passed) |
| `ruff check`, `ruff format --check`, `mypy --strict` | clean |
| Admin web `lint`, `typecheck`, `build` | clean |
| Flutter `analyze` / `test` | **not run** |
| CI workflows | written, never run |

Backend tests by area: JWT/token handling and registration (30 + 9), role matrix (19), profile operations and cross-user isolation (16), DB constraints (22), RLS as `anon`/`authenticated` roles (18, including a check that RLS alone blocks writes if grants were wrong), storage policies (13), migrations round trip and model/DB drift (3), admin promotion script (3). I broke a policy on purpose and confirmed the RLS tests failed, then restored it.

## 10. Remaining configuration and decisions (yours)

1. Provide a Supabase dev project; run the dashboard checklist in AUTHENTICATION_FLOW.md; apply the migrations; create the first admin (`scripts.create_admin`) and enrol TOTP.
2. Run the Flutter commands: `./scripts/bootstrap_flutter.sh`, then `flutter analyze && flutter test` in `packages/flutter_shared`, `apps/customer_app`, `apps/owner_app`. Add the Android/iOS deep-link config for `io.zuruv.customer` / `io.zuruv.owner`.
3. Confirm: storage limits and allowed types; the one-role-per-account rule (N10); SMS provider for phone login (N24); Google/Apple developer accounts.
4. Still open from Step 1 and affecting later steps: Q1/Q2/Q17/N2/N23 (what is booked), Q4 (venue approval), Q18 (admin permissions), N17 (account deletion), N1 (launch geography), N13 (who maintains categories/amenities).
5. Things I would double-check on a real project: that your database role may create policies on `storage.objects`; that Storage enforces bucket size/type limits; that `app_metadata`/claims in real tokens match the fixtures (`sub`, `email`, `phone` without `+`, `aal`).
6. Account suspension and deletion have no API yet (Step 8 / N17); an operator changes `profiles.status` in the database until then.

## Files

Created: 3 Alembic revisions; `app/models/*`, `app/schemas/profile.py`, `app/repositories/profiles.py`, `app/services/profiles.py`, `app/api/v1/endpoints/{auth,profiles,customers,owners,admin}.py`; `scripts/create_admin.py`; 11 test modules + helpers; `supabase/local/supabase_stub.sql`; `scripts/dev_pg.sh`; Flutter auth in `packages/flutter_shared/lib/src/auth` (+ `testing`); admin `proxy.ts`, `lib/admin-access.ts`, login/MFA/unauthorized pages; the six docs. Changed: `core/config.py`, `core/errors.py`, `api/deps.py`, both Flutter apps' `main/router/providers/home/tests/env`, `docker-compose.yml`, `Makefile`, `supabase/config.toml`, CI backend workflow, env examples, README and Step 2 docs (additive). No file deleted. No git commit made.
