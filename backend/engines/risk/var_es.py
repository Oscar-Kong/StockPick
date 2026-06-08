"""Historical Value-at-Risk and Expected Shortfall."""
from __future__ import annotations

import numpy as np
import pandas as pd

from quant_core.returns import _as_returns_series

MIN_OBSERVATIONS = 20


def _clean(returns) -> np.ndarray:
    return _as_returns_series(returns).dropna().to_numpy()


def historical_var(returns, alpha: float = 0.05) -> float | None:
    """
    Historical VaR at tail probability `alpha`.

    Returns the alpha-quantile of returns (typically negative = loss).
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    arr = _clean(returns)
    if len(arr) < MIN_OBSERVATIONS:
        return None
    return float(np.quantile(arr, alpha))


def historical_expected_shortfall(returns, alpha: float = 0.05) -> float | None:
    """Expected shortfall (CVaR): mean return in the left tail beyond VaR."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")
    arr = _clean(returns)
    if len(arr) < MIN_OBSERVATIONS:
        return None
    threshold = np.quantile(arr, alpha)
    tail = arr[arr <= threshold]
    if tail.size == 0:
        return float(threshold)
    return float(tail.mean())


def tail_risk_flag(
    returns,
    *,
    alpha: float = 0.05,
    var: float | None = None,
    es: float | None = None,
    es_threshold: float = -0.03,
) -> bool:
    """
    Heuristic tail-risk flag: deep expected shortfall or ES materially worse than VaR.
    """
    arr = _clean(returns)
    if len(arr) < MIN_OBSERVATIONS:
        return False
    var = var if var is not None else historical_var(arr, alpha=alpha)
    es = es if es is not None else historical_expected_shortfall(arr, alpha=alpha)
    if var is None or es is None:
        return False
    if es <= es_threshold:
        return True
    # ES substantially worse than VaR indicates fat left tail
    return es < var * 1.25
