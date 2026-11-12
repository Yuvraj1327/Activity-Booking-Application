# Step 9 known issues

## Cannot be verified yet (environment)

1. **Flutter apps never compiled or run.** No SDK here. `flutter analyze`, Flutter tests, widget tests and UI QA are all pending. Treat both apps as unverified until someone runs `flutter analyze` and the tests (`.github/workflows/flutter.yml` runs them in CI).
2. **No live external service has been called:** Razorpay (test mode), Firebase Cloud Messaging, Resend, Google Maps/Places, Supabase Auth and Storage. Required credentials are listed below.
3. **No load or scale testing.** New indexes (`bookings.created_at`, `profiles(role, created_at)`, `venues.created_at`) are justified by query shape only.
4. **Git history not scanned for secrets**: the repository has no commits yet.

## Decisions waiting for the business (not invented; see `OPEN_QUESTIONS.md`)

- Q7/Q8/N7 fees, GST, commission, coupons: platform revenue and owner earnings stay "Not available".
- Q9 cancellation and refunds: **a paid booking cannot be cancelled** and no refund is created. Customers can cancel only unpaid holds.
- Q10 payouts; N22 owner cancellation; N4 hold length; N5 late payments (kept and flagged for review).
- Q4/C1 venue approval workflow: there is no approve/reject step for owners; bookings confirm by verified payment. Owner "approve or reject" is therefore intentionally absent.
- Q18 admin moderation: only active and suspended exist; suspending does not touch existing bookings.
- Reviews: the owner reviews endpoint exists but no review-creation flow is approved; not tested as a journey.

## Technical limits

- Rate limiter is per-process (see security report).
- The background sweep (hold expiry, outbox retry, payment reconcile) runs inside the API process; with several workers each runs it (it is idempotent, but unmeasured).
- Admin CSV export is synchronous and capped at `ADMIN_EXPORT_MAX_ROWS`.
- Owner block times use the device time zone (Step 6 note).

## Required credentials (none were supplied)

Supabase project URL, anon key, JWT secret or JWKS, service-role key (backend only); Razorpay **test** key id, key secret and webhook secret; Firebase project id and service account; Resend API key and verified sender; Google Maps/Places keys for the apps; Android/iOS signing is Step 10.
