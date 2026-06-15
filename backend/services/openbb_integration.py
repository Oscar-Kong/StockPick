"""OpenBB integration layer for Stock Picker screening and enrichment."""
from __future__ import annotations

import logging
from typing import Any

from config import OPENBB_ENABLED, OPENBB_ON_SCAN
from models.schemas import Bucket
from scoring.openbb_governance import adjust_score_for_governance

logger = logging.getLogger(__name__)


def apply_openbb_to_metrics(
    symbol: str,
    metrics: dict[str, Any],
    warnings: list[str],
    *,
    allow_fetch: bool | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Attach OpenBB governance snapshot to screener metrics and valuation warnings."""
    from data.openbb_client import get_risk_snapshot, is_available

    if not OPENBB_ENABLED or not is_available():
        return metrics, warnings

    if allow_fetch is None:
        allow_fetch = OPENBB_ON_SCAN

    snap = get_risk_snapshot(symbol, allow_fetch=allow_fetch, use_cache=True)
    if allow_fetch is False and snap.governance_score == 70.0 and not snap.flags:
        return metrics, warnings
    metrics = dict(metrics)
    metrics["openbb_governance_score"] = snap.governance_score
    metrics["openbb_risk_flags"] = snap.flags
    if snap.recent_filings:
        metrics["openbb_recent_filings"] = [
            {
                "form": f.get("form") or f.get("form_type"),
                "date": f.get("filing_date") or f.get("accepted_date"),
            }
            for f in snap.recent_filings[:3]
        ]
    if snap.insider_sell_ratio is not None:
        metrics["openbb_insider_sell_ratio"] = round(snap.insider_sell_ratio, 2)

    merged_warnings = list(dict.fromkeys(warnings + snap.warnings))
    return metrics, merged_warnings


def apply_openbb_score_adjustment(score: float, metrics: dict[str, Any]) -> float:
    """Post-score governance adjustment (after data-quality pass)."""
    return adjust_score_for_governance(score, metrics.get("openbb_governance_score"))


def governance_signal_value(symbol: str, *, allow_fetch: bool | None = None) -> float | None:
    """0–100 signal for compounder/medium weighted scoring."""
    from data.openbb_client import get_risk_snapshot, is_available

    if not OPENBB_ENABLED or not is_available():
        return None
    if allow_fetch is None:
        allow_fetch = OPENBB_ON_SCAN
    snap = get_risk_snapshot(symbol, allow_fetch=allow_fetch, use_cache=True)
    if allow_fetch is False and not snap.flags and snap.governance_score == 70.0:
        return None
    return snap.governance_score


def enrich_research_risks(symbol: str, risk_pool: list[str]) -> list[str]:
    """Append SEC / insider risks for research report section 8."""
    from data.openbb_client import get_risk_snapshot, is_available

    if not OPENBB_ENABLED or not is_available():
        return risk_pool
    # Keep report generation responsive; do not trigger slow interactive SEC backfills here.
    snap = get_risk_snapshot(symbol, allow_fetch=False, use_cache=True)
    return list(dict.fromkeys(risk_pool + snap.warnings))


def bucket_uses_governance_signal(bucket: Bucket) -> bool:
    return bucket in (Bucket.medium, Bucket.compounder)


def append_governance_signal(
    signals: list,
    symbol: str,
    *,
    allow_fetch: bool | None = None,
) -> list:
    """Add a 5% governance leg and rescale existing signal weights (medium/compounder)."""
    from services.scan_context import is_bulk_scan

    if is_bulk_scan():
        return signals

    from screeners.base import WeightedSignal

    gov = governance_signal_value(symbol, allow_fetch=allow_fetch)
    if gov is None:
        return signals
    scale = 0.95
    out = [
        WeightedSignal(s.name, s.value, s.weight * scale, s.description)
        for s in signals
    ]
    out.append(
        WeightedSignal(
            "SEC / insider governance",
            gov,
            0.05,
            "OpenBB: recent SEC filings and insider activity",
        )
    )
    return out
