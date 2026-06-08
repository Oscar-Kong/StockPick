#!/usr/bin/env bash
set -euo pipefail

# Stops backend + frontend processes started by scripts/dev-up.sh.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT_DIR/storage/dev"
PID_FILE="$STATE_DIR/dev-up.pids"

is_running() {
  local pid="$1"
  kill -0 "$pid" >/dev/null 2>&1
}

if [[ ! -f "$PID_FILE" ]]; then
  echo "No PID file found at $PID_FILE"
  echo "If processes are still running, stop them manually."
  exit 0
fi

# shellcheck disable=SC1090
source "$PID_FILE"

stop_one() {
  local name="$1"
  local pid="$2"
  if [[ -z "$pid" ]]; then
    return
  fi
  if is_running "$pid"; then
    echo "Stopping $name (PID $pid)..."
    kill "$pid" >/dev/null 2>&1 || true
    sleep 0.5
    if is_running "$pid"; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  else
    echo "$name already stopped (PID $pid not running)."
  fi
}

stop_one "backend" "${BACKEND_PID:-}"
stop_one "frontend" "${FRONTEND_PID:-}"

rm -f "$PID_FILE" "$STATE_DIR/backend.pid" "$STATE_DIR/frontend.pid"
rm -f "$ROOT_DIR/frontend/.next/dev/lock"
echo "Done."
