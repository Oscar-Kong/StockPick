"""Named entry-rule variants for bucket backtests (awesome-quant style presets)."""
from __future__ import annotations

from typing import Callable

import pandas as pd

from scoring.fundamental import revenue_eps_consistency_score, roic_margin_stability_score
from scoring.technical import (
    adx_score,
    bollinger_lower_touch_score,
    breakout_score,
    golden_cross_score,
    macd_rsi_confluence_score,
    momentum_score,
    relative_strength_vs_spy,
    trend_score,
    volume_spike_score,
)

EntryFn = Callable[[pd.DataFrame, pd.DataFrame, int], bool]

# (bucket, variant_id) -> human label
ENTRY_VARIANT_LABELS: dict[tuple[str, str], str] = {
    ("penny", "default"): "Momentum + volume (default)",
    ("penny", "macd_rsi"): "MACD + RSI confluence",
    ("penny", "bollinger_revert"): "Bollinger lower-band bounce",
    ("medium", "default"): "Trend / breakout + RS vs SPY",
    ("medium", "adx_trend"): "ADX-confirmed trend + RS",
    ("medium", "dual_ma"): "Dual MA (50/200) + breakout",
    ("compounder", "default"): "Uptrend (SMA50 proxy)",
    ("compounder", "quality_momentum"): "Quality gate + trend",
    ("compounder", "golden_cross"): "Golden cross + trend",
}


def list_entry_variants(bucket: str) -> list[dict[str, str]]:
    return [
        {"id": vid, "label": ENTRY_VARIANT_LABELS.get((bucket, vid), vid)}
        for b, vid in ENTRY_VARIANT_LABELS
        if b == bucket
    ]


def _penny_default(window: pd.DataFrame, _spy: pd.DataFrame, _idx: int) -> bool:
    return momentum_score(window, days=5) >= 65 and volume_spike_score(window) >= 60


def _penny_macd_rsi(window: pd.DataFrame, _spy: pd.DataFrame, _idx: int) -> bool:
    return macd_rsi_confluence_score(window) >= 65 and volume_spike_score(window) >= 50


def _penny_bollinger(window: pd.DataFrame, _spy: pd.DataFrame, _idx: int) -> bool:
    return bollinger_lower_touch_score(window) >= 70 and volume_spike_score(window) >= 55


def _medium_default(window: pd.DataFrame, spy_window: pd.DataFrame, _idx: int) -> bool:
    t = trend_score(window)
    b = breakout_score(window)
    rs = relative_strength_vs_spy(window, spy_window, days=20)
    return (t >= 60 or b >= 70) and rs >= 55


def _medium_adx(window: pd.DataFrame, spy_window: pd.DataFrame, _idx: int) -> bool:
    return (
        adx_score(window) >= 60
        and trend_score(window) >= 55
        and relative_strength_vs_spy(window, spy_window, days=20) >= 50
    )


def _medium_dual_ma(window: pd.DataFrame, spy_window: pd.DataFrame, _idx: int) -> bool:
    return golden_cross_score(window) >= 55 and relative_strength_vs_spy(window, spy_window, days=20) >= 52


def _compounder_default(window: pd.DataFrame, _spy: pd.DataFrame, _idx: int) -> bool:
    return trend_score(window) >= 55


def _compounder_quality_momentum(
    window: pd.DataFrame,
    _spy: pd.DataFrame,
    _idx: int,
    *,
    info: dict | None = None,
    fundamentals: dict | None = None,
) -> bool:
    if trend_score(window) < 50:
        return False
    if info and fundamentals:
        rev = float(revenue_eps_consistency_score(info, fundamentals))
        roic = float(roic_margin_stability_score(info, fundamentals))
        return rev >= 50 and roic >= 50
    return trend_score(window) >= 60


def _compounder_golden_cross(window: pd.DataFrame, _spy: pd.DataFrame, _idx: int) -> bool:
    return golden_cross_score(window) >= 60 and trend_score(window) >= 50


_REGISTRY: dict[tuple[str, str], EntryFn] = {
    ("penny", "default"): _penny_default,
    ("penny", "macd_rsi"): _penny_macd_rsi,
    ("penny", "bollinger_revert"): _penny_bollinger,
    ("medium", "default"): _medium_default,
    ("medium", "adx_trend"): _medium_adx,
    ("medium", "dual_ma"): _medium_dual_ma,
    ("compounder", "default"): _compounder_default,
    ("compounder", "golden_cross"): _compounder_golden_cross,
}


def get_entry_fn(
    bucket: str,
    variant: str | None = None,
    *,
    info: dict | None = None,
    fundamentals: dict | None = None,
) -> tuple[EntryFn, str]:
    """Resolve entry function; compounder quality_momentum needs fundamentals closure."""
    vid = (variant or "default").strip().lower()
    if bucket == "compounder" and vid == "quality_momentum":

        def _wrapped(window: pd.DataFrame, spy: pd.DataFrame, idx: int) -> bool:
            return _compounder_quality_momentum(
                window, spy, idx, info=info, fundamentals=fundamentals
            )

        return _wrapped, "quality_momentum"

    key = (bucket, vid)
    if key not in _REGISTRY:
        vid = "default"
        key = (bucket, vid)
    return _REGISTRY[key], vid
