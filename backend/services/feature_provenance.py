"""Point-in-time feature provenance tracking."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from data.db_engine import get_engine
from engines.quant_models import FeatureProvenance


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _today() -> str:
    return _utcnow().strftime("%Y-%m-%d")


def persist_feature_provenance(
    symbol: str,
    features: dict[str, tuple[float | None, str]],
    *,
    as_of_date: str | None = None,
    filing_date: str | None = None,
) -> None:
    """Store PIT metadata: feature_name -> (value, source)."""
    engine = get_engine()
    as_of = as_of_date or _today()
    now = _utcnow()
    with Session(engine) as session:
        for name, (value, source) in features.items():
            row = (
                session.query(FeatureProvenance)
                .filter(
                    FeatureProvenance.symbol == symbol.upper(),
                    FeatureProvenance.feature_name == name,
                    FeatureProvenance.as_of_date == as_of,
                )
                .first()
            )
            payload = dict(
                symbol=symbol.upper(),
                feature_name=name,
                as_of_date=as_of,
                data_value=value,
                source=source,
                filing_date=filing_date,
                ingested_at=now,
                available_to_model_at=now,
            )
            if row:
                for k, v in payload.items():
                    setattr(row, k, v)
            else:
                session.add(FeatureProvenance(**payload))
        session.commit()


def features_from_reconcile(rec: Any) -> dict[str, tuple[float | None, str]]:
    out: dict[str, tuple[float | None, str]] = {}
    if rec is None:
        return out
    for fld in getattr(rec, "fields", []) or []:
        src = next(iter(fld.sources), "reconciler") if fld.sources else "reconciler"
        out[fld.field] = (fld.value, src)
    return out
