"""Named OpenAlpha-inspired formulas — registry + evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json
import pandas as pd

from scoring.openalpha_factors import OPENALPHA_SCORERS, score_openalpha_factor

REGISTRY_PATH = Path(__file__).resolve().parent / "openalpha_registry.json"


@dataclass(frozen=True)
class AlphaFormula:
    id: str
    sleeve: str
    display_name: str
    openalpha_ref: str
    expression: str
    factor_key: str
    weight: float
    tier: str
    enabled_live: bool


def load_registry(path: Path | None = None) -> list[AlphaFormula]:
    path = path or REGISTRY_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[AlphaFormula] = []
    for row in raw.get("formulas", []):
        out.append(
            AlphaFormula(
                id=str(row["id"]),
                sleeve=str(row["sleeve"]),
                display_name=str(row["display_name"]),
                openalpha_ref=str(row.get("openalpha_ref", "")),
                expression=str(row.get("expression", "")),
                factor_key=str(row["factor_key"]),
                weight=float(row.get("weight", 0.05)),
                tier=str(row.get("tier", "experimental")),
                enabled_live=bool(row.get("enabled_live", True)),
            )
        )
    return out


def formulas_for_sleeve(sleeve: str) -> list[AlphaFormula]:
    return [f for f in load_registry() if f.sleeve == sleeve]


def evaluate_formula(
    formula: AlphaFormula | str,
    hist: pd.DataFrame,
    spy: pd.DataFrame | None = None,
) -> float | None:
    if isinstance(formula, str):
        match = next((f for f in load_registry() if f.id == formula or f.factor_key == formula), None)
        if not match:
            return score_openalpha_factor(formula, hist, spy)
        formula = match
    return score_openalpha_factor(formula.factor_key, hist, spy)


def registry_summary() -> list[dict[str, Any]]:
    return [
        {
            "id": f.id,
            "sleeve": f.sleeve,
            "display_name": f.display_name,
            "openalpha_ref": f.openalpha_ref,
            "expression": f.expression,
            "factor_key": f.factor_key,
            "implemented": f.factor_key in OPENALPHA_SCORERS,
        }
        for f in load_registry()
    ]
