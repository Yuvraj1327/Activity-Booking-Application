# Commission management

Admin-configurable platform commission: global, per activity (sport) and per venue, versioned, with an immutable snapshot on every booking and integration into the ledger, owner earnings, finance and reports.

Source of truth for the schema: Alembic `0012_commission_management.py`; hand-runnable copy `supabase/migrations/013_commission_management.sql` (checked by `supabase/verify_sync.sh`).

## 1. Priority (shown in the Admin Panel under Commission)

Exactly **one** rule applies to a booking. First match wins:

1. **Venue-specific** rule (active)
2. **Activity-specific** rule for the venue's sport (active)
3. **Global default** rule (active)

A deactivated rule, or one whose first version has not started yet, is skipped and the next scope is tried. If **no** rule applies, the percentage of the approved *finance configuration* (`finance_configs.commission_bps`) is used and the ledger entry says `commission_scope = finance_config`; that is exactly how commission worked before this feature.

The priority is a tuple in `app/domain/commission.py` (`DEFAULT_PRIORITY`) and `CommissionService.priority`. It must be a permutation of the three scopes, so it can be reordered without any overlap ambiguity (`validate_priority`). It is not exposed as an admin setting: changing how overlapping rules resolve is a financial decision and should be a reviewed code or configuration change.

**A venue with several sports.** A venue can list several categories and a booking has no sport of its own. When more than one of those sports has an active activity rule **with different percentages** (and the venue has no active venue rule), the system does **not** choose: the snapshot is stored with `ambiguous = true`, no rate, scope `none`; the ledger skips the booking (`blocked_ambiguous_commission` in the accrual result) and does not fall back to the global or finance-configuration percentage; the Rules page lists the affected venues. The client must pick a tie-break; it is then enabled with the environment setting `COMMISSION_ACTIVITY_TIEBREAK=lowest|highest` (unset = unresolved). Giving the venue its own venue rule also resolves it for new bookings. Existing ambiguous snapshots stay blocked (immutable).

## 2. Data model

| Table | Purpose | Mutability |
|---|---|---|
| `commission_rules` | Identity of a rule: `scope` global / activity / venue, `category_id` or `venue_id`. One per target (partial unique indexes), CHECK ties the target to the scope. | append-only (trigger) |
| `commission_rule_versions` | Every create / edit / activate / deactivate is a **new row**: `version`, `commission_bps` (0-10000), `previous_bps`, `is_active`, `effective_from`, `reason`, `created_by`, `created_at`. | append-only (trigger) |
| `booking_commission_snapshots` | The rate resolved for a booking: scope, rule id, rule version, percentage, activity, `effective_at`, the priority used, and every candidate rule considered. One row per booking (primary key). | append-only (trigger) |
| `ledger_entries` (extended) | New columns `commission_bps`, `commission_scope`, `commission_rule_id`, `commission_rule_version`, `commission_base_paise` (NULL on entries written before this feature). | append-only (existing trigger) |
| `finance_configs.commission_base` | `base` (slot price before discount, fee, tax: the previous behaviour) or `base_after_discount`. | immutable once approved |

A rule's state at time *T* is the version with the greatest `effective_from <= T` (ties: highest version). The end of a version (`effective_to`) is the start of the next one and is computed, so nothing is ever updated. Admin ids are `ON DELETE RESTRICT` so history keeps its author.

Rule changes cannot be back-dated (`EFFECTIVE_FROM_IN_PAST`; 90 s clock-skew tolerance, then clamped to now). That is what makes resolution at any past instant reproducible.

## 3. Calculation and immutability

* **When the rate is fixed:** at booking creation (`BookingService._create` calls `CommissionService.snapshot_for_new_booking` inside the booking transaction, in a savepoint so a failure can never block a booking). Idempotent booking retries and payment retries reuse the existing booking and therefore the same snapshot; `ON CONFLICT DO NOTHING` plus the primary key make a second snapshot impossible.
* **Bookings without a snapshot** (made before this feature, or if the snapshot step failed) get one at accrual time, resolved **as of the booking's creation time**, with `source = accrual_backfill`. Because rules cannot be back-dated this gives the same answer as at booking time.
* **When money is recorded:** the existing ledger accrual (`FinanceService.accrue`, run by the sweep and by `POST /admin/finance/accrue`) writes one `sale` entry per captured payment, using the snapshot's percentage. It still needs an **approved finance configuration**; without one nothing is written (Q7/Q8 gate unchanged).
* **Arithmetic:** integer paise only. `commission = round_half_up(commission_base × bps / 10000)`, owner net = court charge − commission − owner-borne discount (only when the approved configuration says discounts are owner-borne). Fee and tax are never part of the commission base.
* **No duplicates:** ledger `entry_key` is unique (`sale:<payment id>`); the database allows one payment per booking; accrual additionally refuses a second sale entry for the same booking. Replayed webhooks, re-run accrual and payment retries change nothing. Unpaid, failed, expired bookings never get a ledger entry.
* **Refunds:** each processed refund adds a negative `refund` entry that reverses commission, owner share and platform share **proportionally** (cumulative, no rounding drift). Reports net refunds out and never count a refund twice. The business policy for refunds (Q9) is still open; this is the technical mechanism only.
* **Historical safety:** editing, deactivating or replacing a rule inserts a version. Snapshots, ledger entries, payouts and reports of earlier bookings are not touched (database triggers refuse UPDATE and DELETE).

"Owner net payable" is an accounting figure from the internal ledger. It does **not** mean money was transferred. Payouts stay a separate, disabled-by-default flow (`payouts_enabled`, four-eyes approval, recorded after an out-of-band transfer); no payout integration was added.

## 4. API

All admin routes are under `/api/v1`. Reads need `commission.view`; changes need `commission.manage`; reports and exports need `finance.view` (+ `exports.download`). Customers and owners get 403. `commission.manage` is marked sensitive in the role editor. Every change writes an audit row (`admin.commission_rule_created`, `admin.commission_rule_changed`) with before, after and reason.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /admin/commission/rules?scope&active_only&q` | commission.view | Global rule, and activity/venue rules, each with the version in force and any scheduled change; priority |
| `GET /admin/commission/active` | commission.view | What applies now: global %, effective date, active overrides |
| `POST /admin/commission/rules` | commission.manage | Create the global / an activity / a venue rule (`scope`, `category_id` or `venue_id`, `commission_bps`, `is_active`, optional `effective_from`, `reason`) |
| `GET /admin/commission/rules/{id}` | commission.view | One rule with all versions |
| `POST /admin/commission/rules/{id}/versions` | commission.manage | Change %, activate or deactivate, optionally scheduled. Appends a version |
| `GET /admin/commission/history?scope&venue_id&category_id&from&to` | commission.view | Immutable history: previous %, new %, scope, target, effective start and end, admin, reason, timestamp |
| `GET /admin/commission/calculate?venue_id&base_paise&category_id&at` | commission.view | Read-only: which rule applies and the commission for an amount |
| `GET /admin/commission/bookings/{id}` | finance.view | Booking snapshot, ledger calculation, refunds net |
| `GET /admin/commission/report?from&to&venue_id&category_id&owner_id` | finance.view | Totals; by activity, venue, day, rule scope; reconciliation checks |
| `GET /admin/commission/owners/{owner_id}/earnings` | finance.view | An owner's booking-wise earnings as the owner sees them |
| `GET /admin/exports/commission.csv` | exports.download + finance.view | One row per ledger entry with percentage, rule, version (audited) |
| `GET /admin/finance/summary` | finance.view | Now also returns `commission` totals and `reconciled` |
| `GET /owners/earnings/breakdown` | owner | Booking-wise: customer paid, court charge, fee, tax, commission % and amount, other deductions, net payable, refunds, formula. `available:false` until a finance configuration is approved |
| `GET /owners/earnings/bookings/{id}` | owner | One booking's calculation (404 for another owner's booking) |
| `GET /owners/commission` | owner | Current rate per own venue and the rate history that applies to them (no admin names or reasons) |

`GET /owners/earnings` and every other owner endpoint are unchanged.

## 5. Reconciliation checks (`report.reconciliation`)

Each is a count of mismatches over the selected range; `ok` is true when none:

1. every ledger sale equals its captured payment amount
2. every ledger refund equals its processed refund
3. commission recomputes from `commission_base × bps` (half-up)
4. ledger commission matches the booking's snapshot (rate and rule)
5. at most one sale entry per booking
6. captured payments not yet in the ledger (informational: run accrual)

## 6. Admin Panel

Sidebar **Commission** (`commission.view`): *Rules* (priority explanation, global card with active % and effective date, activity table with create/change/activate/deactivate, venue search then set, scheduled changes), *History* (filters: scope, activity, venue, change date), *Reports* (totals, by scope/activity/venue/date, reconciliation, CSV). The commission panel also appears on **Booking** and **Payment** detail, the **Ledger** shows percentage, rule scope and version, **Finance** shows commission totals and reconciliation, and the finance configuration form has the `commission_base` choice.

Percentages are entered in basis points (1000 = 10%, 1250 = 12.5%) like the other finance forms.

## 7. Owner app

*Payments & Earnings* keeps everything it had. When `GET /owners/earnings/breakdown` is available the "Not available yet" card is replaced by **Commission & net earnings**: net earnings after commission, platform commission, and one expandable card per booking with each line and the formula. The app never calculates money. If the breakdown cannot be loaded, the screen falls back to the previous state.

## 8. Decisions still needed (not guessed)

| # | Decision | Current technical behaviour | Open question |
|---|---|---|---|
| 1 | Commission base: before or after coupon discount | `base` (slot price before discount); `base_after_discount` available per finance configuration | Q7/Q8 |
| 2 | Taxes and platform fee | Never in the commission base; fee goes to platform, tax is held | Q7 |
| 3 | Who bears customer promotional discounts | `discount_borne_by` in the finance configuration; shown to the owner as "Other deductions" only when owner-borne | Q8 |
| 4 | Refunds and partial refunds | Proportional reversal of commission and owner share per processed refund | Q9 |
| 5 | Rounding | Half-up to the paisa, in one function (`mul_bps` / `div_round`) | Q7 |
| 6 | Accrual milestone | At payment capture (via the sweep/accrual), not at completion | Q8/Q9/Q10 |
| 7 | Venue with several sports and several activity rules | **Blocked, not guessed**: no rate, no accrual, until `COMMISSION_ACTIVITY_TIEBREAK` is approved and set | new |
| 8 | Whether commission rule changes need a second administrator | Single admin with `commission.manage`, audited | new |
| 9 | Payout processing | Not integrated; owner net payable is a ledger figure | Q10 |
| 10 | Existing finance configuration percentage | Kept as the fallback when no rule applies | new |
