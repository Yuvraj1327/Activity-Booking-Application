# Payment status flow (Step 7)

## Payment states (`payments.status`, validated in `app/domain/payment_state.py`)

```
created ──> pending ──> authorized ──> captured ──> partially_refunded ──> refunded
   │            │             │            └───────────────────────────────> refunded
   │            │             └──> failed
   │            └──> captured / failed
   └──> authorized / captured / failed
failed ──> pending / authorized / captured      (the same Razorpay order may be retried)
```

| From | Allowed to |
|---|---|
| created | pending, authorized, captured, failed |
| pending | authorized, captured, failed |
| authorized | captured, failed |
| failed | pending, authorized, captured |
| captured | refunded, partially_refunded |
| partially_refunded | partially_refunded, refunded |
| refunded | (none) |

Same-state updates are idempotent no-ops. `captured` can never return to `failed`/`pending`. Refund states are entered **only** when Razorpay reports `refund.processed` (for example a refund issued in the dashboard); this system never starts a refund.

## Booking states touched by payments (actor `system` only)

| Event | Booking |
|---|---|
| order created | `payment_status` → `pending` |
| captured, booking `pending_payment` | `pending_payment → confirmed`, `payment_status=paid`, `confirmed_at` set, `expires_at` cleared |
| captured, booking `payment_failed` | `payment_failed → pending_payment → confirmed` (two history rows) |
| failed, booking `pending_payment` | `pending_payment → payment_failed`, `payment_status=failed` |
| retry (create-order again) | `payment_failed → pending_payment`, `payment_status=pending` |
| captured, booking `expired`/cancelled | **unchanged**; payment flagged `review_required` (`LATE_PAYMENT_BOOKING_<STATUS>`) |
| full refund reported, booking `refund_pending` | `refund_pending → refunded`, `payment_status=refunded` |

## Customer-visible states

| App state | Meaning | Source |
|---|---|---|
| Processing | creating the order / checkout open | local |
| Verification in progress | sent to `/payments/verify`, awaiting the answer | local |
| Payment pending | the server has not confirmed yet; the app polls `GET /payments/{id}`; webhook will finish it | `confirmed=false`, status not failed |
| Payment successful | `confirmed=true` (payment captured **and** booking confirmed) | server |
| Payment failed | `status=failed` or invalid signature | server |
| Payment cancelled | the customer closed checkout (no server call needed) | local |
| Time ran out | `HOLD_EXPIRED` / booking `expired` | server |
| Payment received (review) | `needs_review=true` | server |

## Decision table for incoming signals

| Signal | Payment row | Result |
|---|---|---|
| order id not ours | none | event stored `ignored`, 200 |
| order id differs from the row's | exists | `rejected` |
| amount or currency differs (captured/authorised) | exists | `rejected`, `review_required=AMOUNT_MISMATCH`, admins notified |
| second *captured* payment id on an already-paid order | exists | `rejected`, `review_required=DUPLICATE_PAYMENT_ATTEMPT` |
| failed attempt after a capture | exists | `ignored` |
| same event id again | exists | `duplicate` (no state change, no notification, no email) |
| different event id, same capture (`order.paid` after `payment.captured`) | exists | `duplicate` |
