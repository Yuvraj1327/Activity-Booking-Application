#!/usr/bin/env bash
# Seeds the e2e database through the real API (fake payment gateway), then serves the REAL FastAPI app on it.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
OUT="$HERE/../.stack"
mkdir -p "$OUT"
cd "$ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
python -m scripts.e2e_seed "$OUT" >"$OUT/seed.log" 2>&1 || { tail -30 "$OUT/seed.log"; exit 1; }
export DATABASE_URL="$(cat "$OUT/db_url.txt")"
export ENVIRONMENT=development LOG_JSON=false BACKGROUND_SWEEP_SECONDS=0
export SUPABASE_URL="https://e2e.supabase.co" SUPABASE_JWT_SECRET="${E2E_JWT_SECRET:?E2E_JWT_SECRET is required}"
export ADMIN_REQUIRE_MFA=true
exec uvicorn app.main:app --host 127.0.0.1 --port "${E2E_API_PORT:-8018}"
