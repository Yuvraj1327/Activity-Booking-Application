#!/usr/bin/env bash
# Copies the Google Maps SDK keys from the app's root .env into the two git-ignored native config
# files, because the Android/iOS Maps SDKs start before Flutter and cannot read the dotenv asset.
#   android/secrets.properties        -> read by android/app/build.gradle.kts (manifest placeholder)
#   ios/Flutter/Secrets.xcconfig      -> included by Debug/Release.xcconfig (Info.plist GMSApiKey)
# Run it after editing .env:  ./tool/sync_native_keys.sh
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "No .env found. Run: cp .env.example .env" >&2; exit 1; }

get() { grep -E "^$1=" .env | head -n1 | cut -d= -f2- | tr -d '\r"' | xargs || true; }

ANDROID_KEY="$(get GOOGLE_MAPS_API_KEY_ANDROID)"
IOS_KEY="$(get GOOGLE_MAPS_API_KEY_IOS)"

# Google Sign-In (iOS) needs the REVERSED iOS client id as a URL scheme:
#   123-abc.apps.googleusercontent.com  ->  com.googleusercontent.apps.123-abc
GOOGLE_IOS_CLIENT_ID="$(get GOOGLE_IOS_CLIENT_ID)"
if [ -n "$GOOGLE_IOS_CLIENT_ID" ]; then
  REVERSED="com.googleusercontent.apps.${GOOGLE_IOS_CLIENT_ID%.apps.googleusercontent.com}"
else
  REVERSED="com.zuruv.zuruv.google-not-configured"
  echo "warning: GOOGLE_IOS_CLIENT_ID is empty (native Google sign-in will not work on iOS)" >&2
fi

printf 'GOOGLE_MAPS_API_KEY_ANDROID=%s\n' "$ANDROID_KEY" > android/secrets.properties
{
  printf 'GOOGLE_MAPS_API_KEY_IOS=%s\n' "$IOS_KEY"
  printf 'GOOGLE_IOS_REVERSED_CLIENT_ID=%s\n' "$REVERSED"
} > ios/Flutter/Secrets.xcconfig

[ -n "$ANDROID_KEY" ] || echo "warning: GOOGLE_MAPS_API_KEY_ANDROID is empty (Android maps will show a grey tile)" >&2
[ -n "$IOS_KEY" ] || echo "warning: GOOGLE_MAPS_API_KEY_IOS is empty (iOS maps will show a grey tile)" >&2
echo "Native map keys synced from .env."
