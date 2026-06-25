"""SQLAlchemy models for quant v2 (Phase 1 subset)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class QuantBase(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactorDefinition(QuantBase):
    __tablename__ = "factor_definitions"

    factor_id = Column(String(64), primary_key=True)
    sleeve = Column(String(16), nullable=False)
    display_name = Column(String(128), nullable=False)
    tier = Column(String(16), nullable=False)
    formula_version = Column(String(32), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class ScoreAttribution(QuantBase):
    __tablename__ = "score_attribution"
    __table_args__ = (UniqueConstraint("symbol", "sleeve", "as_of_date", name="uq_score_attr"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    sleeve = Column(String(16), nullable=False)
    as_of_date = Column(String(10), nullable=False)
    raw_score = Column(Float, nullable=False)
    dq_multiplier = Column(Float, nullable=False)
    risk_deduction = Column(Float, nullable=False)
    regime_mult = Column(Float, nullable=False)
    sector_tilt = Column(Float, nullable=False)
    final_score = Column(Float, nullable=False)
    factors_json = Column(Text, nullable=False)
    weights_json = Column(Text, nullable=False)
    strategy_version = Column(String(32), nullable=False)


class RiskScoreRow(QuantBase):
    __tablename__ = "risk_scores"
    __table_args__ = (UniqueConstraint("symbol", "sleeve", "as_of_date", name="uq_risk_scores"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    sleeve = Column(String(16), nullable=False)
    as_of_date = Column(String(10), nullable=False)
    risk_score = Column(Float, nullable=False)
    breakdown_json = Column(Text, nullable=False)
    deduction_pts = Column(Float, nullable=False, default=0.0)


class FactorIcHistory(QuantBase):
    __tablename__ = "factor_ic_history"
    __table_args__ = (
        UniqueConstraint("factor_id", "sleeve", "as_of_date", "horizon_days", name="uq_factor_ic"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_id = Column(String(64), nullable=False, index=True)
    sleeve = Column(String(16), nullable=False)
    as_of_date = Column(String(10), nullable=False)
    horizon_days = Column(Integer, nullable=False)
    ic = Column(Float, nullable=True)
    ir = Column(Float, nullable=True)
    hit_rate = Column(Float, nullable=True)
    sample_n = Column(Integer, nullable=True)


class FactorWeight(QuantBase):
    __tablename__ = "factor_weights"
    __table_args__ = (
        UniqueConstraint("sleeve", "regime", "factor_id", "effective_from", name="uq_factor_weights"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    sleeve = Column(String(16), nullable=False)
    regime = Column(String(32), nullable=False)
    factor_id = Column(String(64), nullable=False)
    weight = Column(Float, nullable=False)
    ic_at_set = Column(Float, nullable=True)
    effective_from = Column(String(10), nullable=False)
    effective_to = Column(String(10), nullable=True)
    model_version = Column(String(32), nullable=False)


class MarketRegime(QuantBase):
    __tablename__ = "market_regimes"

    as_of_date = Column(String(10), primary_key=True)
    regime = Column(String(32), nullable=False)
    features_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class UniversePit(QuantBase):
    __tablename__ = "universe_pit"

    as_of_date = Column(String(10), primary_key=True)
    symbol = Column(String(16), primary_key=True)
    bucket_hint = Column(String(16), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class BacktestRun(QuantBase):
    __tablename__ = "backtest_runs"

    run_id = Column(String(64), primary_key=True)
    run_type = Column(String(32), nullable=False)
    config_json = Column(Text, nullable=False)
    metrics_json = Column(Text, nullable=False)
    started_at = Column(DateTime, nullable=False, default=_utcnow)
    finished_at = Column(DateTime, nullable=True)


class PairsResearchRun(QuantBase):
    __tablename__ = "pairs_research_runs"

    run_id = Column(String(64), primary_key=True)
    status = Column(String(16), nullable=False, default="completed")
    config_json = Column(Text, nullable=False, default="{}")
    summary_json = Column(Text, nullable=False, default="{}")
    pairs_json = Column(Text, nullable=False, default="[]")
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=_utcnow)
    finished_at = Column(DateTime, nullable=True)


class BacktestEquityPoint(QuantBase):
    __tablename__ = "backtest_equity_points"

    run_id = Column(String(64), primary_key=True)
    as_of_date = Column(String(10), primary_key=True)
    equity = Column(Float, nullable=False)


class JobQueueItem(QuantBase):
    __tablename__ = "job_queue"

    job_id = Column(String(36), primary_key=True)
    job_name = Column(String(64), nullable=False, index=True)
    payload_json = Column(Text, nullable=False, default="{}")
    status = Column(String(16), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    strategy_version = Column(String(32), nullable=False)
    factor_model_version = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class QuantAuditLog(QuantBase):
    __tablename__ = "quant_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False, index=True)
    symbol = Column(String(16), nullable=True, index=True)
    sleeve = Column(String(16), nullable=True)
    strategy_version = Column(String(32), nullable=False)
    factor_model_version = Column(String(32), nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class TradePrediction(QuantBase):
    __tablename__ = "trade_predictions"

    trade_id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, nullable=True, index=True)
    symbol = Column(String(16), nullable=False, index=True)
    sleeve = Column(String(16), nullable=False)
    expected_return_pct = Column(Float, nullable=True)
    horizon_days = Column(Integer, nullable=True)
    score_snapshot = Column(Float, nullable=False)
    dq_multiplier = Column(Float, nullable=True)
    risk_deduction = Column(Float, nullable=True)
    factors_json = Column(Text, nullable=False)
    weights_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class TradeOutcome(QuantBase):
    __tablename__ = "trade_outcomes"

    trade_id = Column(Integer, primary_key=True)
    actual_return_pct = Column(Float, nullable=False)
    prediction_error_pct = Column(Float, nullable=True)
    factor_attribution_json = Column(Text, nullable=False)
    closed_at = Column(DateTime, nullable=False, default=_utcnow)


class PositionRecommendation(QuantBase):
    __tablename__ = "position_recommendations"
    __table_args__ = (
        UniqueConstraint("symbol", "sleeve", "as_of_date", name="uq_position_rec"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    sleeve = Column(String(16), nullable=False)
    as_of_date = Column(String(10), nullable=False)
    recommended_pct = Column(Float, nullable=False)
    max_pct = Column(Float, nullable=False)
    stop_loss_pct = Column(Float, nullable=True)
    portfolio_alloc_pct = Column(Float, nullable=False)
    inputs_json = Column(Text, nullable=False)


class PredictionSnapshot(QuantBase):
    """Point-in-time recommendation record for outcome tracking."""

    __tablename__ = "prediction_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    sleeve = Column(String(16), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    price = Column(Float, nullable=False)
    recommendation = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    time_horizon_days = Column(Integer, nullable=False)
    alpha_score = Column(Float, nullable=True)
    valuation_score = Column(Float, nullable=True)
    catalyst_score = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    data_confidence = Column(Float, nullable=True)
    market_regime = Column(String(32), nullable=True)
    expected_return_pct = Column(Float, nullable=True)
    expected_downside_pct = Column(Float, nullable=True)
    model_version = Column(String(32), nullable=False)
    source = Column(String(32), nullable=False, default="v2_score")
    trade_id = Column(Integer, nullable=True, index=True)
    features_json = Column(Text, nullable=False, default="{}")
    thesis_json = Column(Text, nullable=False, default="{}")


class PredictionOutcome(QuantBase):
    """Forward returns resolved against benchmarks."""

    __tablename__ = "prediction_outcomes"

    prediction_id = Column(Integer, primary_key=True)
    return_5d = Column(Float, nullable=True)
    return_20d = Column(Float, nullable=True)
    return_60d = Column(Float, nullable=True)
    return_90d = Column(Float, nullable=True)
    excess_vs_spy_20d = Column(Float, nullable=True)
    excess_vs_spy_60d = Column(Float, nullable=True)
    excess_vs_sector_20d = Column(Float, nullable=True)
    excess_vs_sector_60d = Column(Float, nullable=True)
    excess_vs_spy_90d = Column(Float, nullable=True)
    excess_vs_sector_90d = Column(Float, nullable=True)
    max_drawdown_60d = Column(Float, nullable=True)
    hit_target = Column(Boolean, nullable=True)
    hit_stop = Column(Boolean, nullable=True)
    resolved_at = Column(DateTime, nullable=False, default=_utcnow)


class FeatureProvenance(QuantBase):
    """Point-in-time metadata for model features."""

    __tablename__ = "feature_provenance"
    __table_args__ = (
        UniqueConstraint("symbol", "feature_name", "as_of_date", name="uq_feature_prov"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    feature_name = Column(String(64), nullable=False)
    as_of_date = Column(String(10), nullable=False)
    data_value = Column(Float, nullable=True)
    source = Column(String(32), nullable=False)
    filing_date = Column(String(10), nullable=True)
    ingested_at = Column(DateTime, nullable=False, default=_utcnow)
    available_to_model_at = Column(DateTime, nullable=False, default=_utcnow)


class ForwardReturnLabel(QuantBase):
    __tablename__ = "forward_return_labels"
    __table_args__ = (
        UniqueConstraint("symbol", "as_of_date", "horizon_days", name="uq_fwd_label"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    as_of_date = Column(String(10), nullable=False)
    horizon_days = Column(Integer, nullable=False)
    fwd_return = Column(Float, nullable=True)
    excess_vs_spy = Column(Float, nullable=True)
    excess_vs_sector = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    sector = Column(String(64), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorDecileHistory(QuantBase):
    __tablename__ = "factor_decile_history"
    __table_args__ = (
        UniqueConstraint(
            "factor_id", "sleeve", "as_of_date", "horizon_days", "decile",
            name="uq_factor_decile",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_id = Column(String(64), nullable=False, index=True)
    sleeve = Column(String(16), nullable=False)
    as_of_date = Column(String(10), nullable=False)
    horizon_days = Column(Integer, nullable=False)
    decile = Column(Integer, nullable=False)
    avg_forward_return = Column(Float, nullable=True)
    sample_n = Column(Integer, nullable=True)
    regime = Column(String(32), nullable=True)
    sector = Column(String(64), nullable=True)


class FundamentalsPit(QuantBase):
    """Point-in-time fundamental row keyed by filing availability."""

    __tablename__ = "fundamentals_pit"
    __table_args__ = (
        UniqueConstraint("symbol", "as_of_date", "metric", name="uq_fund_pit"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=False, index=True)
    as_of_date = Column(String(10), nullable=False)
    metric = Column(String(64), nullable=False)
    value = Column(Float, nullable=True)
    filing_date = Column(String(10), nullable=True)
    source = Column(String(32), nullable=False, default="reconciled")
    available_to_model_at = Column(DateTime, nullable=False, default=_utcnow)


class ResearchIdea(QuantBase):
    __tablename__ = "research_ideas"

    id = Column(String(64), primary_key=True)
    title = Column(String(256), nullable=False)
    hypothesis = Column(Text, nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    why_now = Column(Text, nullable=False, default="")
    source_type = Column(String(64), nullable=False, default="user_created")
    source_references_json = Column(Text, nullable=False, default="[]")
    sleeve = Column(String(16), nullable=True)
    universe_definition_json = Column(Text, nullable=False, default="{}")
    suggested_experiment_type = Column(String(64), nullable=True)
    suggested_parameters_json = Column(Text, nullable=False, default="{}")
    priority = Column(Integer, nullable=False, default=50)
    confidence = Column(Float, nullable=False, default=0.5)
    status = Column(String(32), nullable=False, default="new")
    user_notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class ResearchExperiment(QuantBase):
    __tablename__ = "research_experiments"

    id = Column(String(64), primary_key=True)
    idea_id = Column(String(64), nullable=True, index=True)
    name = Column(String(256), nullable=False)
    experiment_type = Column(String(64), nullable=False)
    hypothesis = Column(Text, nullable=False, default="")
    null_hypothesis = Column(Text, nullable=False, default="")
    success_criteria = Column(Text, nullable=False, default="")
    failure_criteria = Column(Text, nullable=False, default="")
    sleeve = Column(String(16), nullable=True)
    universe_definition_json = Column(Text, nullable=False, default="{}")
    parameters_json = Column(Text, nullable=False, default="{}")
    preset = Column(String(32), nullable=True)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class ResearchExperimentJob(QuantBase):
    """Tracks experiment launch progress with discrete stages (no fake percentages)."""

    __tablename__ = "research_experiment_jobs"

    job_id = Column(String(64), primary_key=True)
    experiment_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending")
    current_stage = Column(String(64), nullable=True)
    stages_json = Column(Text, nullable=False, default="[]")
    run_id = Column(String(64), nullable=True)
    last_success_run_id = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class ResearchRunIndex(QuantBase):
    """Thin unified index over persisted research results — payloads live elsewhere."""

    __tablename__ = "research_runs"

    run_id = Column(String(64), primary_key=True)
    experiment_id = Column(String(64), nullable=True, index=True)
    idea_id = Column(String(64), nullable=True, index=True)
    run_type = Column(String(64), nullable=False, index=True)
    name = Column(String(256), nullable=False, default="")
    status = Column(String(32), nullable=False, default="completed")
    verdict = Column(String(64), nullable=True)
    evidence_impact = Column(String(32), nullable=False, default="informational")
    reliability_json = Column(Text, nullable=True)
    sleeve = Column(String(16), nullable=True, index=True)
    universe_json = Column(Text, nullable=False, default="[]")
    parameters_json = Column(Text, nullable=False, default="{}")
    strategy_version = Column(String(32), nullable=False, default="")
    factor_model_version = Column(String(32), nullable=False, default="")
    data_cutoff = Column(String(10), nullable=True)
    sample_size = Column(Integer, nullable=True)
    primary_metrics_json = Column(Text, nullable=False, default="[]")
    warnings_json = Column(Text, nullable=False, default="[]")
    blockers_json = Column(Text, nullable=False, default="[]")
    result_reference_json = Column(Text, nullable=False, default="{}")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
    archived = Column(Integer, nullable=False, default=0)
    research_notes = Column(Text, nullable=False, default="")
    interpretation_json = Column(Text, nullable=True)


class EvidenceMemory(QuantBase):
    __tablename__ = "evidence_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(16), nullable=True, index=True)
    universe_json = Column(Text, nullable=True)
    original_signal_json = Column(Text, nullable=False, default="{}")
    factor_snapshot_ref_json = Column(Text, nullable=False, default="{}")
    market_regime = Column(String(32), nullable=True)
    experiment_id = Column(String(64), nullable=True, index=True)
    run_id = Column(String(64), nullable=True, index=True)
    deterministic_finding = Column(Text, nullable=False, default="")
    verdict = Column(String(64), nullable=True)
    evidence_impact = Column(String(32), nullable=False, default="informational")
    reliability_json = Column(Text, nullable=True)
    forward_outcomes_json = Column(Text, nullable=False, default="{}")
    confirmation_status = Column(String(32), nullable=False, default="pending")
    related_decisions_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class FactorLineage(QuantBase):
    __tablename__ = "factor_lineage"
    __table_args__ = (
        UniqueConstraint(
            "factor_id",
            "calculation_date",
            "sleeve",
            "strategy_version",
            "factor_model_version",
            name="uq_factor_lineage",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_id = Column(String(64), nullable=False, index=True)
    factor_name = Column(String(128), nullable=False)
    raw_factor_version = Column(String(32), nullable=False, default="")
    transformation_version = Column(String(32), nullable=False, default="")
    normalization_method = Column(String(64), nullable=False, default="percentile_0_100")
    winsorization_method = Column(String(64), nullable=False, default="none")
    neutralization_method = Column(String(64), nullable=False, default="none")
    formula_version = Column(String(32), nullable=False, default="")
    calculation_date = Column(String(10), nullable=False)
    data_cutoff = Column(String(10), nullable=False)
    universe_json = Column(Text, nullable=False, default="[]")
    sleeve = Column(String(16), nullable=False)
    strategy_version = Column(String(32), nullable=False)
    factor_model_version = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class NotificationDelivery(QuantBase):
    """Persisted notification delivery attempts (morning scan email, etc.)."""

    __tablename__ = "notification_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_type = Column(String(64), nullable=False, index=True)
    market_date = Column(String(10), nullable=False, index=True)
    scheduled_for = Column(DateTime, nullable=True)
    recipient_hash = Column(String(64), nullable=False, index=True)
    delivery_kind = Column(String(16), nullable=False, default="primary")
    status = Column(String(16), nullable=False, default="pending")
    provider = Column(String(32), nullable=False, default="")
    provider_message_id = Column(String(128), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    scan_ids_json = Column(Text, nullable=False, default="{}")
    error_code = Column(String(64), nullable=True)
    error_summary = Column(Text, nullable=True)
    is_resend = Column(Boolean, nullable=False, default=False)
    is_dry_run = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    sent_at = Column(DateTime, nullable=True)


class NotificationSentLock(QuantBase):
    """One successful primary delivery per notification type + market date + recipient."""

    __tablename__ = "notification_sent_locks"
    __table_args__ = (
        UniqueConstraint("notification_type", "market_date", "recipient_hash", name="uq_notification_sent_lock"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_type = Column(String(64), nullable=False)
    market_date = Column(String(10), nullable=False)
    recipient_hash = Column(String(64), nullable=False)
    delivery_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class ChangeProposal(QuantBase):
    __tablename__ = "change_proposals"

    id = Column(String(64), primary_key=True)
    title = Column(String(256), nullable=False)
    finding = Column(Text, nullable=False, default="")
    supporting_run_ids_json = Column(Text, nullable=False, default="[]")
    proposed_change_json = Column(Text, nullable=False, default="{}")
    affected_sleeve = Column(String(16), nullable=True)
    affected_factors_json = Column(Text, nullable=False, default="[]")
    expected_benefit = Column(Text, nullable=False, default="")
    main_risks = Column(Text, nullable=False, default="")
    required_validation = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="draft")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
