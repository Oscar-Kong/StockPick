"""Forward-looking labels without mixing future data into past feature rows."""
from __future__ import annotations

import pandas as pd

from quant_core.returns import _as_series
from quant_core.validation import assert_aligned


def forward_return_label(prices, horizon: int) -> pd.Series:
    """
    Forward simple return over `horizon` periods: price_{t+h} / price_t - 1.

    The label at index t uses only prices at t and t+horizon. The last `horizon`
    observations are NaN so they cannot be used as training rows with contemporaneous
    features at the same timestamp.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    p = _as_series(prices, name="price")
    out = p.shift(-horizon) / p - 1.0
    out.name = f"fwd_return_{horizon}"
    return out


def forward_excess_return_label(
    asset_prices,
    benchmark_prices,
    horizon: int,
) -> pd.Series:
    """Forward asset return minus forward benchmark return on aligned prices."""
    asset = _as_series(asset_prices, name="asset")
    bench = _as_series(benchmark_prices, name="benchmark")
    assert_aligned(asset, bench)
    asset_fwd = forward_return_label(asset, horizon)
    bench_fwd = forward_return_label(bench, horizon)
    out = asset_fwd - bench_fwd
    out.name = f"fwd_excess_return_{horizon}"
    return out


def large_move_label(prices, horizon: int, threshold: float) -> pd.Series:
    """
    Binary label: 1 when |forward return| >= threshold, else 0.

    Rows with undefined forward returns remain NaN.
    """
    if threshold < 0:
        raise ValueError("threshold must be non-negative")
    fwd = forward_return_label(prices, horizon)
    out = (fwd.abs() >= threshold).astype("float")
    out = out.where(fwd.notna())
    out.name = f"large_move_{horizon}_{threshold}"
    return out
