"""Brokerage integration data models (no credentials stored)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

BrokerageSource = Literal["manual", "csv", "snaptrade"]


@dataclass
class ParsedTrade:
    symbol: str
    side: str  # buy | sell
    quantity: float
    price: float
    fees: float = 0.0
    executed_at: datetime | None = None
    order_id: str | None = None
    row_hash: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class ReconstructedHolding:
    symbol: str
    shares: float
    avg_cost: float
    bucket: str = "penny"


@dataclass
class BrokerageSyncResult:
    source: BrokerageSource
    trades_imported: int = 0
    trades_skipped: int = 0
    holdings_count: int = 0
    synced_at: datetime | None = None
    message: str = ""
