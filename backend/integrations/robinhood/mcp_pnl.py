"""Robinhood MCP realized P/L — equities, options, crypto, and prediction markets."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MCP_MAX_PNL_PAGES = 20


@dataclass
class RealizedPnlSummary:
    total: float
    equity: float
    events: float
    trade_count: int
    source: str = "robinhood_mcp"


def _iter_trades(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for item in payload:
            out.extend(_iter_trades(item))
        return out
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("trades"), list):
        return [t for t in data["trades"] if isinstance(t, dict)]
    for key in ("trades", "results", "items"):
        if isinstance(payload.get(key), list):
            return [t for t in payload[key] if isinstance(t, dict)]
    return []


def _pnl_cursor(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict):
        cursor = data.get("next_cursor") or data.get("cursor")
        if isinstance(cursor, str) and cursor.strip():
            return cursor.strip()
    for key in ("next_cursor", "cursor"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def summarize_realized_trades(trades: list[dict[str, Any]]) -> RealizedPnlSummary:
    """Sum MCP per-trade realized_gain; empty symbol → prediction/event contracts."""
    equity = 0.0
    events = 0.0
    for trade in trades:
        gain = _float(trade.get("realized_gain"))
        symbol = str(trade.get("symbol") or "").strip()
        if symbol:
            equity += gain
        else:
            events += gain
    total = round(equity + events, 2)
    return RealizedPnlSummary(
        total=total,
        equity=round(equity, 2),
        events=round(events, 2),
        trade_count=len(trades),
    )


def parse_pnl_trade_history_pages(pages: list[Any]) -> RealizedPnlSummary:
    trades: list[dict[str, Any]] = []
    for page in pages:
        trades.extend(_iter_trades(page))
    return summarize_realized_trades(trades)
