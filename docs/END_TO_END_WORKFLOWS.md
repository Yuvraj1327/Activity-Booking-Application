# End-to-end workflows

Status key: **API-tested** = exercised in the pytest suite against real Postgres with fake payment/push/e-mail gateways; **UI-tested** = Playwright; **Not run** = needs Flutter SDK or external credentials.

## Customer

| # | Step | Status |
|---|---|---|
| 1-3 | Register, log in, complete profile (`/auth/profile`, `/customers/me`) | API-tested; real Supabase sign-in **not run** |
| 4-8 | Home, browse, search, filter, venue detail with images, amenities, price | API-tested; Flutter screens **not run** |
| 9-11 | Select slot, server quote, create booking (hold, idempotent) | API-tested incl. concurrency |
| 12 | Razorpay checkout | **Not run** (no credentials, no SDK); order creation and gateway fake tested |
| 13-14 | Backend verifies signature; booking becomes confirmed | API-tested |
| 15 | Confirmation notification and e-mail | API-tested with fakes; real FCM and Resend **not run** |
| 16-17 | Booking history and detail | API-tested |
| 18 | Cancel: allowed for unpaid holds; paid bookings refused until Q9 is answered | API-tested |
| 19 | Favourites, profile | API-tested |
| 20 | Review a completed booking (once); see reviews on a venue | API-tested (Step 10); Flutter not run |
| 21 | Directions to a venue (opens Google Maps link) | Flutter, not run; no API involved |

## Owner

| # | Step | Status |
|---|---|---|
| 1-2 | Register, profile | API-tested |
| 3-8 | Venue (with address search, Step 10), images, amenities, hours, price, availability, publish | API-tested; uploads against a fake storage gateway, real Supabase Storage **not run** |
| 9-11 | Dashboard, receive bookings, booking details | API-tested |
| 12-13 | Approve/reject and manual status changes | **Intentionally absent** (no approved workflow, Q4); statuses change only through the booking state machine |
| 14-15 | Payments, earnings (gross only), analytics | API-tested; deductions and net are "not available" |
| 16 | Notifications; reviews list and reply | API-tested (reviews built in Step 10); Flutter screens not run |
| - | Cross-owner isolation | API-tested |

## Admin

| # | Step | Status |
|---|---|---|
| 1 | Login, MFA, unauthorised page | UI-tested (auth mocked) |
| 2-8 | Dashboard, customers, owners, venues, bookings, payments, analytics | UI-tested and API-tested |
| 9 | Search, sort, filter, paging | UI-tested and API-tested |
| 10 | Notifications | UI-tested |
| 11 | CSV exports | API-tested (privacy, formula-injection, cap) and UI-tested |
| 12 | Audit log, permission limits | UI-tested and API-tested |
