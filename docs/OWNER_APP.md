# ZURUV Owner app (Step 5)

Flutter app for venue owners. Same stack and shared package as the Customer app (`packages/flutter_shared`: auth, theme, API client). It is a separate app with its own flows; it never reads the database directly.

> **Verification status.** The Flutter code was written without a Flutter SDK. It has **not** been compiled, analysed (`flutter analyze`) or run, its tests have not been executed, and there are **no screenshots**. The backend it calls is tested (175 tests). Treat the first `flutter analyze && flutter test` on a machine with Flutter as part of Step 5 acceptance.

## Run

```bash
./scripts/bootstrap_flutter.sh
cd apps/owner_app && cp .env.example .env   # fill in public values
flutter run
flutter analyze && flutter test
```

## Structure

```
lib/
  core/{config,constants,network,router,storage,theme,utils}
  features/{splash,onboarding,dashboard,venues,venue_form,schedules,bookings,
            earnings,analytics,reviews,notifications,profile,shell}
  shared/{models,repositories,widgets}
  main.dart, app.dart
```

Auth screens (login, owner registration, forgot/reset password, session restore, suspended, wrong-role) come from `flutter_shared`; this app supplies `expectedRole = owner` and `AuthUiConfig`. Models, one repository (`OwnerRepository`), Riverpod providers and screens are separate files. State: Riverpod; navigation: GoRouter with a `StatefulShellRoute` (tabs keep their state) and full-screen routes pushed over the tabs.

## The 14 screens

| # | Screen | Route | State |
|---|---|---|---|
| 1 | Splash (ZURUV + OWNER, tagline, court-line artwork) | `/splash` | Done. Licensed sports photography is not supplied, so artwork is drawn in code |
| 2 | Onboarding (5 pages) | `/onboarding` | Done, shown once per device |
| 3 | Auth | shared | Done in Step 3 (e-mail; Google/Apple/phone only where configured). Only owners get in |
| 4 | Dashboard | `/dashboard` | Venue counts, average rating, venue performance, recent activity are **real**. Revenue, bookings, utilization, monthly revenue, booking overview say "not available yet" |
| 5 | My Venues | `/venues` | Done: own venues, search, status filter, paging, photos, rating, price, Add |
| 6 | Add / Edit Venue | `/venues/new`, `/venues/:id/edit` | Done: all fields below, photo upload/preview/reorder/cover/remove, save draft, publish |
| 7 | Manage Slots | `/venues/:id/slots` | **Opening hours only** (weekly + special dates). Slot length, courts and pricing wait for Step 6 and are labelled as such |
| 8 | Incoming Bookings | `/bookings` | **Step 6:** Upcoming / Past / Cancelled tabs with real rows (customer name, venue and court, date and time, code, amount, status), paging, pull to refresh. Unpaid holds are not listed |
| 9 | Booking Details | `/bookings/:id` | **Step 6:** real details and status history. Read-only: no status actions (owner cancellation N22 undecided) |
| 9b | Courts & blocked times | `/venues/:id/courts` | **Step 6:** add/edit/deactivate/delete courts with slot length and price per slot; block a court or the whole venue for a period; shows `SCHEDULE_CONFLICT` refusals |
| 10 | Payments & Earnings | `/earnings` | Layout + payout link; no figures until Step 7 |
| 11 | Analytics | `/analytics` | Date filter works; venue performance real; the rest unavailable |
| 12 | Reviews | `/reviews` | "No reviews yet"; no reviews feature exists. Replies not offered |
| 13 | Notifications | `/notifications` | Real list, group filter, read / unread, mark all read |
| 14 | Profile & Settings | `/profile` + sub-pages | Profile + photo, business info (real), bank/payout (disabled UI foundation), notification preferences (device-local), help, terms (placeholders), log out |

Bottom navigation: Dashboard, Venues, Bookings, Earnings, Profile. Analytics, Reviews and Notifications are reached from Profile / the dashboard bell.

## Venue form

Required: **name** only (a draft can be saved early). Optional: description, sports (categories), city, address, postal code, latitude + longitude (both or neither), starting price per hour (whole rupees, stored as paise), contact phone (E.164), facilities/amenities. "State" is shown from the chosen city; there is no separate state column (D-50). Photos need a saved venue, so a new venue is saved as a draft first. Photos: JPG/PNG/WebP, up to 5 MB and 10 per venue (checked in the app for quick feedback and again on the server by file content). Publishing needs city + coordinates + at least one sport, and listings go live without admin approval because Q4 is unanswered.

## Honest empty states

Wherever data does not exist yet, the app shows what it is waiting for (for example "Step 6 (availability and booking engine)") instead of zeros, sample rows or invented rules. Nothing in the app is hard-coded business data.

## Payments & Earnings (Step 7)

Real, confirmed data only: gross amount customers paid, number of paid bookings, per-venue gross, and the payment list. Everything that needs unapproved rules (platform fees, commission, GST, net earnings, settlement timing, payout status) is one card that says "Not available yet". Push notifications are registered after sign-in; tapping one opens the booking.

## Security

- Only the Owner role gets past the shared route guard; the API repeats the check on every call (customers get 403).
- The app holds only the public Supabase anon key. Venue photos are uploaded **to the API**, which writes them with the service-role key on the server.
- Ownership is enforced on the backend: another owner's venue, image or notification is a 404. The app never sends an owner id.
- The profile picture goes to the private `profile-images` bucket in the user's own folder (as in the Customer app). Bank details are not collected, sent or stored at all (D-57).
- Expired sessions are handled by the shared auth layer (sign-out with a notice). Network errors show a retry.
