"""Adjusted-price audit for Factor Discovery staging (SQL-aggregate first)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from data.db_engine import get_engine
from data.historical_store import DailyQuote
from services.factor_discovery.staging.audit_limits import (
    MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY,
    MAXIMUM_SAMPLE_SYMBOLS,
)
from services.factor_discovery.staging.policies import HistoricalAdjustedPricesPolicy


@dataclass
class PriceAuditReport:
    policy_id: str
    total_rows: int = 0
    adjusted_rows: int = 0
    raw_rows: int = 0
    symbols: int = 0
    earliest_date: str | None = None
    latest_date: str | None = None
    duplicate_rows: int = 0
    non_finite_prices: int = 0
    nonpositive_prices: int = 0
    future_dates: int = 0
    invalid_symbols: int = 0
    mixed_adjustment_symbols: list[str] = field(default_factory=list)
    suspicious_jumps: list[dict] = field(default_factory=list)
    blocking_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    audit_hash: str = ""
    audit_limits: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "total_rows": self.total_rows,
            "adjusted_rows": self.adjusted_rows,
            "raw_rows": self.raw_rows,
            "symbols": self.symbols,
            "earliest_date": self.earliest_date,
            "latest_date": self.latest_date,
            "duplicate_rows": self.duplicate_rows,
            "non_finite_prices": self.non_finite_prices,
            "nonpositive_prices": self.nonpositive_prices,
            "future_dates": self.future_dates,
            "invalid_symbols": self.invalid_symbols,
            "mixed_adjustment_symbols": self.mixed_adjustment_symbols[:MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY],
            "suspicious_jumps": self.suspicious_jumps[:MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY],
            "blocking_codes": self.blocking_codes,
            "warnings": self.warnings,
            "audit_hash": self.audit_hash,
            "audit_limits": self.audit_limits,
        }


def _audit_hash(report: PriceAuditReport) -> str:
    payload = json.dumps(
        {
            "total": report.total_rows,
            "adjusted": report.adjusted_rows,
            "blocking": report.blocking_codes,
            "mixed_count": len(report.mixed_adjustment_symbols),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


class FactorDiscoveryPriceAuditService:
    def __init__(self, policy: HistoricalAdjustedPricesPolicy | None = None) -> None:
        self._policy = policy or HistoricalAdjustedPricesPolicy()

    def audit(self, *, sample_jump_symbols: int = MAXIMUM_SAMPLE_SYMBOLS) -> PriceAuditReport:
        report = PriceAuditReport(
            policy_id=self._policy.policy_id,
            audit_limits={
                "maximum_sample_symbols": sample_jump_symbols,
                "maximum_flagged_examples_per_category": MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY,
            },
        )
        engine = get_engine()
        with Session(engine) as session:
            report.total_rows = session.query(func.count(DailyQuote.id)).scalar() or 0
            if report.total_rows == 0:
                report.blocking_codes.append("no_daily_quotes")
                report.audit_hash = _audit_hash(report)
                return report

            report.adjusted_rows = (
                session.query(func.count(DailyQuote.id)).filter(DailyQuote.adjusted == 1).scalar() or 0
            )
            report.raw_rows = report.total_rows - report.adjusted_rows
            report.symbols = session.query(func.count(func.distinct(DailyQuote.symbol))).scalar() or 0
            report.earliest_date = session.query(func.min(DailyQuote.date)).scalar()
            report.latest_date = session.query(func.max(DailyQuote.date)).scalar()

            report.duplicate_rows = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM (SELECT symbol, date FROM daily_quotes "
                        "GROUP BY symbol, date HAVING COUNT(*) > 1)"
                    )
                ).scalar()
                or 0
            )

            report.nonpositive_prices = (
                session.query(func.count(DailyQuote.id))
                .filter(
                    (DailyQuote.close <= 0)
                    | (DailyQuote.open <= 0)
                    | (DailyQuote.high <= 0)
                    | (DailyQuote.low <= 0)
                )
                .scalar()
                or 0
            )

            report.invalid_symbols = int(
                session.execute(
                    text(
                        "SELECT COUNT(*) FROM (SELECT DISTINCT symbol FROM daily_quotes "
                        "WHERE symbol IS NULL OR TRIM(symbol) = '' OR LENGTH(symbol) > 16)"
                    )
                ).scalar()
                or 0
            )

            mixed = session.execute(
                text(
                    "SELECT symbol FROM daily_quotes GROUP BY symbol "
                    "HAVING COUNT(DISTINCT adjusted) > 1 "
                    f"LIMIT {MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY}"
                )
            ).fetchall()
            report.mixed_adjustment_symbols = [r[0] for r in mixed]

            # Bounded suspicious jumps via SQL window — no full-table Python materialization
            jump_rows = session.execute(
                text(
                    f"""
                    WITH ordered AS (
                        SELECT symbol, date, close,
                               LAG(close) OVER (PARTITION BY symbol ORDER BY date) AS prev_close
                        FROM daily_quotes
                        WHERE symbol IN (
                            SELECT symbol FROM daily_quotes GROUP BY symbol
                            ORDER BY symbol LIMIT {int(sample_jump_symbols)}
                        )
                    )
                    SELECT symbol, date, close, prev_close
                    FROM ordered
                    WHERE prev_close IS NOT NULL AND prev_close > 0
                      AND ABS(close / prev_close - 1.0) > 0.5
                    LIMIT {MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY}
                    """
                )
            ).fetchall()
            report.suspicious_jumps = [
                {
                    "symbol": r[0],
                    "date": r[1],
                    "return_abs": round(abs(float(r[2]) / float(r[3]) - 1.0), 4),
                }
                for r in jump_rows
            ]

        if report.raw_rows > 0:
            report.blocking_codes.append("raw_unadjusted_rows_present")
        if report.mixed_adjustment_symbols:
            report.blocking_codes.append("mixed_adjustment_within_symbol")
        if report.nonpositive_prices:
            report.blocking_codes.append("nonpositive_prices")
        if report.adjusted_rows == 0:
            report.blocking_codes.append("no_adjusted_rows")
        if report.duplicate_rows:
            report.blocking_codes.append("duplicate_symbol_date_rows")
        if report.invalid_symbols:
            report.blocking_codes.append("invalid_symbols")
        if report.adjusted_rows / max(report.total_rows, 1) < 0.99:
            report.warnings.append("adjusted_price_ratio_below_99pct")
        if report.suspicious_jumps:
            report.warnings.append("suspicious_price_jumps_detected")
        report.audit_hash = _audit_hash(report)
        return report
