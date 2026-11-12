# Known issues and external dependencies (final)

Severity: **High** = blocks a safe production launch; **Medium** = launch-able with awareness; **Low** = polish.

## High

| # | Issue | What to do |
|---|---|---|
| 1 | **Flutter apps were never compiled, analyzed or run.** All Flutter results are "written", not "verified". | Run `scripts/bootstrap_flutter.sh`, then `flutter analyze` and `flutter test` in `packages/flutter_shared`, `apps/customer_app`, `apps/owner_app`. Fix what they report, then device-test the full journeys in `END_TO_END_WORKFLOWS.md`. |
| 2 | **No live external service was called**: Supabase Auth/Storage, Razorpay, FCM, Resend, Google Places. Each is implemented behind a gateway and tested with fakes only. | Follow `MANUAL_DEPLOYMENT_GUIDE.md` §6 smoke test in test mode before going live. |
| 3 | **Business rules not decided** (the software refuses or shows "Not available" rather than guessing): refunds and cancellation of paid bookings (Q9), fees/GST/commission/coupons (Q7, Q8, N7), payouts (Q10), hold duration (N4), late payments (N5), venue approval workflow (Q4/C1), owner cancellation (N22). | Answer `OPEN_QUESTIONS.md`. Until then: paid bookings cannot be cancelled online, platform revenue / owner net earnings are "Not available", and `BOOKING_HOLD_MINUTES` must be set by you or booking creation answers 503. |

## Medium

| # | Issue | Notes |
|---|---|---|
| 4 | Rate limiter and background sweep are in-process | Run one API instance, or move limits to an edge/shared store later. Set `FORWARDED_ALLOW_IPS=*` on Railway. |
| 5 | Admin CSV export is synchronous, capped by `ADMIN_EXPORT_MAX_ROWS` | Fine at current scale; unmeasured under load. |
| 6 | Review rules are a conservative default (completed booking only, once, no edit/delete, one owner reply, no moderation) | Q15/N14/Q18 — confirm or change. |
| 7 | `available_today` scans at most 150 candidate venues per request | Adequate for a city-sized catalogue; revisit with a pre-computed index at scale. |
| 8 | Owner block times use the device time zone | Step 6 note; venue-local time zone entry would be safer. |
| 9 | Phone/Google/Apple sign-in are off by default and unverified | Need Supabase provider setup (N24); enable via env flags only after configuring. |
| 10 | Admin suspension does not touch existing bookings; no "inactive" state | Q18. |
| 11 | No Crashlytics/Sentry | N26 not approved; logs only. |
| 12 | Git history was never scanned for secrets (no commits existed) | Run the scanner / a history scanner after the first commit. |

## Low

- Address search costs money per request once a Google key is added (N27a); directions use a free Google Maps link.
- Admin has no permission-editing screen: roles are fixed, admins are promoted by operator script.
- Pagination in the admin uses offset paging; very deep pages are slower.
- Reference images exist only for the customer and owner apps; the admin follows the shared design language (no admin mockups were supplied).
- Android `<queries>` for https links is added by `scripts/configure_customer_platforms.py`; re-run it after regenerating platform folders.

## Credentials and accounts you must supply

Supabase (URL, anon key, service-role key, DB URLs, JWKS or JWT secret) · Razorpay (key id, key secret, webhook secret; live KYC) · Firebase (project id, service account; `google-services.json`, `GoogleService-Info.plist`, APNs key) · Resend (API key, verified domain) · Google Cloud (Places API (New) key, billing) · Railway, Vercel · Apple Developer, Google Play Console · Android upload keystore.
