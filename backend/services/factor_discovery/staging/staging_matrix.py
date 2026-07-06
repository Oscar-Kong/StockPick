"""Staging matrix construction for extended Phase 9B.2 validation."""
from __future__ import annotations

from dataclasses import dataclass, field

from core.sleeve import ACTIVE_SLEEVES, normalize_sleeve
from services.factor_discovery.staging.policies import STAGING_FACTOR_DEFINITIONS, STAGING_FROZEN_FACTOR
from services.factor_discovery.staging.supported_dates import RegimeSlice

EXTENDED_STAGING_BASELINE_FACTOR = {
    "factor_key": "staging_momentum_baseline_20d",
    "display_name": "Staging Momentum Baseline 20D",
    "dsl": "rank(delta(adjusted_close, 20))",
    "direction": "long_high",
    "family_suffix": "staging_baseline_v1",
    "role": "baseline",
}

STAGING_MATRIX_FACTORS = (STAGING_FROZEN_FACTOR, *STAGING_FACTOR_DEFINITIONS, EXTENDED_STAGING_BASELINE_FACTOR)


@dataclass
class StagingMatrixCell:
    cell_id: str
    sleeve: str
    slice_id: str
    slice_label: str
    start_date: str
    end_date: str
    regime_type: str
    factor_key: str
    factor_dsl: str
    factor_role: str
    random_seed: int
    reproducibility_candidate: bool = False

    def to_dict(self) -> dict:
        return {
            "cell_id": self.cell_id,
            "sleeve": self.sleeve,
            "slice_id": self.slice_id,
            "slice_label": self.slice_label,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "regime_type": self.regime_type,
            "factor_key": self.factor_key,
            "factor_dsl": self.factor_dsl,
            "factor_role": self.factor_role,
            "random_seed": self.random_seed,
            "reproducibility_candidate": self.reproducibility_candidate,
        }


@dataclass
class StagingMatrix:
    sleeves: list[str]
    cells: list[StagingMatrixCell] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sleeves": self.sleeves,
            "cell_count": len(self.cells),
            "cells": [c.to_dict() for c in self.cells],
        }


def build_staging_matrix(
    *,
    sleeves: list[str],
    slices: list[RegimeSlice],
    random_seed: int = 42,
    include_baseline: bool = True,
) -> StagingMatrix:
    normalized = [normalize_sleeve(s) for s in sleeves]
    for s in normalized:
        if s not in ACTIVE_SLEEVES:
            raise ValueError(f"unsupported sleeve: {s}")

    factors = list(STAGING_MATRIX_FACTORS)
    if not include_baseline:
        factors = [f for f in factors if f.get("role") != "baseline"]

    cells: list[StagingMatrixCell] = []
    for sleeve in normalized:
        for sl in slices:
            for spec in factors:
                role = spec.get("role", "candidate")
                cell_id = f"{sleeve}:{sl.slice_id}:{spec['factor_key']}"
                repro = spec["factor_key"] == STAGING_FROZEN_FACTOR["factor_key"] and sl.slice_id in {
                    "middle_period",
                    "recent_period",
                }
                cells.append(
                    StagingMatrixCell(
                        cell_id=cell_id,
                        sleeve=sleeve,
                        slice_id=sl.slice_id,
                        slice_label=sl.label,
                        start_date=sl.start_date,
                        end_date=sl.end_date,
                        regime_type=sl.regime_type,
                        factor_key=spec["factor_key"],
                        factor_dsl=spec["dsl"],
                        factor_role=role,
                        random_seed=random_seed,
                        reproducibility_candidate=repro,
                    )
                )
    return StagingMatrix(sleeves=normalized, cells=cells)
