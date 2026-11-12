# Environment variables

None of these files may be committed. Only the `*.example` files are tracked.

## Backend — `backend/.env`

| Variable | Required | Notes |
|---|---|---|
| `ENVIRONMENT` | no (`development`) | `development`, `test`, `staging`, `production`. Production enforces the checks below and hides `/docs`. |
| `LOG_LEVEL`, `LOG_JSON` | no | `INFO`, `true`. Use `LOG_JSON=false` for readable local logs. |
| `CORS_ORIGINS` | prod: yes | Comma list or JSON array. `*` is rejected in production. Defaults to `localhost:3000` otherwise. |
| `DATABASE_URL` | prod: yes | Supabase Postgres URL (`postgresql://...`; converted to asyncpg). Without it the API runs and `/health` reports `not_configured`. |
| `ALEMBIC_DATABASE_URL` | no | Direct/session connection for migrations. Falls back to `DATABASE_URL`. |
| `DB_USE_NULLPOOL`, `DB_STATEMENT_CACHE_SIZE` | no | Pooler support. Transaction pooler (port 6543): set `DB_USE_NULLPOOL=true`. Prepared statements are off by default. |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_CONNECT_TIMEOUT`, `DB_HEALTH_TIMEOUT` | no | Pool/timeouts (5, 5, 30, 10, 3). |
| `SUPABASE_URL` | prod: yes* | Also the source of the default JWKS URL and issuer. |
| `SUPABASE_ANON_KEY` | no | Public key. |
| `SUPABASE_SERVICE_ROLE_KEY` | no | **Server only, secret.** Not used by any Step 2 code. |
| `SUPABASE_JWT_SECRET` | no | Only for projects that sign with a legacy shared HS256 secret. |
| `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` | no | Overrides. Audience defaults to `authenticated`. |
| `ADMIN_REQUIRE_MFA` | no | `true`/`false`. Empty = required in staging/production only. Admin endpoints then need an `aal2` session. |
| `TEST_DATABASE_URL` | tests | Superuser URL of a **throwaway** Postgres for the DB tests (not Supabase). Without it DB tests are skipped. |
| `ALEMBIC_DATABASE_URL` | no | Direct/session connection for `alembic upgrade head` (falls back to `DATABASE_URL`). |

\* In production either `SUPABASE_URL` or `SUPABASE_JWT_SECRET` must be set.

## Flutter apps — `apps/<app>/env/dev.json` (passed with `--dart-define-from-file`)

| Variable | Notes |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Public values only. Never the service-role key. |
| `AUTH_REDIRECT_URL` | Deep link used by e-mail confirmation, password reset and OAuth, e.g. `io.zuruv.customer://login-callback`. Must be allow-listed in Supabase. |
| `GOOGLE_AUTH_ENABLED`, `APPLE_AUTH_ENABLED`, `PHONE_AUTH_ENABLED` | `true`/`false` (default false). Show the method only after its Supabase provider is configured. |
| `API_BASE_URL` | e.g. `http://localhost:8008/api/v1`; Android emulator `http://10.0.2.2:8008/api/v1`; real device: your LAN IP. |

## Admin web — `apps/admin_web/.env.local`

`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8008/api/v1`). Everything `NEXT_PUBLIC_` is visible in the browser.

## Root `.env` (docker compose only)

`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` for the optional local Postgres. Choose your own values.
