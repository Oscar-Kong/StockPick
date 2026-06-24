"""Normalize and validate OHLC history frames for screening."""
from __future__ import annotations

from typing import Any

import pandas as pd

from data.history_freshness import assess_history_freshness
from data.price_service import PERIOD_MIN_BARS

OHLC_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def normalize_ohlc_history(df: pd.DataFrame | None, *, copy: bool = True) -> pd.DataFrame | None:
    """Validate columns, coerce types, sort by date ascending, and return a safe copy."""
    if df is None or df.empty:
        return None

    work = df.copy() if copy else df
    rename = {c: c.lower() for c in work.columns if isinstance(c, str)}
    if rename:
        work = work.rename(columns=rename)

    missing = [col for col in OHLC_COLUMNS if col not in work.columns]
    if missing:
        return None

    work = work[list(OHLC_COLUMNS)].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    for col in ("open", "high", "low", "close", "volume"):
        work[col] = pd.to_numeric(work[col], errors="coerce")

    work = work.dropna(subset=["date", "close"]).sort_values("date")
    if work.empty:
        return None

    return work.reset_index(drop=True)


def validate_preloaded_history(
    df: pd.DataFrame | None,
    period: str,
    *,
    require_fresh: bool = False,
    min_bars: int | None = None,
) -> tuple[bool, str | None, pd.DataFrame | None]:
    """Return (ok, rejection_reason, normalized_frame)."""
    normalized = normalize_ohlc_history(df)
    if normalized is None or normalized.empty:
        return False, "invalid_or_empty_history", None

    required_bars = min_bars if min_bars is not None else PERIOD_MIN_BARS.get(period, 100)
    if len(normalized) < max(required_bars, 3):
        return False, "insufficient_history", normalized

    last_close = float(normalized["close"].iloc[-1])
    if last_close <= 0:
        return False, "invalid_price", normalized

    freshness = assess_history_freshness(normalized, required_bars, source="stage_a_bulk")
    if not freshness.is_sufficient:
        return False, "insufficient_history", normalized
    if require_fresh and not freshness.is_fresh:
        return False, "stale_history", normalized

    return True, None, normalized
