"""Buy vs wait conviction for scan candidates (research hint — not a trade order)."""
from __future__ import annotations

from typing import Any

from engines.recommendation.engine import recommendation_label_from_score
from models.schemas import RiskLevel

_RISK_WAIT_BONUS: dict[RiskLevel, float] = {
    RiskLevel.low: 0.0,
    RiskLevel.medium: 12.0,
    RiskLevel.high: 28.0,
}


def _normalize_pair(buy_raw: float, wait_raw: float) -> tuple[float, float]:
    buy_raw = max(0.0, buy_raw)
    wait_raw = max(0.0, wait_raw)
    total = buy_raw + wait_raw
    if total <= 0:
        return 50.0, 50.0
    buy_pct = round(100.0 * buy_raw / total, 1)
    wait_pct = round(100.0 - buy_pct, 1)
    return buy_pct, wait_pct


def _gate_label(
    label: str,
    *,
    data_quality_score: float | None,
    provider_limited: bool,
    earnings_soon: bool,
    risk_level: RiskLevel,
) -> tuple[str, list[str]]:
    gates: list[str] = []
    if data_quality_score is not None and data_quality_score < 35:
        return "high_risk_no_decision", ["Insufficient data quality"]
    if provider_limited:
        if label in ("strong_buy", "buy"):
            label = "watch"
        gates.append("Partial provider data")
    if data_quality_score is not None and data_quality_score < 50:
        if label in ("strong_buy", "buy"):
            label = "watch"
        gates.append("Low data quality")
    if earnings_soon and label == "strong_buy":
        label = "buy"
        gates.append("Earnings soon")
    if risk_level == RiskLevel.high and label == "strong_buy":
        label = "buy"
        gates.append("Elevated risk")
    return label, gates


def _short_reason(
    label: str,
    *,
    score: float,
    gates: list[str],
) -> str:
    if gates:
        return gates[0]
    if label in ("strong_buy", "buy"):
        return f"Score {score:.0f} supports entry"
    if label == "watch":
        return "Setup forming — confirm before sizing"
    if label == "avoid":
        return "Weak score — skip for now"
    if label == "high_risk_no_decision":
        return "Data too thin for a confident call"
    return "Mixed signals — patience"


def compute_scan_trade_hint(
    *,
    score: float,
    sleeve: str,
    risk_level: RiskLevel,
    data_quality_score: float | None = None,
    earnings_soon: bool = False,
    provider_limited: bool = False,
) -> dict[str, Any]:
    """Return recommendation label plus buy/wait mix for a scan row."""
    score = max(0.0, min(100.0, float(score)))

    buy_raw = max(0.0, (score - 35.0) * 1.4)
    wait_raw = max(5.0, 100.0 - score * 0.85) + _RISK_WAIT_BONUS.get(risk_level, 12.0)

    if earnings_soon:
        wait_raw += 15.0
        buy_raw *= 0.75
    if provider_limited:
        wait_raw += 20.0
        buy_raw *= 0.6

    if data_quality_score is not None:
        dq = float(data_quality_score)
        if dq < 50:
            buy_raw *= 0.55
            wait_raw += 18.0
        if dq < 35:
            buy_raw *= 0.3
            wait_raw += 25.0

    if sleeve == "penny":
        if score < 58:
            buy_raw *= 0.5
            wait_raw += 10.0
        if risk_level == RiskLevel.high:
            buy_raw *= 0.65
    elif sleeve == "compounder":
        if score < 62:
            buy_raw *= 0.45
            wait_raw += 8.0

    buy_pct, wait_pct = _normalize_pair(buy_raw, wait_raw)
    label = recommendation_label_from_score(score)
    label, gates = _gate_label(
        label,
        data_quality_score=data_quality_score,
        provider_limited=provider_limited,
        earnings_soon=earnings_soon,
        risk_level=risk_level,
    )

    return {
        "recommendation": label,
        "buy_pct": buy_pct,
        "wait_pct": wait_pct,
        "trade_hint_reason": _short_reason(label, score=score, gates=gates),
    }


def attach_trade_hint_to_metrics(
    metrics: dict[str, Any],
    *,
    score: float,
    sleeve: str,
    risk_level: RiskLevel,
    data_quality_score: float | None = None,
    earnings_soon: bool = False,
    provider_limited: bool = False,
) -> dict[str, Any]:
    out = dict(metrics)
    out.update(
        compute_scan_trade_hint(
            score=score,
            sleeve=sleeve,
            risk_level=risk_level,
            data_quality_score=data_quality_score,
            earnings_soon=earnings_soon or bool(metrics.get("earnings_soon")),
            provider_limited=provider_limited or bool(metrics.get("provider_limited_partial_data")),
        )
    )
    return out
