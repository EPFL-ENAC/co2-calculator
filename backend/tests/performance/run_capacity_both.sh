#!/usr/bin/env bash
# Re-run the capacity ladder against BOTH databases with the fixed sampler
# (#2295). Same backend (2 uvicorn workers ≈ 2 pods' connection budget) for
# both phases, so the local-vs-dev delta is purely the database.
#
# Switching DB_URL means editing backend/.env: dotenv wins over inline env
# vars in this project, so an inline DB_URL= would be silently ignored.
#
# Usage: bash tests/performance/run_capacity_both.sh
set -uo pipefail
trap 'echo "aborted — check $ENV_FILE against its backup" >&2' ERR
cd "$(dirname "$0")/../.." || exit 1

ENV_FILE=.env
REPORTS=tests/performance/reports
PORT=8010
HOST="http://127.0.0.1:$PORT"
# Never hardcode a DSN here: this repo is public. Supply both via the
# environment, e.g. from a local untracked file you source before running.
: "${LOCAL_URL:?set LOCAL_URL to the local postgres DSN}"
: "${DEV_URL:?set DEV_URL to the remote DSN (do not commit it)}"

backup=$(mktemp)
cp "$ENV_FILE" "$backup"
echo "env backed up to $backup"

set_db_url() {
  python3 - "$ENV_FILE" "$1" <<'PY'
import sys
path, url = sys.argv[1], sys.argv[2]
lines = open(path).read().splitlines()
out, done = [], False
for line in lines:
    if line.startswith("DB_URL=") and not done:
        out.append(f"DB_URL={url}")
        done = True
    elif line.startswith("DB_URL="):
        out.append("# " + line)
    else:
        out.append(line)
open(path, "w").write("\n".join(out) + "\n")
PY
}

start_backend() {
  [ -f "$REPORTS/uvicorn-$PORT.pid" ] && kill "$(cat "$REPORTS/uvicorn-$PORT.pid")" 2>/dev/null
  pkill -f "uvicorn app.main:app --host 127.0.0.1 --port $PORT" 2>/dev/null
  sleep 3
  nohup uv run uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --workers 2 \
    > "$REPORTS/uvicorn-$PORT-$1.log" 2>&1 &
  echo $! > "$REPORTS/uvicorn-$PORT.pid"
  for _ in $(seq 1 60); do
    curl -sf -o /dev/null "$HOST/openapi.json" && { echo "backend up ($1)"; return 0; }
    sleep 2
  done
  echo "BACKEND FAILED TO START ($1); last log lines:"; tail -5 "$REPORTS/uvicorn-$PORT-$1.log"
  return 1
}

run_ladder() {
  local prefix=$1
  for u in 50 100 200 500 1000; do
    echo "=== $prefix reads @$u"
    make perf-load PERF_HOST="$HOST" PERF_USERS=$u \
      PERF_CLASSES=ExplorerReadUser PERF_TAG="${prefix}_read_$u"
  done
  echo "=== $prefix module reads @1000"
  make perf-load PERF_HOST="$HOST" PERF_USERS=1000 \
    PERF_CLASSES=ModuleReadUser PERF_TAG="${prefix}_module_1000"
}

echo "########## PHASE 1: local docker postgres ##########"
set_db_url "$LOCAL_URL"
if start_backend local; then run_ladder loc; else echo "SKIPPED local ladder"; fi

echo "########## PHASE 2: remote dev postgres ##########"
set_db_url "$DEV_URL"
if start_backend dev; then run_ladder devdb; else echo "SKIPPED dev ladder"; fi

echo "########## CAPACITY TABLE ##########"
make perf-capacity

# Leave .env as the session found it (dev), and say so out loud.
set_db_url "$DEV_URL"
echo "env restored to DEV DB_URL (backup: $backup)"
echo "CAPACITY_BOTH_DONE"
