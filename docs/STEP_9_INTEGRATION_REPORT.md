# Step 9 integration report

## Method

Inspected the repository first (config, URLs, CORS, secrets, existing tests) before changing anything, then closed real gaps found. The existing architecture was kept.

## Component status

| Component | Status | Evidence |
|---|---|---|
| FastAPI backend (port 8008) | Works | 330 tests; live process on 8008 answered `/health` and enforced 401, CORS and 429 |
| Postgres (local, Supabase-compatible stub) | Works | migrations up/down/up with 0008; constraints and RLS tests |
| Admin web (Next.js) | Works against real FastAPI and Postgres | 81 Playwright tests; Supabase Auth mocked |
| Customer and owner Flutter apps | **Not verified** | No SDK |
| Supabase Auth, Storage | **Not verified live** | No project or credentials |
| Razorpay test mode, FCM, Resend, Google Maps | **Not verified live** | No credentials; fakes only |

## Configuration checks

- API base URL: configurable everywhere. The localhost fallback is now debug/development only (Flutter `AppEnv`, admin `env.ts`). Backend CORS has no default origin list outside development.
- Environment files: `.example` files only are tracked; real env files are ignored.
- Service-role key: read only by the backend (`app/services/storage.py`, settings); not in any client source or the built admin bundle.

## Changes made in Step 9

1. `app/core/ratelimit.py`, setting `RATE_LIMIT_PER_MINUTE`, wired in `main.py`.
2. Migration `0008`: three indexes for admin filters. Indexes only.
3. `AppEnv.apiBaseUrl` (Flutter) and `env.ts` (admin web): no silent localhost in release or production.
4. `scripts/scan_secrets.py`: repo and bundle secret scanner.
5. `tests/test_step9_integration.py`: 23 tests.
6. The e2e seed disables the limiter (it makes hundreds of calls from one address); this was discovered because the limiter correctly blocked the seed.

## Flows verified at API level (real DB, fake gateway)

Customer: profile, browse and search venues, slots, server quote, hold, create order, verify, confirm, history, detail, cancel hold, favourites. Owner: own bookings, earnings (gross only), isolation from other owners. Admin: dashboard, lists, detail, exports, audit. See `END_TO_END_WORKFLOWS.md`. None of these were driven through the Flutter UI.

## Production-flow clean-up

Searched all Dart, TypeScript and backend source for mock, dummy and fake data: none in production paths. The only fake auth gateway lives in a test-only library and is not imported by app code. Unavailable figures are shown as "not available", never as numbers.
