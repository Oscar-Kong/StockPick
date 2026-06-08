"""Liquidity penalty by market cap tier and volume."""
from __future__ import annotations

from typing import Any


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        v = float(val)
        return default if v != v else v
    except (TypeError, ValueError):
        return default


def liquidity_penalty(
    info: dict[str, Any],
    *,
    avg_volume: float | None = None,
    price: float | None = None,
) -> tuple[float, str]:
    """Return penalty points (0–15) and rationale."""
    mcap = _safe_float(info.get("marketCap") or info.get("market_cap"))
    vol = avg_volume or _safe_float(info.get("averageVolume") or info.get("averageVolume10days"))
    px = price or _safe_float(info.get("currentPrice") or info.get("regularMarketPrice") or info.get("price"))

    penalty = 0.0
    reasons: list[str] = []

    dollar_vol = vol * px if vol and px else 0.0

    if mcap >= 10_000_000_000:
        tier = "large"
    elif mcap >= 2_000_000_000:
        tier = "mid"
    elif mcap >= 300_000_000:
        tier = "small"
    else:
        tier = "micro"
        penalty += 8.0
        reasons.append("Micro-cap liquidity risk")

    if dollar_vol < 5_000_000:
        penalty += 6.0
        reasons.append("Low average dollar volume")
    elif dollar_vol < 20_000_000:
        penalty += 3.0
        reasons.append("Moderate dollar volume")

    if tier == "small":
        penalty += 2.0
    elif tier == "mid":
        penalty += 1.0

    penalty = min(15.0, penalty)
    rationale = "; ".join(reasons) if reasons else f"{tier}-cap, acceptable liquidity"
    return round(penalty, 2), rationale


def transaction_cost_bps(info: dict[str, Any]) -> float:
    """Estimated round-trip cost in basis points."""
    mcap = _safe_float(info.get("marketCap") or info.get("market_cap"))
    if mcap >= 10_000_000_000:
        return 7.5
    if mcap >= 2_000_000_000:
        return 17.5
    if mcap >= 300_000_000:
        return 50.0
    return 75.0
