# ZURUV — project handover

**Status (2026-11-12): development complete within what could be verified here. Not yet production-ready**: the Flutter apps need their first real compile/test run, and every external integration needs a test-mode run with your credentials. Nothing has been deployed or published.

## What this is

Sports venue booking platform: Customer app and Owner app (Flutter), Admin (Next.js), one FastAPI backend, Supabase (Postgres, Auth, Storage, RLS). Razorpay payments, FCM push, Resend e-mail, Google Places address search.

## Repository map

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (`app/api`, `services`, `repositories`, `gateways`, `models`), Alembic (`alembic/versions` 0001–0009), tests, operator scripts (`scripts/create_admin.py`, `seed_reference_data.py`, `seed_demo_venues.py`), `Dockerfile` |
| `apps/customer_app`, `apps/owner_app` | Flutter apps (Riverpod, go_router, dio); `env/*.example.json` |
| `packages/flutter_shared` | Shared auth, API client, theme, push |
| `apps/admin_web` | Next.js 16 admin, vitest, Playwright |
| `supabase/` | Local-only Postgres stub and config for tests |
| `scripts/` | `bootstrap_flutter.sh`, platform configurators, `dev_pg.sh`, `scan_secrets.py` |
| `.github/workflows/` | CI: backend, admin, flutter |
| `docs/` | Everything below |

## Read in this order

1. `MANUAL_DEPLOYMENT_GUIDE.md` — your deployment runbook
2. `ENVIRONMENT_VARIABLES.md` — every variable, what it does, where it lives
3. `KNOWN_ISSUES.md` and `OPEN_QUESTIONS.md` — what is unverified and which business decisions are yours
4. `FINAL_FEATURE_CHECKLIST.md`, `FINAL_TEST_REPORT.md` — what exists and the evidence
5. Reference: `SYSTEM_ARCHITECTURE`, `API_DOCUMENTATION`, `DATABASE_SCHEMA`, `BOOKING_ENGINE`, `PAYMENT_ARCHITECTURE`, `ROLE_PERMISSION_MATRIX`, `ADMIN_PERMISSION_MATRIX`, `END_TO_END_WORKFLOWS`, `STEP_2…9` reports, `STEP_9_SECURITY_REPORT`

## Design rules to preserve

- Authorization is decided only by the backend. Apps and admin never talk to the database directly (RLS blocks `anon`/`authenticated`).
- Money is integer paise, gross only. Platform revenue, net earnings and refunds are "Not available" until Q7–Q10 are answered — do not compute them client-side.
- Booking status changes only through `BookingService._move`; payment state only through `PaymentService._apply`. Services call `commit()` explicitly.
- Double booking is prevented by a database constraint, not only by application checks.
- Secrets live only in backend / Railway / Vercel server variables. `NEXT_PUBLIC_*` and Flutter `.env` values (bundled as an asset) are public. `scripts/scan_secrets.py` enforces this in CI.
- Unconfigured integrations answer "not configured"; they never fake success.

## Local development quick start

```bash
scripts/dev_pg.sh start                       # throwaway Postgres on :54399 for tests
cd backend && python3.13 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
export TEST_DATABASE_URL=postgresql://zt@127.0.0.1:54399/postgres
pytest -q && ruff check app tests scripts alembic && mypy app
uvicorn app.main:app --port 8008 --reload     # needs backend/.env, see ENVIRONMENT_VARIABLES.md
cd ../apps/admin_web && npm ci && npm run dev
```

More: `DEVELOPMENT_SETUP.md`.

## First week after handover (suggested)

1. Run Flutter analyze/tests; fix findings; device-test both apps against a staging API.
2. Create Supabase staging, Railway staging, Vercel preview; run the smoke test in test mode.
3. Answer the open business questions; the code has marked places to wire each rule (`OPEN_QUESTIONS.md`).
4. Rotate any credential that ever appears in a chat or ticket; set budget alerts on Google Cloud and Razorpay.
5. Only then switch Razorpay to Live and submit store builds.

## Support boundaries

Nothing was deployed, published, paid for or sent to a real user by this work. No credentials were supplied or stored.
