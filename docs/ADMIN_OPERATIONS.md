# Admin operations (Stage 8b)

This document describes the administrator features added on top of the Step 8 console: roles and permissions,
venue approval, owner KYC, refunds, finance, payouts, disputes, support, coupons, CMS, monitoring and a stronger
audit trail. Everything is connected to the real API and database; nothing is mocked.

Source of truth: `backend/alembic/versions/0011_admin_operations.py` (mirrored in
`supabase/migrations/012_admin_operations.sql`, kept identical by `supabase/verify_sync.sh`).

## 1. What is switched OFF until the client decides

Each unresolved business decision is a **configuration row that defaults to the safe value**. Nothing irreversible
or money-moving can happen until a person with the right permission turns it on, with a recorded reason.

| Switch (Platform switches page) | Default | Blocks | Decision needed from the client |
|---|---|---|---|
| `venue_approval_required` | off | Owners publish immediately (as before). When on, publishing sends the venue to the approval queue and an owner cannot bypass it. | **Q4** – is publishing immediate, or approved by an admin? |
| `refunds_enabled` | off | Every real refund. The refund button is disabled and the API answers `REFUNDS_DISABLED`. | **Q9** – cancellation and refund policy (windows, percentages, who may cancel, gateway-fee treatment). |
| `payouts_enabled` | off | Creating, approving and recording payouts (`PAYOUTS_DISABLED`). | **Q10** – how and when owners are paid; and which payout product is used. |
| `payout_requires_kyc` | **on** | A payout to an owner whose KYC is not verified. | **N11** – which documents are required before payouts. |
| Finance configuration (fee, tax, commission) | none approved | Fees and tax on bookings, commission, owner earnings, platform revenue. With none approved they stay 0 / "Not available". | **Q7** fee and tax rules (rates, base, rounding, invoicing) and **Q8** commission / revenue model. |

Other open items and what the software does meanwhile:

* **Q18** (what suspension does to existing bookings): suspending an account or venue never cancels or refunds
  anything. The venue page shows how many upcoming confirmed bookings are affected so an admin decides case by case.
* **N11** (KYC): the system records, reviews and verifies whatever documents an owner uploads (identity, address,
  business registration, GST, bank account, other). It does **not** decide which are mandatory.
* **N22** (owner cancellation): unchanged. Owners still cannot cancel bookings.

### Rules the finance configuration forces (so nothing is guessed)
* A configuration is created as a **draft**, approved by a **different administrator** (four-eyes), and is then
  **immutable** (database trigger). To change a rate, approve a new version; the old one is retired, never edited.
* Money is integer paise; rounding is half-up in one function (`app/domain/finance_math.py`).
* Tax base (`fee` or `base_and_fee`), who bears coupon discounts (`platform` or `owner`) are explicit fields with
  **no default**: someone has to choose them. The accountant should confirm both (part of Q7).
* A payment is split by the configuration in force **when it was captured**; later changes never re-price it.
* The ledger is append-only. A refund adds a negative entry using cumulative proportional reversal, so repeated
  partial refunds add up to exactly the original sale with no rounding drift.

## 2. Credentials and gateway configuration that are still needed

* **Razorpay** keys and webhook secret (test, then live). Test and live are kept apart: the key prefix
  (`rzp_test_` / `rzp_live_`) must match the environment (`production` needs live keys, everything else test keys),
  otherwise refunds are refused with `GATEWAY_MODE_MISMATCH`. The Monitoring page shows the mode and any mismatch.
* **Refund API**: implemented against Razorpay's `POST /payments/{id}/refund` with `X-Refund-Idempotency` and a
  receipt equal to our refund id. It has only been tested against a fake; it needs a test-mode run (see section 6).
* **Payouts**: automatic payouts are **not integrated**. The current integration has Orders, Payments, capture,
  refunds and payment listing only. Whether RazorpayX or Route is enabled on the account is **unverified** and
  nothing assumes it. Payout records are tracked and marked paid after your team makes the transfer, with the
  bank/UPI reference.
* **Supabase Storage**: the private bucket `kyc-documents` is created by the migration (no public access, no client
  policies). The backend needs `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (already required for venue images).
* **Existing admins** are migrated to the built-in `super_admin` role so nothing changes for them. **New admins have
  no role** until a `roles.manage` administrator assigns one. The first admin: `python -m scripts.create_admin
  --email … --name … --role super_admin`.

## 3. Modules and where they live

| Module | Admin pages | API (under `/api/v1/admin`) | Tables |
|---|---|---|---|
| Dashboard & analytics | `/dashboard`, `/analytics` (tabs: bookings, transactions, platform, sports, cities, venues) | `/dashboard`, `/analytics/{bookings,revenue,platform,sports,cities,venues}`, `/exports/analytics.csv` | – |
| Customers & owners | `/customers/[id]`, `/owners/[id]`, `/kyc` | `/owners/{id}/history`, `/owners/{id}/payouts`, `/owners/{id}/kyc`, `/kyc/*`, `/customers/{id}/history` | `owner_profiles.kyc_*`, `owner_kyc_documents` |
| Venues | `/venues`, `/venues/[id]`, `/venue-reports` | `/venues/{id}/{approve,reject,suspend,reinstate,verify,unverify,history}`, `/venue-reports` | `venues` (+status, verification), `venue_moderation_events`, `venue_reports` |
| Bookings | `/bookings`, `/bookings/[id]` | `/bookings` (+sport, city, owner, venue, refund filters), `/bookings/{id}/cancel` | `bookings` (+`cancelled_by_admin`) |
| Disputes | `/disputes` | `/disputes`, `/disputes/{id}/{events,resolve}` | `disputes`, `dispute_events` |
| Payments & refunds | `/payments`, `/payments/[id]`, `/refunds` | `/payments/{id}/refunds`, `/refunds`, `/refunds/{id}/reconcile`, `/exports/refunds.csv` | `refunds` |
| Finance | `/finance`, `/finance/configs`, `/finance/ledger`, `/payouts`, `/finance/reconciliation` | `/finance/*`, `/payouts*`, `/exports/{ledger,payouts}.csv` | `finance_configs`, `ledger_entries`, `payouts`, `reconciliation_*` |
| Support | `/support` | `/support/tickets*` (+ customer `GET /support/tickets/{id}/messages`) | `support_tickets`, `support_ticket_messages` |
| Sports | `/categories` | `/categories*` | `categories` |
| Coupons | `/coupons` | `/coupons*`; customers pass `coupon_code` to `POST /bookings/quote` and `POST /bookings` | `coupons`, `coupon_redemptions` |
| CMS | `/cms` | `/cms*`; public `GET /content`, `GET /content/{slug}` | `cms_contents` |
| Roles | `/roles`, `/platform` | `/roles*`, `/admins/{id}/role`, `/permissions`, `/settings*` | `admin_roles`, `admin_profiles`, `platform_settings` |
| Monitoring | `/monitoring` | `/monitoring` | – |
| Audit | `/audit` | `/audit-logs` (+actor, entity, record id, date filters), `/audit-actions` | `audit_logs` |

### Behaviour worth knowing
* **Venue approval.** With the workflow on, `POST /owners/venues/{id}/publish` returns `status: pending_review`.
  Owners cannot publish a suspended venue, cannot unpublish one, and cannot send a status in a PATCH (rejected 422).
  Existing published venues stay published when the workflow is switched on. Edits to an already-approved venue do
  not trigger re-review (a policy choice the client may want to revisit).
* **Admin cancellation** uses the booking state machine (`cancelled_by_admin`). It never touches money: a paid
  booking stays paid until a separate, audited refund is made. A full refund requires the booking to be cancelled
  first, so booking and payment cannot drift apart. Booking list filter `refund_status=awaiting` finds cancelled,
  paid bookings with no refund decision yet.
* **Refunds** commit a `requested` row *before* calling Razorpay, use the row id as receipt and idempotency key,
  and mark a timeout/5xx `uncertain` (the balance stays locked until **Check with Razorpay** settles it, which
  re-sends with the same idempotency key if the gateway has no record). Duplicate and out-of-order webhooks are
  harmless; refunds made in the Razorpay dashboard are mirrored with `source = gateway`.
* **Sports analytics** split each booking equally across a venue's sports, so shares add up to the real total
  (`tagged_bookings` shows the unsplit count). Bookings at venues with no sport appear separately.
* **Coupons** are validated twice on the server (quote, then booking creation under a row lock). A discount can
  never take a booking below ₹1 (Razorpay's minimum). A redemption stops counting when its booking expires or is
  cancelled unpaid.
* **KYC documents** are PDF/JPEG/PNG up to 5 MB, type-checked from the file bytes, stored privately, viewed only
  through the API (never a public URL), and every view is audited.
* **CMS** pages the apps already look for: `terms-customer`, `terms-owner`, `privacy` and published FAQs
  (`kind = faq`). Until something is published, the apps keep their built-in text.

## 4. Permissions

Defined once in `backend/app/core/permissions.py` and enforced by `require_permission` on every admin route; the
web console hides what a role cannot use, but the API is the authority. `super_admin` always holds every permission.
Nobody can grant a permission they do not hold, change their own role, edit the built-in role, or demote the last
super_admin. `backend/tests/test_admin_authorization_sweep.py` discovers every `/admin` route from the OpenAPI
document and proves it is closed to anonymous callers, customers, owners, admins without MFA, admins with no role
and admins holding only `dashboard.view`; a new route that forgets its permission fails that test.

## 5. Audit

Every sensitive mutation writes `audit_logs` with actor, action, entity type and id, `before`, `after`, `reason`
(mandatory where it matters) and the request id. The table is append-only at the database level.

## 6. Not verified here (needs a human or an account)

* A real Razorpay **test-mode** refund, a real refund webhook, and the reconciliation call against Razorpay's
  `GET /payments` listing. Run the checklist in `docs/MANUAL_DEPLOYMENT_GUIDE.md` §6 with test keys, then refund a
  small test payment before ever enabling refunds in production.
* Supabase Storage with the real service-role key (KYC upload and view). Tests use an in-memory fake.
* The Flutter apps do not yet have screens for: owner KYC upload, reporting a venue, reading support replies, or
  entering a coupon code. The **backend endpoints exist and are tested** (`/owners/kyc*`, `POST /venues/{id}/report`,
  `GET /support/tickets/{id}/messages`, `coupon_code`); the apps already show the new venue/booking statuses and the
  CMS content.
* Real-device behaviour of the Flutter changes.
