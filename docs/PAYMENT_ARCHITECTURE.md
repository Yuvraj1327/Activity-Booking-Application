# Payment architecture (Step 7)

Razorpay is the payment gateway. The backend is the only component that knows the API secret, the only one that decides amounts, and the only one that marks anything paid.

## Components

| Piece | Where | Role |
|---|---|---|
| `RazorpayGateway` (`app/gateways/razorpay.py`) | backend | Creates orders, fetches payments, captures authorised payments, checks both HMAC signatures. Behind a `PaymentGateway` Protocol, so tests inject a fake. |
| `PaymentService` (`app/services/payments.py`) | backend | Order creation, verify, webhook, reconciliation, owner/admin reads. |
| `_apply` | `PaymentService` | The **single** function that turns gateway evidence into payment and booking state. Verify, webhook and reconciliation all call it. |
| `BookingService._move` | Step 6 | Still the only place a booking status changes. Payment confirmation uses actor `system`. |
| `payments`, `payment_events` | PostgreSQL (migration `0007`) | Financial records; see below. |
| Razorpay Checkout | Customer Flutter app | Collects the money. Reports a *claim* only. |

## Payment flow

```
Customer app            FastAPI backend                         Razorpay
     |  POST /payments/create-order {booking_id}                     |
     |------------------>| lock booking; amount := booking.total     |
     |                   | (server side, never from the client)      |
     |                   |-- create order (amount, receipt) -------->|
     |                   |<-- order_id -----------------------------|
     |                   | INSERT payments(status=created)           |
     |<-- order_id, key_id (public), prefill --|                     |
     |  open Checkout(order_id) ------------------------------------>|
     |<-- success{order_id, payment_id, signature} | failed | closed -|
     |  POST /payments/verify {order, payment, signature}            |
     |------------------>| 1. HMAC(order|payment, key_secret) == sig? |
     |                   | 2. GET payment from Razorpay (evidence)   |
     |                   | 3. order, amount, currency match our row? |
     |                   | 4. ONE transaction: payment=captured,     |
     |                   |    booking confirmed+paid (actor system), |
     |                   |    history, notifications/emails queued   |
     |<-- PaymentOut{confirmed:true} --|                             |
     |                   |<== webhook payment.captured (independent) |
     |                   |     same _apply -> "duplicate", no-op     |
     |  after COMMIT: push + email dispatched (never inside the txn) |
```

If the customer closes the app after paying, the **webhook alone** confirms the booking. If the webhook is lost, GET `/payments/{id}` and the background sweep ask Razorpay for the order's payments and apply the result.

## Rules that are enforced (and tested)

* The amount comes from `bookings.total_amount_paise` on the server. A client-sent amount is a `422`.
* One payment per booking and per gateway order: `UNIQUE(booking_id)`, `UNIQUE(provider, provider_order_id)`, `UNIQUE(provider, provider_payment_id)`. Calling create-order again returns the same order; a retry after a failed attempt reuses it.
* Success requires: valid signature **and** payment fetched from Razorpay **and** order id, amount and currency equal to our row. Otherwise nothing is confirmed (`AMOUNT_MISMATCH` also flags the payment for review).
* Webhooks: signature over the **raw bytes**, a webhook secret separate from the API secret, a unique gateway event id (`payment_events.provider_event_id`), row locks (booking, then payment). Six concurrent deliveries of one event apply exactly once.
* A late or out-of-order `payment.failed` never downgrades a captured payment.
* Gateway unreachable during verify: the booking is **not** confirmed; the app shows "verification in progress" and the webhook/reconciliation completes it.
* Card numbers and CVV never reach the backend. `payment_events.detail` drops `card`, `vpa`, `email`, `contact`, `bank`, `wallet`, `acquirer_data` and `notes`.
* Secrets: `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` exist only in the backend environment. The app receives the public key id with each order.

## Tables (migration `0007`)

`payments`: id, booking_id, customer_id, venue_id, provider, `provider_order_id`, `provider_payment_id`, `amount_paise`, `currency`, `status`, `method`, `failure_code`, `failure_reason`, `review_required`, `review_reason`, `gateway_refs` (receipt and order status only), `captured_at`, `failed_at`, timestamps.

`payment_events` (append-only; UPDATE is blocked by trigger): payment_id, `provider_event_id` (unique), `event_type`, `source` (`webhook`/`verify`/`reconcile`/`system`), order/payment references, `outcome` (`applied`/`duplicate`/`ignored`/`rejected`), sanitised `detail`.

Not created, deliberately: `refunds` and payout tables. No refund or payout policy is approved (Q9, Q10), and inventing one would put wrong money rules into the database.

RLS: customers read their own payments, owners the payments of their venues, admins all; no client can write. `payment_events` has no client access at all.

## Payment and booking consistency

| Gateway evidence | `payments.status` | Booking status | `bookings.payment_status` |
|---|---|---|---|
| order created | `created` | `pending_payment` | `pending` |
| payment authorised (backend captures it) | `authorized` | `pending_payment` | `pending` |
| payment captured, hold still ours | `captured` | `confirmed` (actor `system`) | `paid` |
| payment failed | `failed` | `payment_failed` | `failed` |
| retry on the same order | `pending` | `pending_payment` | `pending` |
| captured **after** the hold expired / booking cancelled | `captured`, `review_required` | unchanged (`expired`, ...) | `paid` |
| amount mismatch | unchanged, `review_required` | unchanged | unchanged |

Status transitions are validated in `app/domain/payment_state.py` (see `PAYMENT_STATUS_FLOW.md`).

## Expiry and slot release (with the Step 6 engine)

Holds still expire lazily (`BookingService.settle_due`) and the background sweep also runs it. A hold that is still `pending_payment` when money arrives is confirmed even if `expires_at` just passed, because its blocking slot row still exists and nobody else could have taken it (the check happens inside the booking row lock). Once a hold has been settled to `expired`, the slot is free and may already be someone else's, so late money is **recorded and flagged for staff**, not auto-confirmed and not auto-refunded (open question N5). Admins receive a `payment.review` notification and see the payment under `GET /admin/payments?review_required=true`.

## Background processing

No Redis or Celery. Notifications and emails are written to the database (an outbox) in the same transaction as the business change, then delivered **after commit** by a FastAPI background task. One `asyncio` loop per API process (`BACKGROUND_SWEEP_SECONDS`, default 60, `0` disables) retries undelivered pushes and emails, expires holds and reconciles payments that stayed open longer than `PAYMENT_RECONCILE_AFTER_MINUTES`. Every claim uses `FOR UPDATE SKIP LOCKED`, so several instances are safe. Revisit when volume or latency requires a real worker.

## What is not built (and why)

Refunds, refund policy, platform fee/commission/GST, payouts and settlement, coupons: unapproved rules (Q7–Q10, N7). Cancelling a **paid** booking still answers `409 CANCELLATION_NOT_AVAILABLE`.
