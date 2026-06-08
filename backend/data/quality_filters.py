"""Centralized stock quality filters — OTC, liquidity, delisting, penny rules."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from config import (
    MEDIUM_MIN_VOLUME,
    MEDIUM_PRICE_MIN,
    MIN_HISTORY_BARS,
    PENNY_MIN_VOLUME,
    PENNY_PRICE_MAX,
    PENNY_PRICE_MIN,
)


@dataclass
class QualityFilterResult:
    passed: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "reasons": self.reasons}


def is_otc_symbol(symbol: str, info: dict | None = None) -> bool:
    sym = symbol.upper().strip()
    if any(sym.endswith(s) for s in OTC_SUFFIXES):
        return True
    if info:
        exchange = (info.get("exchange") or info.get("fullExchangeName") or "").lower()
        if any(kw in exchange for kw in OTC_EXCHANGE_KEYWORDS):
            return True
        quote_type = (info.get("quoteType") or "").upper()
        if quote_type in ("OTC", "PINK"):
            return True
    return False


def is_likely_delisted(
    symbol: str,
    history: pd.DataFrame | None,
    info: dict | None = None,
) -> bool:
    if history is None or history.empty:
        return True
    if len(history) < 10:
        return True
    last_close = float(history["close"].iloc[-1])
    if last_close <= 0:
        return True
    # Stale data: no bar in last 30 calendar days
    last_date = pd.to_datetime(history["date"].iloc[-1])
    if (pd.Timestamp.now() - last_date).days > 30:
        return True
    if info:
        status = (info.get("regularMarketPrice") or info.get("currentPrice") or 0)
        if status == 0 and last_close > 0:
            pass  # may still be valid from history
    return False


def check_liquidity(
    history: pd.DataFrame,
    min_avg_volume: float,
    lookback: int = 20,
) -> bool:
    if history.empty or len(history) < 5:
        return False
    tail = history["volume"].tail(min(lookback, len(history)))
    avg_vol = float(tail.mean())
    return avg_vol >= min_avg_volume


def apply_quality_filters(
    symbol: str,
    bucket: Bucket,
    price: float,
    history: pd.DataFrame | None,
    info: dict | None = None,
    *,
    min_volume: float | None = None,
    allow_penny: bool = True,
) -> QualityFilterResult:
    """Apply fixed rules to exclude low-quality names before scoring."""
    reasons: list[str] = []

    if is_otc_symbol(symbol, info):
        reasons.append("OTC/pink-sheet excluded")

    if is_likely_delisted(symbol, history, info):
        reasons.append("Delisted or stale price history")

    required_bars = MIN_HISTORY_BARS
    if bucket == Bucket.penny:
        required_bars = min(80, MIN_HISTORY_BARS)
    elif bucket == Bucket.medium:
        required_bars = min(90, MIN_HISTORY_BARS)

    if history is None or history.empty or len(history) < required_bars:
        reasons.append(f"Insufficient history (<{required_bars} bars)")

    if bucket == Bucket.penny:
        if not allow_penny and price < PENNY_PRICE_MAX:
            reasons.append("Penny stock excluded for this bucket")
        if not (PENNY_PRICE_MIN <= price <= PENNY_PRICE_MAX):
            reasons.append(f"Price outside penny range ({PENNY_PRICE_MIN}-{PENNY_PRICE_MAX})")
        vol_thresh = min_volume or PENNY_MIN_VOLUME
    elif bucket == Bucket.medium:
        if price < MEDIUM_PRICE_MIN:
            reasons.append(f"Price below medium minimum ({MEDIUM_PRICE_MIN})")
        vol_thresh = min_volume or MEDIUM_MIN_VOLUME
    else:
        vol_thresh = min_volume or 500_000

    if history is not None and not history.empty:
        if not check_liquidity(history, vol_thresh):
            reasons.append(f"Low liquidity (avg volume < {vol_thresh:,.0f})")

    return QualityFilterResult(passed=len(reasons) == 0, reasons=reasons)
