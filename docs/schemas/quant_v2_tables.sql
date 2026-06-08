-- Proposed schema extensions for institutional quant v2
-- Apply via Alembic/SQLAlchemy migration when implementing Phase 1+
-- Compatible with existing SQLite/PostgreSQL used by data/db_engine.py

-- Factor catalog
CREATE TABLE IF NOT EXISTS factor_definitions (
    factor_id       VARCHAR(64) PRIMARY KEY,
    sleeve          VARCHAR(16) NOT NULL,  -- penny | medium | compounder | all
    display_name    VARCHAR(128) NOT NULL,
    tier            VARCHAR(16) NOT NULL,  -- critical | important | secondary
    formula_version VARCHAR(32) NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Daily factor values (normalized 0-100 in norm_score)
CREATE TABLE IF NOT EXISTS factor_values (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      VARCHAR(16) NOT NULL,
    as_of_date  VARCHAR(10) NOT NULL,
    factor_id   VARCHAR(64) NOT NULL,
    raw_value   REAL,
    norm_score  REAL,
    UNIQUE(symbol, as_of_date, factor_id)
);
CREATE INDEX IF NOT EXISTS idx_factor_values_sym_date ON factor_values(symbol, as_of_date);

-- Rolling IC / IR panel
CREATE TABLE IF NOT EXISTS factor_ic_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    factor_id   VARCHAR(64) NOT NULL,
    sleeve      VARCHAR(16) NOT NULL,
    as_of_date  VARCHAR(10) NOT NULL,
    horizon_days INTEGER NOT NULL,
    ic          REAL,
    ir          REAL,
    hit_rate    REAL,
    sample_n    INTEGER,
    UNIQUE(factor_id, sleeve, as_of_date, horizon_days)
);

-- Effective weights by sleeve and regime
CREATE TABLE IF NOT EXISTS factor_weights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sleeve          VARCHAR(16) NOT NULL,
    regime          VARCHAR(32) NOT NULL,
    factor_id       VARCHAR(64) NOT NULL,
    weight          REAL NOT NULL,
    ic_at_set       REAL,
    effective_from  VARCHAR(10) NOT NULL,
    effective_to    VARCHAR(10),
    model_version   VARCHAR(32) NOT NULL,
    UNIQUE(sleeve, regime, factor_id, effective_from)
);

-- Market regime history
CREATE TABLE IF NOT EXISTS market_regimes (
    as_of_date  VARCHAR(10) PRIMARY KEY,
    regime      VARCHAR(32) NOT NULL,
    features_json TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Unified risk
CREATE TABLE IF NOT EXISTS risk_scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      VARCHAR(16) NOT NULL,
    sleeve      VARCHAR(16) NOT NULL,
    as_of_date  VARCHAR(10) NOT NULL,
    risk_score  REAL NOT NULL,
    breakdown_json TEXT NOT NULL,
    deduction_pts REAL NOT NULL DEFAULT 0,
    UNIQUE(symbol, sleeve, as_of_date)
);

-- Score pipeline attribution
CREATE TABLE IF NOT EXISTS score_attribution (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          VARCHAR(16) NOT NULL,
    sleeve          VARCHAR(16) NOT NULL,
    as_of_date      VARCHAR(10) NOT NULL,
    raw_score       REAL NOT NULL,
    dq_multiplier   REAL NOT NULL,
    risk_deduction  REAL NOT NULL,
    regime_mult     REAL NOT NULL,
    sector_tilt     REAL NOT NULL,
    final_score     REAL NOT NULL,
    factors_json    TEXT NOT NULL,
    weights_json    TEXT NOT NULL,
    strategy_version VARCHAR(32) NOT NULL,
    UNIQUE(symbol, sleeve, as_of_date)
);

-- Position sizing output
CREATE TABLE IF NOT EXISTS position_recommendations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          VARCHAR(16) NOT NULL,
    sleeve          VARCHAR(16) NOT NULL,
    as_of_date      VARCHAR(10) NOT NULL,
    recommended_pct REAL NOT NULL,
    max_pct         REAL NOT NULL,
    stop_loss_pct   REAL,
    portfolio_alloc_pct REAL,
    inputs_json     TEXT NOT NULL,
    UNIQUE(symbol, sleeve, as_of_date)
);

-- Phase 7: background job queue (when JOB_QUEUE_BACKEND=db)
CREATE TABLE IF NOT EXISTS job_queue (
    job_id              VARCHAR(36) PRIMARY KEY,
    job_name            VARCHAR(64) NOT NULL,
    payload_json        TEXT NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending',
    error_message       TEXT,
    strategy_version    VARCHAR(32) NOT NULL,
    factor_model_version VARCHAR(32) NOT NULL,
    created_at          TIMESTAMP NOT NULL,
    started_at          TIMESTAMP,
    finished_at         TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_job_queue_status ON job_queue(status, created_at);

-- Phase 7: quant audit trail
CREATE TABLE IF NOT EXISTS quant_audit_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type          VARCHAR(64) NOT NULL,
    symbol              VARCHAR(16),
    sleeve              VARCHAR(16),
    strategy_version    VARCHAR(32) NOT NULL,
    factor_model_version VARCHAR(32) NOT NULL,
    payload_json        TEXT NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_event ON quant_audit_logs(event_type, created_at DESC);

-- Live feedback: prediction at trade open
CREATE TABLE IF NOT EXISTS trade_predictions (
    trade_id        INTEGER PRIMARY KEY,
    symbol          VARCHAR(16) NOT NULL,
    sleeve          VARCHAR(16) NOT NULL,
    expected_return_pct REAL,
    horizon_days    INTEGER,
    score_snapshot  REAL,
    factors_json    TEXT,
    weights_json    TEXT,
    created_at      TIMESTAMP NOT NULL
);

-- Live feedback: outcome at trade close
CREATE TABLE IF NOT EXISTS trade_outcomes (
    trade_id        INTEGER PRIMARY KEY,
    actual_return_pct REAL,
    prediction_error_pct REAL,
    factor_attribution_json TEXT,
    closed_at       TIMESTAMP NOT NULL
);

-- Institutional backtest runs
CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id          VARCHAR(64) PRIMARY KEY,
    run_type        VARCHAR(32) NOT NULL,
    config_json     TEXT NOT NULL,
    metrics_json    TEXT NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backtest_equity_points (
    run_id          VARCHAR(64) NOT NULL,
    as_of_date      VARCHAR(10) NOT NULL,
    equity          REAL NOT NULL,
    PRIMARY KEY(run_id, as_of_date)
);

-- Point-in-time universe (survivorship)
CREATE TABLE IF NOT EXISTS universe_pit (
    as_of_date      VARCHAR(10) NOT NULL,
    symbol          VARCHAR(16) NOT NULL,
    bucket_hint     VARCHAR(16),
    is_active       INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(as_of_date, symbol)
);

-- AI reports v2
CREATE TABLE IF NOT EXISTS ai_reports_v2 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          VARCHAR(16) NOT NULL,
    sleeve          VARCHAR(16) NOT NULL,
    schema_version  VARCHAR(16) NOT NULL,
    report_json     TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ai_reports_v2_sym ON ai_reports_v2(symbol, created_at DESC);
