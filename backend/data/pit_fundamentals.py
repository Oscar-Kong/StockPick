"""Point-in-time fundamentals from snapshots and filings."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from data.db_engine import get_engine
from engines.quant_models import FundamentalsPit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def persist_reconcile_as_pit(symbol: str, canonical: dict, *, as_of_date: str | None = None) -> None:
    """Store reconciler canonical metrics with today as available date."""
    as_of = as_of_date or _utcnow().strftime("%Y-%m-%d")
    engine = get_engine()
    metrics = {
        "pe_ratio": canonical.get("pe_ratio"),
        "revenue_ttm": canonical.get("revenue_ttm"),
        "market_cap": canonical.get("market_cap"),
        "roe": canonical.get("roe"),
        "profit_margin": canonical.get("profit_margin"),
    }
    now = _utcnow()
    with Session(engine) as session:
        for name, val in metrics.items():
            if val is None:
                continue
            row = (
                session.query(FundamentalsPit)
                .filter(
                    FundamentalsPit.symbol == symbol.upper(),
                    FundamentalsPit.as_of_date == as_of,
                    FundamentalsPit.metric == name,
                )
                .first()
            )
            payload = dict(
                symbol=symbol.upper(),
                as_of_date=as_of,
                metric=name,
                value=float(val),
                filing_date=None,
                source="reconciled",
                available_to_model_at=now,
            )
            if row:
                for k, v in payload.items():
                    setattr(row, k, v)
            else:
                session.add(FundamentalsPit(**payload))
        session.commit()


def get_pit_metric(symbol: str, metric: str, as_of_date: str) -> float | None:
    engine = get_engine()
    with Session(engine) as session:
        row = (
            session.query(FundamentalsPit)
            .filter(
                FundamentalsPit.symbol == symbol.upper(),
                FundamentalsPit.metric == metric,
                FundamentalsPit.as_of_date <= as_of_date,
            )
            .order_by(FundamentalsPit.as_of_date.desc())
            .first()
        )
        return float(row.value) if row and row.value is not None else None
