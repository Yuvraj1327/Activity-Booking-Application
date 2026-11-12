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

Rules enforced and tested:
- No endpoint accepts a user id; the subject is always the verified token. Sending `role`, `status`, `id` or `email` in a body is rejected (422).
- `admin` cannot be requested through the API. Admins are created by an operator with `python -m scripts.create_admin` (promotes an existing Supabase user; refuses users who already have another role).
- A role cannot change after creation (database trigger).
- Admin endpoints additionally require an MFA-verified session (`aal2`) when `ADMIN_REQUIRE_MFA` is on (automatic in staging/production).

## Capabilities from the approved architecture (§8.4), and where they land

| Capability | Customer | Owner | Admin | Built in |
|---|---|---|---|---|
| Own profile | ✔ | ✔ | ✔ | Step 3 |
| Browse published venues | ✔ | ✔ | ✔ | Step 4 |
| Create / manage venues | ✖ | own only | ✖ by default | Step 5 (ownership already enforced by FK + RLS) |
| Bookings, payments | customer | owner (own venues) | read | Steps 6–7 |
| Manage accounts | own | own | per Q18 | Step 8 |

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
