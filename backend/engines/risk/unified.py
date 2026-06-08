"""Unified risk assessment — macro, company, events, score deductions (Phase 4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import FRED_API_KEY, RISK_ENGINE_V2
from engines.risk.engine import RiskAssessment, RiskEngine
@dataclass
class UnifiedRiskResult:
    """risk_index: 0=safe, 100=severe; safety_score: inverse for UI compatibility."""
    risk_index: float
    safety_score: float
    deduction_pts: float
    macro: list[str] = field(default_factory=list)
    company: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    score_deductions: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, str]] = field(default_factory=list)
    breakdown: list[dict[str, Any]] = field(default_factory=list)
    volatility_risk: dict[str, Any] = field(default_factory=dict)


def _check_deductions(
    *,
    days_until_earnings: float | None,
    governance_score: float | None,
    data_quality_score: float | None,
    valuation_warnings: list[str] | None,
    openbb_flags: list[str] | None,
) -> list[dict[str, Any]]:
    deductions: list[dict[str, Any]] = []
    if days_until_earnings is not None and 0 <= days_until_earnings <= 7:
        deductions.append({"category": "earnings_soon", "points": 8.0})
    if governance_score is not None and governance_score < 45:
        deductions.append({"category": "governance", "points": 10.0})
    if data_quality_score is not None and data_quality_score < 40:
        deductions.append({"category": "data_quality", "points": 15.0})
    flags_text = " ".join(openbb_flags or []).lower()
    warnings_text = " ".join(valuation_warnings or []).lower()
    if "insider" in flags_text and "sell" in flags_text:
        deductions.append({"category": "insider_sell", "points": 6.0})
    if "offering" in flags_text or "secondary" in flags_text:
        deductions.append({"category": "secondary_offering", "points": 12.0})
    if "fraud" in warnings_text or "litigation" in warnings_text or "lawsuit" in warnings_text:
        deductions.append({"category": "headline_risk", "points": 20.0})
    return deductions


def _macro_risks() -> list[str]:
    if not FRED_API_KEY:
        return ["Macro: configure FRED_API_KEY for rate/GDP regime context"]
    try:
        from data.fred_client import FredClient

        score = FredClient().macro_regime_score()
        if score >= 60:
            return ["Macro backdrop supportive for risk assets"]
        if score <= 40:
            return ["Macro backdrop challenging — tighter financial conditions"]
        return ["Macro backdrop mixed — sector selection matters"]
    except Exception:
        return ["Macro data temporarily unavailable"]


class UnifiedRiskEngine:
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
        metrics: dict[str, Any] | None = None,
        returns: Any | None = None,
    ) -> UnifiedRiskResult:
        vol_payload: dict[str, Any] = {}
        if returns is not None:
            try:
                from engines.risk.volatility import assess_volatility_risk

                vol_payload = assess_volatility_risk(returns)
            except Exception:
                vol_payload = {}

        base: RiskAssessment = RiskEngine.assess(
            symbol,
            sleeve,
            final_score=final_score,
            days_until_earnings=days_until_earnings,
            valuation_warnings=valuation_warnings,
            data_quality_score=data_quality_score,
            reconcile_flags=reconcile_flags,
            last_scanned_at=last_scanned_at,
            openbb_risk_flags=openbb_risk_flags,
            openbb_governance_score=openbb_governance_score,
            apply_deduction=RISK_ENGINE_V2,
            volatility_risk=vol_payload,
        )
        if not vol_payload and base.volatility_risk:
            vol_payload = base.volatility_risk

        structured = _check_deductions(
            days_until_earnings=days_until_earnings,
            governance_score=openbb_governance_score,
            data_quality_score=data_quality_score,
            valuation_warnings=valuation_warnings,
            openbb_flags=openbb_risk_flags,
        )
        deduction_pts = min(40.0, sum(d["points"] for d in structured) + base.deduction_pts * 0.5)
        risk_index = round(min(100.0, deduction_pts * 2.5), 1)
        safety_score = round(max(0.0, 100.0 - risk_index), 1)

        company: list[str] = []
        if days_until_earnings is not None and days_until_earnings <= 14:
            company.append(f"Earnings in {int(days_until_earnings)} day(s)")
        if openbb_governance_score is not None and openbb_governance_score < 50:
            company.append("Governance / insider activity flagged")
        if data_quality_score is not None and data_quality_score < 55:
            company.append("Cross-source data quality below preferred threshold")
        for w in valuation_warnings or []:
            company.append(w)

        events: list[str] = []
        for flag in openbb_risk_flags or []:
            events.append(flag)
        m = metrics or {}
        for h in m.get("news_red_flags") or []:
            events.append(str(h))

        if vol_payload.get("sufficient_data"):
            regime = vol_payload.get("volatility_regime")
            if regime in ("elevated", "extreme"):
                company.append(f"Realized volatility regime: {regime}")
            if vol_payload.get("tail_risk"):
                events.append("Historical tail risk elevated (deep expected shortfall)")

        return UnifiedRiskResult(
            risk_index=risk_index,
            safety_score=safety_score,
            deduction_pts=round(deduction_pts, 1),
            macro=_macro_risks(),
            company=company[:8],
            events=events[:8],
            score_deductions=structured,
            alerts=base.alerts,
            breakdown=base.breakdown + [{"layer": "structured", **d} for d in structured],
            volatility_risk=vol_payload,
        )
