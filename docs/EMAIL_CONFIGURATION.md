# Email configuration (Resend, Step 7)

## Setup

1. Create a Resend account and **verify a sending domain** (DNS records: SPF, DKIM). Until it is verified Resend only allows its onboarding sender.
2. Create an API key (sending access).
3. Backend environment (never in Flutter / Next.js):
```
RESEND_API_KEY=re_...
EMAIL_FROM_ADDRESS=ZURUV <bookings@your-verified-domain>
```
Unset values make deliveries `skipped` with `last_error="Email is not configured."`; nothing is sent and nothing fails.

## Templates (`app/services/email_templates.py`)

| Template | Sent when | Recipient |
|---|---|---|
| `booking_confirmed` | payment verified and booking confirmed | customer |
| `payment_received` | payment verified | customer |
| `booking_cancelled` | customer cancels a confirmed booking | customer |
| `owner_new_booking` | verified payment confirms a booking | owner |
| `owner_booking_cancelled` | customer cancels a confirmed booking | owner |

Every dynamic value is HTML-escaped (tested). Each template renders HTML and a plain-text alternative. Add a template by adding a function to `TEMPLATES`; callers reference it by name through `EmailSpec`.

Not built: registration verification (Supabase Auth keeps sending it; moving it to Resend means configuring Supabase's SMTP and is a separate decision) and "important owner notifications" beyond the two above, because no other owner event exists yet.

## Delivery, errors and duplicates

* Rows in `email_deliveries` are the queue and the log: `queued → sent | failed | skipped`, `attempts`, `provider_message_id`, `last_error` (short, never the API key or the message body).
* Retryable provider errors (network, 429, 5xx) stay `queued` and are retried by the sweep up to 5 attempts, then `failed`. Non-retryable errors (e.g. 4xx) are `failed` immediately.
* Resend is called with an `Idempotency-Key` equal to the delivery's dedupe key, so a retry after a timeout cannot double-send.
* Duplicate business events (repeated webhooks) cannot create a second delivery: `UNIQUE(dedupe_key)`.
* A recipient who switched email off in `notification_preferences` gets no email row at all.
* A provider outage never affects the payment or booking: emails are dispatched after the commit.

## Checking it

Query `email_deliveries` (or the admin API when Step 8 adds a screen): `SELECT template, status, attempts, last_error FROM email_deliveries ORDER BY created_at DESC;`
**Not verified against real Resend**: tests use a fake sender.
