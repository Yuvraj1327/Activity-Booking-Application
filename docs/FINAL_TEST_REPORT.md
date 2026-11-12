# Final test report (Step 10)

Every number below comes from a command run in this environment on 2026-11-12, after the last code change. Nothing is listed as passing that was not executed.

## Executed and passing

| Suite | Command | Result |
|---|---|---|
| Backend unit + integration + DB (real PostgreSQL, fake payment / push / e-mail / storage / Places gateways) | `pytest -q` (from `backend/`, `TEST_DATABASE_URL` set) | **346 passed**, 3 warnings, no failures |
| Backend lint / format | `ruff format --check`, `ruff check app tests scripts alembic` | clean (119 files) |
| Backend types | `mypy app` | **no issues in 83 source files** |
| Admin TypeScript | `npx tsc --noEmit` | clean |
| Admin lint | `npx eslint .` | clean |
| Admin unit | `npx vitest run` | **26 passed** (2 files) |
| Admin production build | `next build` (public env set) | succeeds |
| Admin end-to-end (real FastAPI + Postgres, Supabase Auth mocked with HS256 tokens; desktop + tablet) | `npx playwright test --project=setup --project=desktop --project=tablet --grep-invert "capture|tablet$"` | **81 passed** |
| Secret scan | `python scripts/scan_secrets.py` and on `apps/admin_web/.next/static` | clean |
| Python syntax of platform script | manifest patch run twice on a sample manifest | updated once, then idempotent |

### What the backend suite covers

Auth and role checks (anonymous 401, wrong role 403, suspended 403, MFA required), profile creation, catalogue and filters (including `available_today`), favourites, owner venue CRUD and publish rules, image rules, schedules and conflict protection, availability and pricing, booking creation/idempotency/cancellation, **concurrent booking attempts for the same slot and for different courts**, payments (order creation, signature verification, webhook signature, duplicate and out-of-order events, reconciliation), notifications and e-mail outbox, reviews (completed-only, once, immutability, aggregate trigger, owner reply), owner isolation, admin lists/detail/status/analytics/exports/audit, rate limiting, migrations (27 tables, upgrade/downgrade) and RLS on every application table, Places proxy.

## Written but NOT executed

| Suite | State |
|---|---|
| Flutter `flutter analyze` (customer, owner, shared) | **Not run.** No Flutter SDK could be obtained (downloads return 403). |
| Flutter tests: customer 99, owner 59, shared 24 test cases written | **Not run.** Count is a text count of test declarations, not results. |
| Dart syntax | Every changed Dart file parses with a tree-sitter Dart grammar. This proves syntax only — not types, imports or runtime behaviour. |
| Android / iOS builds | **Not run.** |
| Flutter UI / screenshot comparison with `docs/reference/*.jpg` | **Not done.** |

Expect the first `flutter analyze` to report issues (missing imports, type mismatches). They are untested territory; fix them before a store build. CI (`.github/workflows/flutter.yml`) runs analyze + tests once the repository is on GitHub.

## Not tested because no credentials / live service exists here

Supabase Auth sign-in (e2e uses mocked tokens), Supabase Storage uploads, hosted Postgres pooler behaviour, Razorpay test mode (checkout, real signatures, real webhooks), Firebase push delivery, Resend delivery, Google Places responses (the gateway is tested against a fake Google), Railway/Vercel runtime behaviour, load/scale.

## Fixed during Step 10 because testing found it

- Review creation and owner reply were not persisted until `commit()` was added (found by the new tests).
- Rating `"5"` (string) was accepted; now strict integer 1–5.
- Playwright server start failed under the new rate limiter (seed used one client address); seed disables the limiter.
- Existing Flutter tests asserted the old disabled controls (Today chip, bank-details button); updated with the new behaviour.
