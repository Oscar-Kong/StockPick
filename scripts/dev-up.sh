#!/usr/bin/env bash
set -euo pipefail

# Starts backend + frontend development servers in background.
# Logs and PID files are stored under storage/dev/.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
STATE_DIR="$ROOT_DIR/storage/dev"
PID_FILE="$STATE_DIR/dev-up.pids"
BACKEND_LOG="$STATE_DIR/backend.log"
FRONTEND_LOG="$STATE_DIR/frontend.log"

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-18731}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-18730}"

mkdir -p "$STATE_DIR"

is_running() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

check_required_cmds() {
  for cmd in lsof nohup npm; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      echo "Missing required command: $cmd"
      exit 1
    fi
  done
}

cleanup_frontend_lock() {
  local lock_file="$FRONTEND_DIR/.next/dev/lock"
  [[ -f "$lock_file" ]] || return 0

  local lock_pid
  lock_pid="$(python3 - <<PY
import json
from pathlib import Path
p = Path("$lock_file")
try:
    obj = json.loads(p.read_text(encoding="utf-8"))
    print(obj.get("pid",""))
except Exception:
    print("")
PY
)"

  if [[ -n "$lock_pid" ]] && is_running "$lock_pid"; then
    echo "Found existing Next dev process (PID $lock_pid) from lock file; stopping it..."
    kill "$lock_pid" >/dev/null 2>&1 || true
    sleep 1
    if is_running "$lock_pid"; then
      kill -9 "$lock_pid" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "$lock_file"
}

wait_for_start() {
  local name="$1"
  local pid="$2"
  local port="$3"
  local log="$4"
  local tries=20

  for _ in $(seq 1 "$tries"); do
    if ! is_running "$pid"; then
      echo "$name exited during startup. Last log lines:"
      tail -n 40 "$log" || true
      return 1
    fi
    if port_in_use "$port"; then
      return 0
    fi
    sleep 0.5
  done

  echo "$name did not bind port $port in time. Last log lines:"
  tail -n 40 "$log" || true
  return 1
}

check_required_cmds

if [[ -f "$PID_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$PID_FILE"
  stale=0
  if [[ -n "${BACKEND_PID:-}" ]] && is_running "$BACKEND_PID"; then
    echo "Backend already running (PID $BACKEND_PID)."
    echo "Run scripts/dev-down.sh first if you want a restart."
    exit 1
  elif [[ -n "${BACKEND_PID:-}" ]]; then
    stale=1
  fi
  if [[ -n "${FRONTEND_PID:-}" ]] && is_running "$FRONTEND_PID"; then
    echo "Frontend already running (PID $FRONTEND_PID)."
    echo "Run scripts/dev-down.sh first if you want a restart."
    exit 1
  elif [[ -n "${FRONTEND_PID:-}" ]]; then
    stale=1
  fi
  if [[ "$stale" -eq 1 ]]; then
    echo "Clearing stale PID file (previous dev processes are not running)."
    rm -f "$PID_FILE" "$STATE_DIR/backend.pid" "$STATE_DIR/frontend.pid"
  fi
fi

if port_in_use "$BACKEND_PORT"; then
  echo "Backend port $BACKEND_PORT is already in use."
  echo "Choose another port: BACKEND_PORT=xxxxx ./scripts/dev-up.sh"
  exit 1
fi
if port_in_use "$FRONTEND_PORT"; then
  echo "Frontend port $FRONTEND_PORT is already in use."
  echo "Choose another port: FRONTEND_PORT=xxxxx ./scripts/dev-up.sh"
  exit 1
fi

if [[ -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  BACKEND_PY="$BACKEND_DIR/.venv/bin/python"
else
  BACKEND_PY="python3"
fi

cleanup_frontend_lock

echo "Starting backend on http://$BACKEND_HOST:$BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  # Watch only app code — not .venv/ (18k+ files) or data_store (avoids reload/CPU spikes).
  nohup "$BACKEND_PY" -m uvicorn main:app --reload \
    --reload-dir "$BACKEND_DIR" \
    --reload-exclude '.venv/*' \
    --reload-exclude 'data_store/*' \
    --reload-exclude '**/__pycache__/*' \
    --reload-exclude '.ruff_cache/*' \
    --host "$BACKEND_HOST" --port "$BACKEND_PORT" >>"$BACKEND_LOG" 2>&1 &
  echo $! >"$STATE_DIR/backend.pid"
)
BACKEND_PID="$(cat "$STATE_DIR/backend.pid")"

echo "Starting frontend on http://$FRONTEND_HOST:$FRONTEND_PORT ..."
(
  cd "$FRONTEND_DIR"
  export NEXT_PUBLIC_API_URL="http://$BACKEND_HOST:$BACKEND_PORT"
  export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=4096}"
  nohup npm run dev >>"$FRONTEND_LOG" 2>&1 &
  echo $! >"$STATE_DIR/frontend.pid"
)
FRONTEND_PID="$(cat "$STATE_DIR/frontend.pid")"

if ! wait_for_start "Backend" "$BACKEND_PID" "$BACKEND_PORT" "$BACKEND_LOG"; then
  exit 1
fi
if ! wait_for_start "Frontend" "$FRONTEND_PID" "$FRONTEND_PORT" "$FRONTEND_LOG"; then
  exit 1
fi

cat >"$PID_FILE" <<EOF
BACKEND_PID=$BACKEND_PID
FRONTEND_PID=$FRONTEND_PID
EOF

sleep 1
echo ""
echo "Started:"
echo "  Backend PID:  $BACKEND_PID"
echo "  Frontend PID: $FRONTEND_PID"
echo "  App URL:      http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "  API URL:      http://$BACKEND_HOST:$BACKEND_PORT"
echo ""
echo "Logs:"
echo "  $BACKEND_LOG"
echo "  $FRONTEND_LOG"
echo ""
echo "Stop both with: scripts/dev-down.sh"
