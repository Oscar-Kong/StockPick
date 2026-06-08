"""Peer universe for relative valuation."""
from __future__ import annotations

import logging
from typing import Any

from config import FMP_API_KEY, FMP_ENABLED

logger = logging.getLogger(__name__)


def peer_symbols(symbol: str, sector: str | None, *, limit: int = 12) -> list[str]:
    sym = symbol.upper()
    if not sector or not FMP_ENABLED or not FMP_API_KEY:
        return []
    try:
        import requests

        url = "https://financialmodelingprep.com/api/v3/stock-screener"
        params = {
            "sector": sector,
            "marketCapMoreThan": 1_000_000_000,
            "limit": limit + 5,
            "apikey": FMP_API_KEY,
        }
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            return []
        peers = [str(row.get("symbol", "")).upper() for row in data if row.get("symbol")]
        return [p for p in peers if p != sym][:limit]
    except Exception as exc:
        logger.debug("peer_symbols failed %s: %s", sym, exc)
        return []


def peer_median_multiples(peers: list[str]) -> dict[str, float | None]:
    if not peers:
        return {"pe": None, "forward_pe": None, "pb": None}
    pes: list[float] = []
    fpes: list[float] = []
    pbs: list[float] = []
    try:
        from data.reconciler import DataReconciler

        rec = DataReconciler()
        for p in peers:
            info, fund, _ = rec.get_canonical_fundamentals(p)
            pe = info.get("trailingPE") or fund.get("pe_ratio")
            fpe = info.get("forwardPE")
            pb = fund.get("price_to_book") or info.get("priceToBook")
            if pe and float(pe) > 0:
                pes.append(float(pe))
            if fpe and float(fpe) > 0:
                fpes.append(float(fpe))
            if pb and float(pb) > 0:
                pbs.append(float(pb))
    except Exception:
        pass

    def _med(vals: list[float]) -> float | None:
        if not vals:
            return None
        vals.sort()
        return vals[len(vals) // 2]

    return {"pe": _med(pes), "forward_pe": _med(fpes), "pb": _med(pbs)}
