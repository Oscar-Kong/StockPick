"""Abstract brokerage read-only provider."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

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


def classify_holding_bucket(symbol: str, avg_cost: float) -> str:
    """Penny by default; compounder for large-cap names."""
    from config import COMPOUNDER_MARKET_CAP_MIN, PENNY_PRICE_MAX
    from data.candidate_builder import build_candidate
    from data.price_service import PriceService

    try:
        ctx = build_candidate(symbol, history_period="3mo", reconcile=False, price_service=PriceService())
        if ctx:
            price = float(ctx.price or avg_cost)
            mcap = ctx.info.get("marketCap")
            if mcap and float(mcap) >= COMPOUNDER_MARKET_CAP_MIN and price > PENNY_PRICE_MAX:
                return "compounder"
    except Exception:
        pass
    if avg_cost > PENNY_PRICE_MAX * 2:
        return "compounder"
    return "penny"


def reconstruct_holdings(trades: list[ParsedTrade]) -> list[ReconstructedHolding]:
    """Average-cost reconstruction from trade history."""
    lots: dict[str, dict] = {}

    sorted_trades = sorted(
        trades,
        key=lambda t: t.executed_at or datetime.min,
    )

    for t in sorted_trades:
        sym = t.symbol.upper()
        if sym not in lots:
            lots[sym] = {"shares": 0.0, "cost": 0.0}

        qty = abs(float(t.quantity))
        if qty <= 0:
            continue

        side = t.side.lower()
        if side in ("buy", "b", "purchase"):
            cost_add = qty * float(t.price) + float(t.fees)
            lots[sym]["shares"] += qty
            lots[sym]["cost"] += cost_add
        elif side in ("sell", "s", "sale"):
            held = lots[sym]["shares"]
            if held <= 0:
                continue
            sell_qty = min(qty, held)
            avg = lots[sym]["cost"] / held if held else float(t.price)
            lots[sym]["shares"] -= sell_qty
            lots[sym]["cost"] -= avg * sell_qty

    out: list[ReconstructedHolding] = []
    for sym, data in lots.items():
        shares = round(data["shares"], 6)
        if shares <= 1e-6:
            continue
        avg_cost = round(data["cost"] / shares, 4) if shares else 0.0
        out.append(
            ReconstructedHolding(
                symbol=sym,
                shares=shares,
                avg_cost=avg_cost,
                bucket=classify_holding_bucket(sym, avg_cost),
            )
        )
    return sorted(out, key=lambda h: h.symbol)
