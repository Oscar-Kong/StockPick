"""Portfolio optimization service (PyPortfolioOpt optional)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from config import PYPFOPT_ENABLED
from data.price_service import PriceService


@dataclass
class OptimizeResult:
    optimizer: str
    symbols_used: list[str]
    excluded: list[str]
    weights: dict[str, float]
    expected_return: float | None = None
    expected_volatility: float | None = None
    expected_sharpe: float | None = None
    notes: list[str] | None = None


def _price_panel(symbols: list[str], period: str) -> tuple[pd.DataFrame, list[str]]:
    ps = PriceService()
    series: dict[str, pd.Series] = {}
    excluded: list[str] = []
    for symbol in symbols:
        hist = ps.get_history(symbol, period=period)
        if hist.empty or len(hist) < 80:
            excluded.append(symbol)
            continue
        s = hist[["date", "close"]].copy()
        s["date"] = pd.to_datetime(s["date"])
        s = s.dropna().drop_duplicates(subset=["date"])
        if len(s) < 80:
            excluded.append(symbol)
            continue
        series[symbol] = s.set_index("date")["close"].astype(float)
    if not series:
        return pd.DataFrame(), excluded
    panel = pd.concat(series, axis=1).sort_index().ffill().dropna(how="any")
    panel = panel.loc[:, panel.nunique() > 1]
    missing = [s for s in symbols if s not in panel.columns]
    excluded.extend(missing)
    return panel, sorted(set(excluded))


WEIGHT_SUM_TOLERANCE = 1e-6


def validate_weight_constraints(n_assets: int, max_weight: float, cash_buffer: float) -> None:
    """Raise when max_weight × n_assets cannot reach the invested target."""
    if n_assets <= 0:
        raise ValueError("No assets to allocate")
    invested_target = 1.0 - cash_buffer
    capacity = n_assets * max_weight
    if capacity < invested_target - WEIGHT_SUM_TOLERANCE:
        pct_max = int(round(max_weight * 100))
        raise ValueError(
            f"A {pct_max}% maximum position weight across {n_assets} assets can invest at most "
            f"{int(round(capacity * 100))}%. Increase the maximum weight, add more assets, "
            f"or increase the cash reserve."
        )


def _normalize_weights(raw: dict[str, float], max_weight: float, cash_buffer: float) -> dict[str, float]:
    """Scale weights so sum(asset_weights) == 1 - cash_buffer (applied exactly once)."""
    if not raw:
        raise ValueError("No weights to normalize")

    invested_target = max(0.0, 1.0 - cash_buffer)
    n = len(raw)
    validate_weight_constraints(n, max_weight, cash_buffer)

    positive = {k: max(0.0, float(v)) for k, v in raw.items()}
    total = sum(positive.values())
    if total <= 0:
        base = min(max_weight, invested_target / max(1, n))
        return {k: round(base, 6) for k in raw}

    weights = {k: v / total * invested_target for k, v in positive.items()}

    if max_weight >= 1:
        return {k: round(v, 6) for k, v in weights.items()}

    for _ in range(n + 1):
        clipped = {k: min(v, max_weight) for k, v in weights.items()}
        current_sum = sum(clipped.values())
        if abs(current_sum - invested_target) <= WEIGHT_SUM_TOLERANCE:
            return {k: round(v, 6) for k, v in clipped.items()}

        residual = invested_target - current_sum
        if residual <= WEIGHT_SUM_TOLERANCE:
            return {k: round(v, 6) for k, v in clipped.items()}

        room = {k: max(0.0, max_weight - clipped[k]) for k in clipped}
        room_total = sum(room.values())
        if room_total <= WEIGHT_SUM_TOLERANCE:
            validate_weight_constraints(n, max_weight, cash_buffer)
            raise ValueError(
                "Allocation constraints are infeasible after max-weight clipping. "
                "Increase max weight, add assets, or adjust cash reserve."
            )
        for k in clipped:
            clipped[k] += residual * (room[k] / room_total)
        weights = clipped

    return {k: round(v, 6) for k, v in weights.items()}


def _fallback_optimize(
    symbols: list[str],
    objective: str,
    max_weight: float,
    cash_buffer: float,
    target_return: float | None,
    lookback_period: str,
) -> OptimizeResult:
    panel, excluded = _price_panel(symbols, lookback_period)
    if panel.empty or len(panel.columns) < 2:
        raise ValueError("Need at least 2 symbols with sufficient history for optimization")

    rets = panel.pct_change().dropna(how="any")
    mu = rets.mean() * 252
    cov = rets.cov() * 252
    vol = np.sqrt(np.diag(cov))
    inv_vol = np.where(vol > 0, 1.0 / vol, 0.0)

    if objective in ("min_vol", "risk_parity"):
        raw = {s: inv_vol[i] for i, s in enumerate(panel.columns)}
    else:
        # Sharpe-like proxy and target-return blending without heavy solvers.
        sharpe_proxy = np.where(vol > 0, mu.values / vol, 0.0)
        if objective == "target_return" and target_return is not None:
            shift = target_return - np.nanmean(mu.values)
            sharpe_proxy = sharpe_proxy + np.sign(shift) * 0.25
        raw = {s: max(0.0, float(sharpe_proxy[i])) for i, s in enumerate(panel.columns)}
        if sum(raw.values()) == 0:
            raw = {s: inv_vol[i] for i, s in enumerate(panel.columns)}

    weights = _normalize_weights(raw, max_weight=max_weight, cash_buffer=cash_buffer)
    port_ret = float(sum(weights[s] * mu[s] for s in weights))
    w = np.array([weights[s] for s in panel.columns])
    port_vol = float(np.sqrt(np.dot(w, np.dot(cov.values, w))))
    sharpe = port_ret / port_vol if port_vol > 0 else 0.0
    notes = ["Used fallback optimizer (no PyPortfolioOpt solver)."]
    return OptimizeResult(
        optimizer="fallback",
        symbols_used=list(panel.columns),
        excluded=excluded,
        weights=weights,
        expected_return=round(port_ret, 4),
        expected_volatility=round(port_vol, 4),
        expected_sharpe=round(sharpe, 4),
        notes=notes,
    )


def _pypfopt_optimize(
    symbols: list[str],
    objective: str,
    max_weight: float,
    cash_buffer: float,
    target_return: float | None,
    lookback_period: str,
) -> OptimizeResult:
    panel, excluded = _price_panel(symbols, lookback_period)
    if panel.empty or len(panel.columns) < 2:
        raise ValueError("Need at least 2 symbols with sufficient history for optimization")

    from pypfopt import EfficientFrontier, expected_returns, risk_models

    mu = expected_returns.mean_historical_return(panel)
    cov = risk_models.sample_cov(panel)
    ef = EfficientFrontier(mu, cov, weight_bounds=(0, max_weight))
    if objective in ("min_vol", "risk_parity"):
        ef.min_volatility()
    elif objective == "target_return" and target_return is not None:
        ef.efficient_return(target_return=target_return)
    else:
        ef.max_sharpe()

    cleaned = ef.clean_weights()
    weights = _normalize_weights(cleaned, max_weight=max_weight, cash_buffer=cash_buffer)
    p_ret, p_vol, p_sharpe = ef.portfolio_performance(verbose=False)
    return OptimizeResult(
        optimizer="pypfopt",
        symbols_used=list(panel.columns),
        excluded=excluded,
        weights=weights,
        expected_return=round(float(p_ret), 4),
        expected_volatility=round(float(p_vol), 4),
        expected_sharpe=round(float(p_sharpe), 4),
        notes=[],
    )


def _apply_kelly_overlay(weights: dict[str, float], panel: pd.DataFrame, fraction: float = 0.5) -> dict[str, float]:
    """Half-Kelly style cap per symbol using daily win-rate proxy."""
    adjusted: dict[str, float] = {}
    for sym, w in weights.items():
        if sym not in panel.columns:
            adjusted[sym] = w
            continue
        rets = panel[sym].pct_change().dropna()
        if len(rets) < 20:
            adjusted[sym] = w * 0.5
            continue
        p = float((rets > 0).mean())
        avg_win = float(rets[rets > 0].mean()) if (rets > 0).any() else 0.0
        avg_loss = float(rets[rets < 0].mean()) if (rets < 0).any() else -0.01
        if avg_loss >= 0:
            kelly = 0.0
        else:
            b = abs(avg_win / avg_loss) if avg_loss else 1.0
            kelly = p - (1 - p) / max(b, 1e-6)
        kelly = max(0.0, min(0.25, kelly * fraction))
        adjusted[sym] = w * max(kelly, 0.05)
    total = sum(adjusted.values())
    if total <= 0:
        return weights
    return {k: v / total for k, v in adjusted.items()}


def optimize_portfolio(
    symbols: list[str],
    *,
    objective: str = "max_sharpe",
    max_weight: float = 0.30,
    cash_buffer: float = 0.0,
    target_return: float | None = None,
    lookback_period: str = "1y",
    kelly_overlay: bool = False,
) -> OptimizeResult:
    symbols = [s.strip().upper() for s in symbols if s and s.strip()]
    symbols = list(dict.fromkeys(symbols))
    if len(symbols) < 2:
        raise ValueError("Provide at least 2 unique symbols")

    obj = objective
    if obj == "kelly":
        obj = "max_sharpe"
        kelly_overlay = True

    if PYPFOPT_ENABLED:
        try:
            result = _pypfopt_optimize(
                symbols,
                objective=obj,
                max_weight=max_weight,
                cash_buffer=cash_buffer,
                target_return=target_return,
                lookback_period=lookback_period,
            )
        except Exception as exc:
            result = _fallback_optimize(
                symbols,
                objective=obj,
                max_weight=max_weight,
                cash_buffer=cash_buffer,
                target_return=target_return,
                lookback_period=lookback_period,
            )
            result.notes = (result.notes or []) + [f"PyPortfolioOpt unavailable: {exc}"]
    else:
        result = _fallback_optimize(
            symbols,
            objective=obj,
            max_weight=max_weight,
            cash_buffer=cash_buffer,
            target_return=target_return,
            lookback_period=lookback_period,
        )

    if kelly_overlay and result.symbols_used:
        panel, _ = _price_panel(result.symbols_used, lookback_period)
        if not panel.empty:
            raw = _apply_kelly_overlay(result.weights, panel)
            result.weights = _normalize_weights(raw, max_weight=max_weight, cash_buffer=cash_buffer)
            result.notes = (result.notes or []) + ["Applied half-Kelly overlay on weights."]

    weight_sum = sum(result.weights.values())
    expected_sum = max(0.0, 1.0 - cash_buffer)
    if abs(weight_sum - expected_sum) > WEIGHT_SUM_TOLERANCE * max(1, len(result.weights)):
        result.notes = (result.notes or []) + [
            f"Weight sum {weight_sum:.6f} deviates from target {expected_sum:.6f}."
        ]

    if objective == "risk_parity":
        result.notes = (result.notes or []) + ["Risk parity via inverse-volatility weights."]
    return result

