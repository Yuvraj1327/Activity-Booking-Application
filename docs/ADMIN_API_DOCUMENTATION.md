# Admin API (Step 8)

Base path `/api/v1/admin`. Every route requires a bearer token and an **admin** profile (role read from `profiles`; MFA `aal2` when required; suspended → 403). Anonymous → 401; customer or owner → 403. Errors use the standard envelope. Money is integer paise.

## Mapping to the brief

The brief proposed some paths. They were adjusted to the existing architecture:

| Brief | Implemented | Why |
|---|---|---|
| `GET /admin/notifications` | existing `GET /notifications` (any role, own only) | The notification system already scopes by recipient; admins receive their events there. A duplicate endpoint was not added. |
| `PATCH …/status` `Active/Inactive/Suspended` | `active` or `suspended` only | The database models only those two. "Inactive" is not modelled (Q18 open). |
| Payment detail/list | already existed from Step 7 (`/admin/payments*`); extended with search and filters, not duplicated | |

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /me` | Verify the caller is an admin (used by the web for server-side access checks). |
| `GET /dashboard?from&to` | KPI counts, booking and payment trends, money breakdown, popular venues, recent bookings and registrations. |
| `GET /analytics/bookings?from&to&granularity` | Totals, status distribution, trend (`day`, `week`, `month`). |
| `GET /analytics/revenue?from&to&granularity` | Transaction totals and success/failure trend. Refunds are reported unavailable. |
| `GET /analytics/platform?from&to&granularity` | Customer and owner registrations, venue growth, popular categories, most-booked venues. |
| `GET /activity?limit` | Latest bookings, payments and account events. |
| `GET /owners` | `q`, `status`, `sort` (`created_at`, `name`, `venues`, `bookings`), `order`, `limit`, `offset`. |
| `GET /owners/{id}` | Profile, contact, venues, booking activity. |
| `PATCH /owners/{id}/status` | `{status: active|suspended, reason (3–300 chars)}`. Audited. |
| `GET /customers`, `GET /customers/{id}` | Same filters; detail has booking history. Contact details are masked in lists. |
| `PATCH /customers/{id}/status` | As for owners. |
| `GET /venues`, `GET /venues/{id}` | Read-only: owner, category, city, publication status, created date, booking counts. |
| `GET /bookings` | `q` (booking id), `status`, `payment_status`, `venue_id`, `owner_id`, `customer_id`, `from`, `to`, paging. |
| `GET /bookings/{id}` | Booking, status history, related payments. |
| `GET /payments/summary` | Counts and gross totals. |
| `GET /payments` | `q`, `status`, `review_required`, `venue_id`, `from`, `to`, paging. |
| `GET /payments/{id}` | Payment, gateway reference and events. No credentials or card data. |
| `GET /exports/bookings.csv`, `/exports/payments.csv`, `/exports/customers.csv`, `/exports/owners.csv` | Date-filtered CSV, capped at `ADMIN_EXPORT_MAX_ROWS`, `Cache-Control: no-store`. Each export is audited (`admin.export`). |
| `GET /audit-logs` | Audit trail of sensitive admin actions. |

## Status change rules

- Row locked `FOR UPDATE`; target must have the matching role (an owner id on the customer route → 404).
- An admin cannot change their own status or another admin's.
- Writes an `audit_logs` row `admin.account_status_changed` (actor, target, old and new status, reason) in the same transaction, and notifies admins (`admin.account_status`).
- Suspension only blocks sign-in access. It does **not** cancel or refund bookings (Q18 open).

## CSV privacy

Booking and transaction exports contain no customer e-mail or phone. Customer and owner reports omit e-mail and phone. Cells starting with `=`, `+`, `-`, `@` are prefixed to prevent spreadsheet formula injection.

## Validation and errors

`from` after `to` → 422 `INVALID_RANGE`; range over 366 days → 422; unknown status → 422 `INVALID_STATUS` / `INVALID_PAYMENT_STATUS`; unknown sort value → 422; `limit` is bounded; search text is escaped before `ILIKE`.
