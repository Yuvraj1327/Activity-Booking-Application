# API documentation (Steps 3–4)

Base URL (dev): `http://localhost:8008`. Interactive docs: `/docs` (hidden in production). All routes except `/health` are under `/api/v1`. Authenticated routes need `Authorization: Bearer <Supabase access token>`.

## Conventions

- **Errors** always have the same shape: `{"code": "...", "message": "...", "details": null | [...], "request_id": "..."}`; `X-Request-ID` is echoed in the header. Validation details list only the field location, message and type, never the submitted value.
- **Request bodies are strict**: unknown fields (for example `role`, `status`, `id`) → `422`.
- **PATCH**: omitted field = unchanged; `null` clears an optional field; required fields (`full_name`, `business_name`) cannot be null; an empty body is a 422.
- Phones are E.164 (`+919876543210`).

| Status | Meaning | Typical `code` |
|---|---|---|
| 401 | Missing/invalid/expired token | `MISSING_TOKEN`, `INVALID_TOKEN`, `TOKEN_EXPIRED`, `USER_NOT_FOUND`, `AUTH_NOT_CONFIGURED` |
| 403 | Signed in but not allowed | `PROFILE_REQUIRED`, `ACCOUNT_SUSPENDED`, `INSUFFICIENT_ROLE`, `MFA_REQUIRED` |
| 404 | Not found | `NOT_FOUND`, `PROFILE_NOT_FOUND`, `VENUE_NOT_FOUND` |
| 409 | Conflict | `ROLE_CONFLICT` |
| 422 | Validation | `VALIDATION_ERROR`, `INVALID_CITY`, `INVALID_AVATAR_PATH`, `INVALID_LOCATION`, `LOCATION_REQUIRED`, `INVALID_PRICE_RANGE` |
| 503 | Database unavailable/not configured | `DATABASE_NOT_CONFIGURED`, `SERVICE_UNAVAILABLE` |

## Endpoints

### `GET /health`
Public. `{"status":"ok|degraded","app","version","environment","database":{"status":"ok|unavailable|not_configured","latency_ms"}}`. `degraded` unless the database answered `SELECT 1`.

### `GET /api/v1/auth/me`
Any valid token (a profile is not required). Returns who the token belongs to and the profile, if any.
```json
{"user_id":"…","email":"a@b.co","phone":null,"has_profile":true,
 "profile":{"id":"…","role":"customer","status":"active","full_name":"Asha Rao","email":"a@b.co","phone":null,"avatar_path":null,"created_at":"…","updated_at":"…"}}
```

### `POST /api/v1/auth/profile`
Create the profile for the signed-in user.
```json
{"role":"customer","full_name":"Asha Rao"}
{"role":"owner","full_name":"Ravi K","business_name":"Ravi Sports Arena","business_phone":"+918012345678"}
```
`201` + profile when created; `200` + profile if it already existed with the same role (idempotent); `409 ROLE_CONFLICT` if it exists with a different role; `422` for `role: admin`, unknown fields, missing `business_name` for owners, business fields for customers. User id, e-mail and verified phone come from the token.

### `GET /api/v1/profiles/me`, `PATCH /api/v1/profiles/me`
Any active role. PATCH accepts `full_name`, `phone`, `avatar_path` (must be inside your own `profile-images` folder).

### `GET /api/v1/customers/me`, `PATCH /api/v1/customers/me`
Customers only. `{"profile":{…},"preferred_city_id":null}`. PATCH accepts `preferred_city_id` (must be an active city).

### `GET /api/v1/owners/me`, `PATCH /api/v1/owners/me`
Owners only. `{"profile":{…},"business_name","business_phone","business_email","business_address"}`. PATCH accepts any of the business fields.

### `GET /api/v1/admin/me`
Admins only (and an MFA-verified session when `ADMIN_REQUIRE_MFA`). Returns the admin profile; used by the admin web to confirm access.

### `GET /api/v1/version`
Public. `{"name","version","api_version"}`.

### Catalogue and discovery (Step 4)

All need a signed-in, active account (any role may browse; admins and owners see the same published data). Only **published** venues are ever returned.

| Endpoint | Notes |
|---|---|
| `GET /api/v1/cities` | Active cities, by name. |
| `GET /api/v1/categories` | Active categories in `sort_order` (`id, slug, name, icon_key`). |
| `GET /api/v1/amenities` | Active amenities. |
| `GET /api/v1/venues` | Search + filter + sort + page. Query: `q` (name, address, city or category name; `%`/`_` are escaped), `category` (slug), `city_id`, `min_price` / `max_price` (paise per hour), `lat` + `lng` (together; adds `distance_km` to every item), `radius_km` (needs `lat`/`lng`), `sort` = `popular` (default) · `rating` · `price_asc` · `price_desc` · `distance` (needs `lat`/`lng`) · `newest`, `limit` (1–50, default 20), `offset`. Returns `{items:[VenueCard], limit, offset, has_more}`; `has_more` is computed by fetching one extra row, so there is no total count. |
| `GET /api/v1/venues/{id}` | `VenueCard` fields plus `description, postal_code, google_place_id, contact_phone, timezone, category_details[], amenities[], images[]`. `images` lists **active** images only, cover first, as public Storage URLs (`<SUPABASE_URL>/storage/v1/object/public/venue-images/<path>`). Optional `lat`/`lng` for `distance_km`. Draft, archived or unknown ids give `404 VENUE_NOT_FOUND`. |

`VenueCard`: `id, name, city_id, city_name, address_line, latitude, longitude, cover_image_url, categories[] (slugs), starting_price_paise, currency, rating_avg, rating_count, distance_km, is_favorite`. `is_favorite` is always `false` for non-customers.

### Favourites (Step 4, customers only)

| Endpoint | Notes |
|---|---|
| `GET /api/v1/favorites?limit&offset` | Own favourites, newest first, same page shape as `/venues`. Venues that are no longer published are hidden (the row is kept). |
| `POST /api/v1/favorites` `{"venue_id"}` | `204`. Idempotent. Unknown or unpublished venue → `404 VENUE_NOT_FOUND`. |
| `DELETE /api/v1/favorites/{venue_id}` | `204`. Idempotent. Can only ever affect the caller's own row. |

Owners and admins get `403 INSUFFICIENT_ROLE` on `/favorites`.

### Owner venue management (Step 5, owners only)

All routes require an active **owner** (`403 INSUFFICIENT_ROLE` otherwise, `401` without a token). A venue that does not exist **or belongs to another owner** returns the same `404 VENUE_NOT_FOUND`.

| Endpoint | Notes |
|---|---|
| `GET /owners/venues?q&status&limit&offset` | Own venues (any status), newest-updated first; `status` ∈ draft/published/archived. |
| `POST /owners/venues` | Creates a **draft**. Only `name` is required. Optional: description, address_line, city_id, postal_code, latitude+longitude (together), contact_phone, starting_price_paise, timezone (IANA, default Asia/Kolkata), category_ids, amenity_ids. Errors: `INVALID_CITY`, `INVALID_CATEGORY`, `INVALID_AMENITY`, `INVALID_TIMEZONE`. |
| `GET/PATCH /owners/venues/{id}` | Detail includes `images`, `category_details`, `amenities`, `state` (from the city) and `publish_blockers`. PATCH: omitted = unchanged, `null` = clear (not `name`/`timezone`); lists replace. A published venue cannot lose its city, location or last category (`PUBLISHED_VENUE_INCOMPLETE`). |
| `POST /owners/venues/{id}/publish`, `/unpublish` | Publish needs a city, coordinates and ≥ 1 category (`PUBLISH_REQUIREMENTS`, blockers in `details`). **There is no admin approval step yet (Q4).** Unpublish returns the venue to draft. |
| `DELETE /owners/venues/{id}` | `204`. Hard delete; images, links and hours cascade; stored files are removed best-effort. **Step 6:** a venue that has any booking is refused, `409 VENUE_HAS_BOOKINGS`. |
| `POST /owners/venues/{id}/images` | `multipart/form-data`: `file` (+ optional `alt_text`). JPEG/PNG/WebP detected from the **bytes**, ≤ 5 MiB, ≤ 10 per venue (`INVALID_IMAGE`, `IMAGE_TOO_LARGE`, `IMAGE_LIMIT_REACHED`). First image becomes the cover. `503 STORAGE_NOT_CONFIGURED` when the server has no Storage credentials. |
| `PUT /owners/venues/{id}/images/order` `{image_ids}` | Must list every image exactly once (`INVALID_IMAGE_ORDER`). |
| `PATCH /owners/venues/{id}/images/{image_id}` | `is_cover`, `alt_text`, `sort_order`. Deleting the cover promotes the next image. `DELETE` → `204`. |
| `GET/PUT /owners/venues/{id}/schedules` | `regular` always 7 days (`weekday` 0 = Monday, `intervals` empty = closed), `special` dates, and `slot_configuration` = computed from the courts: `{status:"not_configured", resources, message}` or `{status:"configured", courts:[…]}`. A change that would break a future booking is refused: `409 SCHEDULE_CONFLICT` (Step 6). PUT replaces whichever of `regular` / `special` is sent. Duplicate weekdays/dates and overlapping or reversed intervals → `INVALID_SCHEDULE`/`422`. |
| `GET /owners/dashboard` | Real: venue counts, review-count-weighted `average_rating`, per-venue performance, recent notifications. **Step 6:** `total_bookings` (int) and `booking_overview` (`{upcoming, completed, cancelled}`) are real counts (unpaid holds excluded). Still `{available:false, depends_on, message}`: `total_revenue`, `monthly_revenue` (Step 7) and `average_utilization` (N8). |
| `GET /owners/analytics?date_from&date_to` | Range ≤ 366 days (`INVALID_DATE_RANGE`). Venue performance is real; every booking/revenue figure is `available:false`. |
| `GET /owners/notifications?group&unread_only&limit&offset`, `POST …/{id}/read`, `POST …/read-all` | Own notifications; `group` ∈ all/bookings/payments/reviews (by type prefix). Another owner's id → `404 NOTIFICATION_NOT_FOUND`. |
| `GET /owners/earnings`, `GET /owners/reviews` | Answer `available:false` with an empty `items` list and the step they wait for (Step 7 / reviews feature). Bookings are real since Step 6, see below. |


### Availability and bookings (Step 6)

Details: `AVAILABILITY_LOGIC.md`, `BOOKING_ENGINE.md`, `BOOKING_STATUS_FLOW.md`. Times are ISO-8601 with an offset; slots carry `starts_at`/`ends_at` in UTC plus `local_start`/`local_end` ("HH:MM") in the venue's time zone. Money is integer paise.

**Customer** (any signed-in user may read availability; bookings need an active **customer**; another customer's booking is `404 BOOKING_NOT_FOUND`):

| Endpoint | Notes |
|---|---|
| `GET /venues/{id}/availability?date=YYYY-MM-DD&resource_id` | Per court: `state` (`available`, `fully_booked`, `closed`, `not_configured`), `message`, and **only free slots**. `closed_reason`/`note` for holidays. Errors: `404 VENUE_NOT_FOUND` (also for unpublished), `404 RESOURCE_NOT_FOUND`, `422 INVALID_DATE` (past, or > 400 days). |
| `GET /venues/{id}/availability/dates?date_from&date_to` | Dates in the range (≤ 31 days) with ≥ 1 free slot. `422 INVALID_DATE_RANGE`. |
| `POST /bookings/quote` `{resource_id, starts_at}` | Revalidates the slot and returns the server price: `base/fees/tax/discount/total_amount_paise` (fees, tax, discount are 0, Q7/Q8/N7), `note`. Same slot errors as below. |
| `POST /bookings` `{resource_id, starts_at}` + header `Idempotency-Key` (8–100 chars, recommended) | `201` booking (`pending_payment` with `expires_at`, or `confirmed` when `BOOKING_MODE=instant`). Replay of the same key + body → `200` with the original booking. Errors: `422 INVALID_SLOT` (not a bookable slot / outside hours), `422 SLOT_NOT_BOOKABLE` (started or outside the booking window), `409 SLOT_UNAVAILABLE` (taken), `409 RESOURCE_NOT_CONFIGURED`, `404 RESOURCE_NOT_FOUND`, `422 IDEMPOTENCY_KEY_REUSED`, `422 INVALID_IDEMPOTENCY_KEY`, `503 BOOKING_NOT_CONFIGURED`. Clients cannot send price, duration, status or a customer id. |
| `GET /bookings?bucket=upcoming\|past\|cancelled&limit&offset` | Own bookings. `past` = completed or expired. |
| `GET /bookings/{id}` | Booking with `history`, `price` snapshot, `can_cancel`. |
| `GET /bookings/{id}/cancellation-preview` | `{can_cancel, code, message}`. |
| `POST /bookings/{id}/cancel` `{reason?}` | `200` booking. `409 INVALID_STATUS_TRANSITION`, `409 CANCELLATION_NOT_AVAILABLE`, `409 CANCELLATION_WINDOW_CLOSED`. |

Example booking response (abridged):

```json
{"id":"…","booking_code":"ZUR-7K3M9QXA","status":"pending_payment","payment_status":"unpaid",
 "venue_name":"Ace Arena","resource_name":"Court 1","booking_date":"2030-01-07",
 "starts_at":"2030-01-07T03:30:00Z","ends_at":"2030-01-07T04:30:00Z","local_start":"09:00","local_end":"10:00",
 "duration_minutes":60,"currency":"INR","base_amount_paise":50000,"total_amount_paise":50000,
 "price":{"slot_price_paise":50000,"fees_paise":0,"tax_paise":0,"discount_paise":0,"…":"…"},
 "expires_at":"2030-01-06T21:40:00Z","can_cancel":true,
 "history":[{"from_status":null,"to_status":"pending_payment","actor_role":"customer","reason":null,"created_at":"…"}]}
```

**Owner** (own venues only; others → `404`):

| Endpoint | Notes |
|---|---|
| `GET /owners/bookings?bucket&venue_id&limit&offset`, `GET /owners/bookings/{id}` | Bookings at own venues with `customer_name` (name only, N9) and history. Unpaid holds are not listed until confirmed. Read-only: owners cannot change statuses (N22). |
| `GET/POST /owners/venues/{id}/resources`, `PATCH/DELETE …/resources/{rid}` | Courts: `name`, `slot_minutes` (5–720), `slot_price_paise`, `sort_order`, `is_active`; `configured` = has both. Changing `slot_minutes`/`is_active` is checked against future bookings (`409 SCHEDULE_CONFLICT`). Delete is refused when the court has bookings (`409 RESOURCE_HAS_BOOKINGS`). |
| `GET/POST /owners/venues/{id}/blocks`, `DELETE …/blocks/{bid}` | Temporary unavailable periods (`resource_id` null = whole venue). Creating one that overlaps a future booking → `409 SCHEDULE_CONFLICT`. |
| `PUT /owners/venues/{id}/schedules` | As Step 5, plus the `SCHEDULE_CONFLICT` check. |

**Admin** (MFA rule as Step 3): `GET /admin/bookings?status&venue_id&limit&offset`, `GET /admin/bookings/{id}` — read-only, includes `customer_id` and `owner_id`.

`SCHEDULE_CONFLICT` body: `details = {count, bookings:[{booking_id, booking_code, starts_at, ends_at, status}]}` (first 20).

### Payments, notifications and devices (Step 7)

Details: `RAZORPAY_INTEGRATION.md`, `PAYMENT_STATUS_FLOW.md`, `NOTIFICATION_ARCHITECTURE.md`. Money is integer paise. The client never sends an amount.

| Endpoint | Who | Notes |
|---|---|---|
| `POST /payments/create-order` `{booking_id}` | customer | Returns `{payment, checkout:{key_id, order_id, amount_paise, currency, name, description, prefill}}`. Same booking → same order. Errors: `404 BOOKING_NOT_FOUND`, `409 ALREADY_PAID / HOLD_EXPIRED / BOOKING_NOT_PAYABLE / PAYMENT_NOT_REQUIRED`, `422 AMOUNT_NOT_PAYABLE`, `503 PAYMENTS_NOT_CONFIGURED / PAYMENT_PROVIDER_*`. Extra body fields (e.g. `amount_paise`) → `422`. |
| `POST /payments/verify` `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` | customer | Returns `PaymentOut` (`status`, `confirmed`, `needs_review`, `booking_status`, ...). `confirmed:true` only after signature + gateway fetch + matching amount. `400 PAYMENT_SIGNATURE_INVALID`. |
| `POST /payments/webhook` | Razorpay | `X-Razorpay-Signature` over the raw body; `X-Razorpay-Event-Id`. `200 {received, outcome}` (`applied|duplicate|ignored|rejected`); `400 WEBHOOK_SIGNATURE_INVALID`; `503 WEBHOOK_NOT_CONFIGURED`. |
| `GET /payments/{id}`, `GET /payments/history` | customer | Own only (others → 404). `GET {id}` re-checks the gateway while the payment is open. |
| `GET /owners/earnings`, `GET /owners/payments` | owner | Gross captured amounts for own venues. `deductions`, `net_earnings`, `payouts` are `{available:false,...}`. |
| `GET /admin/payments` (`status`, `review_required`), `/admin/payments/{id}`, `/admin/payments/summary` | admin | Records, references, gateway events, review queue, gross total. Never credentials or card data. |
| `GET /notifications` (`group`, `unread_only`, `limit`, `offset`), `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all` | any role | Own only. Items now include `booking_id`, `payment_id`. |
| `GET/PUT /notifications/preferences` `{push_enabled, email_enabled}` | any role | Defaults: both on. |
| `PUT /devices/token` `{token, platform, app}`, `POST /devices/token/remove` `{token}` | any role | Idempotent upsert / sign-out removal. A token re-registered by another account moves to it. |

### Admin (Step 8, admin only)

Full reference: `ADMIN_API_DOCUMENTATION.md`. Routes under `/admin`: `me`, `dashboard`, `analytics/{bookings,revenue,platform}`, `activity`, `owners[/{id}[/status]]`, `customers[/{id}[/status]]`, `venues[/{id}]`, `bookings[/{id}]`, `payments[/summary|/{id}]`, `exports/{bookings,payments,customers,owners}.csv`, `audit-logs`. Read-only except the two audited `PATCH …/status` calls.

## Differences from the Step 1 catalogue

Step 1 proposed `GET /v1/me`, `POST /v1/auth/register/customer|owner`, `GET|PATCH /v1/customer/profile` and `/v1/owner/profile`. Step 3 follows the paths in the Step 3 brief instead (`/auth/me`, `/auth/profile`, `/customers/me`, `/owners/me`) under the Step 2 prefix `/api/v1`. Not implemented (belong to later steps or open questions): `DELETE /me` (account deletion, N17), device tokens (Step 7).

- **Step 4:** favourites are at `/favorites` (not `/customer/favorites`) and removal is by venue id (D-39). `/cities`, `/categories`, `/amenities`, `/venues` are authenticated, not public, because the apps only run signed in.

- **Step 5:** owner routes are `/owners/...`, not the catalogue's `/v1/owner/...` (the Step 5 brief names `/owners/...` and `/owners/me` already existed). Images are one multipart call, not signed-upload + finalize, because the bucket is write-only for the backend (D-51). Hours are `GET/PUT /owners/venues/{id}/schedules` (D-52), not `schedule/regular|special`. Not implemented: `/owner/payout-account` (N11), real earnings (Step 7). (Courts and bookings arrived in Step 6.)

## Operator script

`python -m scripts.create_admin --email … --name …` (from `backend/`, with `DATABASE_URL`). Promotes an existing Supabase user to admin. Needs no service-role key.

- **Step 6:** availability is `GET /venues/{id}/availability` (+ `/availability/dates`); the `/slots` alias is not provided because it would return the same data. Owner schedule editing stays `PUT /owners/venues/{id}/schedules` (replace semantics, D-52) instead of separate `POST/PATCH special-schedules`. Added, not in the brief: `POST /bookings/quote`, `GET /bookings/{id}/cancellation-preview`, courts and blocks routes, `GET /admin/bookings…`. Booking-code format and the status list are proposals pending Q11.


## Settings endpoints (mobile app, both roles)

| Method + path | Role | Purpose |
|---|---|---|
| `GET/PUT /notifications/preferences` | any | `push_enabled`, `email_enabled`, `booking_enabled`, `payment_enabled`, `promo_enabled`. The server skips push **and** e-mail for a type whose switch is off (`booking.*`, `payment.*`, `promo.*`); the in-app copy is always kept. |
| `PATCH /profiles/me` | any | now also accepts `language` (`en`/`hi`); `avatar_path: null` removes the photo |
| `POST /profiles/me/deletion-request` | any | records `deletion_requested_at` (idempotent). Nothing is deleted; an administrator processes the request. |
| `DELETE /profiles/me/deletion-request` | any | cancels the request |
| `GET/PATCH /customers/me` | customer | `preferred_category_ids` (unknown category -> 422 `INVALID_CATEGORY`; duplicates removed) |
| `POST /support/tickets` | any | `{kind, subject(3-120), message(10-2000), app_version?, platform?}`; max 5 per hour per user (409 `RATE_LIMITED`) |
| `GET /support/tickets` | any | the caller's own messages only |

Password change, session listing/sign-out-everywhere and e-mail are handled by Supabase Auth directly from the app.
