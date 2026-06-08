"""Time-series diagnostics for analyze — log-return stats and plain-English interpretation."""
from __future__ import annotations

import logging
from typing import Any, Literal

import pandas as pd

from quant_core.diagnostics import (
    adf_test,
    autocorrelation_summary,
    excess_kurtosis,
    jarque_bera_test,
    skewness,
)
from quant_core.returns import annualized_volatility, log_returns

logger = logging.getLogger(__name__)

InterpretationPhrase = Literal[
    "mostly noise",
    "possible momentum",
    "possible mean reversion",
    "high tail risk",
    "insufficient data",
]

MIN_PRICE_BARS = 25
MIN_RETURN_OBS = 20
DEFAULT_LOOKBACK = 252
PERIODS_PER_YEAR = 252


def _period_for_lookback(lookback: int) -> str:
    if lookback <= 126:
        return "6mo"
    if lookback <= 252:
        return "1y"
    if lookback <= 504:
        return "2y"
    return "5y"


def load_daily_closes(symbol: str, lookback: int) -> tuple[pd.Series, str, list[str]]:
    """
    Load daily close prices, preferring historical_store then PriceService.

    Returns (close_series, data_source, notes).
    """
    sym = symbol.upper()
    notes: list[str] = []
    target = max(int(lookback), MIN_PRICE_BARS)

    try:
        from data.historical_store import HistoricalStore

        quotes = HistoricalStore().get_quotes(sym, limit=target + 10)
        if quotes:
            df = pd.DataFrame(quotes)
            closes = df["close"].astype(float).reset_index(drop=True)
            if len(closes) >= MIN_PRICE_BARS:
                if len(closes) > target:
                    closes = closes.iloc[-target:].reset_index(drop=True)
                notes.append(f"Loaded {len(closes)} bars from historical_store")
                return closes, "historical_store", notes
            notes.append(
                f"historical_store had only {len(closes)} bars; falling back to price service"
            )
    except Exception as exc:
        logger.debug("Historical store load failed for %s: %s", sym, exc)
        notes.append("historical_store unavailable; using price service")

    try:
        from data.price_service import PriceService

        hist = PriceService().get_history(sym, period=_period_for_lookback(target))
        if hist is None or hist.empty or "close" not in hist.columns:
            notes.append("No price history returned from price service")
            return pd.Series(dtype=float), "none", notes
        closes = hist["close"].astype(float).reset_index(drop=True)
        if len(closes) > target:
            closes = closes.iloc[-target:].reset_index(drop=True)
        notes.append(f"Loaded {len(closes)} bars from price_service")
        return closes, "price_service", notes
    except Exception as exc:
        logger.warning("Price service load failed for %s: %s", sym, exc)
        notes.append(f"price_service error: {exc}")
        return pd.Series(dtype=float), "none", notes


def interpret_log_returns(log_rets: pd.Series) -> tuple[InterpretationPhrase, list[str]]:
    """Map log-return diagnostics to plain-English interpretation phrases."""
    r = log_rets.dropna()
    n = len(r)
    if n < MIN_RETURN_OBS:
        return "insufficient data", [f"Need at least {MIN_RETURN_OBS} return observations; got {n}."]

    notes: list[str] = []
    acf = autocorrelation_summary(r, max_lag=min(20, n - 1))
    lag1 = acf.get("lag1")
    ek = excess_kurtosis(r)
    jb = jarque_bera_test(r)

    if ek >= 1.0:
        notes.append(f"Excess kurtosis {ek:.2f} suggests fat tails.")
        return "high tail risk", notes
    if jb.get("available") and jb.get("pvalue") is not None and jb["pvalue"] < 0.05 and ek > 0.5:
        notes.append("Jarque-Bera rejects normality with elevated kurtosis.")
        return "high tail risk", notes

    if lag1 is not None and lag1 >= 0.08:
        notes.append(f"Lag-1 autocorrelation {lag1:.3f} hints at short-term momentum.")
        return "possible momentum", notes

    if lag1 is not None and lag1 <= -0.05:
        notes.append(f"Lag-1 autocorrelation {lag1:.3f} hints at mean reversion.")
        return "possible mean reversion", notes

    vol = float(r.std(ddof=1)) if len(r) >= 2 else 0.0
    m = float(r.mean())
    snr = abs(m) / vol if vol > 0 else 0.0
    lag1_display = 0.0 if lag1 is None else float(lag1)
    notes.append(f"Low serial structure (lag-1 ACF={lag1_display:.3f}, SNR={snr:.3f}).")
    return "mostly noise", notes


def build_time_series_diagnostics(symbol: str, lookback: int = DEFAULT_LOOKBACK) -> dict[str, Any]:
    """
    Compute log-return diagnostics for a symbol over a lookback window.

    Returns a JSON-serializable dict suitable for AnalyzeTimeSeriesDiagnosticsResponse.
    """
    sym = symbol.upper()
    lookback = max(5, int(lookback))
    closes, data_source, load_notes = load_daily_closes(sym, lookback)
    notes = list(load_notes)

    price_bars = int(len(closes))
    if price_bars < MIN_PRICE_BARS:
        return {
            "symbol": sym,
            "lookback": lookback,
            "price_bars": price_bars,
            "return_bars": 0,
            "observations": 0,
            "data_source": data_source,
            "sufficient_data": False,
            "mean": None,
            "annualized_volatility": None,
            "skewness": None,
            "excess_kurtosis": None,
            "jarque_bera": {"available": False, "reason": "insufficient_data"},
            "adf": {"available": False, "reason": "insufficient_data"},
            "autocorrelation": {"lags": [], "acf": [], "n": 0, "lag1": None},
            "interpretation": "insufficient data",
            "notes": notes + [f"Need at least {MIN_PRICE_BARS} daily closes; got {price_bars}."],
        }

    log_rets = log_returns(closes).dropna()
    return_bars = int(len(log_rets))
    if return_bars < MIN_RETURN_OBS:
        return {
            "symbol": sym,
            "lookback": lookback,
            "price_bars": price_bars,
            "return_bars": return_bars,
            "observations": return_bars,
            "data_source": data_source,
            "sufficient_data": False,
            "mean": float(log_rets.mean()) if return_bars else None,
            "annualized_volatility": None,
            "skewness": None,
            "excess_kurtosis": None,
            "jarque_bera": {"available": False, "reason": "insufficient_data"},
            "adf": {"available": False, "reason": "insufficient_data"},
            "autocorrelation": {"lags": [], "acf": [], "n": return_bars, "lag1": None},
            "interpretation": "insufficient data",
            "notes": notes + [f"Need at least {MIN_RETURN_OBS} log returns; got {return_bars}."],
        }

    max_lag = min(20, return_bars - 1)
    acf_summary = autocorrelation_summary(log_rets, max_lag=max_lag)
    jb = jarque_bera_test(log_rets)
    adf = adf_test(log_rets)
    interpretation, interp_notes = interpret_log_returns(log_rets)
    notes.extend(interp_notes)

    mean = float(log_rets.mean())
    ann_vol = float(annualized_volatility(log_rets, periods_per_year=PERIODS_PER_YEAR))

    return {
        "symbol": sym,
        "lookback": lookback,
        "price_bars": price_bars,
        "return_bars": return_bars,
        "observations": return_bars,
        "data_source": data_source,
        "sufficient_data": True,
        "mean": round(mean, 6),
        "annualized_volatility": round(ann_vol, 6),
        "skewness": round(float(skewness(log_rets)), 4),
        "excess_kurtosis": round(float(excess_kurtosis(log_rets)), 4),
        "jarque_bera": jb,
        "adf": adf,
        "autocorrelation": acf_summary,
        "interpretation": interpretation,
        "notes": notes,
    }
