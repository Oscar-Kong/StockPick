"""Pairs-trading research (diagnostics only — no auto-trade, not used in scan ranking)."""
from __future__ import annotations

import itertools
from typing import Any

import pandas as pd

from data.price_service import PriceService
from engines.pairs.cointegration import engle_granger_test, statsmodels_available
from engines.pairs.spread import build_spread, estimate_half_life, spread_zscore
from utils.pydantic_util import json_safe

MIN_HISTORY_BARS = 60
PERIOD_MAP = {"6mo": "6mo", "1y": "1y", "2y": "2y", "3y": "3y", "5y": "5y"}
DEFAULT_MAX_PAIRS = 100


def load_aligned_closes(
    symbols: list[str],
    period: str,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Fetch and align daily close prices for pair analysis."""
    ps = PriceService()
    tickers = list(dict.fromkeys(s.upper() for s in symbols))
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

    if len(series) < 2:
        raise ValueError("Need at least 2 symbols with sufficient history")

    panel = pd.concat(series, axis=1).sort_index().ffill().dropna(how="any")
    panel.columns = [str(c).upper() for c in panel.columns]
    panel = panel.loc[:, panel.nunique() > 1]

    used = [s for s in tickers if s in panel.columns]
    excluded = sorted(set(excluded + [s for s in tickers if s not in used]))
    if len(used) < 2:
        raise ValueError("Need at least 2 symbols after price alignment")

    return panel, used, excluded


def analyze_pair(
    sym_y: str,
    sym_x: str,
    panel: pd.DataFrame,
    *,
    zscore_window: int = 60,
) -> dict[str, Any]:
    """Run cointegration + spread diagnostics for one ordered pair."""
    y = panel[sym_y]
    x = panel[sym_x]
    coint = engle_granger_test(y, x)

    warning = coint.get("warning")
    if not coint.get("sufficient"):
        return {
            "pair": [sym_y, sym_x],
            "symbol_y": sym_y,
            "symbol_x": sym_x,
            "hedge_ratio": coint.get("hedge_ratio"),
            "intercept": coint.get("intercept"),
            "p_value": coint.get("p_value"),
            "cointegrated_5pct": False,
            "half_life_sessions": None,
            "latest_z_score": None,
            "observations": coint.get("observations", 0),
            "sufficient": False,
            "engine": coint.get("engine"),
            "warning": warning or "insufficient_data",
        }

    hedge = float(coint["hedge_ratio"])
    intercept = float(coint["intercept"])
    spread = build_spread(y, x, hedge_ratio=hedge, intercept=intercept)
    zinfo = spread_zscore(spread, window=zscore_window)
    hl = estimate_half_life(spread)

    pair_warning = warning
    if zinfo.get("warning"):
        pair_warning = zinfo["warning"]
    elif hl.get("warning") and pair_warning is None:
        pair_warning = hl["warning"]

    return {
        "pair": [sym_y, sym_x],
        "symbol_y": sym_y,
        "symbol_x": sym_x,
        "hedge_ratio": hedge,
        "intercept": intercept,
        "p_value": coint.get("p_value"),
        "cointegrated_5pct": bool(coint.get("cointegrated_5pct")),
        "half_life_sessions": hl.get("half_life_sessions"),
        "mean_reverting": hl.get("mean_reverting"),
        "latest_z_score": zinfo.get("latest_z_score"),
        "zscore_window": zinfo.get("window"),
        "spread_mean": zinfo.get("spread_mean"),
        "spread_std": zinfo.get("spread_std"),
        "observations": int(coint.get("observations", len(spread))),
        "sufficient": True,
        "engine": coint.get("engine"),
        "warning": pair_warning,
    }


def run_pairs_research(
    symbols: list[str],
    *,
    lookback_period: str = "1y",
    zscore_window: int = 60,
    max_pairs: int | None = DEFAULT_MAX_PAIRS,
    p_value_threshold: float | None = None,
    price_panel: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Evaluate all symbol pair combinations for cointegration research.

    Not used for auto-trading or scan ranking.
    """
    period = PERIOD_MAP.get(lookback_period, lookback_period)

    if price_panel is None:
        panel, used, excluded = load_aligned_closes(symbols, period)
    else:
        panel = price_panel.sort_index().astype(float)
        panel.columns = [str(c).upper() for c in panel.columns]
        used = [s.upper() for s in symbols if s.upper() in panel.columns]
        excluded = [s.upper() for s in symbols if s.upper() not in used]
        if len(used) < 2:
            raise ValueError("Need at least 2 symbols in price panel")

    combos = list(itertools.combinations(sorted(used), 2))
    results: list[dict[str, Any]] = []
    for sym_y, sym_x in combos:
        results.append(analyze_pair(sym_y, sym_x, panel, zscore_window=zscore_window))

    if p_value_threshold is not None:
        filtered = [
            r
            for r in results
            if r.get("p_value") is not None and float(r["p_value"]) <= p_value_threshold
        ]
        if filtered:
            results = filtered

    def _sort_key(row: dict[str, Any]) -> tuple:
        p = row.get("p_value")
        if p is None:
            return (1, 1.0)
        return (0, float(p))

    results.sort(key=_sort_key)

    if max_pairs is not None and max_pairs > 0:
        results = results[:max_pairs]

    sm_avail = statsmodels_available()
    notes = [
        "Research output only — not used for auto-trading or scan ranking.",
        f"Evaluated {len(combos)} pair combinations.",
    ]
    if not sm_avail:
        notes.append("statsmodels unavailable — using OLS + ADF fallback for cointegration.")

    cointegrated = sum(1 for r in results if r.get("cointegrated_5pct"))
    insufficient = sum(1 for r in results if not r.get("sufficient"))

    return json_safe({
        "research_only": True,
        "lookback_period": lookback_period,
        "symbols_requested": [s.upper() for s in symbols],
        "symbols_used": used,
        "excluded": excluded,
        "observation_count": len(panel),
        "pairs_evaluated": len(combos),
        "pairs_returned": len(results),
        "cointegrated_count": cointegrated,
        "insufficient_count": insufficient,
        "statsmodels_available": sm_avail,
        "pairs": results,
        "notes": notes,
    })
