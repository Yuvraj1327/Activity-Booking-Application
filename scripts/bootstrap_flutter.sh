#!/usr/bin/env bash
# Generates the native Android/iOS runners for the ZURUV mobile app and fetches dependencies.
# Run once after cloning (needs Flutter >= 3.27 on your PATH). Existing lib/ and
# pubspec.yaml are kept; `flutter create .` only adds the missing platform folders.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

command -v flutter >/dev/null || { echo "Flutter SDK not found on PATH"; exit 1; }

(cd "$ROOT/packages/flutter_shared" && flutter pub get)

(cd "$ROOT/apps/mobile_app" \
  && flutter create --platforms=android,ios --org com.zuruv --project-name zuruv . \
  && flutter pub get)

# Location / photo permissions and the auth deep link.
python3 "$ROOT/scripts/configure_mobile_platforms.py"

echo "Done. Copy apps/mobile_app/.env.example to apps/mobile_app/.env, then:"
echo "  cd apps/mobile_app && flutter run"
echo "Build (you deploy these yourself):  flutter build apk --release   |   flutter build appbundle --release"
