"""Partial-data fallback scoring for Scan when strict filters reject all candidates."""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_partial_data_fallback_score(history: pd.DataFrame | None) -> float | None:
    """Momentum/volume heuristic used only when provider data is limited."""
    if history is None or history.empty or len(history) < 21:
        return None
    try:
        close = history["close"]
        vol = history["volume"]
        ret_20 = float(close.iloc[-1] / close.iloc[-20] - 1.0) * 100.0
        vol_ratio = float(vol.tail(5).mean() / max(vol.tail(20).mean(), 1.0))
        return max(0.0, min(100.0, 50.0 + (ret_20 * 1.8) + ((vol_ratio - 1.0) * 12.0)))
    except Exception as exc:
        logger.warning("Fallback score skipped: %s", exc)
        return None
