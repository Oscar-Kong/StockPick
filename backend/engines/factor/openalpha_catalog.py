"""Merge OpenAlpha-inspired factors into the live catalog when enabled."""
from __future__ import annotations

from engines.factor.catalog import FactorSpec, active_factor_catalog
from engines.factor.expr import load_registry


def openalpha_factor_specs() -> list[FactorSpec]:
    specs: list[FactorSpec] = []
    for f in load_registry():
        if not f.enabled_live:
            continue
        specs.append(
            FactorSpec(
                factor_id=f"{f.sleeve}_oa_{f.factor_key}",
                display_name=f.display_name,
                weight=f.weight,
                tier=f.tier,
                formula_version="openalpha-us-v1",
                signal_name=f.display_name,
            )
        )
    return specs


def merge_catalog_with_openalpha(base: dict[str, list[FactorSpec]]) -> dict[str, list[FactorSpec]]:
    """Add OpenAlpha legs and renormalize sleeve weights to sum to 1."""
    oa_by_sleeve: dict[str, list[FactorSpec]] = {}
    for spec in openalpha_factor_specs():
        sleeve = spec.factor_id.split("_", 1)[0]
        oa_by_sleeve.setdefault(sleeve, []).append(spec)

    merged: dict[str, list[FactorSpec]] = {}
    for sleeve, legs in base.items():
        extra = oa_by_sleeve.get(sleeve, [])
        if not extra:
            merged[sleeve] = list(legs)
            continue
        oa_weight = sum(s.weight for s in extra)
        scale = max(0.01, 1.0 - oa_weight)
        base_sum = sum(s.weight for s in legs) or 1.0
        scaled = [
            FactorSpec(
                s.factor_id,
                s.display_name,
                round(s.weight / base_sum * scale, 4),
                s.tier,
                s.formula_version,
                s.signal_name,
            )
            for s in legs
        ]
        merged[sleeve] = scaled + extra
    return merged


def catalog_with_openalpha() -> dict[str, list[FactorSpec]]:
    from config import OPENALPHA_FACTORS_ENABLED

    base = active_factor_catalog()
    if not OPENALPHA_FACTORS_ENABLED:
        return base
    return merge_catalog_with_openalpha(base)
