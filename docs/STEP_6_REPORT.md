# Step 6 report: Availability and Booking Engine

Date: 2026-11-12. Scope followed: the Step 6 brief. Step 7 (Razorpay, payment confirmation, refunds) was **not** started.

## 0. What is and is not verified

| Area | Verified how | Result |
|---|---|---|
| Backend (slot engine, availability, bookings, cancellation, owner courts/blocks, schedule policy, admin view, dashboard counts) | 40 new tests + the 175 earlier ones, local PostgreSQL 16 + Supabase stub | **215 passed**; `ruff check` and `ruff format --check` clean; `mypy app` clean (60 files) |
| Concurrency | 6 tests with real threads, separate app instances and separate DB pools, run 8 times in a row | Passed every time |
| Migration `0006` | Existing up / down-to-base / up test, ORM-vs-schema comparison, RLS tests extended to the 4 new tables | Passed |
| Flutter apps | **Syntax only** (a Dart parser accepted all 29 new or changed files). No Flutter SDK here | `flutter analyze` **not run**; Flutter tests **not run** (23 test cases in the two new files — 16 Customer, 7 Owner — plus additions to existing test files); apps **never compiled or launched**; **no screenshots** |
| Supabase (real Auth, Storage, RLS with real roles) | Not available | Not tested. RLS is tested against local Postgres roles only |
| Payments | Not part of this step | Nothing is paid; no booking can reach `confirmed` through a payment |

Expect small compile or analyzer fixes on the first real `flutter analyze` and `flutter test`. Please run them before accepting Step 6.

## 1. Availability engine status: done (backend)

Weekly hours, special dates (closure or custom hours replace the weekly hours), owner blocks, existing reservations (stale holds ignored), per-court slot length and price, venue time zone with DST-safe conversion. Returns only free slots, with a state per court. `AVAILABILITY_LOGIC.md`.

## 2. Slot generation status: done

One pure, reusable module (`app/domain/slot_engine.py`, 11 database-free tests). Slots start at opening and repeat every `slot_minutes`; nothing crosses closing; the unused remainder is dropped; ambiguous or non-existent DST times are skipped; started slots are never offered. A booking request must equal a generated slot exactly. Nothing is computed in Flutter.

## 3. Booking database implementation: done

Migration `0006`: `bookings`, `booking_slots`, `booking_status_history`, `availability_blocks`, plus `venue_resources.slot_minutes/slot_price_paise`. Unique booking code and idempotency key, price snapshot, status/payment CHECKs, history append-only trigger, RLS (select only), indexes for customer/venue/court/status/holds and a GiST index for slots. `BOOKING_ENGINE.md` has the relationship diagram. The `bookings` row carries every field the brief lists (id, customer, venue, resource, date, start, end, duration, base and total amount, payment status, booking status, created time).

## 4. Double-booking prevention: four layers

In-transaction revalidation, a PostgreSQL **exclusion constraint** on `(resource_id, slot_range) WHERE is_blocking`, `FOR SHARE` / `FOR UPDATE` venue-row locks between customer bookings and owner schedule edits, and idempotency keys. Conflicts are `409 SLOT_UNAVAILABLE` (the constraint's error is translated), and the transaction rolls back cleanly. A raw SQL insert that bypasses the service is also refused. Full strategy: `BOOKING_ENGINE.md`.

## 5. APIs

Customer: availability, available dates, quote, create, list, detail, cancellation preview, cancel. Owner: bookings list/detail, courts CRUD, blocks, schedules (with conflict check), dashboard counts. Admin: bookings list/detail. All validate input, require a JWT and the right role, and answer another user's records with `404`. Catalogue and examples: `API_DOCUMENTATION.md`. Deviations: no `/slots` alias; schedules stay `PUT` with replace semantics (no separate `POST/PATCH special-schedules`); extra `quote` and `cancellation-preview` endpoints.

## 6. Customer app integration (written, not run)

Venue details "Book Now" → date strip (14 days) → courts and slot chips straight from the API → review sheet that **re-checks the slot with the server and shows the server price** → confirm with an `Idempotency-Key` (reused for retries of the same slot, so a double tap or a flaky network cannot create two bookings) → booking details. States handled: loading, available, unavailable/closed/not configured, conflict (selection cleared, availability reloaded, message), offline (sheet stays, retry), server rejection, success. My Bookings: Upcoming / Past / Cancelled with paging and refresh (reloads after create or cancel); details with history; cancel asks the server first and shows the server's reason when it is not allowed. The text on the review sheet and details says plainly that payment is not available yet.

## 7. Owner app integration (written, not run)

Courts screen (add/edit/deactivate/delete, slot length, price in rupees sent as paise, blocked times for a court or the whole venue), hours screen shows the real `slot_configuration` and shows `SCHEDULE_CONFLICT` refusals with the affected booking codes, bookings list/details (read-only, customer name only, history), dashboard total and overview counts. Revenue and utilization remain "not available yet".

## 8. Status transitions

`pending_payment → confirmed | payment_failed | expired | cancelled_by_customer`, `payment_failed → pending_payment | expired | cancelled_by_customer`, `confirmed → cancelled_by_customer | cancelled_by_owner | completed`, cancellations → `refund_pending → refunded`. Only the customer may cancel their own booking; owners and admins cannot change a status; only `system` may confirm, expire, complete or refund. One function applies every change and writes history. Diagram and rules: `BOOKING_STATUS_FLOW.md`.

## 9. Automated test results

| Suite | Count | Covers |
|---|---|---|
| `test_slot_engine.py` | 11 | normal hours, remainders, split hours, closed days, special hours and closures, overlap vs adjacent, started slots, notice/advance rules, DST, pricing, status rules |
| `test_booking_api.py` | 23 | availability (free slots only, closed weekday, special hours, holiday closure, not-configured court, invalid dates, unknown/unpublished venue, date range), create (snapshot, history, server price), invalid slots, conflicts, owner block, multiple courts, instant mode, not-configured settings, idempotency, hold expiry, IDOR and role checks, owner/admin views, cancellation (hold, notice rule, unset rule, paid, completed), append-only history, schedule-conflict policy, court/venue delete guards, court validation |
| `test_booking_concurrency.py` | 6 | see section 10 |
| Earlier suites | 175 | unchanged except two Step 5 assertions that now expect real booking data |

## 10. Concurrency test results

10 customers book one slot at the same instant → exactly 1 × `201`, 9 × `409 SLOT_UNAVAILABLE`, 1 booking row, 1 blocking slot. 6 simultaneous retries with one `Idempotency-Key` → 1 booking, all answers return it. 8 customers on 8 different slots → 8 × `201`. Two courts at the same time → both succeed. A booking racing an owner closing that day (4 rounds) → never both. A raw insert overlapping a blocking slot → rejected by `ex_booking_slots_no_overlap`; a non-blocking overlap and a back-to-back slot are accepted. Run 8 times in a row without a failure. (An early run of the idempotency test did fail, which exposed a real bug: a loser of the race saw the winner's slot as taken and returned a conflict instead of the replay. Fixed, covered by that test.)

## 11. Remaining business decisions (nothing below was invented)

| Decision | Open question | What the code does meanwhile |
|---|---|---|
| Venue vs court vs multiple resources; what is booked | Q1, Q2, Q17, N2, N23 | Courts with owner-set slot length and price; one slot per booking; no capacity bookings |
| Court choice by customer or auto-assignment | N3 | Customer picks the court |
| Variable durations / multi-slot | N2 | Not offered; database allows several slots per booking |
| Hold duration | N4 | `BOOKING_HOLD_MINUTES` has no default; hold mode answers `503` until set |
| Booking window (notice, advance) | N6 | Optional settings, off by default |
| Fees, GST, commission, discounts, coupons | Q7, Q8, N7 | All 0 and not calculated |
| Customer cancellation window, charges, refunds | Q9, Q10 | Window setting off by default; paid bookings cannot be cancelled; no charge calculated |
| Owner cancellation or rejection of a booking | N22 | Owners cannot change statuses |
| Admin powers over bookings | Q18 | Read-only |
| Booking statuses and codes | Q11 | Proposal in `BOOKING_STATUS_FLOW.md` |
| What happens to bookings when the schedule changes | Q16 | Refuse the change and list the bookings (architecture default) |
| Customer contact visible to owners | N9 | Name only |
| Utilization definition | N8 | Not calculated |
| Customer "Today" filter on discovery | (roadmap) | Not built; needs a venue-list availability query |

## 12. Decisions made in this step

| # | Decision | Why |
|---|---|---|
| D-59 | Slot length and price live on `venue_resources` (NULL = not configured). A court without both cannot be booked. | Smallest model consistent with the architecture; no invented defaults; the owner supplies the real numbers |
| D-60 | Owners do not see unpaid holds (`pending_payment`, `payment_failed`) in lists or counts; they appear once confirmed | A hold may expire in minutes; showing it would create noise and false revenue expectations. Easy to reverse |
| D-61 | Slots are generated on demand and never stored | Architecture §9; avoids a stale table |
| D-62 | Expired holds and finished bookings are settled lazily on read, and queries ignore stale holds | No background worker exists yet; correctness does not depend on one |
| D-63 | Unknown or foreign booking ids return 404, never 403 | No existence leak |
| D-64 | Schedule changes that would invalidate a future booking are refused as a whole (rollback), never auto-cancelling | Architecture default for Q16; no customer is surprised |
| D-65 | A venue or court with booking records cannot be deleted (409); deactivate or unpublish instead | Supersedes D-56 now that bookings exist |
| D-66 | `instant` booking mode exists for testing and venues without online payment; it never sets `payment_status` to paid | Needed to test confirmed-booking rules before Step 7 without faking a payment |
| D-67 | Idempotency key is optional but recommended; the apps always send one | Keeps direct API use simple; protects the app |
| D-68 | The Owner app sends block times in the device time zone | The venue-time-zone picker is not built; correct whenever the owner is in the venue's zone |

## 13. Known limitations

- Flutter not compiled or run (section 0). The Owner app's `DropdownButtonFormField(value:)` may print a deprecation hint on the newest Flutter.
- Availability for a date is one request per date; the date strip does not grey out fully booked days (the endpoint `/availability/dates` exists but the strip does not call it yet).
- Hold expiry and completion are lazy (no scheduled job, no expiry notification to the customer).
- Customer notifications for bookings are not built (only owner in-app notifications); push is Step 7.
- The Customer "Today" filter, favourites-by-availability and owner utilization analytics are not built.
- `price_snapshot` carries only the slot price.

## 14. Commands

Backend, from `backend/`:

```bash
scripts/dev_pg.sh start                      # or: docker compose up -d db   (from the repo root)
source .venv/bin/activate
export TEST_DATABASE_URL=postgresql://zt@127.0.0.1:54399/postgres
ruff format --check app tests scripts && ruff check app tests scripts && mypy app
pytest -q                                    # 215 tests
pytest tests/test_slot_engine.py tests/test_booking_api.py tests/test_booking_concurrency.py -q   # Step 6 only
alembic upgrade head                         # applies 0006 to your DATABASE_URL
alembic downgrade 0005                       # reverts it
```

Booking settings (all empty by default; see `ENVIRONMENT_VARIABLES.md`): `BOOKING_MODE`, `BOOKING_HOLD_MINUTES`, `CANCELLATION_MIN_NOTICE_HOURS`, `BOOKING_MIN_NOTICE_MINUTES`, `BOOKING_MAX_ADVANCE_DAYS`. For a first manual try set `BOOKING_HOLD_MINUTES=10`.

Apps (needs the Flutter SDK, not available here):

```bash
cd apps/customer_app && flutter pub get && flutter analyze && flutter test
cd apps/owner_app    && flutter pub get && flutter analyze && flutter test
```

Manual flow: sign in as an owner → open a venue → Courts & blocked times → add a court (60 min, ₹500) → Manage slots & hours → set weekly hours → publish; sign in as a customer → open the venue → Book Now.

## 15. Next step (not started)

Step 7 — Payments and notifications: Razorpay order/verify/webhook moving bookings `pending_payment → confirmed` as actor `system`, `payment_failed`, refunds, the paid-booking cancellation rule, push notifications. It needs the open answers marked Q7–Q10 and your explicit approval.
