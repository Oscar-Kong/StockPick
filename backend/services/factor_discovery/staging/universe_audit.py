"""Point-in-time universe audit (SQL-aggregate first)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from data.db_engine import get_engine
from data.historical_store import DailyQuote
from engines.quant_models import UniversePit
from services.factor_discovery.staging.audit_limits import (
    MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY,
    MAXIMUM_QUOTE_ALIGNMENT_SAMPLE,
)
from services.factor_discovery.staging.policies import STAGING_COVERAGE_MINIMUMS, UniversePitMembershipPolicy
from services.factor_discovery.staging.symbol_identity import normalize_symbol


@dataclass
class UniverseAuditReport:
    policy_id: str
    total_membership_rows: int = 0
    unique_symbols: int = 0
    unique_dates: int = 0
    earliest_date: str | None = None
    latest_date: str | None = None
    min_eligible_per_date: int = 0
    median_eligible_per_date: float = 0.0
    max_eligible_per_date: int = 0
    entry_events: int = 0
    exit_events: int = 0
    empty_dates: list[str] = field(default_factory=list)
    duplicate_memberships: int = 0
    constant_membership_ratio: float = 0.0
    current_list_only_pattern: bool = False
    symbols_without_quotes: list[str] = field(default_factory=list)
    quotes_without_membership: int = 0
    blocking_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    survivorship_status: str = "unknown"
    audit_hash: str = ""
    coverage_minimums: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "total_membership_rows": self.total_membership_rows,
            "unique_symbols": self.unique_symbols,
            "unique_dates": self.unique_dates,
            "earliest_date": self.earliest_date,
            "latest_date": self.latest_date,
            "min_eligible_per_date": self.min_eligible_per_date,
            "median_eligible_per_date": self.median_eligible_per_date,
            "max_eligible_per_date": self.max_eligible_per_date,
            "entry_events": self.entry_events,
            "exit_events": self.exit_events,
            "empty_dates": self.empty_dates[:MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY],
            "duplicate_memberships": self.duplicate_memberships,
            "constant_membership_ratio": self.constant_membership_ratio,
            "current_list_only_pattern": self.current_list_only_pattern,
            "symbols_without_quotes": self.symbols_without_quotes[:MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY],
            "quotes_without_membership": self.quotes_without_membership,
            "blocking_codes": self.blocking_codes,
            "warnings": self.warnings,
            "survivorship_status": self.survivorship_status,
            "audit_hash": self.audit_hash,
            "coverage_minimums": self.coverage_minimums,
        }


def _audit_hash(report: UniverseAuditReport) -> str:
    payload = json.dumps(
        {
            "rows": report.total_membership_rows,
            "blocking": report.blocking_codes,
            "constant_ratio": report.constant_membership_ratio,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


class FactorDiscoveryUniverseAuditService:
    def __init__(self, policy: UniversePitMembershipPolicy | None = None) -> None:
        self._policy = policy or UniversePitMembershipPolicy()
        self._coverage_minimums = STAGING_COVERAGE_MINIMUMS

    def audit(self) -> UniverseAuditReport:
        report = UniverseAuditReport(
            policy_id=self._policy.policy_id,
            coverage_minimums=self._coverage_minimums,
        )
        engine = get_engine()
        with Session(engine) as session:
            report.total_membership_rows = (
                session.query(func.count()).select_from(UniversePit).filter(UniversePit.is_active.is_(True)).scalar() or 0
            )
            if report.total_membership_rows == 0:
                report.blocking_codes.append("universe_pit_empty")
                report.survivorship_status = "unverified"
                report.audit_hash = _audit_hash(report)
                return report

            report.unique_symbols = (
                session.query(func.count(func.distinct(UniversePit.symbol)))
                .filter(UniversePit.is_active.is_(True))
                .scalar()
                or 0
            )
            report.unique_dates = (
                session.query(func.count(func.distinct(UniversePit.as_of_date)))
                .filter(UniversePit.is_active.is_(True))
                .scalar()
                or 0
            )
            report.earliest_date = (
                session.query(func.min(UniversePit.as_of_date)).filter(UniversePit.is_active.is_(True)).scalar()
            )
            report.latest_date = (
                session.query(func.max(UniversePit.as_of_date)).filter(UniversePit.is_active.is_(True)).scalar()
            )

            report.duplicate_memberships = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM (SELECT as_of_date, symbol FROM universe_pit "
                        "GROUP BY as_of_date, symbol HAVING COUNT(*) > 1)"
                    )
                ).scalar()
                or 0
            )

            counts = session.execute(
                text(
                    "SELECT as_of_date, COUNT(*) AS c FROM universe_pit "
                    "WHERE is_active = 1 GROUP BY as_of_date ORDER BY as_of_date"
                )
            ).fetchall()
            if counts:
                values = [int(r[1]) for r in counts]
                report.min_eligible_per_date = min(values)
                report.max_eligible_per_date = max(values)
                report.median_eligible_per_date = float(sorted(values)[len(values) // 2])

            if report.unique_dates >= 2:
                set_stats = session.execute(
                    text(
                        """
                        WITH daily AS (
                            SELECT as_of_date,
                                   GROUP_CONCAT(DISTINCT symbol ORDER BY symbol) AS symset
                            FROM universe_pit
                            WHERE is_active = 1
                            GROUP BY as_of_date
                        )
                        SELECT COUNT(*) AS day_count,
                               COUNT(DISTINCT symset) AS distinct_sets
                        FROM daily
                        """
                    )
                ).fetchone()
                distinct_sets = int(set_stats[1] or 0) if set_stats else 0
                membership_sets_match = distinct_sets <= 1
                report.constant_membership_ratio = 1.0 if membership_sets_match else 0.0
                if membership_sets_match and report.unique_dates > 5:
                    report.current_list_only_pattern = True
                    report.blocking_codes.append("constant_membership_detected")
                    report.survivorship_status = "current_list_bias_detected"
                elif membership_sets_match:
                    report.warnings.append("constant_membership_over_short_window")
                    report.survivorship_status = "pit_membership_partially_verified"
                else:
                    report.survivorship_status = "pit_membership_verified"

            # Entry/exit events from daily membership deltas (SQL bounded)
            delta_rows = session.execute(
                text(
                    """
                    WITH daily AS (
                        SELECT as_of_date, symbol FROM universe_pit WHERE is_active = 1
                    ),
                    keyed AS (
                        SELECT symbol,
                               as_of_date,
                               LAG(as_of_date) OVER (PARTITION BY symbol ORDER BY as_of_date) AS prev_date
                        FROM daily
                    )
                    SELECT
                        SUM(CASE WHEN prev_date IS NULL THEN 1 ELSE 0 END) AS entries,
                        SUM(CASE WHEN prev_date IS NOT NULL
                                  AND JULIANDAY(as_of_date) - JULIANDAY(prev_date) > 7 THEN 1 ELSE 0 END) AS gaps
                    FROM keyed
                    """
                )
            ).fetchone()
            if delta_rows:
                report.entry_events = int(delta_rows[0] or 0)

            exit_rows = session.execute(
                text(
                    """
                    WITH daily AS (
                        SELECT as_of_date, symbol FROM universe_pit WHERE is_active = 1
                    ),
                    keyed AS (
                        SELECT symbol,
                               as_of_date,
                               LEAD(as_of_date) OVER (PARTITION BY symbol ORDER BY as_of_date) AS next_date
                        FROM daily
                    )
                    SELECT COUNT(*) FROM keyed
                    WHERE next_date IS NULL OR JULIANDAY(next_date) - JULIANDAY(as_of_date) > 7
                    """
                )
            ).scalar()
            report.exit_events = int(exit_rows or 0)

            missing_quote = session.execute(
                text(
                    f"""
                    SELECT DISTINCT up.symbol FROM universe_pit up
                    LEFT JOIN daily_quotes dq ON dq.symbol = up.symbol
                    WHERE up.is_active = 1 AND dq.symbol IS NULL
                    LIMIT {MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY}
                    """
                )
            ).fetchall()
            report.symbols_without_quotes = [normalize_symbol(r[0]) for r in missing_quote]

            report.quotes_without_membership = int(
                session.execute(
                    text(
                        f"""
                        SELECT COUNT(*) FROM (
                            SELECT DISTINCT dq.date, dq.symbol FROM daily_quotes dq
                            LEFT JOIN universe_pit up
                              ON up.as_of_date = dq.date AND up.symbol = dq.symbol AND up.is_active = 1
                            WHERE up.symbol IS NULL
                            LIMIT {MAXIMUM_QUOTE_ALIGNMENT_SAMPLE}
                        )
                        """
                    )
                ).scalar()
                or 0
            )

        if report.unique_dates < 2:
            report.blocking_codes.append("insufficient_pit_date_coverage")
        if report.min_eligible_per_date < self._coverage_minimums["min_eligible_symbols_per_date"]:
            report.blocking_codes.append("insufficient_eligible_symbols_per_date")
        if report.duplicate_memberships:
            report.blocking_codes.append("duplicate_membership_rows")
        if report.symbols_without_quotes:
            report.warnings.append("membership_without_quote_coverage")
        report.audit_hash = _audit_hash(report)
        return report

    @staticmethod
    def expand_interval_membership(
        intervals: list[dict],
        *,
        sessions: list[str],
        effective_end_inclusive: bool = True,
    ) -> list[dict]:
        session_set = sorted(set(sessions))
        out: list[dict] = []
        for interval in intervals:
            sym = normalize_symbol(str(interval["symbol"]))
            start = str(interval["effective_start"])[:10]
            end = str(interval.get("effective_end") or sessions[-1])[:10]
            for d in session_set:
                in_range = start <= d <= end if effective_end_inclusive else start <= d < end
                if in_range:
                    out.append(
                        {
                            "as_of_date": d,
                            "symbol": sym,
                            "is_active": True,
                            "bucket_hint": interval.get("bucket_hint", "staging"),
                            "instrument_id": interval.get("instrument_id"),
                            "source_id": interval.get("source_id"),
                            "source_version": interval.get("source_version"),
                        }
                    )
        return out

    @staticmethod
    def load_trading_sessions(
        *,
        start: str | None,
        end: str | None,
    ) -> list[str]:
        with Session(get_engine()) as session:
            q = session.query(DailyQuote.date).distinct()
            if start:
                q = q.filter(DailyQuote.date >= start)
            if end:
                q = q.filter(DailyQuote.date <= end)
            dates = sorted({r[0] for r in q.all()})
        # Weekday filter — observed calendar fallback
        from datetime import datetime

        out = []
        for d in dates:
            dt = datetime.strptime(d[:10], "%Y-%m-%d")
            if dt.weekday() < 5:
                out.append(d[:10])
        return out
