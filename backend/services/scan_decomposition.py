"""Decompose scan candidates into alpha, confidence, and tradability scores."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from config import SCAN_RANKING_WEIGHTS
from models.schemas import Bucket, RiskLevel
from screeners.base import WeightedSignal


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class DecomposedScanScore:
    alpha_score: float
    confidence_score: float
    tradability_score: float
    ranking_score: float
    warnings: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    factor_contributions: list[dict[str, Any]] = field(default_factory=list)
    ranking_weights: dict[str, float] = field(default_factory=dict)

    def to_metrics_dict(self) -> dict[str, Any]:
        return {
            "alpha_score": round(self.alpha_score, 1),
            "confidence_score": round(self.confidence_score, 1),
            "tradability_score": round(self.tradability_score, 1),
            "ranking_score": round(self.ranking_score, 1),
            "ranking_warnings": list(self.warnings),
            "missing_data": list(self.missing_data),
            "factor_contributions": list(self.factor_contributions),
            "ranking_weights": dict(self.ranking_weights),
        }


def _ranking_weights(bucket: Bucket) -> dict[str, float]:
    key = bucket.value
    weights = dict(SCAN_RANKING_WEIGHTS.get(key) or SCAN_RANKING_WEIGHTS["penny"])
    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def compute_ranking_score(
    alpha: float,
    confidence: float,
    tradability: float,
    *,
    bucket: Bucket,
) -> tuple[float, dict[str, float]]:
    w = _ranking_weights(bucket)
    score = (
        alpha * w.get("alpha", 0.65)
        + confidence * w.get("confidence", 0.20)
        + tradability * w.get("tradability", 0.15)
    )
    return round(_clamp(score), 1), w


def _factor_contributions(signals: list[WeightedSignal]) -> list[dict[str, Any]]:
    ranked = sorted(signals, key=lambda s: abs(s.contribution), reverse=True)
    out: list[dict[str, Any]] = []
    for sig in ranked[:8]:
        out.append(
            {
                "name": sig.name,
                "norm_score": round(float(sig.value), 1),
                "weight": round(float(sig.weight), 4),
                "contribution": round(float(sig.contribution), 2),
            }
        )
    return out


def compute_alpha_score(
    *,
    raw_score: float,
    signals: list[WeightedSignal],
    metrics: dict[str, Any],
) -> float:
    """Setup attractiveness from factor composite (before confidence/tradability blend)."""
    base = float(metrics.get("raw_score") or raw_score)
    usable = [s for s in signals if s.value > 0 and s.weight > 0]
    if not usable:
        return round(_clamp(base * 0.85), 1)
    return round(_clamp(base), 1)


def compute_confidence_score(
    *,
    metrics: dict[str, Any],
    quality_score: float | None,
    hist_len: int,
    signals: list[WeightedSignal],
    min_history_bars: int = 21,
) -> tuple[float, list[str], list[str]]:
    missing: list[str] = []
    warnings: list[str] = []

    dq = quality_score
    if dq is None:
        dq = metrics.get("data_quality_score")
    if dq is None:
        missing.append("data_quality_score")
        dq = 50.0
    else:
        dq = float(dq)

    parts: list[float] = [dq * 0.45]

    if hist_len >= min_history_bars + 120:
        parts.append(92.0)
    elif hist_len >= min_history_bars + 60:
        parts.append(82.0)
    elif hist_len >= min_history_bars:
        parts.append(70.0)
    else:
        missing.append("insufficient_history")
        parts.append(35.0)

    if metrics.get("provider_limited_partial_data"):
        warnings.append("provider_limited_partial_data")
        parts.append(42.0)
    else:
        parts.append(78.0)

    reconcile_flags = metrics.get("data_quality_flags") or []
    if isinstance(reconcile_flags, list) and reconcile_flags:
        penalty = min(25.0, len(reconcile_flags) * 4.0)
        parts.append(_clamp(75.0 - penalty))
        if penalty >= 12:
            warnings.append("reconcile_flags")

    missing_fund = metrics.get("missing_fundamental_fields") or metrics.get("missing_fields")
    if missing_fund:
        if isinstance(missing_fund, list):
            missing.extend(str(x) for x in missing_fund[:5])
        parts.append(_clamp(68.0 - min(20.0, len(missing_fund) * 2.0)))
    else:
        parts.append(72.0)

    usable_factors = sum(1 for s in signals if s.weight > 0 and s.value > 0)
    if usable_factors >= 5:
        parts.append(88.0)
    elif usable_factors >= 3:
        parts.append(72.0)
    else:
        missing.append("usable_factors")
        parts.append(48.0)

    liq_warn = metrics.get("liquidity_warnings") or metrics.get("dilution_warnings") or []
    if isinstance(liq_warn, list):
        for w in liq_warn:
            ws = str(w)
            if ws not in warnings:
                warnings.append(ws)
        if liq_warn:
            parts.append(_clamp(70.0 - min(30.0, len(liq_warn) * 6.0)))

    score = sum(parts) / len(parts)
    return round(_clamp(score), 1), warnings, missing


def compute_tradability_score(
    *,
    bucket: Bucket,
    metrics: dict[str, Any],
    price: float,
    history: pd.DataFrame | None,
) -> tuple[float, list[str]]:
    warnings: list[str] = []
    parts: list[float] = []

    adv = metrics.get("average_dollar_volume_20d")
    if adv is not None:
        adv_f = float(adv)
        if adv_f >= 5_000_000:
            parts.append(90.0)
        elif adv_f >= 1_000_000:
            parts.append(75.0)
        elif adv_f >= 500_000:
            parts.append(58.0)
        else:
            parts.append(35.0)
            warnings.append("insufficient_liquidity")
    elif history is not None and not history.empty:
        tail = history.tail(min(20, len(history)))
        dv = float((tail["close"] * tail["volume"]).mean())
        if dv >= 1_000_000:
            parts.append(70.0)
        else:
            parts.append(45.0)
            warnings.append("low_dollar_volume")
    else:
        parts.append(50.0)

    rel_vol = metrics.get("relative_volume_ratio") or metrics.get("volume_ratio")
    if rel_vol is not None:
        rv = float(rel_vol)
        if 0.8 <= rv <= 3.5:
            parts.append(82.0)
        elif rv > 5.0:
            parts.append(45.0)
            warnings.append("abnormal_volume")
        else:
            parts.append(65.0)

    atr = metrics.get("atr_percent")
    if atr is not None:
        atr_f = float(atr)
        if bucket == Bucket.penny:
            if 3.0 <= atr_f <= 12.0:
                parts.append(80.0)
            elif atr_f > 15.0:
                parts.append(40.0)
                warnings.append("very_high_atr")
            else:
                parts.append(55.0)
        else:
            if atr_f <= 8.0:
                parts.append(78.0)
            elif atr_f <= 15.0:
                parts.append(62.0)
            else:
                parts.append(45.0)

    if price > 0:
        if bucket == Bucket.penny:
            if 0.5 <= price <= 5.0:
                parts.append(78.0)
            else:
                parts.append(50.0)
        elif price >= 10.0:
            parts.append(82.0)
        else:
            parts.append(60.0)

    spread = metrics.get("spread_estimate_pct")
    if spread is not None:
        sp = float(spread)
        if sp <= 5.0:
            parts.append(85.0)
        elif sp <= 10.0:
            parts.append(65.0)
        else:
            parts.append(40.0)
            warnings.append("wide_intraday_spread")

    gap = metrics.get("gap_percent")
    if gap is not None and abs(float(gap)) >= 8.0:
        parts.append(42.0)
        warnings.append("extreme_gap")
    elif gap is not None:
        parts.append(72.0)

    if history is not None and len(history) >= 10:
        vol = history["volume"].astype(float).tail(10)
        if vol.mean() > 0 and vol.std() / max(vol.mean(), 1.0) > 1.2:
            parts.append(55.0)
        else:
            parts.append(75.0)

    if not parts:
        return 50.0, warnings
    score = sum(parts) / len(parts)
    adv_f = float(adv) if adv is not None else None
    atr_f = float(atr) if atr is not None else None
    spread_f = float(spread) if spread is not None else None
    if adv_f is not None and adv_f < 500_000:
        if (atr_f is not None and atr_f > 15.0) or (spread_f is not None and spread_f > 10.0):
            score = min(score, 48.0)
    return round(_clamp(score), 1), warnings


def build_decomposed_scores(
    *,
    raw_score: float,
    signals: list[WeightedSignal],
    metrics: dict[str, Any],
    bucket: Bucket,
    price: float,
    history: pd.DataFrame | None,
    quality_score: float | None,
    hist_len: int,
) -> DecomposedScanScore:
    alpha = compute_alpha_score(raw_score=raw_score, signals=signals, metrics=metrics)
    confidence, conf_warn, missing = compute_confidence_score(
        metrics=metrics,
        quality_score=quality_score,
        hist_len=hist_len,
        signals=signals,
    )
    tradability, trade_warn = compute_tradability_score(
        bucket=bucket,
        metrics=metrics,
        price=price,
        history=history,
    )
    warnings = list(dict.fromkeys(conf_warn + trade_warn))
    ranking, weights = compute_ranking_score(alpha, confidence, tradability, bucket=bucket)
    return DecomposedScanScore(
        alpha_score=alpha,
        confidence_score=confidence,
        tradability_score=tradability,
        ranking_score=ranking,
        warnings=warnings,
        missing_data=missing,
        factor_contributions=_factor_contributions(signals),
        ranking_weights=weights,
    )


def passes_persistence_safety(
    *,
    bucket: Bucket,
    confidence_score: float,
    tradability_score: float,
    metrics: dict[str, Any],
) -> bool:
    """Incumbents failing safety are not protected by persistence."""
    if confidence_score < 35.0:
        return False
    if tradability_score < 30.0:
        return False
    if metrics.get("provider_limited_partial_data") and confidence_score < 45.0:
        return False
    if bucket == Bucket.penny and confidence_score < 40.0 and tradability_score < 45.0:
        return False
    return True
