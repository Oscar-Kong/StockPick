"""Factor Discovery research data capability reporting."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FactorResearchDataCapabilities:
    provider_id: str
    price_research_available: bool
    adjusted_prices_available: bool
    pit_universe_available: bool
    pit_fundamentals_available: bool
    pit_sector_history_available: bool
    historical_market_cap_available: bool
    supported_date_range: tuple[str, str] | None
    supported_fields: tuple[str, ...] = field(default_factory=tuple)
    blocking_reasons: tuple[str, ...] = field(default_factory=tuple)
    provider_data_version: str = ""

    def ready_for_fields(self, required_fields: set[str]) -> tuple[bool, tuple[str, ...]]:
        missing = sorted(f for f in required_fields if f not in self.supported_fields)
        reasons = list(self.blocking_reasons)
        if missing:
            reasons.append(f"unsupported_fields:{','.join(missing)}")
        if not self.price_research_available:
            reasons.append("price_research_unavailable")
        if not self.adjusted_prices_available:
            reasons.append("adjusted_prices_unavailable")
        if not self.pit_universe_available:
            reasons.append("pit_universe_unavailable")
        neutralization_fields = {"sector", "industry", "market_cap"}
        if required_fields & neutralization_fields:
            if "sector" in required_fields or "industry" in required_fields:
                if not self.pit_sector_history_available:
                    reasons.append("pit_sector_history_unavailable")
            if "market_cap" in required_fields and not self.historical_market_cap_available:
                reasons.append("historical_market_cap_unavailable")
        fund_fields = {"free_cash_flow", "revenue", "earnings"}
        if required_fields & fund_fields and not self.pit_fundamentals_available:
            reasons.append("pit_fundamentals_unavailable")
        return (len(reasons) == 0, tuple(dict.fromkeys(reasons)))
