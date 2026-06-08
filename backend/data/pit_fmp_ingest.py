"""FMP-backed point-in-time fundamentals ingest."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config import FMP_API_KEY, FMP_ENABLED
from data.db_engine import get_engine
from data.pit_fundamentals import persist_reconcile_as_pit
from engines.quant_models import FundamentalsPit

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _panel_symbols() -> list[str]:
    try:
        from data.cache import Cache

        cached = Cache().get("universe:sp500")
        if cached and cached.get("symbols"):
            return [s.upper() for s in cached["symbols"][:40]]
    except Exception:
        pass
    return ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]


def _fetch_fmp_income(symbol: str) -> list[dict]:
    if not FMP_ENABLED or not FMP_API_KEY:
        return []
    try:
        import requests

        url = f"https://financialmodelingprep.com/api/v3/income-statement/{symbol.upper()}"
        r = requests.get(url, params={"apikey": FMP_API_KEY, "limit": 8}, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.debug("FMP income fetch failed %s: %s", symbol, exc)
        return []


def ingest_fmp_pit(symbol: str) -> dict:
    """Store quarterly revenue/eps with filing date as PIT rows."""
    rows = _fetch_fmp_income(symbol)
    if not rows:
        return {"symbol": symbol.upper(), "written": 0, "skipped": True}

    engine = get_engine()
    written = 0
    now = _utcnow()
    sym = symbol.upper()

    with Session(engine) as session:
        for row in rows:
            filing = str(row.get("fillingDate") or row.get("acceptedDate") or row.get("date") or "")[:10]
            as_of = str(row.get("date") or filing)[:10]
            if not as_of:
                continue
            metrics = {
                "revenue_ttm": row.get("revenue"),
                "net_income": row.get("netIncome"),
                "eps": row.get("eps"),
                "operating_income": row.get("operatingIncome"),
            }
            for name, val in metrics.items():
                if val is None:
                    continue
                try:
                    fval = float(val)
                except (TypeError, ValueError):
                    continue
                existing = (
                    session.query(FundamentalsPit)
                    .filter(
                        FundamentalsPit.symbol == sym,
                        FundamentalsPit.as_of_date == as_of,
                        FundamentalsPit.metric == name,
                    )
                    .first()
                )
                payload = dict(
                    symbol=sym,
                    as_of_date=as_of,
                    metric=name,
                    value=fval,
                    filing_date=filing or None,
                    source="fmp",
                    available_to_model_at=now,
                )
                if existing:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                else:
                    session.add(FundamentalsPit(**payload))
                written += 1
        session.commit()
    return {"symbol": sym, "written": written, "quarters": len(rows)}


def build_pit_panel(*, symbols: list[str] | None = None) -> dict:
    """Batch ingest FMP PIT for universe; also snapshot today's reconciled metrics."""
    symbols = symbols or _panel_symbols()
    results: list[dict] = []
    for sym in symbols:
        try:
            from data.reconciler import DataReconciler

            rec = DataReconciler().reconcile(sym)
            if rec and rec.canonical:
                persist_reconcile_as_pit(sym, rec.canonical)
        except Exception:
            pass
        results.append(ingest_fmp_pit(sym))
    ok = sum(r.get("written", 0) for r in results)
    return {"symbols": len(symbols), "rows_written": ok, "details": results[:10]}
