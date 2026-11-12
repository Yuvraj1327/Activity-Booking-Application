# Step 7 report: Payments & Notifications

Date: 2026-11-12. Scope followed: the Step 7 brief. Step 8 was **not** started.

## 0. What is and is not verified

| Area | Verified how | Result |
|---|---|---|
| Backend (payments, webhook, reconcile, notifications, push, email, owner/admin payment APIs) | 53 new tests + updated old ones; ruff format/check, mypy (73 files) | **268 passed**, lint and types clean |
| Concurrency | 6 concurrent identical webhooks; verify racing a webhook | Applied exactly once |
| Migration `0007` | Up / down / up, ORM-vs-schema comparison, RLS tests for the new tables | Passed (25 tables) |
| Flutter apps | **Syntax only** (parser accepted all 37 new or changed Dart files) | `flutter analyze` and Flutter tests **not run** (no SDK) |
| Razorpay, Firebase (FCM), Resend, Supabase | **Never called.** Tests use fakes that contain the real signature logic | Not verified against the real services |

## 1. Razorpay integration status
Implemented behind a `PaymentGateway` protocol (`app/gateways/razorpay.py`): create order, fetch payment, fetch order payments, signature checks. Test mode only. Not exercised against Razorpay itself.

## 2. Order creation status
`POST /payments/create-order` takes only a booking id. The amount is read from `bookings.total_amount_paise` on the server; extra fields such as `amount_paise` are rejected (422). One order per booking (`UNIQUE(booking_id)`); retries reuse it. Expired, already paid, not-owned and non-payable bookings are refused.

## 3. Signature verification status
`POST /payments/verify` checks HMAC-SHA256(`order_id|payment_id`) with `compare_digest`, then fetches the payment from Razorpay and checks order, amount and currency before confirming. A wrong signature gives 400. The app shows success only when the response says `confirmed: true`.

## 4. Webhook verification status
`POST /payments/webhook` verifies HMAC over the raw body with the separate webhook secret. Idempotency is the unique `provider_event_id` on the append-only `payment_events` table. Duplicates, unknown events and amount mismatches are acknowledged with a defined outcome and applied at most once.

## 5. Payment DB implementation
Migration `0007`: `payments`, `payment_events`, `user_device_tokens`, `notification_preferences`, `email_deliveries`, and new columns on `notifications`. States: created, pending, authorized, captured, failed, refunded, partially_refunded, with validated transitions (`PAYMENT_STATUS_FLOW.md`). One `_apply` function serves verify, webhook and reconcile; lock order is booking, then payment. A payment captured after the hold settled is kept and flagged `review_required` (no auto-refund).

## 6. Customer Checkout integration
Pay screen with Processing, Payment pending, Verification in progress, Payment successful and Payment failed states, retry, payment history, pay/retry on booking details, push-tap routing, unread badge. Written and syntax-checked only; **not compiled or run**.

## 7. Owner payment integration
`GET /owners/payments` and `GET /owners/earnings` return real gross captured amounts for the owner's own venues. Deductions, net earnings and payouts are explicitly unavailable and shown as "Not available yet".

## 8. FCM status
Backend FCM HTTP v1 sender (service-account JWT), token register/refresh/remove endpoints, preferences, invalid-token cleanup, outbox with retry; Flutter registration and tap navigation. **No push has been sent to a device.** The apps have no `android/` or `ios/` folders and no `google-services.json` / `GoogleService-Info.plist`; setup steps are in `NOTIFICATION_ARCHITECTURE.md`.

## 9. Resend status
Sender, five HTML-escaped templates, `email_deliveries` log with a unique dedupe key (no duplicate emails), retry in the sweep loop. **No email has been sent.** Registration verification email stays with Supabase Auth.

## 10. Admin payment visibility
`GET /admin/payments` (status and review filters), `/admin/payments/{id}` (with gateway events), `/admin/payments/summary`. Admin-only; no credentials or card data. There is no admin web UI yet (Step 8).

## 11. Automated test results
268 passed (ruff, mypy clean). New: `test_payments_api.py` (35), `test_notifications_step7.py` (17), plus a config test. Flutter tests were written (push, payment flow, notifications, earnings) but **not run**.

## 12. Security test results
Covered by passing tests: forged/missing checkout and webhook signatures rejected; webhook signed over the raw body only; client-sent amount rejected; another customer's payment returns 404; owner and admin role gating; replay and concurrent webhooks apply once; amount mismatch rejected; no secret in any response; RLS on the new tables. Not tested: real Razorpay behaviour, network-level attacks, penetration testing.

## 13. Required dashboard configuration
Razorpay test-mode key id/secret; webhook URL `/api/v1/payments/webhook` with its own secret and events `payment.authorized`, `payment.captured`, `payment.failed`, `order.paid`, `refund.processed`; Firebase project, service account, and Android/iOS apps with native config files; Resend verified sender domain. Steps in `RAZORPAY_INTEGRATION.md`, `NOTIFICATION_ARCHITECTURE.md`, `EMAIL_CONFIGURATION.md`. Fill the seven `.env.example` placeholders on the backend only.

## 14. Remaining unresolved business rules
Q7 fees/tax, Q8 commission, Q9 cancellation and refund policy, Q10 payouts, N4 hold duration, N5 late-payment handling, N7 coupons, N11 KYC, N25 Razorpay country/marketplace. Consequently: no refunds, payouts, fees or GST are implemented, and paid bookings still cannot be cancelled.
