"""Stage A preliminary ranking from bulk OHLC and cached metadata."""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from data.historical_store import HistoricalStore
from data.universe import get_universe
from data.universe_builder import check_bucket_eligibility
from models.schemas import Bucket

logger = logging.getLogger(__name__)

PENNY_FEATURE_WEIGHTS: dict[str, float] = {
    "rel_volume": 0.25,
    "momentum_5d": 0.20,
    "breakout_position": 0.15,
    "dollar_volume_quality": 0.15,
    "trend_consistency": 0.10,
    "atr_tradeability": 0.10,
    "acceleration": 0.05,
}

COMPOUNDER_FEATURE_WEIGHTS: dict[str, float] = {
    "trend_12m": 0.30,
    "trend_smoothness": 0.25,
    "liquidity": 0.20,
    "drawdown_stability": 0.15,
    "fundamental_quality": 0.10,
}

_MIN_BARS_PENNY = 21
_MIN_BARS_COMPOUNDER = 60


@dataclass
class StageACandidate:
    symbol: str
    pre_score: float
    features: dict[str, float]
    data_quality: float | None = None
    warnings: list[str] = field(default_factory=list)
    rank: int = 0
    raw_features: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pre_score"] = round(float(self.pre_score), 2)
        payload["features"] = {k: round(float(v), 2) for k, v in self.features.items()}
        payload["raw_features"] = {k: round(float(v), 4) for k, v in self.raw_features.items()}
        return payload


@dataclass
class StageAExcluded:
    symbol: str
    rejection_reason: str

    def to_dict(self) -> dict[str, str]:
        return {"symbol": self.symbol.upper(), "rejection_reason": self.rejection_reason}


@dataclass
class StageARankingResult:
    ranked: list[StageACandidate]
    excluded: list[StageAExcluded]

    def to_diagnostics(self, *, advanced_count: int | None = None) -> dict[str, Any]:
        return {
            "eligible_count": len(self.ranked),
            "excluded_count": len(self.excluded),
            "advanced_count": advanced_count if advanced_count is not None else len(self.ranked),
            "candidates": [c.to_dict() for c in self.ranked],
            "excluded": [e.to_dict() for e in self.excluded],
        }


def _feature_weights(bucket: Bucket) -> dict[str, float]:
    if bucket == Bucket.compounder:
        return dict(COMPOUNDER_FEATURE_WEIGHTS)
    return dict(PENNY_FEATURE_WEIGHTS)


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _winsorize(values: list[float], *, lower_pct: float = 5.0, upper_pct: float = 95.0) -> list[float]:
    if len(values) < 2:
        return list(values)
    arr = np.asarray(values, dtype=float)
    lo, hi = np.percentile(arr, [lower_pct, upper_pct])
    return np.clip(arr, lo, hi).tolist()


def _percentile_scores(raw_by_symbol: dict[str, dict[str, float | None]]) -> dict[str, dict[str, float]]:
    feature_names: set[str] = set()
    for feats in raw_by_symbol.values():
        feature_names.update(feats.keys())

    scored: dict[str, dict[str, float]] = {sym: {} for sym in raw_by_symbol}
    for fname in feature_names:
        pairs = [
            (sym, feats[fname])
            for sym, feats in raw_by_symbol.items()
            if feats.get(fname) is not None and math.isfinite(float(feats[fname]))
        ]
        if not pairs:
            continue
        winsorized = _winsorize([float(v) for _, v in pairs])
        order = sorted(range(len(pairs)), key=lambda i: winsorized[i])
        n = len(order)
        for rank_idx, orig_idx in enumerate(order):
            sym = pairs[orig_idx][0]
            pct = 50.0 if n == 1 else 100.0 * rank_idx / max(n - 1, 1)
            scored[sym][fname] = pct
    return scored


def _weighted_pre_score(
    feature_pct: dict[str, float],
    weights: dict[str, float],
    *,
    warnings: list[str],
) -> float:
    available = {k: v for k, v in feature_pct.items() if k in weights and v is not None}
    if not available:
        warnings.append("no_scorable_features")
        return 0.0

    weight_total = sum(weights[k] for k in available)
    if weight_total <= 0:
        return 0.0

    missing = [k for k in weights if k not in available]
    if missing:
        warnings.append(f"missing_features:{','.join(sorted(missing))}")

    return sum((weights[k] / weight_total) * available[k] for k in available)


def _atr_pct(hist: pd.DataFrame, period: int = 14) -> float | None:
    if len(hist) < period + 1:
        return None
    high = hist["high"].astype(float)
    low = hist["low"].astype(float)
    close = hist["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = float(tr.tail(period).mean())
    price = float(close.iloc[-1])
    if price <= 0:
        return None
    return atr / price * 100.0


def _compute_penny_raw_features(hist: pd.DataFrame) -> tuple[dict[str, float | None], list[str]]:
    warnings: list[str] = []
    if len(hist) < _MIN_BARS_PENNY:
        warnings.append("insufficient_history")
        return {}, warnings

    close = hist["close"].astype(float)
    volume = hist["volume"].astype(float)
    feats: dict[str, float | None] = {}

    from scoring.penny_liquidity import relative_volume_ratio_from_df

    feats["rel_volume"] = relative_volume_ratio_from_df(hist)

    if len(close) >= 6:
        feats["momentum_5d"] = (float(close.iloc[-1]) / float(close.iloc[-6]) - 1.0) * 100.0
    else:
        warnings.append("momentum_5d_unavailable")

    window = hist.tail(20)
    hi = float(window["high"].max())
    lo = float(window["low"].min())
    last = float(close.iloc[-1])
    if hi > lo:
        feats["breakout_position"] = (last - lo) / (hi - lo) * 100.0
    else:
        feats["breakout_position"] = 50.0

    tail = hist.tail(min(20, len(hist)))
    feats["dollar_volume_quality"] = float((tail["close"] * tail["volume"]).mean())

    daily_ret = close.pct_change().dropna()
    if len(daily_ret) >= 10:
        up_ratio = float((daily_ret.tail(20) > 0).mean())
        feats["trend_consistency"] = up_ratio * 100.0
    else:
        warnings.append("trend_consistency_unavailable")

    atr_pct = _atr_pct(hist)
    if atr_pct is not None:
        # Peak tradeability near ~3% ATR/price; convert to higher-is-better raw score.
        feats["atr_tradeability"] = max(0.0, 10.0 - abs(atr_pct - 3.0))
    else:
        warnings.append("atr_tradeability_unavailable")

    if len(close) >= 11:
        ret5 = float(close.iloc[-1] / close.iloc[-6] - 1.0)
        ret10 = float(close.iloc[-1] / close.iloc[-11] - 1.0)
        feats["acceleration"] = (ret5 - ret10) * 100.0
    else:
        warnings.append("acceleration_unavailable")

    return feats, warnings


def _compute_compounder_raw_features(
    hist: pd.DataFrame,
    *,
    cached_quality: float | None,
) -> tuple[dict[str, float | None], list[str]]:
    warnings: list[str] = []
    if len(hist) < _MIN_BARS_COMPOUNDER:
        warnings.append("insufficient_history")
        return {}, warnings

    close = hist["close"].astype(float)
    feats: dict[str, float | None] = {}

    lookback = min(len(close) - 1, 252)
    if lookback >= 20:
        feats["trend_12m"] = (float(close.iloc[-1]) / float(close.iloc[-1 - lookback]) - 1.0) * 100.0
        if lookback < 200:
            warnings.append("trend_12m_short_history")
    else:
        warnings.append("trend_12m_unavailable")

    window = close.tail(min(60, len(close)))
    if len(window) >= 10:
        log_prices = np.log(window.values)
        x = np.arange(len(log_prices), dtype=float)
        slope, intercept = np.polyfit(x, log_prices, 1)
        predicted = slope * x + intercept
        ss_res = float(np.sum((log_prices - predicted) ** 2))
        ss_tot = float(np.sum((log_prices - log_prices.mean()) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        rets = window.pct_change().dropna()
        vol_penalty = float(rets.std()) if len(rets) else 0.0
        feats["trend_smoothness"] = max(0.0, (r2 * 100.0) - (vol_penalty * 50.0))
    else:
        warnings.append("trend_smoothness_unavailable")

    tail = hist.tail(min(20, len(hist)))
    feats["liquidity"] = float((tail["close"] * tail["volume"]).mean())

    running_max = close.cummax()
    drawdown = (close - running_max) / running_max.replace(0, np.nan)
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    feats["drawdown_stability"] = (1.0 + max_dd) * 100.0

    if cached_quality is not None and cached_quality > 0:
        feats["fundamental_quality"] = float(cached_quality)
    else:
        warnings.append("fundamental_quality_missing")

    return feats, warnings


def _compute_raw_features(
    bucket: Bucket,
    hist: pd.DataFrame,
    *,
    cached_quality: float | None,
) -> tuple[dict[str, float | None], list[str]]:
    if bucket == Bucket.compounder:
        return _compute_compounder_raw_features(hist, cached_quality=cached_quality)
    return _compute_penny_raw_features(hist)


def _load_cached_quality_map(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {}
    try:
        return HistoricalStore().get_cached_quality_scores(symbols)
    except Exception as exc:
        logger.warning("Stage A cached quality batch lookup failed: %s", exc)
        return {}


def rank_stage_a_candidates(
    bucket: Bucket,
    bulk_hist: dict[str, pd.DataFrame],
    *,
    bulk_info: dict[str, dict] | None = None,
    universe: list[str] | None = None,
    cached_quality: dict[str, float] | None = None,
    apply_eligibility: bool = True,
) -> StageARankingResult:
    """Rank eligible symbols by cross-sectional preliminary score (descending)."""
    symbols = universe or get_universe(bucket.value)
    bulk_info = bulk_info or {}
    quality_map = cached_quality if cached_quality is not None else {}
    if bucket == Bucket.compounder and not quality_map:
        eligible_syms = [s.upper() for s in symbols if bulk_hist.get(s.upper()) is not None]
        quality_map = _load_cached_quality_map(eligible_syms)

    excluded: list[StageAExcluded] = []
    raw_by_symbol: dict[str, dict[str, float | None]] = {}
    meta_by_symbol: dict[str, dict[str, Any]] = {}

    for symbol in symbols:
        sym = symbol.upper()
        hist = bulk_hist.get(sym)
        if hist is None or hist.empty:
            excluded.append(StageAExcluded(sym, "missing_history"))
            continue

        info = bulk_info.get(sym, {})
        if apply_eligibility:
            passed, reason = check_bucket_eligibility(bucket, hist, info)
            if not passed:
                excluded.append(StageAExcluded(sym, reason or "eligibility_failed"))
                continue

        dq = _safe_float(quality_map.get(sym))
        raw_feats, warnings = _compute_raw_features(bucket, hist, cached_quality=dq)
        if not raw_feats:
            excluded.append(StageAExcluded(sym, "insufficient_feature_data"))
            continue

        raw_by_symbol[sym] = raw_feats
        meta_by_symbol[sym] = {"data_quality": dq, "warnings": warnings}

    if not raw_by_symbol:
        return StageARankingResult(ranked=[], excluded=excluded)

    feature_pct = _percentile_scores(raw_by_symbol)
    weights = _feature_weights(bucket)
    candidates: list[StageACandidate] = []

    for sym, raw_feats in raw_by_symbol.items():
        meta = meta_by_symbol[sym]
        warnings = list(meta["warnings"])
        pct_feats = feature_pct.get(sym, {})
        pre_score = _weighted_pre_score(pct_feats, weights, warnings=warnings)
        candidates.append(
            StageACandidate(
                symbol=sym,
                pre_score=pre_score,
                features=pct_feats,
                data_quality=meta["data_quality"],
                warnings=warnings,
                raw_features={k: float(v) for k, v in raw_feats.items() if v is not None},
            )
        )

    candidates.sort(key=lambda c: (-c.pre_score, c.symbol))
    for idx, candidate in enumerate(candidates, start=1):
        candidate.rank = idx

    return StageARankingResult(ranked=candidates, excluded=excluded)


def select_stage_b_symbols(ranked: list[StageACandidate], cap: int) -> list[str]:
    """Return top-N symbols for Stage B in preliminary-score order."""
    return [c.symbol for c in ranked[:cap]]
