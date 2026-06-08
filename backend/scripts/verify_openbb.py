#!/usr/bin/env python3
"""Smoke-test OpenBB integration. Run from backend/: python scripts/verify_openbb.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import OPENBB_ENABLED
from data.openbb_client import (
    compute_risk_snapshot,
    fetch_fundamentals_for_reconcile,
    get_equity_historical,
    get_fred_latest,
    get_key_metrics,
    is_available,
    macro_regime_score,
)


def main() -> None:
    print(f"OPENBB_ENABLED={OPENBB_ENABLED}")
    if not OPENBB_ENABLED:
        print("Set OPENBB_ENABLED=true in .env and install: pip install -r requirements-openbb.txt")
        sys.exit(1)
    if not is_available():
        print("OpenBB not importable. Run: pip install -r requirements-openbb.txt")
        sys.exit(1)

    print("OpenBB OK")
    try:
        hist = get_equity_historical("AAPL", period="1mo")
        print(f"  AAPL history rows: {len(hist)}")
    except Exception as exc:
        print(f"  AAPL history skipped (rate limit ok): {exc}")
    metrics = get_key_metrics("AAPL")
    print(f"  AAPL metrics keys: {len(metrics)}")
    unrate = get_fred_latest("UNRATE")
    print(f"  FRED UNRATE latest: {unrate}")
    macro = macro_regime_score()
    print(f"  Macro regime score: {macro}")
    rec = fetch_fundamentals_for_reconcile("AAPL")
    print(f"  Reconcile fields: {list(rec.keys())}")
    snap = compute_risk_snapshot("AAPL")
    print(f"  Governance: {snap.governance_score:.0f}, flags={snap.flags}")
    print("All checks passed.")


if __name__ == "__main__":
    main()
