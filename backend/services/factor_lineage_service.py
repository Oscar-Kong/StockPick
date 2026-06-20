"""Factor lineage metadata — extends catalog + IC persistence."""
from __future__ import annotations

from datetime import date, datetime, timezone

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from data.db_engine import get_engine
from engines.factor.catalog import active_factor_catalog
from engines.quant_models import FactorDefinition, FactorIcHistory, FactorLineage
from models.schemas_research import FactorLineageListResponse, FactorLineageResponse
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_response(row: FactorLineage) -> FactorLineageResponse:
    return FactorLineageResponse(
        id=row.id,
        factor_id=row.factor_id,
        factor_name=row.factor_name,
        raw_factor_version=row.raw_factor_version or "",
        transformation_version=row.transformation_version or "",
        normalization_method=row.normalization_method or "",
        winsorization_method=row.winsorization_method or "",
        neutralization_method=row.neutralization_method or "",
        formula_version=row.formula_version or "",
        calculation_date=row.calculation_date,
        data_cutoff=row.data_cutoff,
        universe=json_loads(row.universe_json, []),
        sleeve=row.sleeve,
        strategy_version=row.strategy_version,
        factor_model_version=row.factor_model_version,
        created_at=row.created_at,
    )


def record_factor_lineage(
    *,
    factor_id: str,
    sleeve: str,
    calculation_date: str | None = None,
    data_cutoff: str | None = None,
    universe: list[str] | None = None,
    strategy_version: str | None = None,
    factor_model_version: str | None = None,
) -> FactorLineageResponse:
    """Upsert lineage row from catalog + IC context."""
    catalog = active_factor_catalog()
    spec = None
    for factors in catalog.values():
        for f in factors:
            if f.factor_id == factor_id:
                spec = f
                break
    display_name = spec.display_name if spec else factor_id
    formula_version = spec.formula_version if spec else ""

    if not spec:
        engine = get_engine()
        with Session(engine) as session:
            row = session.get(FactorDefinition, factor_id)
            if row:
                display_name = row.display_name
                formula_version = row.formula_version or formula_version

    calc_date = calculation_date or date.today().isoformat()
    cutoff = data_cutoff or calc_date
    engine = get_engine()
    with Session(engine) as session:
        existing = (
            session.query(FactorLineage)
            .filter(
                FactorLineage.factor_id == factor_id,
                FactorLineage.calculation_date == calc_date,
                FactorLineage.sleeve == sleeve,
                FactorLineage.strategy_version == (strategy_version or STRATEGY_VERSION),
                FactorLineage.factor_model_version == (factor_model_version or FACTOR_MODEL_VERSION),
            )
            .first()
        )
        if existing:
            return _to_response(existing)

        row = FactorLineage(
            factor_id=factor_id,
            factor_name=display_name,
            raw_factor_version=formula_version,
            transformation_version="v1",
            normalization_method="percentile_0_100",
            winsorization_method="mad_3sigma",
            neutralization_method="sector_neutral_optional",
            formula_version=formula_version,
            calculation_date=calc_date,
            data_cutoff=cutoff,
            universe_json=json_dumps(universe or []),
            sleeve=sleeve,
            strategy_version=strategy_version or STRATEGY_VERSION,
            factor_model_version=factor_model_version or FACTOR_MODEL_VERSION,
            created_at=_utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_response(row)


def sync_lineage_from_ic_panel(sleeve: str, as_of_date: str) -> int:
    """Record lineage for all factors in latest IC panel date."""
    engine = get_engine()
    count = 0
    with Session(engine) as session:
        rows = (
            session.query(FactorIcHistory)
            .filter(FactorIcHistory.sleeve == sleeve, FactorIcHistory.as_of_date == as_of_date)
            .all()
        )
        factor_ids = sorted({r.factor_id for r in rows})
    for factor_id in factor_ids:
        record_factor_lineage(
            factor_id=factor_id,
            sleeve=sleeve,
            calculation_date=as_of_date,
            data_cutoff=as_of_date,
        )
        count += 1
    return count


def get_factor_lineage(
    factor_id: str,
    *,
    sleeve: str | None = None,
    limit: int = 20,
) -> FactorLineageListResponse:
    engine = get_engine()
    with Session(engine) as session:
        q = session.query(FactorLineage).filter(FactorLineage.factor_id == factor_id)
        if sleeve:
            q = q.filter(FactorLineage.sleeve == sleeve)
        total = q.count()
        rows = q.order_by(FactorLineage.calculation_date.desc()).limit(limit).all()
        return FactorLineageListResponse(items=[_to_response(r) for r in rows], total=total)


def lineage_from_factor_definition(factor_id: str) -> FactorLineageResponse | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(FactorDefinition, factor_id)
        if not row:
            return None
        return record_factor_lineage(
            factor_id=row.factor_id,
            sleeve=row.sleeve,
            calculation_date=date.today().isoformat(),
            data_cutoff=date.today().isoformat(),
        )
