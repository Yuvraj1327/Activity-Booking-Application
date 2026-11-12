# Step 4 report — Customer app: UI and venue discovery

Date: 2026-11-12. Read with: API_DOCUMENTATION.md, DATABASE_SCHEMA.md, AUTHENTICATION_FLOW.md, ROLE_PERMISSION_MATRIX.md, DEVELOPMENT_SETUP.md.

## Headline: what is and is not verified

| Area | Status | Evidence |
|---|---|---|
| New backend: migration `0004`, catalogue / venue search / venue detail / favourites APIs, seed scripts | **Verified** on a local PostgreSQL 16 + Supabase stub (not on Supabase) | 162 backend tests pass (151 existing + 11 new); `ruff` clean; `mypy app` clean; `0004` upgrades, downgrades to `0003` (removes `favorites` and the four `venues` columns) and upgrades again |
| Flutter Customer app (every screen, provider, repository) | **Written, NOT compiled, analysed or run** | There is no Flutter SDK and no pub.dev access in this workspace. `flutter analyze` and `flutter test` have **not** been run. Expect a first-compile round of small fixes. I checked bracket balance of every Dart file and reviewed imports and APIs by hand; that is not a substitute for the compiler |
| Flutter tests (50 in the Customer app + 1 new shared test: widget, controller, model, redirect) | **Written, NOT executed** | same reason |
| Screenshots of the major screens | **Not produced** | the app cannot be run here; see item 9 |
| Real sign-in, Supabase Storage uploads, signed avatar URLs, Google/Apple/phone, device location, image picking | **NOT tested** | need your Supabase project, a device and the SDK. The code paths are implemented and the tests use fakes for them |
| Google Maps / Places | **Prepared only** (interface), not integrated | see item 5 |

## 1. Screens implemented

Splash (branded) · Onboarding (3 pages, Skip, Get Started) · Login, Register, Forgot / Reset password, Phone OTP, Complete profile, Suspended, Auth error (Step 3 screens, reused, unchanged) · **Home** · **Explore** (search, filters, sort, infinite scroll) · **Sport results page** (`/category/:slug`) · **Venue details** · **Favorites** · **Profile** · **Edit profile** (with photo) · My Bookings (placeholder) · Notifications (placeholder) · City / location sheet · Price sheet · More-filters sheet (sport + sort) · "All sports" sheet.

Navigation: `StatefulShellRoute.indexedStack` with Home, Explore, Bookings, Favorites, Profile. Each tab keeps its own stack, scroll position, search text and loaded list, so switching tabs does not reload. Tapping the active tab returns to its first screen. Detail, sport results, notifications and edit-profile open full screen above the tabs.

## 2. UI components created

Design system: tokens (`Gap`, `Radii`, `Shadows`), `buildCustomerTheme()` (bottom navigation, chips, snack bars, bottom sheets on top of the shared ZURUV theme), formatters (₹ with Indian grouping, distance).
Reusable widgets: `ZNetworkImage` (cached, placeholder, error fallback, fixed aspect ratio), `ShimmerBox`, `VenueCard`, `VenueCarouselCard`, `VenueCardSkeleton`, `FavoriteButton`, `RatingBadge`, `PriceLabel`, `SectionHeader`, `EmptyState`, `ListFooter` (load-more / retry), `AvatarView`, category and amenity icon maps. Shared with Step 3: `ErrorView`, `LoadingView`, `LoadingButton`, `AuthBanner`, `ResponsivePage`.

## 3. API integrations completed

| App feature | Endpoint | Backend status |
|---|---|---|
| Cities, categories | `GET /cities`, `GET /categories` | **New in Step 4** |
| Home sections, Explore, sport page | `GET /venues` (search, category, city, price range, sort, lat/lng, radius, limit/offset) | **New** |
| Venue details | `GET /venues/{id}` | **New** |
| Favorites list / add / remove | `GET`, `POST /favorites`, `DELETE /favorites/{venue_id}` | **New** |
| Profile view / edit | `GET`, `PATCH /profiles/me` | Step 3 |
| Preferred city | `GET`, `PATCH /customers/me` | Step 3 |
| Auth bootstrap | `GET /auth/me`, `POST /auth/profile` | Step 3 |

One Dio client (`apiClientProvider` from `flutter_shared`) attaches the Supabase JWT; no second client exists. Every repository call goes through `apiCall`, which turns any failure into an `ApiException` (the server's `{code, message}` or a network error). Screens show loading skeletons, an inline retry, empty states, and keep the loaded list when only the next page fails. A removed or unpublished venue shows "This venue is no longer available". No venue, category, city, price or rating is hard-coded in the app; the only static strings are UI copy and the icon mapping.

## 4. Authentication integration status

Unchanged and reused: the Step 3 controller, gateway and guard still decide who gets in. Step 4 added three small, backwards-compatible hooks to `flutter_shared` (existing tests untouched, one new test): `authRedirect(..., extraPublicPaths)`, `buildAuthAwareRouter(preRedirect, extraRefresh, extraPublicPaths, splashBuilder)` and `AuthController.setProfile` (used after profile edits). The app's own launch rules (hold on splash, onboarding once) are a pure function, `launchRedirect`, that runs **before** the guard and never grants access: every protected route still redirects a signed-out, wrong-role or suspended user. The login / register screens are the shared themed ones (violet, rounded); they were not given a separate customer layout. Google, Apple and phone stay behind the Step 3 dart-defines and are hidden until configured. **Not tested against real Supabase.**

## 5. Location integration status

* **City selection: complete.** Chosen in a sheet from `GET /cities`, kept on the device and saved as the account's preferred city (best-effort). It scopes Home and Explore. If the stored city is no longer in the list it is dropped.
* **Current location: implemented, permission-safe.** Never requested at launch. If permission was already granted it is used silently; otherwise Home shows an optional "Venues near you / Enable" card, the city sheet has "Use my current location", and the **Near Me** chip asks only when tapped. Denied, denied-forever (with a Settings action) and services-off each show a clear message and the app keeps working with the manual city. With a position, cards show distance and Home shows "Nearby venues" (25 km, nearest first).
* **Distance** is computed by the API with the haversine formula (D-42). PostGIS is not used.
* **Google Maps / Places: prepared, not integrated.** `PlaceSearchService` is an interface with a no-op default. The architecture needs no key in the app: the planned implementation calls a backend proxy endpoint that holds the key. No Google package is added, no map is drawn, and no key exists anywhere in the code. The venue page shows the address as text; there is no "open in maps" button yet.

## 6. Favorites and profile status

* **Favorites:** heart on every card and on the detail page; optimistic update that rolls back with a message if the API fails; the Favorites tab pages through the list, hides a venue immediately when un-hearted, and refreshes when one is added. State is reset when another account signs in.
* **Profile:** shows name, e-mail, phone, avatar; Edit profile changes name and phone (phone may be cleared) and sends only changed fields; e-mail is read-only. Profile picture: picked from the gallery, checked (JPG / PNG / WebP, ≤ 2 MiB, same limits as the bucket), uploaded **directly to the private `profile-images` bucket under `<user id>/`**, saved with `PATCH /profiles/me` (the API re-checks the folder) and shown through a short-lived signed URL; the previous file is deleted best-effort. Sign out asks for confirmation. **Upload and signed URLs are untested against real Storage.**

## 7. Tests and Flutter analyze results

* **Backend (run):** `pytest` → **162 passed**. New: `test_catalog_api.py` (9) covers authentication, only published venues visible, reference data active-only, search by name / address / category name with `%` escaped, category / price / city filters, all sort orders, distance and radius, pagination without overlap, validation errors, detail with images (pending hidden, cover first, public URL), favourites lifecycle, idempotency, user isolation, unpublished-favourite hiding, customer-only access; `test_seed_scripts.py` (2). `test_migrations.py` / `test_rls.py` updated for the 14th table.
* **Flutter (NOT run):** `flutter analyze`: **not run**. `flutter test`: **not run**. Written: `launch_redirect_test`, `models_test`, `app_flow_test` (splash → onboarding → login, owner turned away, protected routes, tab state kept, sign-out), `discovery_test` (Home sections, More sheet, category browse, error + retry, empty state, optimistic favourite and rollback, Explore search debounce, empty-result clearing, price sheet, disabled Today chip, Near Me denied, pagination controller), `venue_details_test`, `profile_location_test` (edit, validation, server error, city persistence, granted / denied / forever-denied location, stale stored city), plus 1 new shared test. Fakes replace the API, location, avatar storage and auth gateway.
* Responsive layout: lists are capped at 640 px and details at 720 px and centred on tablets, but this has not been looked at on a device or in a test at several sizes.

## 8. Remaining issues and decisions needed

1. **Compile and test the Flutter code** on a machine with the SDK: `./scripts/bootstrap_flutter.sh`, then `flutter analyze` and `flutter test` in `apps/customer_app` and `packages/flutter_shared`; send me the output and I will fix it.
2. **Apply `0004` to your Supabase database** and run `seed_reference_data`; no real venues or photos exist yet (Owner app is Step 5), so use `seed_demo_venues` in development. Demo venues have no images, so every card shows the neutral placeholder until photos are added.
3. **Design assets:** the splash uses a gradient and court-line artwork, not sports photography, and category icons are Material stand-ins. Supply licensed photography and an icon set. Brand colours were sampled from the board (approximate).
4. **Confirm D-40 / D-42 assumptions:** price shown as *per hour* in INR; haversine now, PostGIS later if you want index-backed radius search at scale.
5. **"Today" filter:** the brief lists it, the roadmap defers it until availability exists (Step 6). It is shown **disabled** with a tooltip rather than hidden. Say if you would rather hide it.
6. **"Book Now"** is present as the brief requires but only opens a "Booking opens soon" sheet (no booking or payment in this step). Booking slots, summary, payment and My Bookings are Steps 6–7.
7. Not built: reviews list on the venue page (no reviews table), share, "open in maps", help / settings screens (no design supplied), push notifications, dark mode.
8. Offset pagination with no total count; if rows are inserted between pages a venue could shift, which the app de-duplicates. Cursor pagination can replace it later without app changes to the screens.
9. Carry-over from Steps 1–3 (unchanged): no Supabase credentials, real auth methods untested, Step 1 gate questions (Q1/Q2/Q17/N2/N23 booking model, Q4, Q18, N10, N17, N24, N1, N13) unanswered.

## 9. Screenshots

None. Producing screenshots needs the Flutter SDK and an emulator, neither of which exists in this workspace, and I will not mock them up as if they were the app. After step 1 of the list above, run the app and capture them; the screens to capture are Splash, Onboarding, Home, Explore (with filters), Venue details, Favorites and Profile.

## 10. Run the Customer app

```bash
# once, on a machine with Flutter >= 3.27
./scripts/bootstrap_flutter.sh                 # generates android/ios, adds permissions and the deep link, pub get

# backend (separate terminal), already migrated to 0004
cd backend && source .venv/bin/activate && python -m scripts.seed_reference_data
python -m scripts.seed_demo_venues --owner-email <an existing owner e-mail>   # development only
uvicorn app.main:app --port 8008

# app
cd apps/customer_app
cp .env.example .env           # add SUPABASE_URL, SUPABASE_ANON_KEY; Android emulator: API_BASE_URL=http://10.0.2.2:8008/api/v1
flutter run
```

## Files

Backend: `alembic/versions/0004_favorites_venue_display.py`, `app/models/venue.py` (+`Favorite`), `app/schemas/catalog.py`, `app/repositories/venues.py`, `app/services/venues.py`, `app/api/v1/endpoints/catalog.py`, `scripts/seed_reference_data.py`, `scripts/seed_demo_venues.py`, tests above.
Flutter: `apps/customer_app/lib/{core,features,shared}` (feature-based as specified: `core/{config,constants,network,router,storage,theme,utils}`, `features/{splash,onboarding,home,categories,discovery,venue_details,favorites,profile,notifications,bookings,location,shell}`, `shared/{models,repositories,widgets}`); `packages/flutter_shared/lib/src/auth/{router,controller}.dart` (additive); `scripts/configure_customer_platforms.py`.

## Decisions recorded this step

D-39 favourites keyed by pair, removed by venue id · D-40 interim per-hour display price in INR · D-41 rating aggregates only, "New" until reviews exist · **D-42** distance by haversine in SQL, PostGIS deferred (revises D-32's trigger point) · **D-43** catalogue and venue reads require sign-in (any active role); favourites are customer-only · **D-44** Today chip shown disabled · **D-45** Book Now is a real button that explains booking is not available yet · **D-46** reference data seeded by an idempotent operator script (India-first city list is an assumption, N1); demo venues are dev-only, labelled "(Demo)", with no images or ratings · **D-47** avatars uploaded straight to the private bucket from the app, read through signed URLs · **D-48** Google Places behind an interface; key never in the client · **D-49** offset pagination with `has_more`, no total.
