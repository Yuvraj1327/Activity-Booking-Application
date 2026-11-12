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

## Differences from the Step 1 catalogue

Step 1 proposed `GET /v1/me`, `POST /v1/auth/register/customer|owner`, `GET|PATCH /v1/customer/profile` and `/v1/owner/profile`. Step 3 follows the paths in the Step 3 brief instead (`/auth/me`, `/auth/profile`, `/customers/me`, `/owners/me`) under the Step 2 prefix `/api/v1`. Not implemented (belong to later steps or open questions): `DELETE /me` (account deletion, N17), device tokens (Step 7), favourites, venue endpoints.

- **Step 4:** favourites are at `/favorites` (not `/customer/favorites`) and removal is by venue id (D-39). `/cities`, `/categories`, `/amenities`, `/venues` are authenticated, not public, because the apps only run signed in.

## Operator script

`python -m scripts.create_admin --email … --name …` (from `backend/`, with `DATABASE_URL`). Promotes an existing Supabase user to admin. Needs no service-role key.
