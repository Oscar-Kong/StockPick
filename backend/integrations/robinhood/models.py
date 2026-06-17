"""Brokerage integration data models (no credentials stored)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

BrokerageSource = Literal["manual", "csv", "snaptrade", "demo"]
RowType = Literal["buy", "sell", "event", "excluded"]
# Legacy DB rows may still use side cash | income — normalized to "event" on read.


def normalize_row_type(row_type: str | None) -> RowType:
    rt = (row_type or "excluded").lower()
    if rt in ("cash", "income"):
        return "event"
    if rt in ("buy", "sell", "event", "excluded"):
        return rt  # type: ignore[return-value]
    return "excluded"


@dataclass
class ParsedCsvRow:
    """One parsed Robinhood CSV row."""

    activity_date: str = ""
    process_date: str = ""
    settle_date: str = ""
    instrument: str = ""
    description: str = ""
    trans_code: str = ""
    quantity: float | None = None
    price: float | None = None
    amount: float = 0.0  # signed cash impact (+ deposit/income, - purchase outflow)
    row_type: RowType = "excluded"
    row_hash: str = ""
    executed_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedTrade:
    """Legacy trade shape for buy/sell ledger entries."""

    symbol: str
    side: str  # buy | sell
    quantity: float
    price: float
    fees: float = 0.0
    executed_at: datetime | None = None
    order_id: str | None = None
    row_hash: str = ""
    trans_code: str = ""
    amount: float = 0.0
    description: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class ReconstructedHolding:
    symbol: str
    shares: float
    avg_cost: float
    bucket: str = "penny"
    total_bought: float = 0.0
    total_sold: float = 0.0
    realized_pl: float = 0.0


@dataclass
class ClosedPosition:
    symbol: str
    total_bought: float
    total_sold: float
    realized_pl: float
    last_activity: str = ""


@dataclass
class MiscEventRow:
    """Non-position cash activity (deposits, dividends, lending, etc.)."""

    activity_date: str
    trans_code: str
    description: str
    amount: float
    instrument: str = ""


@dataclass
class PortfolioRebuildResult:
    """Weighted-average-cost reconstruction (documented method)."""

    open_holdings: list[ReconstructedHolding]
    closed_positions: list[ClosedPosition]
    cash_delta: float
    event_ledger: list[MiscEventRow]
    excluded_rows: list[dict[str, Any]]
    unknown_trans_codes: list[str]
    warnings: list[str]


@dataclass
class BrokerageSyncResult:
    source: BrokerageSource
    trades_imported: int = 0
    trades_skipped: int = 0
    holdings_count: int = 0
    synced_at: datetime | None = None
    message: str = ""
