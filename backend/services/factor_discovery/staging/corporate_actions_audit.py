"""Corporate-action and adjustment consistency audit."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from data.db_engine import get_engine
from data.historical_store import DailyQuote


@dataclass
class CorporateActionsAuditReport:
    largest_jumps: list[dict] = field(default_factory=list)
    mixed_adjustment_symbols: list[str] = field(default_factory=list)
    duplicate_dates: int = 0
    provider_declared_only: bool = True
    blocking_codes: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "largest_jumps": self.largest_jumps[:20],
            "mixed_adjustment_symbols": self.mixed_adjustment_symbols,
            "duplicate_dates": self.duplicate_dates,
            "provider_declared_only": self.provider_declared_only,
            "blocking_codes": self.blocking_codes,
            "limitations": self.limitations,
        }


class FactorDiscoveryCorporateActionsAuditService:
    def audit(self) -> CorporateActionsAuditReport:
        report = CorporateActionsAuditReport(
            limitations=[
                "Only adjusted close series available; split/dividend adjustment is provider-declared",
                "Independent corporate-action verification requires raw+adjusted pairs",
            ]
        )
        per_symbol_adj: dict[str, set[int]] = {}
        prev_close: dict[str, float] = {}
        with Session(get_engine()) as session:
            rows = session.query(DailyQuote).order_by(DailyQuote.symbol, DailyQuote.date).all()
            seen: set[tuple[str, str]] = set()
            for row in rows:
                key = (row.symbol, row.date)
                if key in seen:
                    report.duplicate_dates += 1
                seen.add(key)
                per_symbol_adj.setdefault(row.symbol, set()).add(int(row.adjusted or 0))
                pc = prev_close.get(row.symbol)
                if pc and pc > 0:
                    ret = abs(float(row.close) / pc - 1.0)
                    if ret > 0.45:
                        report.largest_jumps.append(
                            {"symbol": row.symbol, "date": row.date, "return_abs": round(ret, 4)}
                        )
                prev_close[row.symbol] = float(row.close)
        for sym, flags in per_symbol_adj.items():
            if len(flags) > 1:
                report.mixed_adjustment_symbols.append(sym)
        if report.mixed_adjustment_symbols:
            report.blocking_codes.append("mixed_adjustment_evidence")
        return report
