"""Cache Robinhood MCP realized P/L so Home KPIs skip a second MCP round-trip."""
from __future__ import annotations

from typing import Any

from data.cache import Cache
from integrations.robinhood.mcp_pnl import RealizedPnlSummary

REALIZED_PNL_CACHE_KEY = "portfolio:realized_pnl:ytd:v1"
REALIZED_PNL_CACHE_TTL_SEC = 3600.0


def cache_realized_pnl(summary: RealizedPnlSummary) -> None:
    Cache().set(
        REALIZED_PNL_CACHE_KEY,
        {
            "total": summary.total,
            "equity": summary.equity,
            "events": summary.events,
            "trade_count": summary.trade_count,
            "source": summary.source,
        },
        ttl_seconds=REALIZED_PNL_CACHE_TTL_SEC,
    )


def get_cached_realized_pnl() -> RealizedPnlSummary | None:
    raw: Any = Cache().get(REALIZED_PNL_CACHE_KEY)
    if not isinstance(raw, dict) or raw.get("total") is None:
        return None
    return RealizedPnlSummary(
        total=float(raw.get("total") or 0),
        equity=float(raw.get("equity") or 0),
        events=float(raw.get("events") or 0),
        trade_count=int(raw.get("trade_count") or 0),
        source=str(raw.get("source") or "robinhood_mcp"),
    )
