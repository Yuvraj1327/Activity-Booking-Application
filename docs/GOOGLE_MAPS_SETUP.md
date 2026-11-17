# Google Maps setup (mobile app)

The Flutter app uses `google_maps_flutter` for venue maps, markers, "my location", the location picker (owner venue form) and the Explore map view. Directions open in the device's Google Maps app via a plain link (no key needed).

Keys here are **public, restricted client keys**. Never put a backend/server key (for example the backend's `GOOGLE_MAPS_API_KEY`) in the mobile `.env`; it ships inside the app bundle.

## 1. Google Cloud project and billing
1. Open <https://console.cloud.google.com/> and create a project (for example `zuruv-mobile`).
2. **Billing**: attach a billing account (Maps Platform requires one, even for the free monthly credit). Set a budget alert.

## 2. Enable APIs
APIs & Services -> Library, enable:
- **Maps SDK for Android**
- **Maps SDK for iOS**
- **Places API (New)**, only if you want direct autocomplete from the app (`GOOGLE_PLACES_API_KEY`). The owner address search already goes through the backend and does not need it.

## 3. Create three keys (Credentials -> Create credentials -> API key)

| Key | Application restriction | API restriction |
|---|---|---|
| Android | Android apps: package `com.zuruv.zuruv` + your SHA-1 | Maps SDK for Android |
| iOS | iOS apps: bundle id (see `ios/Runner.xcodeproj`, `PRODUCT_BUNDLE_IDENTIFIER`) | Maps SDK for iOS |
| Places (optional) | Same Android/iOS restriction, or none plus tight API limit | Places API (New) |

Get the debug SHA-1:
```bash
keytool -list -v -alias androiddebugkey -keystore ~/.android/debug.keystore -storepass android -keypass android | grep SHA1
```
Add a second Android restriction entry for your release keystore (and Play App Signing certificate) before shipping.

## 4. Add keys locally
```bash
cd apps/mobile_app
cp .env.example .env            # if you have not already
# edit .env:
GOOGLE_MAPS_API_KEY_ANDROID=<android key>
GOOGLE_MAPS_API_KEY_IOS=<ios key>
GOOGLE_PLACES_API_KEY=<optional places key>

./tool/sync_native_keys.sh      # run after every change to the two MAPS keys
```
Why the script: the native Maps SDKs start before Flutter and cannot read the dotenv asset. The script writes two **git-ignored** files:
- `android/secrets.properties` -> `build.gradle.kts` injects it as the `com.google.android.geo.API_KEY` manifest placeholder.
- `ios/Flutter/Secrets.xcconfig` -> included by Debug/Release xcconfig -> `Info.plist` `GMSApiKey` -> `AppDelegate.swift` calls `GMSServices.provideAPIKey`.

`.env`, `android/secrets.properties` and `ios/Flutter/Secrets.xcconfig` are in `.gitignore`. For CI, create the same `.env` from secret variables and run the script before `flutter build`.

## 5. Run
```bash
flutter pub get
./tool/sync_native_keys.sh
flutter run -d <android-emulator-or-device>
flutter run -d <ios-simulator-or-device>   # first time: cd ios && pod install
```
Use an emulator image **with Google Play services** (Play Store icon) on Android.

## Behaviour and error handling
- No key for the current platform, or an unsupported platform (web/desktop): map widgets show a fallback or hide; lists, Directions and manual lat/lng entry keep working.
- Location permission is never requested at launch. It is requested only from "My location" buttons. Denied: a message; denied forever: a message with a Settings action; services off: a message.
- A **wrong or unrestricted-mismatch key** makes the SDK render a grey map with no Dart callback. Check `adb logcat | grep -i "Google Maps"` (Android) or the Xcode console (iOS): "Authorization failure" means the key, package/SHA-1/bundle id or enabled API is wrong.

## Verification checklist (device/emulator)
1. Explore -> map icon: markers appear for venues with coordinates, tapping one shows a card (Directions / View).
2. Venue details: small map with marker above the Directions button.
3. My location button: permission prompt, then blue dot; deny shows the message.
4. Owner -> venue form -> **Pick on map**: pan under the pin, confirm, latitude/longitude fill in.
