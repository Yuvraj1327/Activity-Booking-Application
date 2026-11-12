# Analytics architecture (Step 8)

## Principles

1. **Aggregate in SQL.** The browser and the Next server only receive totals and buckets, never whole tables. Queries use `GROUP BY`, `date_trunc(<granularity>, ts AT TIME ZONE <report tz>)` and `COUNT(*) FILTER (WHERE …)`.
2. **Zero-fill in Python.** Empty days, weeks or months are added so charts have a continuous axis. Empty data returns zeros, not errors.
3. **Bounded ranges.** Default last 30 days, maximum 366 days, validated server-side.
4. **One time zone.** `ADMIN_REPORT_TIMEZONE` (default `Asia/Kolkata`) decides which day an event belongs to, in both the API and the web labels.
5. **Existing indexes.** Aggregates filter on `created_at`, `status` and foreign keys already indexed in Steps 6–7.

## Definitions

| Metric | Definition |
|---|---|
| Bookings (period) | Bookings created in the range. |
| Confirmed / pending / cancelled | Counts by booking status. Cancelled groups customer and owner cancellations and payment failures are shown in their own bucket. |
| Gross booking value | Total of confirmed or completed bookings created in the period. |
| Successful payments | Captured gross amount for payments in `captured`, `refunded`, `partially_refunded`. Before any deduction. |
| Recorded payment transactions | Count of payment rows in the period. |
| Platform revenue | **Unavailable** until fees and commission are approved (Q7, Q8). |
| Owner earnings | **Unavailable** (Q7, Q8, Q10). |
| Refunds | **Unavailable** (Q9). The ledger does not yet record refunds. |

Revenue is never inferred by applying an assumed percentage. Each unavailable figure is returned as `{available: false, depends_on, message}` and the UI shows the reason.

## Charts (Recharts)

Booking trend (area/bars with stacked statuses), status distribution (donut), payment trend (bars), registrations, venue growth, popular categories and venues. Colours follow the ZURUV violet palette; status colours (green, amber, red) also have text labels, so colour is never the only signal.

## Testing

Backend tests check totals against hand-computed fixtures, date-range edges, week and month buckets, an empty platform, and that unavailable figures stay unavailable. Playwright checks KPI cards against the API for the seeded world and the empty-period state.
