# Step 2 report — Project setup and backend foundation

Date: 2026-11-12. Scope: foundation only. No booking, payment, auth flows or admin features (Steps 3–10).

## Verification (what was actually run)

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Flutter customer app builds | **NOT VERIFIED** | No Flutter SDK or pub.dev access in the build environment. Code is written but never compiled. |
| 2 | Flutter owner app builds | **NOT VERIFIED** | Same. |
| 3 | Next.js admin starts | **Passed** | `npm run lint`, `typecheck`, `build` clean; `next start` served `/` (307 to `/dashboard`), `/dashboard`, and a 404 page. |
| 4 | FastAPI starts on 8008 | **Passed** | `uvicorn app.main:app --host 0.0.0.0 --port 8008` from `backend/`. |
| 5 | `GET /health` works | **Passed** | 200, `status: degraded`, `database.status: not_configured` with no credentials. |
| 6 | DB connectivity | **Not tested against Supabase** (no credentials supplied). Code path tested against a *temporary local PostgreSQL 16* (not Supabase): `/health` returned `ok` with latency; an unreachable DB returns `unavailable`; `alembic current` connected. |
| 7 | Environment config | **Passed** | Pydantic Settings tests; production refuses to start without a DB URL or with wildcard CORS. |
| 8 | No secrets committed | **Passed** | Only `*.example` env files are trackable; pattern scan of tracked content found nothing. |
| 9 | Dependencies install | **Backend and admin passed** (clean venv install + 26 tests; `npm install`). **Flutter not verified.** |

Backend: `pytest` 26 passed, 1 skipped (integration; runs when `TEST_DATABASE_URL` is set, and passed against the local Postgres); `ruff` and `mypy --strict` clean. `docker compose config` validates. CI workflows are written but have not run.

## Unresolved issues and risks

1. **Flutter is unverified.** Run `./scripts/bootstrap_flutter.sh`, then `flutter analyze` and `flutter test` in `packages/flutter_shared`, `apps/customer_app`, `apps/owner_app`. Expect to fix minor compile or version-resolution issues; dependency versions (`flutter_riverpod ^2.6.1`, `go_router ^14.6.2`, `dio ^5.7.0`, `supabase_flutter ^2.8.0`) were chosen from knowledge, not resolved.
2. **No Supabase connection tested.** Fill `backend/.env`, then check `/health`. The pooler notes in ENVIRONMENT_VARIABLES.md apply.
3. `supabase/config.toml` was not validated with the Supabase CLI (`major_version` needs confirming against your project); the storage bucket has no size/MIME limits yet.
4. **Brand colours are approximate**, sampled from JPEG boards. Customer primary ≈ `#442EDB`, owner ≈ `#4B2AF9`; the boards disagree. Need exact values.
5. The admin UI components are hand-written in shadcn style (the shadcn registry was unreachable); `npx shadcn add` can replace them later. TypeScript is 5.9 and ESLint 9 for ecosystem compatibility.
6. `npm audit` reports advisories; not triaged.
7. Step 1 is still not formally closed (quotation PDF, walkthrough video, gate questions, G1–G5 sequencing proposals). Unchanged by this step.

## Commands

See [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md). Backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8008`.

## Created

124 tracked files: root (`README.md`, `.gitignore`, `.env.example`, `docker-compose.yml`, `Makefile`), `backend/` (app, alembic, tests, Dockerfile, requirements), `apps/admin_web`, `apps/customer_app`, `apps/owner_app`, `packages/flutter_shared`, `supabase/`, `scripts/bootstrap_flutter.sh`, `.github/workflows/`, five Step 2 docs. **Changed:** `docs/SYSTEM_ARCHITECTURE.md` (appended section 23). Nothing deleted. No git commit was made.
