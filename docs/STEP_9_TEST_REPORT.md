# Step 9 test report

Date: 2026-11-12. Every number below comes from a command run in this session. Anything not listed as run was **not** run.

## Run and passed

| Suite | Command | Result |
|---|---|---|
| Backend (real Postgres, fake gateways) | `pytest` in `backend/` with `TEST_DATABASE_URL` set | **330 passed**, 0 failed (307 before Step 9 + 23 new) |
| Backend lint and types | `ruff format --check`, `ruff check`, `mypy app` | clean (77 source files) |
| Admin web types and lint | `tsc --noEmit`, `eslint .` | clean |
| Admin web unit tests | `vitest run` | **26 passed** |
| Admin web build | `next build` | passed |
| Admin web end-to-end | Playwright, desktop 1440px and tablet 820px, real Next + real FastAPI + real Postgres | **81 passed** |
| Secret scan | `python scripts/scan_secrets.py apps/admin_web/.next/static` | clean (repo and built client bundle); also proven to fail on a planted `rzp_live_` key |
| Live process smoke | uvicorn on port 8008 | `/health` ok; anonymous and garbage-JWT requests 401; CORS allows only the configured origin; limiter returned 429 after the limit |
| Migrations | included in pytest (`test_migrations`: up, down to base, up again; ORM equals schema) | passed with new migration 0008 |

## New tests in Step 9 (`backend/tests/test_step9_integration.py`, 23 tests)

- One paid booking seen consistently by customer, owner and admin; the amount is identical in all views and equals the order amount and the database row.
- A second owner cannot list, read or change another owner's bookings or venue.
- A customer cannot read another customer's booking or payment or create an order for it.
- A paid booking cannot be cancelled until a refund policy is approved (deliberate, Q9); an unpaid hold can be cancelled and the slot reopens.
- Rate limiting: 429 with the standard error body and `Retry-After`; reads and the webhook are not limited; `0` disables it.
- CORS allows only configured origins.
- Six injection strings across 6 list endpoints: no 500, tables intact, `%` is not treated as a wildcard.
- Page size and offset bounds; malformed and unknown ids give clean 422/404.
- No gateway secret appears in responses or the OpenAPI document.

## Already covered by earlier tests and re-run in the 330

Concurrent bookings on one slot (exactly one wins), same-key idempotency, two courts in parallel, owner schedule change racing a booking, the database exclusion constraint itself, hold expiry releasing the slot, client price rejected (422), checkout signature valid and invalid, webhook signature over the raw body, duplicate and concurrent webhooks applied once, verify racing a webhook, late and failed webhooks never downgrading a captured payment, expired, wrong-audience, wrong-signature and `alg:none` JWTs, RLS and storage policies, suspended-user blocks, admin routes denied to customers and owners (16 paths).

## Not run, and why

| Not run | Why |
|---|---|
| `flutter analyze`, Flutter unit and widget tests, both Flutter apps | No Flutter or Dart SDK in this environment. The Flutter code (including the Step 9 `AppEnv` edit) has **never been compiled or run** here. |
| Customer and owner journeys through the Flutter UI | Same reason. Their API-level equivalents are tested above. |
| Real Razorpay test-mode payment and signed webhook from Razorpay | No Razorpay test credentials. Signature logic is tested with the same HMAC scheme against a fake gateway. |
| Firebase push, Resend e-mail, Google Maps/Places | No credentials. Delivery code is tested against fakes only. |
| Real Supabase Auth (token refresh, logout, sign-in), Supabase Storage, Supabase-hosted RLS | No Supabase project. Auth was mocked with HS256 tokens the real backend verifies; RLS ran on a local Postgres with a Supabase-compatible stub. |
| Load, soak and image-loading performance | Not attempted. Index additions are reasoned from query shapes, not benchmarked at scale. |
| Visual QA of the Flutter apps | Not possible without the SDK. |
