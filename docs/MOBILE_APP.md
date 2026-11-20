# ZURUV mobile app (one app, two roles)

There is **one** Flutter app, `apps/mobile_app`: one codebase, one APK, one AAB. It replaces the former
`apps/customer_app` and `apps/owner_app`. The platform is:

| Part | Where | Who uses it |
|---|---|---|
| Mobile app | `apps/mobile_app` | Customers and venue owners |
| Admin website | `apps/admin_web` (Next.js) | Admins only |
| API | `backend` (FastAPI) | Both of the above |
| Database / Auth / Storage | Supabase | Reached only through the API (clients use Supabase for sign-in only) |

No second backend or database exists. The mobile app and the admin website call the same `/api/v1`
endpoints, so a change made in one (a venue published by an owner, a booking cancelled by a customer, a
user suspended by an admin) is read from the same tables by the others.

## Role-based sign-in

* One login screen. **Register** asks "Player / Venue owner" (owners also give a business name).
* After sign-in the app asks the API (`GET /auth/me`) for the account's role. **The role always comes from
  the database**, never from the app or the token.
  * `customer` -> Customer Dashboard (`/home`, tabs Home / Explore / Bookings / Favorites / Profile)
  * `owner` -> Owner Dashboard (`/owner/dashboard`, tabs Dashboard / Venues / Bookings / Earnings / Profile)
  * `admin` -> signed out with "Admin accounts sign in on the ZURUV admin website".
  * suspended -> "Account suspended" screen, as before.
* The account type picked at registration only decides which profile is *requested* the first time
  (`POST /auth/profile`, which accepts `customer` or `owner` only; `admin` is rejected by the app and the API).
* Each role keeps its own theme.

### Navigation

Customer routes are unchanged (`/home`, `/explore`, `/bookings/:id`, `/venues/:id`, ...).
**Every owner route lives under `/owner`** (`/owner/dashboard`, `/owner/venues/:id/courts`, ...), which removes
all path clashes between the two roles. `roleRedirect` (`lib/core/router/app_router.dart`) keeps customers out
of `/owner/*` and owners out of customer pages, opens the right dashboard at `/`, and shows the owner intro
once after an owner's first sign-in. Push notification taps open `/bookings/:id` or `/owner/bookings/:id`
depending on the role.

### Security: where permissions are really enforced

The app-side routing above is a **UX boundary only**. Permissions are enforced by the backend on every request
(`backend/app/api/deps.py`): `require_customer`, `require_owner` and `require_admin` read the role from the
database profile, not from the token, and check ownership of each venue/booking. A customer token calling
`/owners/...` gets 403 `INSUFFICIENT_ROLE` whatever the app does. Admin endpoints additionally require MFA.
Nothing about roles was relaxed by the merge; the backend was not changed.

## Code layout

```
apps/mobile_app/lib/
  main.dart, app.dart          single entry point, theme chosen by role, push handling
  core/                        shared: router (+ role rules), splash, first-run onboarding, config, preferences,
                               tokens, api_helpers, both themes
  customer/                    all customer screens, models, repositories (features/, shared/, core/utils)
  owner/                       all owner screens, models, repository   (features/, shared/, core/utils)
  customer/customer_routes.dart, owner/owner_routes.dart   each role's routes
packages/flutter_shared/       auth (controller, screens, gateway), theme, API client, push - used by both roles
```

The two feature trees were moved as-is into `customer/` and `owner/` (imports rewritten), so no screen or
integration was rewritten. They are separate Dart libraries, so same-named classes (`BookingsScreen`,
`ProfileScreen`, ...) do not collide. Code that was duplicated between the two apps (avatar service,
`ZNetworkImage`, common widgets) is still duplicated per role; de-duplicating it is a possible follow-up.

## Configuration

One `apps/mobile_app/.env` (public values only; bundled as an asset; see `.env.example` and `ENV.md`):
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `API_BASE_URL`, `AUTH_REDIRECT_URL=io.zuruv.app://login-callback`, and the
three `*_AUTH_ENABLED` switches. The admin site keeps its own `apps/admin_web/.env.local`.

## Build (you deploy yourself)

```bash
./scripts/bootstrap_flutter.sh          # once: android/ + ios/ runners, permissions, deep link (idempotent)
cd apps/mobile_app && cp .env.example .env     # fill in public values
flutter run
flutter build apk --release             # one APK  (build/app/outputs/flutter-apk/app-release.apk)
flutter build appbundle --release       # one AAB  (build/app/outputs/bundle/release/app-release.aab)
```

Application id / bundle id: `com.zuruv.zuruv`. Release signing is yours to configure (see
MANUAL_DEPLOYMENT_GUIDE.md).

### Things to change in your dashboards when you deploy

1. **Supabase > Authentication > URL Configuration**: add `io.zuruv.app://login-callback`
   (the old `io.zuruv.customer://` and `io.zuruv.owner://` entries are no longer used).
2. **Firebase** (if you use push): register one Android app and one iOS app for `com.zuruv.zuruv`.
3. **Admin accounts** are unchanged: created by the operator script and used on the website only.

## What changed in the shared package

* `expectedRoleProvider` is gone. `AuthController` accepts customer and owner, rejects admin.
* `AuthUiConfig` no longer carries a role; `signUpRoleProvider` + `AccountTypePicker` choose it at sign-up.
* `completeProfile(role: ...)` and `register(role: ...)` take the chosen role; it travels in the sign-up
  metadata as `requested_role` so e-mail-confirmed sign-ups create the right profile.
* Push registration reports `customer` or `owner` from the signed-in profile, and re-registers with the current
  role when another account signs in on the same phone.

## Migration notes

Preserved: every customer and owner screen, repository, model, API call, Razorpay checkout, location, image
upload, push and deep-link integration.

Not carried over (dead or superseded code):
* Owner `features/home/home_screen.dart`, `core/router.dart`, `core/providers.dart`: the Step 3 "foundation status"
  placeholder, not reachable from the real router.
* Owner `OwnerSplashScreen`: replaced by the single branded splash (the role is unknown at launch).
  The owner's own first-run intro (five pages) is kept and shown after an owner's first sign-in.

### Defects found and fixed while merging

The two apps did **not** build or pass tests when merging started (the notes in OWNER_APP.md say they had been
written without a Flutter SDK). Fixed:

* Owner: `ownerRepositoryProvider`, `citiesProvider`, `categoriesProvider`, `amenitiesProvider` were missing and
  the repository class was cut in two (44 compile errors).
* Customer router: missing `flutter/widgets` import (compile error).
* Customer booking screen and owner opening-hours editor: buttons placed in a `Row` crashed layout
  (the theme's full-width minimum size is infinite there).
* Owner review reply: a `TextEditingController` was disposed while its dialog was still animating out.
* Auth: a sign-out notice ("session expired" / wrong account type) could be lost to a race with the sign-out event.
* Push: a refreshed-token listener kept the first account's role label.
* Shared login: "Don't have an account?" row could overflow on narrow screens.
* Stale tests (wrong finders, missing phone-sized surface, outdated route paths) were corrected.

## Verification

Run from the repo root: `make flutter-analyze` and `make flutter-test`
(`packages/flutter_shared` and `apps/mobile_app`). Role flows are covered by `test/core/router_rules_test.dart`
(pure routing rules), the customer and owner `app_flow_test.dart` files (each role signs in through the unified
app, sees its own dashboard and is bounced from the other's pages) and the shared `auth_controller_test.dart`.


## Settings (Customer and Venue Owner)

Entry: **Profile > Settings** (`/settings` for customers, `/owner/settings` for owners). One implementation in `lib/core/settings/`, mounted by both route files (`settings_routes.dart`).

| Section | Behaviour | Stored |
|---|---|---|
| Profile | existing Edit profile screen: name, phone, upload / replace / **remove** photo (Supabase Storage `profile-images`); e-mail is read-only (it is the sign-in identity) | `profiles`, Storage |
| Account | account info; change password (verifies the current password by re-authenticating, then `updateUser`); account-deletion request with cancel | Supabase Auth, `profiles.deletion_requested_at` |
| Appearance | Light / Dark / System, applied app-wide (customer and owner themes both have a dark variant) | device (`theme_mode_v1`) |
| Preferences | language (en/hi); customers also: sports interests and default city | `profiles.language`, `customer_profiles.preferred_category_ids`, existing city selection |
| Notifications | push, e-mail, bookings, payments, promotions | `notification_preferences` (enforced server side) |
| Privacy & security | location permission status + open phone settings; this device's session; sign out of this device / **all devices** (Supabase global sign-out); privacy policy | Supabase Auth |
| Help & support | role-specific FAQs; contact support, feedback, report an issue (stored as tickets); "My messages" history | `support_tickets` |
| About | app version/build (package_info_plus), Terms, Privacy Policy | n/a |

Honest limits: the language setting changes dates, numbers and system dialogs only (the app's own text is English; full translation is future work). Terms and Privacy pages say the legal text is pending (no text was supplied). Supabase cannot list other devices' sessions from the client, so "active sessions" shows this device plus sign-out-everywhere. Promotional notifications are stored and enforced, but no promotional notification is sent by the platform yet. Support tickets and deletion requests have no admin screen yet (see KNOWN_ISSUES).
