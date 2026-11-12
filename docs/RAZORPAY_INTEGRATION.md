# Razorpay integration guide (Step 7)

Always use **Test Mode** during development. Never put a live key in a repository, a Flutter app or a `NEXT_PUBLIC_*` variable.

## 1. Dashboard setup (Test Mode)

1. Razorpay Dashboard → switch to **Test Mode** (top bar). Menu names below follow the dashboard at the time of writing and may differ slightly.
2. **Account & Settings → API Keys → Generate Test Key.** Copy *Key Id* (`rzp_test_...`) and *Key Secret*. The secret is shown once.
3. **Account & Settings → Webhooks → Add New Webhook.**
   * URL: `https://<your-api-host>/api/v1/payments/webhook` (use a tunnel such as ngrok for a laptop).
   * **Secret:** type a long random string. This is `RAZORPAY_WEBHOOK_SECRET` and must differ from the API key secret.
   * Active events: `payment.authorized`, `payment.captured`, `payment.failed`, `order.paid`, `refund.processed` (and optionally `refund.created`).
4. **Capture:** keep *automatic capture* on (Account & Settings → Payment capture). If you leave it manual, the backend captures authorised payments itself (`POST /payments/{id}/capture` with the server-side amount).
5. **Payment methods:** enable UPI, cards, net banking and wallets under *Configuration → Payment Methods*. What customers see depends on the methods your account has activated; the app does not hard-code any.
6. Settlement, payouts, KYC and Route/marketplace transfers are **not configured by this step** (open questions N11, N25, Q10).

## 2. Backend environment (`backend/.env`)

```
RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
RAZORPAY_KEY_SECRET=...            # backend only
RAZORPAY_WEBHOOK_SECRET=...        # backend only, different from the key secret
```
Unset values make the API answer `503 PAYMENTS_NOT_CONFIGURED` / `WEBHOOK_NOT_CONFIGURED`; nothing is faked.

## 3. API

| Method and path | Who | Purpose |
|---|---|---|
| `POST /api/v1/payments/create-order` `{booking_id}` | customer | Validates the booking, computes the amount, creates (or reuses) the order. Returns the payment record and checkout config (public key id, order id, amount, prefill). |
| `POST /api/v1/payments/verify` `{razorpay_order_id, razorpay_payment_id, razorpay_signature}` | customer | Verifies the signature, fetches the payment from Razorpay, applies it. `400 PAYMENT_SIGNATURE_INVALID` on a bad signature. |
| `POST /api/v1/payments/webhook` | Razorpay | Authenticated by `X-Razorpay-Signature` over the raw body. Always `200` for valid-signature deliveries (`applied`/`duplicate`/`ignored`/`rejected`) so Razorpay does not retry what we deliberately ignored. `400` for a bad signature. |
| `GET /api/v1/payments/{payment_id}` | customer | Own payment. If still open, asks Razorpay what happened (delayed confirmation). |
| `GET /api/v1/payments/history` | customer | Own payments, newest first. |
| `GET /api/v1/owners/payments`, `GET /api/v1/owners/earnings` | owner | Paid (captured) payments of the owner's venues; gross totals. Deductions, net and payouts are reported `available:false`. |
| `GET /api/v1/admin/payments`, `/admin/payments/{id}`, `/admin/payments/summary` | admin (+MFA in staging/prod) | Records, statuses, references, gateway events, failed/review queue, gross captured total. No credentials, no card data. |

Errors: `PAYMENTS_NOT_CONFIGURED` 503, `BOOKING_NOT_FOUND` 404, `ALREADY_PAID` 409, `PAYMENT_NOT_REQUIRED` 409 (instant-mode booking), `BOOKING_NOT_PAYABLE` 409, `HOLD_EXPIRED` 409, `AMOUNT_NOT_PAYABLE` 422 (below ₹1.00), `PAYMENT_PROVIDER_UNAVAILABLE`/`PAYMENT_PROVIDER_ERROR` 503, `PAYMENT_NOT_FOUND` 404.

## 4. Webhook verification flow

```
raw bytes ──> HMAC_SHA256(RAZORPAY_WEBHOOK_SECRET, raw) ──> constant-time compare with X-Razorpay-Signature
   │ mismatch/missing -> 400 WEBHOOK_SIGNATURE_INVALID (nothing stored, a warning is logged)
   v
parse JSON ──> event id = X-Razorpay-Event-Id (fallback: sha256 of body)
   │ already in payment_events -> 200 duplicate
   v
find payments row by order id (then by payment id)  -- unknown -> store "ignored" event, 200
   v
fetch the payment from Razorpay (when configured) -> _apply under row locks
   v
payment_events row inserted in the SAME transaction (unique event id: concurrent duplicates lose and return "duplicate")
```
The signature is checked against the exact bytes received. Re-serialised JSON does not validate (tested).

## 5. Customer app (Razorpay Checkout)

`razorpay_flutter` opens Checkout with the **public** key id and the **order id** from the backend. Its result is only sent to `/payments/verify`. States: Processing, Verification in progress, Payment pending, Payment successful, Payment failed, Payment cancelled, Time ran out, Payment received (needs review), No connection. "Payment successful" is shown only when the API returns `confirmed: true`.

Platform folders (`android/`, `ios/`) do not exist in this repository yet (`flutter create` has not been run), so no native Razorpay configuration is committed. Follow the `razorpay_flutter` README for the minimum Android SDK, the iOS deployment target and the UPI app URL schemes when you generate them.

## 6. Test-mode checks before trusting it

Use Razorpay's published test cards/UPI IDs (dashboard → Test Mode docs). Walk through: success, failure, close the sheet, kill the app right after paying (booking must still confirm via webhook), pay after the hold expired (must be flagged, not confirmed). **None of these has been run against real Razorpay yet**; the automated tests use an in-memory fake with real signature logic.

## 7. Going live later

Replace the keys and the webhook secret with live values in the production environment only, re-create the webhook with the production URL, and re-run the checklist above. Live keys are never used in development testing.
