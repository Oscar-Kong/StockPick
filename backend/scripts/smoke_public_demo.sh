#!/usr/bin/env bash
# Local public-demo smoke test (no real account data).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
DB="$ROOT/backend/data/smoke_public_demo.db"
rm -f "$DB"
export APP_ENV=production
export DEMO_MODE=true
export DEMO_SEED_DATA=true
export DATABASE_URL="sqlite:///$DB"
export ALLOWED_ORIGINS="https://example-stockpick.vercel.app"
export SCHEDULER_ENABLED=false
export LISTING_MASTER_ENABLED=false
cd "$BACKEND"
python -m uvicorn main:app --host 127.0.0.1 --port 8765 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
sleep 3
BASE="http://127.0.0.1:8765"
curl -sf "$BASE/health" | grep -q '"status":"ok"'
curl -sf "$BASE/health/ready" | grep -q '"database":"available"'
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/brokerage/import/robinhood-csv" -F "file=@/dev/null")
test "$code" = "403" || test "$code" = "422"
curl -s -H "Origin: https://evil.example" "$BASE/health" | grep -q ok
echo "smoke ok"
