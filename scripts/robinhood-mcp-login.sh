#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
source "$BACKEND/.venv/bin/activate"
cd "$BACKEND"
exec python scripts/robinhood_mcp_login.py "$@"
