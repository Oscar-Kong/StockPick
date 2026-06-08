#!/usr/bin/env bash
set -euo pipefail

# Smoke test for:
# 1) LLM explain/report paths
# 2) Trade screenshot upload + image analysis fields
#
# Usage:
#   ./scripts/test-llm-trade.sh
#   API_URL=http://127.0.0.1:8010 ./scripts/test-llm-trade.sh

API_URL="${API_URL:-http://127.0.0.1:18731}"

python3 - <<'PY'
import base64
import json
import os
from pathlib import Path

import requests

base = os.getenv("API_URL", "http://127.0.0.1:18731").rstrip("/")
print(f"API_URL {base}")

def p(label, value):
    print(f"{label} {value}")

# Health
h = requests.get(f"{base}/health", timeout=30)
p("HEALTH_STATUS", h.status_code)
if h.ok:
    hb = h.json()
    p("HEALTH_LLM_CONFIGURED", hb.get("llm_configured"))

# Pick a symbol from latest saved scan when available
symbol = "AAPL"
bucket = "medium"
try:
    s = requests.get(f"{base}/saved/scans?limit=1", timeout=30)
    if s.ok and s.json():
        row = s.json()[0]
        bucket = row.get("bucket", bucket)
        symbol = (row.get("results") or [{}])[0].get("symbol", symbol)
except Exception:
    pass
p("TEST_SYMBOL", f"{symbol} ({bucket})")

# Explain (LLM path with fallback)
e = requests.post(f"{base}/explain", json={"symbol": symbol, "bucket": bucket}, timeout=120)
p("EXPLAIN_STATUS", e.status_code)
if e.ok:
    ej = e.json()
    p("EXPLAIN_SOURCE", ej.get("source"))
    p("EXPLAIN_LEN", len(ej.get("explanation", "")))

# Report
r = requests.get(f"{base}/analyze/{symbol}/report?bucket={bucket}", timeout=120)
p("REPORT_STATUS", r.status_code)
if r.ok:
    rj = r.json()
    p("REPORT_HAS_ERROR", bool(rj.get("error")))

# Trade upload screenshot
img_path = Path("/tmp/trade_smoke.png")
img_path.write_bytes(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+R3sAAAAASUVORK5CYII="
    )
)
files = {"screenshot": ("trade_smoke.png", img_path.read_bytes(), "image/png")}
data = {
    "symbol": symbol,
    "side": "long",
    "entry_time": "2026-06-01T09:30:00",
    "entry_price": "100",
    "exit_price": "102",
    "quantity": "10",
    "stop_loss": "95",
    "take_profit": "110",
    "setup_tags": "smoke,test",
    "thesis": "Smoke test",
    "notes": "LLM report/trade upload smoke test",
}
u = requests.post(f"{base}/trades/upload", files=files, data=data, timeout=120)
p("TRADE_UPLOAD_STATUS", u.status_code)
if u.ok:
    uj = u.json()
    rv = uj.get("review", {})
    p("TRADE_ID", uj.get("id"))
    p("IMAGE_ANALYSIS_STATUS", rv.get("image_analysis_status"))
    p("IMAGE_TAGS", rv.get("image_tags"))
    p("IMAGE_INSIGHT", (rv.get("image_insight") or "")[:120])
else:
    p("TRADE_UPLOAD_BODY", u.text[:240])
PY
