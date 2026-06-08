"""Scan pick summary tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_rule_based_pick_summary():
    from services.scan_pick_summary import generate_scan_pick_summary

    out = generate_scan_pick_summary(
        symbol="AAPL",
        bucket="medium",
        score=72.5,
        summary="Apple Inc — consumer electronics.",
        signals=[{"name": "rs_vs_spy", "value": 80, "contribution": 12}],
        metrics={"business_line": "Designs smartphones and services.", "theme_module": "Technology"},
    )
    assert out["symbol"] == "AAPL"
    assert "background" in out and out["background"]
    assert "why_picked" in out and "72" in out["why_picked"]
    assert out["source"] in ("rules", "llm")


if __name__ == "__main__":
    test_rule_based_pick_summary()
    print("scan pick summary ok")
