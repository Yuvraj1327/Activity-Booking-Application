# Admin dashboard (Step 8)

The ZURUV admin web (`apps/admin_web`, Next.js 16 App Router, TypeScript, Tailwind, Recharts) is a **read-mostly monitoring console**. All data comes from the FastAPI admin API, which reads Supabase Postgres. Nothing is hardcoded.

## Architecture

- **Server-side data.** Pages are server components. They read the validated Supabase session on the server and call FastAPI with the user's access token, so there is no CORS and the token never reaches client JavaScript.
- **Authorization lives in the backend.** `proxy.ts` only redirects anonymous visitors to `/login`. Every page then calls `GET /admin/me`. The backend `require_admin` checks the role from the `profiles` table, MFA (`aal2`) when `ADMIN_REQUIRE_MFA` is on, and refuses suspended accounts. The frontend never decides access, and a user cannot make themselves an admin (admins are created only with `python -m scripts.create_admin`).
- **No secrets in the browser.** Only `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` and `NEXT_PUBLIC_API_BASE_URL` are public. The service-role key is not used by the admin web at all.
- **URL state.** Search, filters, sort, date range and paging live in the query string (plain GET forms and links), so every view is shareable and works without client state.
- **Mutations** (suspend or reactivate an account) are server actions that call the protected `PATCH` endpoints. **CSV downloads** pass through a route handler that forwards the session token.

## Sections

| Section | Route | Screenshot |
|---|---|---|
| Sign in | `/login` | ![](screenshots/19-login.png) |
| Access denied (non-admin) | `/unauthorized` (and `/mfa` when a second factor is required) | ![](screenshots/20-access-denied.png) |
| Dashboard | `/dashboard` | ![](screenshots/01-dashboard.png) |
| Analytics: bookings | `/analytics?tab=bookings` | ![](screenshots/02-analytics-bookings.png) |
| Analytics: transactions | `/analytics?tab=transactions` | ![](screenshots/03-analytics-transactions.png) |
| Analytics: platform | `/analytics?tab=platform` | ![](screenshots/04-analytics-platform.png) |
| Owners | `/owners` | ![](screenshots/05-owners.png) |
| Owner detail | `/owners/[id]` | ![](screenshots/06-owner-detail.png) |
| Suspend dialog | owner/customer detail | ![](screenshots/16-suspend-dialog.png) |
| Customers | `/customers` | ![](screenshots/07-customers.png) |
| Customer detail | `/customers/[id]` | ![](screenshots/08-customer-detail.png) |
| Venues (read-only) | `/venues` | ![](screenshots/09-venues.png) |
| Venue detail | `/venues/[id]` | ![](screenshots/10-venue-detail.png) |
| Bookings | `/bookings` | ![](screenshots/11-bookings.png) |
| Booking detail | `/bookings/[id]` | ![](screenshots/12-booking-detail.png) |
| Payments | `/payments` | ![](screenshots/13-payments.png) |
| Payment detail | `/payments/[id]` | ![](screenshots/14-payment-detail.png) |
| Notifications | `/notifications` | ![](screenshots/15-notifications.png) |
| Audit log | `/audit` | ![](screenshots/17-audit-log.png) |
| Empty period | any date filter | ![](screenshots/18-empty-period.png) |
| Tablet (820px) | dashboard, bookings | ![](screenshots/21-tablet-dashboard.png) ![](screenshots/22-tablet-bookings.png) |

Screenshots are taken from the end-to-end suite against a throwaway database seeded with **fixture data** (not production data).

## Date filters

Today, Last 7 days, Last 30 days (default), This month and Custom range, on the dashboard and analytics. The range is limited to 366 days. Days are cut in `ADMIN_REPORT_TIMEZONE` (default `Asia/Kolkata`).

## What the admin cannot do

- Create, edit, publish or delete venues or courts (monitoring only).
- Change a booking or payment status. Booking status changes remain only in `BookingService._move`; payments only in `PaymentService._apply`.
- Set a role, or suspend another admin or themselves.

## Money on screen

Gross booking value and successful payment amount are shown. **Platform revenue, owner earnings and refunds show "Not available"** with the open question that blocks them (Q7, Q8, Q9, Q10). No commission, GST, tax or payout figure is calculated or invented.

## Running it

```bash
cd apps/admin_web
cp .env.example .env.local   # fill the three public values
npm install
npm run dev                  # http://localhost:3000
```
