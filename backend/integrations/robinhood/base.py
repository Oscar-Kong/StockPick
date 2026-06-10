"""Abstract brokerage read-only provider + conservative bucket classification."""
from __future__ import annotations

from abc import ABC, abstractmethod

from config import COMPOUNDER_MARKET_CAP_MIN, PENNY_PRICE_MAX
from integrations.robinhood.models import BrokerageSyncResult, ParsedTrade, ReconstructedHolding


class BrokerageProvider(ABC):
    source: str

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def sync_holdings(self) -> BrokerageSyncResult:
        """Pull latest holdings from external source (read-only)."""
        ...


# Obvious long-term quality tickers — conservative allowlist
_COMPOUNDER_ALLOWLIST = frozenset(
    {
        "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "BRK.B", "BRK.A",
        "V", "MA", "COST", "JPM", "UNH", "HD", "PG", "KO", "PEP", "MRK", "LLY",
    }
)


def classify_holding_bucket(symbol: str, avg_cost: float) -> str:
    """Default speculative names to penny; compounder only when clearly long-term quality."""
    sym = symbol.upper()

    if sym in _COMPOUNDER_ALLOWLIST and avg_cost >= PENNY_PRICE_MAX:
        return "compounder"

    try:
        from data.candidate_builder import build_candidate
        from data.price_service import PriceService

        ctx = build_candidate(sym, history_period="3mo", reconcile=False, price_service=PriceService())
        if ctx:
            price = float(ctx.price or avg_cost)
            mcap = ctx.info.get("marketCap")
            # Strict: large cap AND price above penny range AND not obvious speculator profile
            if (
                mcap
                and float(mcap) >= COMPOUNDER_MARKET_CAP_MIN * 2
                and price >= 50
                and avg_cost >= 20
            ):
                return "compounder"
    except Exception:
        pass

    return "penny"


def reconstruct_holdings(trades: list[ParsedTrade]) -> list[ReconstructedHolding]:
    """Legacy entry: rebuild from stored buy/sell trades only."""
    from datetime import datetime

    from integrations.robinhood.models import ParsedCsvRow
    from integrations.robinhood.portfolio_rebuilder import rebuild_portfolio

    rows = [
        ParsedCsvRow(
            activity_date="",
            instrument=t.symbol,
            trans_code="BUY" if t.side == "buy" else "SELL",
            quantity=t.quantity,
            price=t.price,
            amount=-t.quantity * t.price if t.side == "buy" else t.quantity * t.price,
            row_type="buy" if t.side == "buy" else "sell",
            row_hash=t.row_hash,
            executed_at=t.executed_at or datetime.min,
        )
        for t in trades
    ]
    result = rebuild_portfolio(rows)
    return result.open_holdings
