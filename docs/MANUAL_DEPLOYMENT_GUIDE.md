# ZURUV — Manual deployment guide

Nothing in this repository deploys itself. Every step below is for **you** to run. Nothing here has been run against Railway, Vercel, Supabase production or the app stores; commands are checked against the repository's files, not against those platforms. Where a platform screen may have changed, follow its current docs.

Placeholders look like `<this>`. Real secret values never go in git, in this document, in Flutter `.env`, or in any `NEXT_PUBLIC_*` variable. Variable meanings: [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md).

**Order matters:** 1 Supabase → 2 Backend (Railway) → 3 Admin (Vercel) → 4 Razorpay webhook → 5 Mobile builds → 6 Smoke test.

---

## 0. Before you start

| You need | Used for |
|---|---|
| Supabase project (paid plan recommended for production: backups) | Auth, Postgres, Storage |
| Railway account | FastAPI backend |
| Vercel account | Admin web |
| Razorpay account (test keys first) | Payments |
| Firebase project | Push notifications (FCM) |
| Resend account + verified sender domain | E-mail |
| Google Cloud project with billing, *Places API (New)* enabled | Owner address search (optional) |
| Domains: e.g. `api.<your-domain>`, `admin.<your-domain>` | Public URLs |
| Flutter SDK >= 3.27, Android Studio, (macOS + Xcode for iOS) | Mobile builds |
| Apple Developer + Google Play Console accounts | Store release |

Business decisions still open (refunds, GST, commission, payouts, venue approval) are listed in [KNOWN_ISSUES.md](KNOWN_ISSUES.md) and [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md). The software does not invent them; read that list before going live.

---

## 1. Supabase production

1. Create the project (choose region close to your users and to Railway). Note: project URL, anon key, service-role key, database password.
2. **Auth → URL configuration**
   - Site URL: `https://admin.<your-domain>`
   - Redirect URLs (add all): `https://admin.<your-domain>/**`, `io.zuruv.customer://login-callback`, `io.zuruv.owner://login-callback`
3. **Auth → Providers**: enable Email. Enable Google/Apple/Phone only if you have configured them, and then set `GOOGLE_AUTH_ENABLED` / `APPLE_AUTH_ENABLED` / `PHONE_AUTH_ENABLED` to `true` in the Flutter env files (phone login needs an SMS provider — open question N24).
4. **Auth → SMTP**: point it at Resend SMTP so confirmation and reset e-mails come from your domain (see [EMAIL_CONFIGURATION.md](EMAIL_CONFIGURATION.md)).
5. **Auth → MFA**: enable TOTP. Admins must enrol at first login (the backend demands an `aal2` session in production).
6. **Database connection strings** (Project settings → Database). Pick:
   - *Direct* or *Session pooler* (port 5432) → `ALEMBIC_DATABASE_URL` (migrations).
   - *Transaction pooler* (port 6543) → `DATABASE_URL` for the running API, **with** `DB_USE_NULLPOOL=true`. (If you use the direct/session string for both, leave `DB_USE_NULLPOOL` unset.)
7. **Apply the schema.** From your machine:

   ```bash
   cd backend
   python3.13 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   export ALEMBIC_DATABASE_URL='postgresql://postgres:<password>@<host>:5432/postgres'
   alembic upgrade head          # applies 0001 … 0009
   alembic current               # must print 0009 (head)
   ```

   This creates all 27 tables, row-level security, the `venue-images` and `profile-images` Storage buckets with their policies, and the review aggregates. Take a database backup (Dashboard → Database → Backups) **before** this step on any database that already has data.
8. **Reference data** (categories, amenities, cities — review the city list, it is an India-first assumption, N1):

   ```bash
   export DATABASE_URL='postgresql://postgres:<password>@<host>:5432/postgres'   # direct/session
   python -m scripts.seed_reference_data
   ```

   Do **not** run `seed_demo_venues` in production (it refuses when `ENVIRONMENT=production`).
9. **First admin.** Admins cannot self-register. Create the user (Dashboard → Authentication → Users → Add user, strong password), then:

   ```bash
   python -m scripts.create_admin --email admin@<your-domain> --name "<Name>"
   ```

   Log in to the admin site and enrol TOTP when asked.
10. **Storage**: confirm both buckets exist (Dashboard → Storage). Uploads go through the backend using the service-role key; the apps never hold it.

---

## 2. Backend on Railway

The service is a Docker image: `backend/Dockerfile` (Python 3.13, uvicorn, port **8008**, user `appuser`).

1. Railway → New project → Deploy from GitHub repo. In the service settings set **Root Directory** = `backend`. Railway detects the Dockerfile.
2. **Variables** (names only; values from your accounts). Minimum for a working production API:

   ```
   ENVIRONMENT=production
   PORT=8008
   FORWARDED_ALLOW_IPS=*
   CORS_ORIGINS=https://admin.<your-domain>
   DATABASE_URL=<transaction-pooler URL>
   DB_USE_NULLPOOL=true
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_ANON_KEY=<anon key>
   SUPABASE_SERVICE_ROLE_KEY=<service-role key>      # secret, backend only
   ADMIN_REQUIRE_MFA=true
   ```

   Feature variables (each unset feature answers "not configured"; nothing is faked):

   ```
   RAZORPAY_KEY_ID=rzp_test_xxx   RAZORPAY_KEY_SECRET=...   RAZORPAY_WEBHOOK_SECRET=...
   FIREBASE_PROJECT_ID=...        FIREBASE_SERVICE_ACCOUNT=<service-account JSON text>
   RESEND_API_KEY=...             EMAIL_FROM_ADDRESS=ZURUV <bookings@<your-domain>>
   GOOGLE_MAPS_API_KEY=...
   ```

   Booking rules are **empty by design** until the business decides (Q11, N4, Q9, N6). In `hold` mode (default) `POST /bookings` answers `503 BOOKING_NOT_CONFIGURED` until you set `BOOKING_HOLD_MINUTES`:

   ```
   BOOKING_MODE=hold
   BOOKING_HOLD_MINUTES=<minutes, your decision>
   CANCELLATION_MIN_NOTICE_HOURS=<optional, your decision>
   BOOKING_MIN_NOTICE_MINUTES=<optional>   BOOKING_MAX_ADVANCE_DAYS=<optional>
   ```

3. **Networking**: Settings → Networking → Generate domain (to test), then add custom domain `api.<your-domain>` and create the CNAME Railway shows.
4. **Health check**: Settings → Deploy → Healthcheck path `/health`. A healthy response has `"database": {"status": "ok", ...}`.
5. Deploy. Check:

   ```bash
   curl -s https://api.<your-domain>/health
   curl -s https://api.<your-domain>/api/v1/version
   curl -si https://api.<your-domain>/api/v1/admin/me | head -1     # expect 401
   curl -si https://api.<your-domain>/docs | head -1                # expect 404 in production
   ```

6. Production refuses to start with `*` in `CORS_ORIGINS`, without `DATABASE_URL`, or without `SUPABASE_URL`/`SUPABASE_JWT_SECRET`; the Railway deploy log shows the reason.
7. Run **one** instance first. The rate limiter and the background sweep (hold expiry, notification retry, payment reconcile) are in-process; several replicas multiply the sweeps (idempotent) and weaken per-client limits (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md)).

---

## 3. Admin on Vercel

1. Vercel → Add New → Project → import the repo. **Root Directory** = `apps/admin_web`. Framework: Next.js (auto). Build command `next build`, install `npm ci`.
2. **Environment variables** (Production):

   ```
   NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
   NEXT_PUBLIC_API_BASE_URL=https://api.<your-domain>/api/v1
   ADMIN_REPORT_TIMEZONE=Asia/Kolkata
   NEXT_PUBLIC_ADMIN_REPORT_TIMEZONE=Asia/Kolkata
   ```

   `NEXT_PUBLIC_*` values are visible in the browser. **Never** add the service-role key here. A production build without `NEXT_PUBLIC_API_BASE_URL` does not fall back to localhost; it shows a configuration error instead.
3. Deploy, then Settings → Domains → add `admin.<your-domain>`.
4. Confirm the CORS value on Railway equals this exact origin (scheme + host, no trailing slash) and redeploy the API if you changed it.
5. Optional pre-flight on your machine, same checks CI runs:

   ```bash
   cd apps/admin_web && npm ci && npx tsc --noEmit && npx eslint . && npx vitest run
   NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon> \
   NEXT_PUBLIC_API_BASE_URL=https://api.<your-domain>/api/v1 npx next build
   cd ../.. && python scripts/scan_secrets.py apps/admin_web/.next/static
   ```

---

## 4. Razorpay webhook and CORS/domain checklist

1. Razorpay Dashboard (Test mode first) → Settings → Webhooks → Add:
   - URL: `https://api.<your-domain>/api/v1/payments/webhook`
   - Secret: a new random string. Put the same value in Railway as `RAZORPAY_WEBHOOK_SECRET` (**not** the API key secret).
   - Events: `payment.authorized`, `payment.captured`, `payment.failed`, `order.paid`, `refund.processed` (optionally `refund.created`).
2. Test with a Razorpay **test** payment from the customer app. The booking must turn `confirmed` after the server verifies the signature; duplicates of the same event are ignored.
3. Switching to Live: create live keys, repeat the webhook for Live mode, update the three Railway variables, and complete Razorpay KYC. Marketplace/split settlement and payouts are **not** built (Q10, N25).
4. Domain checklist: `api.` and `admin.` DNS resolve with TLS; Supabase redirect URLs include the admin origin and both app schemes; `CORS_ORIGINS` has only the admin origin (mobile apps are not browsers and need no CORS entry); Resend domain verified (SPF/DKIM).

---

## 5. Flutter release builds

The repository has no `android/` or `ios/` folders (they are generated). **The Flutter apps have never been compiled in the environment that produced this repository** — run the analyzer and tests first and fix anything they report:

```bash
scripts/bootstrap_flutter.sh                  # flutter create + pub get + permissions + deep links
cd packages/flutter_shared && flutter analyze && flutter test
cd ../../apps/customer_app && flutter analyze && flutter test
cd ../owner_app && flutter analyze && flutter test
```

Create the release env files (public values only, git-ignored `.env` in each app, filled with production values before building):

```
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<anon key>
API_BASE_URL=https://api.<your-domain>/api/v1
AUTH_REDIRECT_URL=io.zuruv.customer://login-callback
GOOGLE_AUTH_ENABLED=false
APPLE_AUTH_ENABLED=false
PHONE_AUTH_ENABLED=false
```

(Owner app: `io.zuruv.owner://login-callback`.) A release build without `API_BASE_URL` throws at start-up on purpose.

**Firebase (push):** add Android apps `com.zuruv.zuruv_customer` and `com.zuruv.zuruv_owner` (package names produced by `flutter create --org com.zuruv`) and the iOS apps; download `google-services.json` into `apps/<app>/android/app/` and `GoogleService-Info.plist` into `apps/<app>/ios/Runner/`. Upload your APNs key in Firebase for iOS. Apps run without Firebase; push is then simply off.

**Razorpay (customer app):** the Android/iOS runners use `razorpay_flutter`. The key id comes from the backend with each order, nothing to set in the app. Android needs minSdk 21+ (Flutter default is fine).

**Android release**

```bash
cd apps/customer_app            # repeat for apps/owner_app
keytool -genkey -v -keystore ~/zuruv-upload.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
# create android/key.properties (git-ignored) and wire signingConfigs.release in android/app/build.gradle(.kts)
# per https://docs.flutter.dev/deployment/android#sign-the-app
flutter build appbundle --release   # bundles the app's .env (use production public values)
# output: build/app/outputs/bundle/release/app-release.aab  → upload to Play Console (internal testing first)
```

Back up the keystore and its passwords outside the repo. Set the app name/icon in `android/app/src/main/AndroidManifest.xml` and `res/` as you wish.

**iOS release** (macOS only)

```bash
cd apps/customer_app
open ios/Runner.xcworkspace     # set Team, bundle id, enable Push Notifications + Background Modes (Remote notifications) capabilities
flutter build ipa --release   # bundles the app's .env (use production public values)
# upload build/ios/ipa/*.ipa with Transporter or Xcode Organizer → TestFlight first
```

The location permission text and URL scheme are already added by `scripts/configure_*_platforms.py` (re-run them after any `flutter create`). Apple may require Sign in with Apple if you offer other social logins.

---

## 6. Smoke test after deployment

Use Razorpay **test** mode and a test Supabase user.

1. `GET /health` shows database status `ok`; `/docs` is 404.
2. Admin login with MFA; dashboard loads; Venues/Bookings/Payments pages load (empty is fine).
3. Owner app: register → create venue → upload a photo → set hours → publish.
4. Customer app: register → browse → open venue → pick slot → pay with a Razorpay test card → booking `confirmed`; push/e-mail arrive if configured.
5. Owner app shows the booking; admin shows booking and payment.
6. Customer cancels an unpaid hold (allowed); a paid booking correctly refuses cancellation (Q9 open).
7. Owner address search returns suggestions (if the Google key is set), otherwise a clear "not configured" message.

---

## 7. Rollback

| What | How |
|---|---|
| Backend code | Railway → Deployments → previous deployment → Redeploy (or Rollback). |
| Admin | Vercel → Deployments → previous → Promote to Production. |
| Database | Backup first. Then `ALEMBIC_DATABASE_URL=… alembic downgrade -1` (e.g. `0009 → 0008` drops reviews). Downgrades drop data of the removed objects; prefer restoring the backup when data exists. Roll the **code back first** when a release added a migration, so old code never meets a newer schema. |
| A bad config variable | Revert it in Railway/Vercel and redeploy; feature variables fail "closed" (not configured). |
| Mobile | Halt the staged rollout in Play Console / remove the TestFlight build; ship the previous build number +1 (store versions cannot go backwards). The API stays backwards compatible within `/api/v1`. |
| Webhook problems | Disable the webhook in Razorpay; the backend also reconciles open payments with Razorpay every few minutes (`PAYMENT_RECONCILE_AFTER_MINUTES`). |
