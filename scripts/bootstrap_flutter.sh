#!/usr/bin/env bash
# Generates the native Android/iOS runners for both apps and fetches dependencies.
# Run once after cloning (needs Flutter >= 3.27 on your PATH). Existing lib/ and
# pubspec.yaml are kept; `flutter create .` only adds the missing platform folders.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

command -v flutter >/dev/null || { echo "Flutter SDK not found on PATH"; exit 1; }

(cd "$ROOT/packages/flutter_shared" && flutter pub get)

bootstrap() { # dir project_name org_suffix
  (cd "$ROOT/apps/$1" \
    && flutter create --platforms=android,ios --org com.zuruv --project-name "$2" . \
    && flutter pub get)
}
bootstrap customer_app zuruv_customer
bootstrap owner_app zuruv_owner

# Location / photo permissions and the auth deep link for the Customer app.
python3 "$ROOT/scripts/configure_customer_platforms.py"

echo "Done. Copy apps/*/env/dev.example.json to dev.json, then:"
echo "  cd apps/customer_app && flutter run --dart-define-from-file=env/dev.json"
