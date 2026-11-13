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
| `SUPABASE_SERVICE_ROLE_KEY` | no | **Server only, secret.** Used since Step 5 for one thing: the backend uploads/deletes venue photos in the `venue-images` bucket. Without it, `POST /owners/venues/{id}/images` answers `503 STORAGE_NOT_CONFIGURED`. Never put it in a Flutter or Next.js build. |
| `SUPABASE_JWT_SECRET` | no | Only for projects that sign with a legacy shared HS256 secret. |
| `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` | no | Overrides. Audience defaults to `authenticated`. |
| `ADMIN_REQUIRE_MFA` | no | `true`/`false`. Empty = required in staging/production only. Admin endpoints then need an `aal2` session. |
| `ADMIN_REPORT_TIMEZONE` | no | IANA zone used to cut days in admin reports. Default `Asia/Kolkata`. |
| `ADMIN_EXPORT_MAX_ROWS` | no | Cap on rows in an admin CSV export. Default 20000 (1–200000). |
| `TEST_DATABASE_URL` | tests | Superuser URL of a **throwaway** Postgres for the DB tests (not Supabase). Without it DB tests are skipped. |
| `ALEMBIC_DATABASE_URL` | no | Direct/session connection for `alembic upgrade head` (falls back to `DATABASE_URL`). |

\* In production either `SUPABASE_URL` or `SUPABASE_JWT_SECRET` must be set.

## Flutter apps — `apps/<app>/.env` (loaded with `flutter_dotenv`; copy from `.env.example`)

| Variable | Notes |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Public values only. Never the service-role key. |
| `AUTH_REDIRECT_URL` | Deep link used by e-mail confirmation, password reset and OAuth, e.g. `io.zuruv.app://login-callback`. Must be allow-listed in Supabase. |
| `GOOGLE_AUTH_ENABLED`, `APPLE_AUTH_ENABLED`, `PHONE_AUTH_ENABLED` | `true`/`false` (default false). Show the method only after its Supabase provider is configured. |
| `API_BASE_URL` | e.g. `http://localhost:8008/api/v1`; Android emulator `http://10.0.2.2:8008/api/v1`; real device: your LAN IP. |

## Admin web — `apps/admin_web/.env.local`

`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8008/api/v1`). Everything `NEXT_PUBLIC_` is visible in the browser.

## Root `.env` (docker compose only)

`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` for the optional local Postgres. Choose your own values.

## Booking rules (Step 6, backend)

None of these has an invented default. Each one is an open business decision; leaving it empty switches the related behaviour off (or makes the API say it is not configured). Defaults for tests are set per test.

| Variable | Values | Empty means | Open question |
|---|---|---|---|
| `BOOKING_MODE` | `hold` (default) or `instant` | `hold`: a booking reserves the slot as `pending_payment` until paid or expired. `instant`: confirmed immediately, `payment_status` stays `unpaid` (testing or venues without online payment). It never pretends a payment happened. | Q11 |
| `BOOKING_HOLD_MINUTES` | 1–1440 | In `hold` mode `POST /bookings` answers `503 BOOKING_NOT_CONFIGURED`. | N4 |
| `CANCELLATION_MIN_NOTICE_HOURS` | 0–8760 | Customers cannot cancel a **confirmed** booking online (`409 CANCELLATION_NOT_AVAILABLE`). Unpaid holds can always be released. Paid bookings cannot be cancelled until the refund policy exists (Step 7). | Q9 |
| `BOOKING_MIN_NOTICE_MINUTES` | 0–525600 | No minimum notice (a slot must still not have started). | N6 |
| `BOOKING_MAX_ADVANCE_DAYS` | 1–730 | No maximum advance window. | N6 |

## Payments, push and email (Step 7, backend only)

Real credentials are never committed and never placed in Flutter or in `NEXT_PUBLIC_*` variables. Use Razorpay **test** keys outside production. Unset = the feature answers "not configured" (nothing is faked).

| Variable | Notes |
|---|---|
| `RAZORPAY_KEY_ID` | Public identifier (`rzp_test_...`); returned to the app with each order. |
| `RAZORPAY_KEY_SECRET` | Secret. Signs/verifies checkout signatures and authenticates API calls. |
| `RAZORPAY_WEBHOOK_SECRET` | Secret set in the Razorpay webhook form; **different** from the key secret. |
| `RAZORPAY_API_BASE` | Default `https://api.razorpay.com/v1`. |
| `FIREBASE_PROJECT_ID` | FCM project. |
| `FIREBASE_SERVICE_ACCOUNT` | Secret. Service-account JSON text **or** a path to the file. |
| `RESEND_API_KEY` | Secret. |
| `EMAIL_FROM_ADDRESS` | Sender on a Resend-verified domain, e.g. `ZURUV <bookings@your-domain>`. |
| `BACKGROUND_SWEEP_SECONDS` | Default 60; `0` disables the in-process retry/reconciliation loop. |
| `PAYMENT_RECONCILE_AFTER_MINUTES` | Default 3; open payments older than this are reconciled with Razorpay by the sweep. |

Flutter apps: Firebase is configured through the native `google-services.json` / `GoogleService-Info.plist` (not in git). No Razorpay secret and no service account ever goes in `.env`.

## Admin web (`apps/admin_web/.env.local`)

| Variable | Public? | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | Anon key only. Never the service-role key. |
| `NEXT_PUBLIC_API_BASE_URL` | yes | FastAPI base, e.g. `http://localhost:8008/api/v1`. |
| `ADMIN_REPORT_TIMEZONE` / `NEXT_PUBLIC_ADMIN_REPORT_TIMEZONE` | no / yes | Should match the backend value. Default `Asia/Kolkata`. |
