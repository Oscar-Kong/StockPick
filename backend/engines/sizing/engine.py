"""PositionSizingEngine — conviction-based weights with DQ and risk adjustments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from config import (
    DEFAULT_PORTFOLIO_EXPOSURE,
    POSITION_SIZING_V2,
    SLEEVE_MAX_WEIGHT,
)
from core.sleeve import normalize_sleeve
from engines.scoring.data_quality import dq_multiplier
@dataclass
class SizingResult:
    recommended_pct: float
    max_pct: float
    stop_loss_pct: float
    portfolio_allocation_pct: float
    conviction: float
    sleeve_max_pct: float
    risk_multiplier: float
    dq_multiplier: float
    rationale: str
    inputs: dict[str, Any]


class PositionSizingEngine:
    _STOP_ATR_MULT = {"penny": 2.5, "compounder": 3.0}
    _STOP_BOUNDS = {
        "penny": (8.0, 20.0),
        "compounder": (15.0, 35.0),
    }

    @classmethod
    def compute(
        cls,
        *,
        sleeve: str,
        final_score: float,
        data_quality_score: float | None = None,
        risk_index: float | None = None,
        portfolio_exposure: float | None = None,
        active_positions: int | None = None,
        history: pd.DataFrame | None = None,
    ) -> SizingResult | None:
        if not POSITION_SIZING_V2:
            return None

        w_max = float(SLEEVE_MAX_WEIGHT.get(normalize_sleeve(sleeve), 0.08))
        c = max(0.0, min(1.0, (final_score - 50.0) / 50.0))
        w_base = w_max * (c**2)

        phi = dq_multiplier(data_quality_score)
        r_idx = risk_index if risk_index is not None else 25.0
        m_risk = max(0.4, min(1.0, 1.0 - 0.006 * r_idx))

        w1 = w_base * phi * m_risk
        exposure = portfolio_exposure if portfolio_exposure is not None else DEFAULT_PORTFOLIO_EXPOSURE
        exposure = max(0.0, min(1.0, exposure))
        w2 = w1 * ((1.0 - exposure) ** 0.5)

        if active_positions and active_positions > 12:
            w2 *= 0.85

        w_min = 0.005
        w_rec = max(w_min, min(w_max, w2))
        w_max_out = min(w_max, w_rec * 1.25)

        stop = cls._stop_loss_pct(sleeve, history)

        rationale = (
            f"Score {final_score:.0f} → conviction {c:.0%} of sleeve cap {w_max*100:.1f}%. "
            f"DQ×{phi:.2f}, risk×{m_risk:.2f}, exposure dampener √{1-exposure:.2f}."
        )

        inputs = {
            "final_score": final_score,
            "conviction": round(c, 4),
            "data_quality_score": data_quality_score,
            "risk_index": r_idx,
            "portfolio_exposure": exposure,
            "active_positions": active_positions,
            "sleeve_max_pct": w_max,
        }

        return SizingResult(
            recommended_pct=round(w_rec * 100, 2),
            max_pct=round(w_max_out * 100, 2),
            stop_loss_pct=round(stop, 2),
            portfolio_allocation_pct=round(w_rec * 100, 2),
            conviction=round(c * 100, 1),
            sleeve_max_pct=round(w_max * 100, 2),
            risk_multiplier=round(m_risk, 3),
            dq_multiplier=round(phi, 3),
            rationale=rationale,
            inputs=inputs,
        )

    @classmethod
    def _stop_loss_pct(cls, sleeve: str, history: pd.DataFrame | None) -> float:
        key = normalize_sleeve(sleeve)
        mult = cls._STOP_ATR_MULT.get(key, 2.5)
        lo, hi = cls._STOP_BOUNDS.get(key, (8.0, 20.0))
        atr = 5.0
        if history is not None and not getattr(history, "empty", True):
            try:
                from scoring.technical import atr_percent

                atr = atr_percent(history)
            except Exception:
                pass
        stop = mult * atr
        return max(lo, min(hi, stop))
