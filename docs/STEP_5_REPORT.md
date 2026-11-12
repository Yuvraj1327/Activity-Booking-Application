# Step 5 report: Venue Owner app (UI and venue management)

Date: 2026-11-12. Scope followed: the Step 5 brief. Step 6 (booking engine) and Step 7 (Razorpay) were **not** started.

## 0. What is and is not verified

| Area | Verified how | Result |
|---|---|---|
| Backend (owner venues, images, schedules, dashboard, notifications, isolation) | 13 new tests + the 162 earlier ones, on local PostgreSQL 16 with a Supabase stub | **175 passed**; `ruff check` clean; `mypy app` clean (48 files) |
| Migration `0005` | Existing up / down-to-base / up test, ORM-vs-schema comparison | Passed |
| Flutter app | **Nothing.** No Flutter SDK in this environment | `flutter analyze` **not run**; Flutter tests (42, written) **not run**; app **never compiled or launched**; **no screenshots** |
| Supabase Storage uploads | Backend tested with a fake storage gateway | **Not tested against real Storage** |
| Real sign-in, Google/Apple/phone | Not available (no Supabase project) | Not tested |

Expect small compile or analyzer fixes on the first real `flutter analyze`. Please run it before accepting Step 5.

## 1. Screens implemented (14 of 14, in code)

Splash, Onboarding, Auth (shared package), Dashboard, My Venues, Add/Edit Venue, Manage Slots, Incoming Bookings, Booking Details, Payments & Earnings, Analytics, Reviews, Notifications, Profile & Settings (business info, bank/payout, notification preferences, help, terms, log out). Details and routes: `OWNER_APP.md`. Screens 8–12 are real screens in their layout but show an honest "not available yet" state, because their data comes from Steps 6/7 or from a reviews feature that does not exist.

## 2. Venue management

Create draft, edit, list with search and status filter and paging, publish, take offline, delete (with confirmation), multiple venues per owner, categories (sports), amenities, city, address, postal code, coordinates, contact phone, starting price. Publish requires city + coordinates + one sport, and the API lists what is missing. A published venue cannot be edited into an invalid state.

## 3. API integrations

See `OWNER_API_INTEGRATION.md`. Real: owners/me, venues CRUD, publish/unpublish, images, schedules, dashboard (venue data), analytics (venue performance), notifications. Honest "pending": bookings, booking details, earnings, reviews.

## 4. Image upload

Owner picks a photo (`image_picker`) → the app checks type and size → multipart upload to the API → the API checks the **file bytes** (JPEG/PNG/WebP), 5 MiB, 10 per venue → writes to the public-read `venue-images` bucket with the service-role key (server only) → inserts `venue_images`. First photo is the cover; cover change, reorder and delete are supported; deleting the cover promotes the next photo; deleting a venue removes its files best-effort. Tested with a fake storage gateway including rejection of GIF/text/oversized/11th image. **Not tested with real Supabase Storage.**

## 5. Schedule configuration

Weekly hours (per weekday, up to 5 ranges) and special dates (closure or custom hours, with note) are stored in new tables `schedule_rules` and `schedule_exceptions` (migration `0005`) and edited in Manage Slots. Slot length, courts/resources and pricing rules are **not** configured: they depend on open questions Q1, Q2, Q17, N2 and N23 and belong to Step 6. The API reports `slot_configuration: not_configured` and the screen says so.

## 6. Dashboard data

Real: venue totals/published/draft, review-count-weighted average rating, per-venue performance, recent notifications. Unavailable (labelled, never zero): total bookings, revenue, monthly revenue, booking overview, utilization.

## 7. Security verification (tested on the backend)

- Anonymous → 401; customer, admin and suspended owner → 403 on every owner route.
- Owner B cannot read, edit, delete, publish, unpublish, upload to, reorder images of, or read/replace the schedule of owner A's venue: all return the same 404 as a missing venue. Notifications likewise.
- Uploaded files are validated by content; the service-role key is only read by the backend; no client can write to `venue-images`.
- Owner id is never sent by the client. Bank details are not collected, sent or stored.
- Flutter side: shared route guard (only the Owner role enters), 401 handling in the auth layer; **not run**.

## 8. Decisions

| ID | Decision |
|---|---|
| D-50 | "State" is read from the selected city; there is no state column on venues. |
| D-51 | Photos are uploaded **through the API as multipart**, not via signed upload + finalize, because the bucket is backend-write-only. Limits: 5 MiB, 10 photos, jpeg/png/webp by content. |
| D-52 | Owner routes are `/owners/...` as the brief says; hours are `GET/PUT /owners/venues/{id}/schedules`. |
| D-53 | Schedules store **opening hours only** (local venue time). No slots, courts or prices until Step 6. |
| D-54 | Publishing needs city + coordinates + one sport and has **no admin approval** (Q4 unanswered). Easy to insert an approval status later. |
| D-55 | Data that does not exist yet is returned as `available:false` + `depends_on` + message and shown as such; no zeros, samples or invented rules. |
| D-56 | Deleting a venue is a hard delete (cascades images/links/hours) after confirmation; bookings do not exist yet, so Step 6 must revisit (archive instead of delete once bookings reference venues). |
| D-57 | Bank/payout screen is a disabled UI foundation: nothing is collected or stored until storage, encryption and payout rules are approved (N11, Q10). |
| D-58 | Notification preferences are device-local; Help and Terms are placeholders without invented contact details or legal text; the splash uses drawn court lines because no licensed photography was supplied. |

## 9. Remaining dependencies and open items

- Run `flutter analyze` and `flutter test` (first run on a real SDK), take screenshots of the major screens (none exist).
- Supabase project + Storage credentials to test photo upload and real sign-in; add `io.zuruv.owner://login-callback` to the redirect allow-list.
- Step 6: bookings, slots/courts/pricing (Q1, Q2, Q17, N2, N23), booking list rows and details, utilization and booking analytics; revisit venue deletion (D-56).
- Step 7: payments, earnings, payouts (N11, Q10, commission/refund rules), push notifications.
- Reviews feature and owner replies (not designed).
- Support contact and legal texts for Help/Terms; licensed photography for splash/onboarding; admin approval flow (Q4).
- Earlier open gate questions (Q1/Q2/Q17/N2/N23, Q4, Q16, Q18, N10, N17, N24, N1, N13) are still unresolved.

## 10. Run the Owner app

```bash
./scripts/bootstrap_flutter.sh
cd apps/owner_app && cp env/dev.example.json env/dev.json   # public values only
flutter run --dart-define-from-file=env/dev.json
```
Backend (for the app to talk to): `cd backend && source .venv/bin/activate && alembic upgrade head && python -m scripts.seed_reference_data && uvicorn app.main:app --port 8008` with `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET` (or JWKS) and `SUPABASE_SERVICE_ROLE_KEY` set.
