#!/usr/bin/env bash
# Proves supabase/migrations/*.sql produce the SAME schema as the Alembic migrations.
# LOCAL / THROWAWAY Postgres only (never Supabase). Needs: psql, pg_dump, backend/.venv.
#   scripts/dev_pg.sh start            # from the repo root, once
#   supabase/verify_sync.sh [server-url]   # default postgresql://zt@127.0.0.1:54399/postgres
# Creates two scratch databases, builds one from the SQL files and one with `alembic upgrade head`
# (both on supabase/local/supabase_stub.sql), diffs schema + policies + grants, then drops both.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER="${1:-postgresql://zt@127.0.0.1:54399/postgres}"
PGBIN="${PGBIN:-$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | tail -1)}"
export PATH="$PGBIN:$PATH"
BASE="${SERVER%/*}"
A=zuruv_sync_sql_$$; B=zuruv_sync_alembic_$$
cleanup() { psql "$SERVER" -qc "DROP DATABASE IF EXISTS $A WITH (FORCE)" -c "DROP DATABASE IF EXISTS $B WITH (FORCE)" >/dev/null 2>&1 || true; rm -f /tmp/$A.dump /tmp/$B.dump; }
trap cleanup EXIT
psql "$SERVER" -qc "CREATE DATABASE $A" -c "CREATE DATABASE $B"
for d in $A $B; do psql "$BASE/$d" -q -v ON_ERROR_STOP=1 -f "$ROOT/supabase/local/supabase_stub.sql" >/dev/null; done
for f in "$ROOT"/supabase/migrations/0*.sql; do echo "applying $(basename "$f")"; psql "$BASE/$A" -q -v ON_ERROR_STOP=1 -f "$f"; done
( cd "$ROOT/backend" && . .venv/bin/activate && ALEMBIC_DATABASE_URL="$BASE/$B" alembic upgrade head >/dev/null 2>&1 )
for d in $A $B; do pg_dump "$BASE/$d" -s --no-owner --no-comments -n public -n storage -n auth | grep -v '^\\\(un\)\?restrict' > /tmp/$d.dump; done
if diff -u /tmp/$B.dump /tmp/$A.dump; then echo "IN SYNC: SQL files == Alembic head ($(psql "$BASE/$A" -Atc 'select version_num from public.alembic_version'))"; else echo "DRIFT: update the SQL files to match Alembic"; exit 1; fi
