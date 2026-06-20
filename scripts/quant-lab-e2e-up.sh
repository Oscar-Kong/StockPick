#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT="${QUANT_LAB_E2E_BACKEND_PORT:-18931}"
FRONTEND_PORT="${QUANT_LAB_E2E_FRONTEND_PORT:-18930}"
DB_PATH="$ROOT/storage/dev/quant_lab_e2e.db"

export DATABASE_URL="sqlite:///$DB_PATH"
export NEXT_PUBLIC_API_URL="http://127.0.0.1:${BACKEND_PORT}"

cd "$ROOT/backend"
python scripts/seed_quant_lab_demo.py --db "$DB_PATH" --sleeve medium >/dev/null
source .venv/bin/activate 2>/dev/null || true
python -m uvicorn main:app --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null; then
    break
  fi
  sleep 0.5
done

cd "$ROOT/frontend"
export NEXT_PUBLIC_API_URL="http://127.0.0.1:${BACKEND_PORT}"
if [[ ! -f .next/BUILD_ID ]]; then
  npm run build
fi
npx next start --hostname 127.0.0.1 --port "$FRONTEND_PORT"
