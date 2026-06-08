"""Portfolio factor exposure diagnostics (research only — not trade recommendations)."""
from __future__ import annotations

from typing import Any

import pandas as pd

from data.price_service import PriceService
from engines.factor_model.exposures import (
    build_return_matrix,
    estimate_market_betas,
    rolling_correlation_matrix,
)
from engines.factor_model.pca import pca_standardized_returns

MIN_HISTORY_BARS = 60
PERIOD_MAP = {"6mo": "6mo", "1y": "1y", "2y": "2y", "3y": "3y", "5y": "5y"}


def _load_price_panel(
    symbols: list[str],
    benchmark: str,
    period: str,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Load aligned close prices for portfolio symbols + benchmark."""
    ps = PriceService()
    bench = benchmark.upper()
    tickers = list(dict.fromkeys([s.upper() for s in symbols] + [bench]))
    series: dict[str, pd.Series] = {}
    excluded: list[str] = []

    for symbol in tickers:
        hist = ps.get_history(symbol, period=period)
        if hist.empty or len(hist) < MIN_HISTORY_BARS:
            excluded.append(symbol)
            continue
        s = hist[["date", "close"]].copy()
        s["date"] = pd.to_datetime(s["date"])
        s = s.dropna().drop_duplicates(subset=["date"])
        if len(s) < MIN_HISTORY_BARS:
            excluded.append(symbol)
            continue
        series[symbol] = s.set_index("date")["close"].astype(float)

    if bench not in series:
        raise ValueError(f"benchmark {bench} has insufficient history for lookback {period}")

    portfolio_syms = [s.upper() for s in symbols if s.upper() in series and s.upper() != bench]
    if len(portfolio_syms) < 2:
        raise ValueError("Need at least 2 portfolio symbols with sufficient history")

    cols = portfolio_syms + [bench]
    panel = pd.concat({c: series[c] for c in cols}, axis=1).sort_index().ffill().dropna(how="any")
    panel.columns = [str(c).upper() for c in panel.columns]
    panel = panel.loc[:, panel.nunique() > 1]

    used = [c for c in portfolio_syms if c in panel.columns]
    if bench not in panel.columns:
        raise ValueError(f"benchmark {bench} dropped during alignment")
    if len(used) < 2:
        raise ValueError("Need at least 2 portfolio symbols after price alignment")

    excluded = sorted(set(excluded + [s.upper() for s in symbols if s.upper() not in used]))
    return panel, used, excluded


def build_factor_exposure_report(
    symbols: list[str],
    *,
    benchmark: str = "SPY",
    lookback_period: str = "1y",
    correlation_window: int = 60,
    n_components: int | None = None,
    pc1_concentration_threshold: float = 0.45,
    price_panel: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Portfolio diagnostics: betas vs benchmark, rolling correlation, PCA loadings.

    Does not produce trade recommendations.
    """
    period = PERIOD_MAP.get(lookback_period, lookback_period)
    bench = benchmark.upper()

    if price_panel is None:
        panel, used, excluded = _load_price_panel(symbols, bench, period)
    else:
        panel = price_panel.sort_index().astype(float)
        panel.columns = [str(c).upper() for c in panel.columns]
        used = [s.upper() for s in symbols if s.upper() in panel.columns and s.upper() != bench]
        excluded = [s.upper() for s in symbols if s.upper() not in used]
        if bench not in panel.columns:
            raise ValueError(f"benchmark {bench} missing from supplied price panel")
        if len(used) < 2:
            raise ValueError("Need at least 2 portfolio symbols in price panel")

    returns = build_return_matrix(panel)
    if returns.empty:
        raise ValueError("Could not build return matrix from price history")

    betas = estimate_market_betas(returns, bench)
    correlation = rolling_correlation_matrix(returns, window=correlation_window)
    pca = pca_standardized_returns(
        returns,
        n_components=n_components,
        pc1_concentration_threshold=pc1_concentration_threshold,
    )

    notes: list[str] = [
        "Diagnostic output only — not used for trade recommendations.",
        f"Aligned daily returns: {len(returns)} observations.",
    ]
    if pca.get("concentration_warning"):
        notes.append(
            f"PC1 explains {pca.get('pc1_variance_ratio', 0):.1%} of variance "
            f"(threshold {pc1_concentration_threshold:.1%}) — portfolio may be concentrated in a single factor."
        )
    if excluded:
        notes.append(f"Excluded symbols (insufficient history): {', '.join(excluded)}")

    return {
        "diagnostic_only": True,
        "benchmark": bench,
        "lookback_period": lookback_period,
        "symbols_requested": [s.upper() for s in symbols],
        "symbols_used": used,
        "excluded": excluded,
        "observation_count": len(returns),
        "betas": betas,
        "correlation": correlation,
        "pca": pca,
        "concentration_warning": bool(pca.get("concentration_warning")),
        "notes": notes,
    }
