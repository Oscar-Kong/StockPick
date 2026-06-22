"""Initialize quant v2 tables and seed factor catalog."""
from __future__ import annotations

import logging

from data.db_engine import get_engine
from engines.factor.catalog import active_factor_catalog
from engines.quant_models import (
    BacktestEquityPoint,
    BacktestRun,
    ChangeProposal,
    EvidenceMemory,
    FactorDefinition,
    FactorLineage,
    FeatureProvenance,
    JobQueueItem,
    PairsResearchRun,
    PositionRecommendation,
    PredictionOutcome,
    PredictionSnapshot,
    QuantAuditLog,
    QuantBase,
    ResearchExperiment,
    ResearchExperimentJob,
    ResearchIdea,
    ResearchRunIndex,
    TradeOutcome,
    TradePrediction,
    UniversePit,
)

logger = logging.getLogger(__name__)


def init_quant_db() -> None:
    engine = get_engine()
    QuantBase.metadata.create_all(bind=engine)
    _migrate_quant_columns()
    _seed_factor_definitions()


def _migrate_quant_columns() -> None:
    """Add Round 2 columns on existing SQLite DBs."""
    from sqlalchemy import inspect, text

    insp = inspect(get_engine())
    tables = insp.get_table_names()
    engine = get_engine()
    with engine.begin() as conn:
        if "prediction_snapshots" in tables:
            cols = {c["name"] for c in insp.get_columns("prediction_snapshots")}
            if "source" not in cols:
                conn.execute(text("ALTER TABLE prediction_snapshots ADD COLUMN source VARCHAR(32) DEFAULT 'v2_score'"))
            if "trade_id" not in cols:
                conn.execute(text("ALTER TABLE prediction_snapshots ADD COLUMN trade_id INTEGER"))
        if "trade_predictions" in tables:
            cols = {c["name"] for c in insp.get_columns("trade_predictions")}
            if "snapshot_id" not in cols:
                conn.execute(text("ALTER TABLE trade_predictions ADD COLUMN snapshot_id INTEGER"))
        if "prediction_outcomes" in tables:
            cols = {c["name"] for c in insp.get_columns("prediction_outcomes")}
            if "excess_vs_spy_90d" not in cols:
                conn.execute(text("ALTER TABLE prediction_outcomes ADD COLUMN excess_vs_spy_90d FLOAT"))
            if "excess_vs_sector_90d" not in cols:
                conn.execute(text("ALTER TABLE prediction_outcomes ADD COLUMN excess_vs_sector_90d FLOAT"))
        if "research_runs" in tables:
            cols = {c["name"] for c in insp.get_columns("research_runs")}
            if "archived" not in cols:
                conn.execute(text("ALTER TABLE research_runs ADD COLUMN archived INTEGER DEFAULT 0"))
            if "research_notes" not in cols:
                conn.execute(text("ALTER TABLE research_runs ADD COLUMN research_notes TEXT DEFAULT ''"))
            if "interpretation_json" not in cols:
                conn.execute(text("ALTER TABLE research_runs ADD COLUMN interpretation_json TEXT"))


def _seed_factor_definitions() -> None:
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        for sleeve, factors in active_factor_catalog().items():
            for spec in factors:
                existing = session.get(FactorDefinition, spec.factor_id)
                if existing:
                    continue
                session.add(
                    FactorDefinition(
                        factor_id=spec.factor_id,
                        sleeve=sleeve,
                        display_name=spec.display_name,
                        tier=spec.tier,
                        formula_version=spec.formula_version,
                        is_active=True,
                    )
                )
        session.commit()
    logger.debug("Factor catalog seed complete")
