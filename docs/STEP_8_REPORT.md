# Step 8 report: Admin web dashboard and analytics

**Status: implemented and tested against a real FastAPI and Postgres. Supabase Auth was mocked in the end-to-end suite; Step 9 not started.**

## What was built

- Backend: `app/services/admin.py`, `app/schemas/admin.py`, `app/api/v1/endpoints/admin.py` (rewritten), `app/utils/search.py`, small changes to `payments.py` (admin filters), `profiles.py` (registration notification to admins) and `config.py` (`ADMIN_REPORT_TIMEZONE`, `ADMIN_EXPORT_MAX_ROWS`). No migration; no new table.
- Admin web: login, protected layout, dashboard, analytics (3 tabs), owners, customers, venues, bookings, payments, notifications, audit log, CSV export proxy, error/loading/empty states, desktop and tablet layouts.
- Docs: `ADMIN_DASHBOARD`, `ADMIN_API_DOCUMENTATION`, `ANALYTICS_ARCHITECTURE`, `ADMIN_PERMISSION_MATRIX`, this report; `PROJECT_CONTEXT`, `IMPLEMENTATION_ROADMAP`, `API_DOCUMENTATION`, `ROLE_PERMISSION_MATRIX`, `ENVIRONMENT_VARIABLES`, `OPEN_QUESTIONS` updated. Screenshots in `docs/screenshots/`.

## Test results

| Suite | Result |
|---|---|
| Backend pytest | 307 passed (39 new admin tests) |
| ruff format / ruff check / mypy | clean |
| Admin web `tsc`, `eslint`, `next build` | clean |
| Vitest | 26 passed |
| Playwright (desktop 1440px and tablet 820px) | 81 passed |

Security coverage: anonymous 401, customer 403 and owner 403 on all 16 admin paths (MFA enabled), suspended admin 403, admin cannot suspend self or another admin, wrong-role id → 404, audit row written for each status change and export, role and status cannot be set through the profile API.

## Decisions

- D-69 Admin authorization is the backend only; the web calls `/admin/me`.
- D-70 Admin data is fetched on the Next server with the session token.
- D-71 Analytics aggregate in SQL in `ADMIN_REPORT_TIMEZONE`.
- D-72 Platform revenue, owner earnings and refunds are reported unavailable until Q7–Q10 are approved.
- D-73 Admin status is `active` or `suspended`; "inactive" is not modelled.
- D-74 Admins use the existing `/notifications` system instead of a new `/admin/notifications`.
- D-75 Admin has no write access to bookings, payments or venues.

## Known limitations (honest)

1. Supabase Auth was **mocked** in the e2e suite (HS256 tokens that the real backend verifies). The real Supabase was never contacted; Razorpay, Firebase and Resend were not called.
2. Flutter apps were not touched and not run.
3. "Inactive" owner status is not available. Q18 is unresolved; suspension does not cancel or refund bookings.
4. Platform revenue, owner earnings and refunds are unavailable (Q7–Q10).
5. The loading skeleton is verified by a vitest test only.
6. Screenshots and e2e data are fixture data in a throwaway database; the system Chrome was used because Playwright browser downloads were unavailable.
7. Exports are synchronous and capped; very large exports would need a background job.

## Run

```bash
scripts/dev_pg.sh start
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8008
cd apps/admin_web && npm install && npm run dev
```
