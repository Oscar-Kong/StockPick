"""Initialize quant v2 tables and seed factor catalog."""
from __future__ import annotations

import logging

from data.db_engine import get_engine
from engines.factor.catalog import active_factor_catalog
from engines.factor_discovery_models import (
    FactorDefinitionRecord,
    FactorDiscoveryAttempt,
    FactorDiscoveryRun,
    FactorHypothesisRecord,
    FactorLlmCandidate,
    FactorLlmInteraction,
    FactorLlmReviewEvent,
    FactorMiningEvaluation,
    FactorMiningEvent,
    FactorMiningExposure,
    FactorMiningLineage,
    FactorMiningRevisionProposal,
    FactorMiningSession,
    FactorPromotionCandidate,
    FactorPromotionStatusEvent,
    FactorResearchDataSnapshot,
    FactorResearchFamily,
    FactorSealedTestReceipt,
    FactorShadowEvaluationRun,
    FactorStatusEvent,
    FactorValidationArtifactRecord,
)
from engines.quant_models import (
    BacktestEquityPoint,
    BacktestRun,
    ChangeProposal,
    EvidenceMemory,
    FactorDefinition,
    FactorLineage,
    FeatureProvenance,
    JobQueueItem,
    NotificationDelivery,
    NotificationSentLock,
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
            # List/filter indexes for Results tab queries
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_research_runs_sleeve_completed "
                    "ON research_runs (sleeve, completed_at DESC)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_research_runs_impact_archived "
                    "ON research_runs (evidence_impact, archived)"
                )
            )
        _migrate_factor_discovery_columns(conn, insp, tables)


def _migrate_factor_discovery_columns(conn, insp, tables: list[str]) -> None:
    from sqlalchemy import text

    if "factor_discovery_runs" in tables:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_factor_discovery_runs_experiment "
                "ON factor_discovery_runs (experiment_id)"
            )
        )
        cols = {c["name"] for c in insp.get_columns("factor_discovery_runs")}
        if "launch_payload_hash" not in cols:
            conn.execute(text("ALTER TABLE factor_discovery_runs ADD COLUMN launch_payload_hash VARCHAR(80)"))
        if "recommended_status" not in cols:
            conn.execute(text("ALTER TABLE factor_discovery_runs ADD COLUMN recommended_status VARCHAR(32)"))
    if "factor_definition_records" in tables:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_factor_definition_formula_hash "
                "ON factor_definition_records (formula_hash)"
            )
        )
        cols = {c["name"] for c in insp.get_columns("factor_definition_records")}
        if "lifecycle_version" not in cols:
            conn.execute(text("ALTER TABLE factor_definition_records ADD COLUMN lifecycle_version INTEGER DEFAULT 0"))
        if "recommended_status" not in cols:
            conn.execute(text("ALTER TABLE factor_definition_records ADD COLUMN recommended_status VARCHAR(32)"))
    if "factor_research_data_snapshots" in tables:
        cols = {c["name"] for c in insp.get_columns("factor_research_data_snapshots")}
        if "snapshot_identity_hash" not in cols:
            conn.execute(text("ALTER TABLE factor_research_data_snapshots ADD COLUMN snapshot_identity_hash VARCHAR(80)"))
        if "provider_data_version" not in cols:
            conn.execute(text("ALTER TABLE factor_research_data_snapshots ADD COLUMN provider_data_version VARCHAR(80)"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_factor_snapshots_identity "
                "ON factor_research_data_snapshots (snapshot_identity_hash)"
            )
        )
    if "factor_validation_artifact_records" in tables:
        cols = {c["name"] for c in insp.get_columns("factor_validation_artifact_records")}
        if "prior_artifact_id" not in cols:
            conn.execute(text("ALTER TABLE factor_validation_artifact_records ADD COLUMN prior_artifact_id VARCHAR(64)"))
        if "revalidation_of_artifact_id" not in cols:
            conn.execute(
                text("ALTER TABLE factor_validation_artifact_records ADD COLUMN revalidation_of_artifact_id VARCHAR(64)")
            )
    if "factor_sealed_test_receipts" in tables:
        cols = {c["name"] for c in insp.get_columns("factor_sealed_test_receipts")}
        if "recovery_authorization" not in cols:
            conn.execute(text("ALTER TABLE factor_sealed_test_receipts ADD COLUMN recovery_authorization VARCHAR(128)"))
    if "factor_mining_sessions" in tables:
        cols = {c["name"] for c in insp.get_columns("factor_mining_sessions")}
        for col, ddl in (
            ("pause_reason", "TEXT"),
            ("lease_owner_id", "VARCHAR(128)"),
            ("lease_token", "VARCHAR(80)"),
            ("lease_acquired_at", "DATETIME"),
            ("lease_expires_at", "DATETIME"),
            ("lease_version", "INTEGER DEFAULT 0"),
            ("last_heartbeat_at", "DATETIME"),
        ):
            if col not in cols:
                conn.execute(text(f"ALTER TABLE factor_mining_sessions ADD COLUMN {col} {ddl}"))
    if "factor_mining_exposures" in tables:
        cols = {c["name"] for c in insp.get_columns("factor_mining_exposures")}
        if "reservation_status" not in cols:
            conn.execute(text("ALTER TABLE factor_mining_exposures ADD COLUMN reservation_status VARCHAR(32) DEFAULT 'FINALIZED'"))
        if "prompt_template_id" not in cols:
            conn.execute(text("ALTER TABLE factor_mining_exposures ADD COLUMN prompt_template_id VARCHAR(64)"))


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
