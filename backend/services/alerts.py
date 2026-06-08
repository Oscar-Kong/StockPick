"""Watchlist / analysis alerts (kept separate to avoid import cycles)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from data.historical_store import FactorSnapshot, HistoricalStore

_STALE_HOURS = 24
_SCORE_DROP_THRESHOLD = 8.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


from utils.datetime_util import parse_api_datetime


def _parse_dt(value: str | None) -> datetime | None:
    return parse_api_datetime(value)


def _is_stale(last_scanned_at: str | None) -> bool:
    dt = _parse_dt(last_scanned_at)
    if not dt:
        return True
    return (_utcnow() - dt) > timedelta(hours=_STALE_HOURS)


def _get_previous_score(symbol: str, bucket: str) -> float | None:
    store = HistoricalStore()
    session = store._get_session()
    try:
        rows = (
            session.query(FactorSnapshot)
            .filter(
                FactorSnapshot.symbol == symbol.upper(),
                FactorSnapshot.bucket == bucket,
            )
            .order_by(FactorSnapshot.updated_at.desc())
            .limit(2)
            .all()
        )
        if len(rows) < 2:
            return None
        return float(rows[1].score) if rows[1].score is not None else None
    finally:
        session.close()


def compute_alerts(
    symbol: str,
    *,
    bucket: str,
    score: float | None,
    days_until_earnings: float | None,
    valuation_warnings: list[str] | None,
    data_quality_score: float | None,
    reconcile_flags: list[str] | None,
    last_scanned_at: str | None,
    openbb_risk_flags: list[str] | None = None,
    openbb_governance_score: float | None = None,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []

    if days_until_earnings is not None and 0 <= days_until_earnings <= 7:
        alerts.append(
            {
                "type": "earnings",
                "severity": "high",
                "message": f"Earnings in {int(days_until_earnings)} day(s)",
            }
        )

    if _is_stale(last_scanned_at):
        alerts.append(
            {
                "type": "stale",
                "severity": "medium",
                "message": "Scan data older than 24h — refresh recommended",
            }
        )

    prev = _get_previous_score(symbol, bucket)
    if score is not None and prev is not None and prev - score >= _SCORE_DROP_THRESHOLD:
        alerts.append(
            {
                "type": "score_drop",
                "severity": "medium",
                "message": f"Score fell {prev - score:.1f} pts vs prior snapshot ({prev:.0f} → {score:.0f})",
            }
        )

    for flag in reconcile_flags or []:
        alerts.append({"type": "reconcile", "severity": "medium", "message": flag})

    if data_quality_score is not None and data_quality_score < 40:
        alerts.append(
            {
                "type": "data_quality",
                "severity": "medium",
                "message": f"Low data quality ({data_quality_score:.0f}%)",
            }
        )

    for w in valuation_warnings or []:
        alerts.append({"type": "valuation", "severity": "low", "message": w[:120]})

    if openbb_governance_score is not None and openbb_governance_score < 45:
        alerts.append(
            {
                "type": "governance",
                "severity": "high",
                "message": f"Low SEC/insider governance score ({openbb_governance_score:.0f}/100)",
            }
        )
    for flag in openbb_risk_flags or []:
        if flag == "insider_sell":
            alerts.append(
                {
                    "type": "governance",
                    "severity": "high",
                    "message": "Heavy insider selling (OpenBB SEC data)",
                }
            )
        elif flag == "sec_offering":
            alerts.append(
                {
                    "type": "governance",
                    "severity": "high",
                    "message": "Recent offering / shelf registration filing",
                }
            )
        elif flag == "sec_8k":
            alerts.append(
                {
                    "type": "governance",
                    "severity": "medium",
                    "message": "Recent 8-K — check material events",
                }
            )

    return alerts
