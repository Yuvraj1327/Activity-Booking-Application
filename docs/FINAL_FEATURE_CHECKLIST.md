# Final feature checklist

Legend — **Backend**: pytest against real Postgres with fake gateways. **UI**: Playwright against the real API + Postgres (Supabase Auth mocked). **Flutter**: code written and syntax-checked only; **never compiled, analyzed or run** (no Flutter SDK was obtainable). **Live**: needs credentials nobody has supplied here, so no real call was made.
✅ done and verified at the level named · 🟡 done, verification incomplete (reason given) · ⛔ intentionally not built, waiting for a business answer.

## Customer app

| Feature | Status | Verified by |
|---|---|---|
| Splash, onboarding (5 pages, shown once) | 🟡 | Flutter (not run) |
| Register, login, logout, password reset, session restore, role guard | 🟡 | Backend (profile + roles); Supabase Auth live ✗; Flutter not run |
| Profile view/edit, avatar upload | 🟡 | Backend; Flutter not run; Storage live ✗ |
| Home (categories, nearby, popular) from API | 🟡 | Backend; Flutter not run |
| Discovery: search, category, city, price, rating, sort, **available today**, pagination | ✅ API / 🟡 UI | Backend; Flutter not run |
| Venue details: gallery, amenities, price, rating, **reviews list**, **Directions** | ✅ API / 🟡 UI | Backend; Flutter not run |
| Location: device location, city selection, distance sort | 🟡 | Backend; Flutter not run; Geolocator on device ✗ |
| Date/time selection with live slot availability | ✅ API / 🟡 UI | Backend (availability logic, concurrency) |
| Booking creation, server price quote, hold, idempotency, no double booking | ✅ | Backend incl. concurrency tests |
| Razorpay checkout → server signature verification → confirmed | ✅ server / 🟡 app | Backend with fake gateway; Razorpay test mode ✗; Flutter SDK not run |
| Booking history, details, status timeline | ✅ API / 🟡 UI | Backend |
| Cancel an unpaid hold | ✅ | Backend |
| Cancel a paid booking / refund | ⛔ | Q9 — refused with a clear message |
| Favorites | ✅ API / 🟡 UI | Backend |
| Reviews: rate and review a completed booking (once per booking; no edit or delete, Q15/N14 default) | ✅ API / 🟡 UI | Backend (`test_reviews.py`) |
| Notifications list, mark read, push registration | ✅ API / 🟡 UI | Backend; FCM live ✗ |
| Loading / empty / error states | 🟡 | Flutter widget tests written, not run |

## Owner app

| Feature | Status | Verified by |
|---|---|---|
| Registration, login, business profile | ✅ API / 🟡 UI | Backend; Supabase live ✗ |
| Dashboard (real counts; revenue/utilization labelled unavailable) | ✅ API / 🟡 UI | Backend |
| Venue create/edit, categories, amenities, pricing, contact | ✅ API / 🟡 UI | Backend |
| **Address search → address, postal code, coordinates** | ✅ API (fake Google) / 🟡 UI | Backend `test_places.py`; Google live ✗ |
| Image upload, cover, delete | ✅ API / 🟡 UI | Backend with fake storage; Supabase Storage live ✗ |
| Courts, weekly hours, special dates, availability/blocks | ✅ API / 🟡 UI | Backend (conflict protection for existing bookings) |
| Publish / unpublish (completeness rules) | ✅ API / 🟡 UI | Backend |
| Incoming bookings, details, customer info | ✅ API / 🟡 UI | Backend |
| Approve/reject, manual status change | ⛔ | Q4/C1 — bookings confirm by verified payment; no owner workflow invented |
| Earnings / payment history (gross only) | ✅ API / 🟡 UI | Backend; net/payout ⛔ Q7–Q10 |
| Analytics (bookings; revenue metrics labelled unavailable) | ✅ API / 🟡 UI | Backend |
| **Reviews list, rating summary, filter, one reply per review** | ✅ API / 🟡 UI | Backend |
| Notifications; **server-backed push/e-mail switches** | ✅ API / 🟡 UI | Backend |
| Settings, payout info card, logout | 🟡 | Flutter not run |
| Owners see only their own records | ✅ | Backend isolation tests + RLS tests |

## Admin web

| Feature | Status | Verified by |
|---|---|---|
| Login, MFA, protected routes, unauthorized page | ✅ UI (auth mocked) | Playwright; real Supabase login ✗ |
| Dashboard KPIs (from real records) | ✅ | Backend + Playwright |
| Customers, owners: list, filters, detail, suspend/reactivate | ✅ | Backend + Playwright |
| Venues: monitor, detail, status (no create/edit — by design) | ✅ | Backend + Playwright |
| Bookings, payments: list, filters, detail, gateway events | ✅ | Backend + Playwright |
| Analytics (bookings, transactions, platform) | ✅ | Backend + Playwright |
| Platform revenue, owner earnings, refunds | ⛔ | Q7–Q10 — shown as "Not available" |
| Search, filter, sort, pagination | ✅ | Backend + Playwright |
| Notifications | ✅ | Playwright |
| CSV exports (privacy, formula-injection guard, row cap) | ✅ | Backend + Playwright |
| Audit log | ✅ | Backend + Playwright |
| Permission management UI | ⛔ | Roles are fixed (customer / owner / admin); admins are created by operator script (D-24). Matrix: `ADMIN_PERMISSION_MATRIX.md` |
| Admin reference screenshots | n/a | None were supplied (`docs/screenshots` holds captures *of* the admin); layout follows the approved ZURUV design language |
| Responsive (desktop, tablet), loading/empty/error | ✅ | Playwright |

## Backend, database and integrations

| Area | Status | Verified by |
|---|---|---|
| Endpoints, validation, standard error envelope, RBAC, JWT (JWKS/HS256) | ✅ | 346 pytest |
| Alembic 0001–0009, RLS on all application tables, grants revoked from `anon`/`authenticated` | ✅ | `test_migrations`, `test_rls` |
| Availability, pricing, double-booking prevention (DB constraint) | ✅ | Concurrency tests |
| Payments, webhook idempotency, reconciliation | ✅ with fake gateway | Backend; Razorpay live ✗ |
| Notifications + e-mail outbox with retry | ✅ with fakes | Backend; FCM/Resend live ✗ |
| Rate limiting | ✅ | Backend |
| Secrets: none in Flutter/Next bundles | ✅ | `scripts/scan_secrets.py` (source + built admin bundle) |
| Supabase Auth / Storage / Postgres (hosted) | ✗ not run | Needs your project |
| Razorpay test mode, FCM, Resend, Google Places | ✗ not run | Need your credentials |
