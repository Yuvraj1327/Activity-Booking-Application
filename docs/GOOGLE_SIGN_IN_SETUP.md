# Continue with Google — setup

The mobile app (package / bundle id `com.zuruv.zuruv`) signs in with the **native Google account picker**,
then exchanges Google's ID token for a Supabase session (`signInWithIdToken`). The existing profile flow
(`GET /auth/me` → `POST /auth/profile`) then runs unchanged. If `GOOGLE_WEB_CLIENT_ID` is empty the app falls
back to Supabase's browser (redirect) flow, which only needs steps 1, 2 and 5.

## Security rules (enforced in code, covered by tests)
- A Google sign-up is **always a `customer`**. The role never comes from `user_metadata`; the provider is read
  from Supabase `app_metadata`, which only the server can set. The profile form hides the account-type picker
  for Google users, and the request role is forced to `customer`.
- **Owner** accounts exist only via e-mail sign-up as owner (unchanged) or an admin. **Admin** accounts cannot
  use the mobile app at all (they are signed out with a notice).
- An existing owner/customer who signs in with Google (same verified e-mail) keeps the role stored in the backend.
- E-mail/password login is untouched.

## 1. Google Cloud Console (APIs & Services → Credentials)
Configure the OAuth consent screen first, then create **three** OAuth client IDs:

| Type | Settings | Used for |
|---|---|---|
| **Web application** | Authorised redirect URI: `https://<project-ref>.supabase.co/auth/v1/callback` | Supabase provider + `GOOGLE_WEB_CLIENT_ID` |
| **Android** | Package `com.zuruv.zuruv` + SHA-1 of each signing key (debug: `cd apps/mobile_app/android && ./gradlew signingReport`; also Play App Signing SHA-1 for release) | Native Android sign-in (no ID goes in the app) |
| **iOS** | Bundle ID `com.zuruv.zuruv` | `GOOGLE_IOS_CLIENT_ID` |

## 2. Supabase dashboard
- Authentication → Providers → **Google**: enable; paste the **Web** client ID and secret.
  Under *Authorized Client IDs* also add the **iOS** client ID (comma-separated) so native iOS tokens are accepted.
- Authentication → URL Configuration → *Redirect URLs*: add `io.zuruv.app://login-callback`
  (needed for e-mail links and the browser fallback; already registered as a URL scheme on iOS/Android).
- Keep "Confirm e-mail" as you have it; Google e-mails arrive verified.

## 3. App configuration (`apps/mobile_app/.env`, git-ignored)
```
GOOGLE_AUTH_ENABLED=true
GOOGLE_WEB_CLIENT_ID=<web client id>.apps.googleusercontent.com
GOOGLE_IOS_CLIENT_ID=<ios client id>.apps.googleusercontent.com
```
These are public identifiers (no secrets). The Google **client secret** lives only in Supabase.

Then run `./tool/sync_native_keys.sh`. It writes `GOOGLE_IOS_REVERSED_CLIENT_ID` into the git-ignored
`ios/Flutter/Secrets.xcconfig`, which `Info.plist` uses as the Google callback URL scheme.

## 4. Platform notes
- **Android**: nothing else to edit; the plugin reads the Android client by package + SHA-1. A wrong or missing
  SHA-1 shows as `ApiException: 10` / "Google sign-in failed". Use a physical device or an emulator with Google Play.
- **iOS**: the URL scheme is injected into `Info.plist` (see step 3). Test on a simulator or device.

## 5. Backend
No change. `/auth/me` and `/auth/profile` already reject `admin` signup and are the source of truth for roles.

## 6. Manual test checklist (run on Android **and** iOS)
1. New Google account → account picker → lands in the customer app; `profiles` row has `role=customer`.
2. Sign out, sign in again with the same account → straight in, no profile form.
3. Existing owner (e-mail) signs in with Google using the same e-mail → owner dashboard.
4. Close the Google sheet → back on login, no error.
5. Airplane mode → friendly "Cannot reach…" message, button usable again.
6. E-mail/password login and owner registration still work.
