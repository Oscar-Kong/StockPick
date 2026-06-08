#!/usr/bin/env bash
# Run penny / medium / compounder scans with ScoringEngine Stage B (parity mode).
# Does not edit .env — exports staging flags for this process only.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/scripts/staging-scan-engine.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

export USE_SCORING_ENGINE_IN_SCAN="${USE_SCORING_ENGINE_IN_SCAN:-true}"
export APP_ENV="${APP_ENV:-staging}"
export SCORE_ENGINE_V2_ENABLED="${SCORE_ENGINE_V2_ENABLED:-true}"
export PERSIST_SCORE_ATTRIBUTION="${PERSIST_SCORE_ATTRIBUTION:-true}"
export OPENBB_ON_SCAN="${OPENBB_ON_SCAN:-false}"
export STAGING_SCAN_MODE="${STAGING_SCAN_MODE:-cached}"

if [[ "${1:-}" == "--full" ]]; then
  STAGING_SCAN_MODE=full
  shift
elif [[ "${1:-}" == "--cached" ]]; then
  STAGING_SCAN_MODE=cached
  shift
fi

cd "$ROOT_DIR/backend"

PYTHON="python3"
if [[ -x .venv/bin/python ]]; then
  PYTHON=".venv/bin/python"
fi

mkdir -p "$ROOT_DIR/storage/staging"

echo "=== Staging scan parity (USE_SCORING_ENGINE_IN_SCAN=$USE_SCORING_ENGINE_IN_SCAN mode=$STAGING_SCAN_MODE) ==="
echo "Python: $PYTHON"
STAGING_SCAN_MODE="$STAGING_SCAN_MODE" "$PYTHON" scripts/run_staging_scan_parity.py --mode "$STAGING_SCAN_MODE" "$@"
