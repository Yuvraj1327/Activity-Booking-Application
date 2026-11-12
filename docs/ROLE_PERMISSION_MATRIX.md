# Role permission matrix

Authorisation is decided **server-side from the `profiles` table** (decision D-11). The JWT only proves identity; `role`/`status` claims or `user_metadata` are never used. A suspended account is refused on its next request.

## API (implemented in Step 3)

| Endpoint | Anonymous | Customer | Owner | Admin | Suspended |
|---|---|---|---|---|---|
| `GET /health`, `GET /api/v1/version` | ✔ | ✔ | ✔ | ✔ | ✔ |
| `GET /auth/me` (token only) | 401 | ✔ | ✔ | ✔ | ✔ (shows `suspended`) |
| `POST /auth/profile` (customer or owner only) | 401 | ✔ own | ✔ own | 409/422 | n/a |
| `GET/PATCH /profiles/me` | 401 | ✔ | ✔ | ✔ | 403 |
| `GET/PATCH /customers/me` | 401 | ✔ | 403 | 403 | 403 |
| `GET/PATCH /owners/me` | 401 | 403 | ✔ | 403 | 403 |
| `GET /admin/me` | 401 | 403 | 403 | ✔ (+MFA when required) | 403 |
| `GET /cities`, `/categories`, `/amenities`, `/venues`, `/venues/{id}` (published only) — **Step 4** | 401 | ✔ | ✔ | ✔ | 403 |
| `GET/POST /favorites`, `DELETE /favorites/{venue_id}` — **Step 4** | 401 | ✔ own | 403 | 403 | 403 |
| `/owners/venues` (list, create, get, patch, delete, publish, unpublish, images, schedules) — **Step 5** | 401 | 403 | ✔ **own venues only**; another owner's venue → 404 | 403 | 403 |
| `/owners/dashboard`, `/owners/analytics`, `/owners/notifications`, `/owners/bookings`, `/owners/earnings`, `/owners/reviews` — **Step 5** | 401 | 403 | ✔ own data | 403 | 403 |

Rules enforced and tested:
- No endpoint accepts a user id; the subject is always the verified token. Sending `role`, `status`, `id` or `email` in a body is rejected (422).
- `admin` cannot be requested through the API. Admins are created by an operator with `python -m scripts.create_admin` (promotes an existing Supabase user; refuses users who already have another role).
- A role cannot change after creation (database trigger).
- Admin endpoints additionally require an MFA-verified session (`aal2`) when `ADMIN_REQUIRE_MFA` is on (automatic in staging/production).

Admin web permissions in full: `ADMIN_PERMISSION_MATRIX.md`.

## Capabilities from the approved architecture (§8.4), and where they land

| Capability | Customer | Owner | Admin | Built in |
|---|---|---|---|---|
| Own profile | ✔ | ✔ | ✔ | Step 3 |
| Browse published venues | ✔ | ✔ | ✔ | Step 4 |
| Create / manage venues | ✖ | own only | ✖ by default | Step 5 (ownership already enforced by FK + RLS) |
| Bookings (**Step 6**) | own, create, cancel under the rules | own venues, read, customer name only | read all | Created and cancelled only through the API; no role can set a status directly |
| Payments | customer | owner (own venues) | read | Step 7 |
| Manage accounts | own | own | suspend/reactivate only, audited (rest per Q18) | Step 8 |

## Database (RLS) read access, as the `authenticated` / `anon` roles

| Table | Anonymous | Customer | Owner | Admin |
|---|---|---|---|---|
| `profiles`, `customer_profiles`, `owner_profiles` | none | own row | own row | all |
| `cities`, `categories`, `amenities` | active rows | active | active | active (full list via API) |
| `venues` | published | published | published + **own** drafts | all |
| `venue_categories`, `venue_amenities` | of visible venues | same | same | all |
| `venue_images` | active, of published venues | same | + own pending | all |
| `venue_resources` | active, of published venues | same | + own inactive | all |
| `notifications` | none | own | own | own |
| `audit_logs` | none | none | none | all |
| **Any insert / update / delete** | ✖ | ✖ | ✖ | ✖ (all writes go through the API) |

Suspended users get `NULL` from `app_user_role()`, so they lose everything except reading their own profile row.

## Storage

| Bucket | Read | Write |
|---|---|---|
| `venue-images` (public) | anyone with the URL | backend only (no client policy) |
| `profile-images` (private) | owner of the folder | owner of the folder, path `<user_id>/<name>.jpg|jpeg|png|webp` only |

### Step 6 routes

| Route | Customer | Owner | Admin | Anonymous |
|---|---|---|---|---|
| `GET /venues/{id}/availability`, `/availability/dates` | ✔ | ✔ | ✔ | 401 |
| `POST /bookings/quote`, `POST /bookings`, `GET /bookings`, `GET /bookings/{id}`, `…/cancellation-preview`, `POST …/cancel` | ✔ own only (other's → 404) | 403 | 403 | 401 |
| `GET /owners/bookings`, `/owners/bookings/{id}`, courts and blocks under `/owners/venues/{id}/…` | 403 | ✔ own venues (other's → 404) | 403 | 401 |
| `GET /admin/bookings`, `/admin/bookings/{id}` | 403 | 403 | ✔ (MFA rule) | 401 |

### Step 7 routes

| Route | Customer | Owner | Admin | Anonymous |
|---|---|---|---|---|
| `POST /payments/create-order`, `POST /payments/verify`, `GET /payments/{id}`, `GET /payments/history` | ✔ own only (other's → 404) | 403 | 403 | 401 |
| `POST /payments/webhook` | n/a | n/a | n/a | signature-authenticated (no JWT) |
| `GET /owners/payments`, `GET /owners/earnings` | 403 | ✔ own venues only | 403 | 401 |
| `GET /admin/payments`, `/admin/payments/{id}`, `/admin/payments/summary` | 403 | 403 | ✔ (MFA rule) | 401 |
| `GET /notifications…`, `POST /notifications/{id}/read`, `/read-all`, `GET/PUT /notifications/preferences`, `PUT /devices/token`, `POST /devices/token/remove` | ✔ own | ✔ own | ✔ own | 401 |

Database: `payments` is readable by its customer, by the owner of its venue and by admins (RLS); nobody can write through the API roles.
