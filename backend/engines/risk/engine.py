"""RiskEngine — alert-driven risk score and score deductions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import RISK_ENGINE_V2
from services.alerts import compute_alerts

_SEVERITY_DEDUCTION = {"high": 5.0, "medium": 3.0, "low": 1.0}
_MAX_DEDUCTION = 25.0


@dataclass
class RiskAssessment:
    risk_score: float
    deduction_pts: float
    breakdown: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, str]] = field(default_factory=list)
    volatility_risk: dict[str, Any] = field(default_factory=dict)


class RiskEngine:
    @staticmethod
    def assess(
        symbol: str,
        sleeve: str,
        *,
        final_score: float,
        days_until_earnings: float | None = None,
        valuation_warnings: list[str] | None = None,
        data_quality_score: float | None = None,
        reconcile_flags: list[str] | None = None,
        last_scanned_at: str | None = None,
        openbb_risk_flags: list[str] | None = None,
        openbb_governance_score: float | None = None,
        apply_deduction: bool | None = None,
        volatility_risk: dict[str, Any] | None = None,
        returns: Any | None = None,
    ) -> RiskAssessment:
        alerts = compute_alerts(
            symbol,
            bucket=sleeve,
            score=final_score,
            days_until_earnings=days_until_earnings,
            valuation_warnings=valuation_warnings,
            data_quality_score=data_quality_score,
            reconcile_flags=reconcile_flags,
            last_scanned_at=last_scanned_at,
            openbb_risk_flags=openbb_risk_flags,
            openbb_governance_score=openbb_governance_score,
        )

        breakdown: list[dict[str, Any]] = []
        deduction = 0.0
        for alert in alerts:
            sev = (alert.get("severity") or "low").lower()
            pts = _SEVERITY_DEDUCTION.get(sev, 1.0)
            deduction += pts
            breakdown.append(
                {
                    "type": alert.get("type"),
                    "severity": sev,
                    "message": alert.get("message"),
                    "deduction_pts": pts,
                }
            )
        deduction = min(_MAX_DEDUCTION, deduction)

        vol_payload = dict(volatility_risk or {})
        if not vol_payload and returns is not None:
            try:
                from engines.risk.volatility import assess_volatility_risk

                vol_payload = assess_volatility_risk(returns)
            except Exception:
                vol_payload = {}

        if apply_deduction is None:
            apply_deduction = RISK_ENGINE_V2

        if apply_deduction and vol_payload.get("sufficient_data"):
            vpen = float(vol_payload.get("risk_penalty_pts") or 0.0)
            if vpen > 0:
                deduction = min(_MAX_DEDUCTION, deduction + vpen)
                breakdown.append(
                    {
                        "type": "volatility",
                        "severity": "medium" if vpen < 4 else "high",
                        "message": (
                            f"Vol regime {vol_payload.get('volatility_regime')}"
                            f"{' with tail risk' if vol_payload.get('tail_risk') else ''}"
                        ),
                        "deduction_pts": vpen,
                    }
                )

        risk_score = round(max(0.0, min(100.0, 100.0 - deduction * 3.2)), 1)

        return RiskAssessment(
            risk_score=risk_score,
            deduction_pts=deduction if apply_deduction else 0.0,
            breakdown=breakdown,
            alerts=alerts,
            volatility_risk=vol_payload,
        )

    @staticmethod
    def apply_deduction(score: float, assessment: RiskAssessment) -> float:
        adjusted = score - assessment.deduction_pts
        return round(max(0.0, min(100.0, adjusted)), 2)
