"""Estimate factor weights from IC/IR with regime overlays and constraints."""
from __future__ import annotations

import math

from config import (
    IC_SOFTMAX_ALPHA,
    IC_SOFTMAX_BETA,
    WEIGHT_MAX,
    WEIGHT_MIN,
)
from engines.factor.catalog import FACTOR_CATALOG, static_weights
from engines.weighting.regime_classifier import REGIMES
from engines.weighting.regime_overlays import overlay_multiplier


def _softmax(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    max_z = max(values.values())
    exps = {k: math.exp(v - max_z) for k, v in values.items()}
    total = sum(exps.values()) or 1.0
    return {k: exps[k] / total for k, v in values.items()}


def _apply_constraints(weights: dict[str, float]) -> dict[str, float]:
    if not weights:
        return weights
    clamped = {k: min(WEIGHT_MAX, max(WEIGHT_MIN, v)) for k, v in weights.items()}
    total = sum(clamped.values()) or 1.0
    return {k: v / total for k, v in clamped.items()}


def estimate_base_weights(sleeve: str, ic_panel: dict[str, dict] | None = None) -> dict[str, float]:
    """IC/IR softmax; falls back to catalog static weights when IC missing."""
    specs = FACTOR_CATALOG.get(sleeve, [])
    if not specs:
        return {}
    if ic_panel is not None:
        panel = ic_panel
    else:
        from engines.weighting.ic_panel import load_latest_ic

        panel = load_latest_ic(sleeve)
    if not panel:
        return static_weights(sleeve)

    z_scores: dict[str, float] = {}
    for spec in specs:
        stats = panel.get(spec.factor_id, {})
        ic = float(stats.get("ic") or 0.0)
        ir = float(stats.get("ir") or 0.0)
        decay = 1.0
        if ic != 0 and abs(ic) < 0.02:
            decay = max(0.0, abs(ic) / 0.02)
        z_scores[spec.factor_id] = (IC_SOFTMAX_ALPHA * ic + IC_SOFTMAX_BETA * ir) * decay

    if all(abs(z) < 1e-6 for z in z_scores.values()):
        return static_weights(sleeve)

    raw = _softmax(z_scores)
    return _apply_constraints(raw)


def apply_regime_overlay(
    base: dict[str, float],
    sleeve: str,
    regime: str,
) -> dict[str, float]:
    if not base:
        return base
    adjusted = {
        fid: w * overlay_multiplier(sleeve, regime, fid)
        for fid, w in base.items()
    }
    total = sum(adjusted.values()) or 1.0
    return _apply_constraints({fid: w / total for fid, w in adjusted.items()})


def estimate_all_regime_weights(
    sleeve: str,
    ic_panel: dict[str, dict] | None = None,
) -> dict[str, dict[str, float]]:
    """regime → {factor_id: weight}."""
    base = estimate_base_weights(sleeve, ic_panel)
    return {regime: apply_regime_overlay(base, sleeve, regime) for regime in REGIMES}
