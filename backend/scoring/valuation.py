"""Valuation warnings for medium and compounder buckets."""
from __future__ import annotations

from typing import Any


def _safe(value: Any) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
        return None if v != v else v  # NaN check
    except (TypeError, ValueError):
        return None


def valuation_warnings(info: dict, fundamentals: dict | None = None) -> list[str]:
    """Return human-readable valuation flags."""
    fundamentals = fundamentals or {}
    warnings: list[str] = []

    pe = _safe(info.get("trailingPE")) or _safe(fundamentals.get("pe_ratio"))
    peg = _safe(fundamentals.get("peg_ratio"))
    rev_growth = _safe(info.get("revenueGrowth"))
    earnings_growth = _safe(info.get("earningsGrowth"))

    if pe is not None:
        if pe > 60:
            warnings.append(f"Very high P/E ({pe:.1f}) — priced for perfection")
        elif pe > 40:
            warnings.append(f"Elevated P/E ({pe:.1f}) — check growth justifies multiple")
        elif pe < 0:
            warnings.append("Negative P/E — unprofitable on trailing earnings")

    if peg is not None and peg > 2.5:
        warnings.append(f"High PEG ({peg:.2f}) — growth may not justify price")

    if rev_growth is not None and rev_growth < 0.03 and (earnings_growth or 0) < 0.03:
        warnings.append("Slow revenue/EPS growth vs quality compounder profile")

    if pe and pe > 35 and rev_growth and rev_growth < 0.10:
        warnings.append("High multiple with modest revenue growth — valuation risk")

    return warnings
