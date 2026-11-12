# Owner app ↔ API integration

Base URL: `API_BASE_URL` (default `http://localhost:8008/api/v1`). One Dio client from `flutter_shared` adds the Supabase bearer token. Errors arrive as `{code, message, details, request_id}` and are turned into `ApiException`. Full endpoint contract: `API_DOCUMENTATION.md` (Owner venue management).

| Screen / action | Endpoint(s) | Status |
|---|---|---|
| Role check, session restore | `GET /auth/me` | Real (Step 3) |
| Business profile | `GET/PATCH /owners/me` | Real |
| Name, phone, avatar | `PATCH /profiles/me` + private Storage | Real (avatar upload untested against real Storage) |
| Cities, sports, amenities | `GET /cities`, `/categories`, `/amenities` | Real |
| My Venues | `GET /owners/venues?q&status&limit&offset` | Real |
| Add venue | `POST /owners/venues` | Real |
| Edit venue | `GET/PATCH /owners/venues/{id}` | Real |
| Delete venue | `DELETE /owners/venues/{id}` | Real |
| Publish / take offline | `POST …/publish`, `…/unpublish` | Real |
| Photos | `POST …/images` (multipart), `PUT …/images/order`, `PATCH/DELETE …/images/{id}` | Real API (tested with a fake Storage); **not tested against real Supabase Storage** |
| Manage slots | `GET/PUT …/schedules` | Real (hours only) |
| Dashboard | `GET /owners/dashboard` | Real venue data; booking/revenue fields unavailable |
| Analytics | `GET /owners/analytics?date_from&date_to` | Real venue performance; rest unavailable |
| Notifications | `GET /owners/notifications`, `POST …/{id}/read`, `POST …/read-all` | Real |
| Bookings, booking details (Step 6) | `GET /owners/bookings?bucket`, `GET /owners/bookings/{id}` | **Real (Step 6)**: read-only list with customer name, status and history; unpaid holds hidden |
| Earnings, payouts | `GET /owners/earnings` | "Not available yet" until Step 7 |
| Reviews | `GET /owners/reviews`, `POST /owners/reviews/{id}/reply` | Real since Step 10 |
| Bank details | none | Not collected (D-57) |

## Endpoints in the Step 1 catalogue that are not built

`/owner/payout-account` (N11: where bank data is stored and who may see it), `/owner/venues/{id}/resources` (Q1/Q2 courts), signed-upload + finalize for images (replaced by one multipart call, D-51), `/owner/venues/{id}/schedule/regular|special` (replaced by `…/schedules`, D-52), booking actions (Step 6), real earnings (Step 7).

## Hand-off to later steps

- **Step 6** adds bookings/slots. Replace the `Unavailable` fields in `OwnerBusinessService.dashboard()/analytics()` and the three pending endpoints; the Flutter models already parse `available:false` objects.
- **Step 7** fills earnings, payment notifications and push; the notification type prefixes `booking.`, `payment.`, `payout.`, `review.` already drive the Notifications filter.
- The Bookings list rows, Booking Details content and earnings/payment rows are **not built**; they need the Step 6/7 data shape first. The screens today only show the "not available yet" state.

## Step 6 additions

| Screen / action | Endpoint(s) | Status |
|---|---|---|
| Courts (name, slot length, price, active) | `GET/POST /owners/venues/{id}/resources`, `PATCH/DELETE …/{rid}` | Real. Needs a running API; Flutter untested |
| Blocked times | `GET/POST /owners/venues/{id}/blocks`, `DELETE …/{bid}` | Real. Times are sent from the **device** time zone |
| Manage hours | `PUT /owners/venues/{id}/schedules` | Real; `409 SCHEDULE_CONFLICT` is shown with the affected booking codes |
| Dashboard | `GET /owners/dashboard` | `total_bookings`, `booking_overview` real; revenue and utilization still `available:false` |

## Step 7 additions

| Screen / action | Endpoint(s) | Status |
|---|---|---|
| Payments & Earnings | `GET /owners/earnings`, `GET /owners/payments` | Real **gross** amounts and payment records. Deductions, net earnings, payout status: `available:false`, shown as "Not available yet" (rules unapproved: Q7, Q8, Q10). No commission, GST or settlement figure is displayed. |
| Booking details → Payment line | `payment_status` on the booking | Paid / Payment pending / Payment failed / Refunded / Not paid |
| Notifications | `GET /owners/notifications…` (unchanged) + push | New booking and payment notifications are created by verified payments; tapping a push opens the booking |
| Device token | `PUT /devices/token`, `POST /devices/token/remove` | Registered after sign-in, removed before sign-out |

The dashboard `total_revenue` / `monthly_revenue` stay `available:false` on purpose: they need the same unapproved rules. Gross totals live on the Earnings screen.
