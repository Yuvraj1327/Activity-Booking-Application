# Notification architecture (Step 7)

Three channels, one source of truth: the `notifications` table is the in-app history; push (FCM) and email (Resend) are delivery channels for the same business event. Nothing is sent for anything that is not a **verified** business event (a payment the backend confirmed, a booking cancelled through the API).

## Flow

```
business transaction (payment applied / booking cancelled)
   ├─ INSERT notifications (push_status=pending, dedupe_key)      ┐ same transaction:
   └─ INSERT email_deliveries (status=queued, dedupe_key)         ┘ commit or roll back together
COMMIT
   └─ background task: dispatch_all()
        ├─ push: for each pending notification -> user's device tokens -> FCM HTTP v1
        │        sent -> push_status=sent | invalid token -> token deleted | none -> skipped
        └─ email: render template -> Resend (Idempotency-Key = dedupe key) -> sent | queued (retry) | failed
sweep loop (every BACKGROUND_SWEEP_SECONDS) retries anything still pending/queued
```

A delivery failure never changes payment or booking state: critical state is committed first.

## Event matrix

| Event | Recipient | In-app type | Push | Email template | Dedupe key |
|---|---|---|---|---|---|
| Booking confirmed (payment verified) | customer | `booking.confirmed` | yes | `booking_confirmed` | `payment:<id>:captured:booking_confirmed` |
| Payment received | customer | `payment.received` | yes | `payment_received` | `payment:<id>:captured:payment_received` |
| Payment failed | customer | `payment.failed` | yes | no | `payment:<id>:failed:<gateway payment id>` |
| Payment received but booking not confirmable | customer | `payment.received` | yes | no | `payment:<id>:captured:late_customer` |
| Booking cancelled by the customer (confirmed bookings) | customer | `booking.cancelled` | yes | `booking_cancelled` | `booking:<id>:cancelled:customer` |
| New booking (after verified payment) | owner | `booking.created` | yes | `owner_new_booking` | `payment:<id>:captured:owner_booking` |
| Payment received | owner | `payment.received` | yes | no | `payment:<id>:captured:owner_payment` |
| Booking cancelled | owner | `booking.cancelled` | yes | `owner_booking_cancelled` | `booking:<id>:cancelled:owner` |
| Payment needs review (late payment, amount mismatch, duplicate attempt) | every active admin | `payment.review` | yes | no | `payment:<id>:review:<reason>` |
| Refund updates | customer | **not built**: no refund policy (Q9) | | | |
| New customer review | owner | **not built**: no reviews feature yet | | | |
| Registration verification email | user | stays with **Supabase Auth** (it sends it); not moved to Resend | | | |

Duplicates are impossible by construction: `UNIQUE(user_id, dedupe_key)` on `notifications` and `UNIQUE(dedupe_key)` on `email_deliveries` (suffixed with the recipient). Repeated webhooks, a webhook racing a verify call, and retries therefore create exactly one notification and one email set (tested, including six concurrent deliveries).

## Tables

* `notifications` (existing, extended): `booking_id`, `payment_id`, `dedupe_key`, `push_status` (`pending|sent|failed|skipped`), `push_attempts`, `push_sent_at`. `data` holds **ids only** (`booking_id`, `payment_id`), used for tap navigation. No amounts, tokens or secrets in payloads.
* `user_device_tokens`: `user_id`, `token` (unique), `platform` (`android|ios|web`), `app` (`customer|owner|admin`), `last_seen_at`. Not readable by any client (no grant). A token that is registered by another account is re-assigned to it.
* `notification_preferences`: `push_enabled`, `email_enabled` per user (default both on). Only these two exist; per-category preferences were not specified.
* `email_deliveries`: recipient, template, non-secret `context`, `status` (`queued|sent|failed|skipped`), `attempts`, `provider_message_id`, `last_error`, related booking/payment. This is the delivery-status log and the retry queue.

## API (any signed-in role)

`GET /notifications` (filters `group`, `unread_only`, paging; items include `booking_id`, `payment_id`), `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`, `GET|PUT /notifications/preferences`, `PUT /devices/token` (register or refresh, idempotent upsert), `POST /devices/token/remove` (sign-out). Owners keep their existing `/owners/notifications` endpoints.

## Flutter

`flutter_shared/lib/src/push`: `PushMessaging` (interface; `FirebasePushMessaging` or a no-op when Firebase is not configured), `PushRegistrar` (permission → token → `PUT /devices/token`; re-registers on token refresh; removes the token **before** sign-out), `PushBootstrap` (registers after sign-in and routes taps). Tap handling covers the app open, backgrounded and terminated cases; the route is `/bookings/<booking_id>` or `/notifications`. Notification screens: Customer app (new), Owner app (existing, unchanged).

## FCM platform setup (not committed: the apps have no `android/` or `ios/` folders yet)

1. Firebase Console → create the project → add an Android app (`applicationId` of each app) and an iOS app (bundle id) for **each** of the Customer and Owner apps.
2. Android: put `google-services.json` in `android/app/`, add the `com.google.gms.google-services` Gradle plugin, and `<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>` in the manifest (Android 13+).
3. iOS: put `GoogleService-Info.plist` in `ios/Runner/`, enable *Push Notifications* and *Background Modes → Remote notifications* in Xcode, and upload an APNs auth key (`.p8`) to Firebase → Project settings → Cloud Messaging.
4. Backend: Firebase Console → Project settings → Service accounts → *Generate new private key*. Set `FIREBASE_PROJECT_ID` and `FIREBASE_SERVICE_ACCOUNT` (the JSON text, or a path to the file). The file/JSON is a secret: never in git, Flutter or `NEXT_PUBLIC_*`.
5. Without the native files the apps run normally: `FirebasePushMessaging.init()` falls back to a no-op and in-app notifications still work.

**Not verified:** no push was sent to a real device, and no Firebase project was available. The automated tests use fakes.

## Limitations

* Foreground pushes only refresh the unread badge; no local banner is drawn.
* Token removal on sign-out is best-effort (a failed network call leaves the token until the next login reassigns it or FCM reports it invalid).
* The in-process sweep runs in every API instance; it is correct (row locks) but wasteful at scale. Replace with a worker when needed.
