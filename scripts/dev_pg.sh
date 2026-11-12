#!/usr/bin/env bash
# Starts/stops a THROWAWAY local PostgreSQL (no Docker needed) for backend tests.
# NOT Supabase. Usage: scripts/dev_pg.sh start|stop|url
set -euo pipefail
PGBIN="${PGBIN:-$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | tail -1)}"
D="${ZURUV_PG_DIR:-/tmp/zuruv_pg}"; PORT="${ZURUV_PG_PORT:-54399}"
run() { if [ "$(id -u)" = 0 ]; then su pgtmp -c "$1"; else bash -c "$1"; fi; }
case "${1:-}" in
  start)
    if [ "$(id -u)" = 0 ]; then id pgtmp >/dev/null 2>&1 || useradd -m pgtmp; fi
    if [ ! -d "$D/data" ]; then
      mkdir -p "$D"; [ "$(id -u)" = 0 ] && chown pgtmp "$D"
      run "$PGBIN/initdb -D $D/data -A trust -U zt >/dev/null"
    fi
    run "$PGBIN/pg_ctl -D $D/data -o '-p $PORT -k /tmp' -l $D/log -w start" >/dev/null
    echo "postgresql://zt@127.0.0.1:$PORT/postgres" ;;
  stop) run "$PGBIN/pg_ctl -D $D/data stop -m fast" ;;
  url) echo "postgresql://zt@127.0.0.1:$PORT/postgres" ;;
  *) echo "usage: $0 start|stop|url"; exit 1 ;;
esac
