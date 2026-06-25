"""Configuration for Stock Picker backend.

Aligned with role-based data sources (FMP fundamentals, Finnhub quotes,
Alpha Vantage fallback) and NY-time batch scheduling for US equities.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _api_key(name: str, default: str = "") -> str:
    """Read env var; treat .env.example placeholders as unset."""
    value = os.getenv(name, default).strip()
    if not value:
        return ""
    lower = value.lower()
    if lower.startswith("your_") and lower.endswith("_here"):
        return ""
    return value


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data_store"
DATA_DIR.mkdir(exist_ok=True)

from utils.runtime_flags import get_registry  # noqa: E402

_runtime = get_registry(DATA_DIR)


def _env_bool(name: str, default: str = "false"):
    """Env-backed boolean that supports runtime JSON overrides."""
    return _runtime.register(name, os.getenv(name, default))


# --- Environment ---
APP_ENV = os.getenv("APP_ENV", "development").lower()

# --- Database (PostgreSQL in production; SQLite + WAL for local dev) ---
_default_sqlite = f"sqlite:///{DATA_DIR / 'stock_picker.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", _default_sqlite)
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "5"))


def _ensure_sqlite_parent_dir(url: str) -> None:
    """Create parent directory for relative SQLite paths (Render ephemeral disk)."""
    if not url.lower().startswith("sqlite"):
        return
    raw = url.split("///", 1)[-1] if "///" in url else url.split("://", 1)[-1]
    if raw in (":memory:", "/:memory:"):
        return
    path = Path(raw)
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent_dir(DATABASE_URL)
SQLITE_SOURCE_PATH = os.getenv(
    "SQLITE_SOURCE_PATH",
    str(DATA_DIR / "stock_picker.db"),
)

# --- OpenBB Platform (optional unified data layer) ---
OPENBB_ENABLED = _env_bool("OPENBB_ENABLED", "false")
# SEC/insider fetches are slow (~10–30s/symbol). Off during bulk scans; on for single-symbol analyze.
OPENBB_ON_SCAN = _env_bool("OPENBB_ON_SCAN", "false")
OPENBB_RISK_CACHE_TTL = int(os.getenv("OPENBB_RISK_CACHE_TTL", "86400"))
OPENBB_INSIDER_ON_RISK = _env_bool("OPENBB_INSIDER_ON_RISK", "true")

# --- Quant framework toggles (phased rollout) ---
QLIB_ENABLED = _env_bool("QLIB_ENABLED", "false")
VBT_ENABLED = _env_bool("VBT_ENABLED", "false")
PYPFOPT_ENABLED = _env_bool("PYPFOPT_ENABLED", "false")
FINRL_ENABLED = _env_bool("FINRL_ENABLED", "false")
LEAN_EXPORT_ENABLED = _env_bool("LEAN_EXPORT_ENABLED", "false")
REGIME_OVERLAY_ENABLED = _env_bool("REGIME_OVERLAY_ENABLED", "true")

# --- Institutional quant v2 (phased; see docs/INSTITUTIONAL_QUANT_ARCHITECTURE.md) ---
SCORE_ENGINE_V2_ENABLED = _env_bool("SCORE_ENGINE_V2_ENABLED", "true")
USE_SCORING_ENGINE_IN_SCAN = _env_bool("USE_SCORING_ENGINE_IN_SCAN", "false")
# Stage B scoring mode: legacy | engine | parity_sample (see scan_scoring_config.py).
# When unset, falls back to legacy unless USE_SCORING_ENGINE_IN_SCAN=true → engine.
SCAN_SCORING_MODE = os.getenv("SCAN_SCORING_MODE", "").strip().lower()
SCAN_PARITY_SAMPLE_RATE = float(os.getenv("SCAN_PARITY_SAMPLE_RATE", "0.10"))

# --- Scan final ranking (alpha / confidence / tradability) ---
SCAN_RANKING_WEIGHTS: dict[str, dict[str, float]] = {
    "penny": {
        "alpha": float(os.getenv("SCAN_RANK_ALPHA_WEIGHT_PENNY", "0.65")),
        "confidence": float(os.getenv("SCAN_RANK_CONFIDENCE_WEIGHT_PENNY", "0.20")),
        "tradability": float(os.getenv("SCAN_RANK_TRADABILITY_WEIGHT_PENNY", "0.15")),
    },
    "medium": {
        "alpha": float(os.getenv("SCAN_RANK_ALPHA_WEIGHT_MEDIUM", "0.65")),
        "confidence": float(os.getenv("SCAN_RANK_CONFIDENCE_WEIGHT_MEDIUM", "0.20")),
        "tradability": float(os.getenv("SCAN_RANK_TRADABILITY_WEIGHT_MEDIUM", "0.15")),
    },
    "compounder": {
        "alpha": float(os.getenv("SCAN_RANK_ALPHA_WEIGHT_COMPOUNDER", "0.60")),
        "confidence": float(os.getenv("SCAN_RANK_CONFIDENCE_WEIGHT_COMPOUNDER", "0.25")),
        "tradability": float(os.getenv("SCAN_RANK_TRADABILITY_WEIGHT_COMPOUNDER", "0.15")),
    },
}
SCAN_MAX_PER_SECTOR = int(os.getenv("SCAN_MAX_PER_SECTOR", "3"))
SCAN_MAX_PER_CORRELATION_CLUSTER = int(os.getenv("SCAN_MAX_PER_CORRELATION_CLUSTER", "2"))
SCAN_CORRELATION_CLUSTER_THRESHOLD = float(os.getenv("SCAN_CORRELATION_CLUSTER_THRESHOLD", "0.75"))
SCAN_PERSISTENCE_DELTA = float(os.getenv("SCAN_PERSISTENCE_DELTA", "3.0"))
SCAN_MIN_RESULTS_AFTER_DIVERSIFICATION = int(os.getenv("SCAN_MIN_RESULTS_AFTER_DIVERSIFICATION", "3"))
SCAN_PENNY_LOW_CONFIDENCE_MAX = int(os.getenv("SCAN_PENNY_LOW_CONFIDENCE_MAX", "2"))
SCAN_PENNY_LOW_CONFIDENCE_THRESHOLD = float(os.getenv("SCAN_PENNY_LOW_CONFIDENCE_THRESHOLD", "45.0"))
PERSIST_SCORE_ATTRIBUTION = _env_bool("PERSIST_SCORE_ATTRIBUTION", "true")
_default_model_version = (
    "quant-v2-round2" if os.getenv("SLEEVE_FACTORS_V3_ENABLED", "false").lower() in ("1", "true", "yes")
    else "quant-v2-round2"
)
FACTOR_MODEL_VERSION = os.getenv("FACTOR_MODEL_VERSION", _default_model_version)
DYNAMIC_WEIGHTS_ENABLED = _env_bool("DYNAMIC_WEIGHTS_ENABLED", "true")
RISK_ENGINE_V2 = _env_bool("RISK_ENGINE_V2", "true")
POSITION_SIZING_V2 = _env_bool("POSITION_SIZING_V2", "true")
AI_REPORT_SCHEMA = os.getenv("AI_REPORT_SCHEMA", "v2")
BACKTEST_INSTITUTIONAL = _env_bool("BACKTEST_INSTITUTIONAL", "true")
FACTOR_IC_LOOKBACK_DAYS = int(os.getenv("FACTOR_IC_LOOKBACK_DAYS", "60"))
WEIGHT_REBALANCE_LAMBDA = float(os.getenv("WEIGHT_REBALANCE_LAMBDA", "0.5"))
IC_PANEL_MAX_SYMBOLS = int(os.getenv("IC_PANEL_MAX_SYMBOLS", "40"))
IC_PANEL_FORWARD_DAYS = int(os.getenv("IC_PANEL_FORWARD_DAYS", "20"))
IC_PANEL_HORIZONS = [
    int(x.strip())
    for x in os.getenv("IC_PANEL_HORIZONS", "5,20,60,90").split(",")
    if x.strip().isdigit()
]
WEIGHT_MIN = float(os.getenv("WEIGHT_MIN", "0.02"))
WEIGHT_MAX = float(os.getenv("WEIGHT_MAX", "0.35"))
IC_SOFTMAX_ALPHA = float(os.getenv("IC_SOFTMAX_ALPHA", "1.0"))
IC_SOFTMAX_BETA = float(os.getenv("IC_SOFTMAX_BETA", "0.5"))
QUANT_JOBS_ENABLED = _env_bool("QUANT_JOBS_ENABLED", "true")
QUANT_IC_CRON = os.getenv("QUANT_IC_CRON", "45 20 * * 1-5")

# --- Phase 3: expanded sleeve factors + table-driven hard filters ---
SLEEVE_FACTORS_V3_ENABLED = _env_bool("SLEEVE_FACTORS_V3_ENABLED", "false")
HARD_FILTERS_V3_ENABLED = _env_bool("HARD_FILTERS_V3_ENABLED", "false")
OPENALPHA_FACTORS_ENABLED = _env_bool("OPENALPHA_FACTORS_ENABLED", "false")

# --- Phase 4: unified risk + position sizing + report v2 ---
SLEEVE_MAX_WEIGHT = {
    "penny": float(os.getenv("SLEEVE_MAX_WEIGHT_PENNY", "0.03")),
    "medium": float(os.getenv("SLEEVE_MAX_WEIGHT_MEDIUM", "0.08")),
    "compounder": float(os.getenv("SLEEVE_MAX_WEIGHT_COMPOUNDER", "0.15")),
}
DEFAULT_PORTFOLIO_EXPOSURE = float(os.getenv("DEFAULT_PORTFOLIO_EXPOSURE", "0.5"))
DEFAULT_ACTIVE_POSITIONS = int(os.getenv("DEFAULT_ACTIVE_POSITIONS", "8"))

# --- Phase 5: institutional backtest ---
BT_FEE_BPS_DEFAULT = float(os.getenv("BT_FEE_BPS_DEFAULT", "5"))
BT_SLIP_BPS_DEFAULT = float(os.getenv("BT_SLIP_BPS_DEFAULT", "10"))
BT_MIN_TICKET_USD = float(os.getenv("BT_MIN_TICKET_USD", "1"))
BT_PARTICIPATION_RATE = float(os.getenv("BT_PARTICIPATION_RATE", "0.10"))
BT_DELISTING_HAIRCUT = float(os.getenv("BT_DELISTING_HAIRCUT", "0.50"))

# --- Phase 6: live trade feedback ---
TRADE_FEEDBACK_ENABLED = _env_bool("TRADE_FEEDBACK_ENABLED", "true")
TRADE_FEEDBACK_BAYESIAN_ETA = float(os.getenv("TRADE_FEEDBACK_BAYESIAN_ETA", "0.1"))

# --- Round 2: prediction loop + data confidence gates ---
PREDICTION_SNAPSHOTS_ENABLED = _env_bool("PREDICTION_SNAPSHOTS_ENABLED", "true")
PREDICTION_OUTCOME_HORIZONS = [
    int(x.strip())
    for x in os.getenv("PREDICTION_OUTCOME_HORIZONS", "5,20,60,90").split(",")
    if x.strip().isdigit()
]
DATA_CONFIDENCE_STRONG_REC_MIN = float(os.getenv("DATA_CONFIDENCE_STRONG_REC_MIN", "70"))
DATA_CONFIDENCE_STRONG_BUY_MIN = float(os.getenv("DATA_CONFIDENCE_STRONG_BUY_MIN", "80"))
SIMILAR_SIGNAL_TOLERANCE = float(os.getenv("SIMILAR_SIGNAL_TOLERANCE", "12"))
SIMILAR_SIGNAL_LOOKBACK_DAYS = int(os.getenv("SIMILAR_SIGNAL_LOOKBACK_DAYS", "730"))
VALUATION_ENGINE_ENABLED = _env_bool("VALUATION_ENGINE_ENABLED", "true")
MULTI_AGENT_PIPELINE_ENABLED = _env_bool("MULTI_AGENT_PIPELINE_ENABLED", "true")
LLM_AGENTS_ENABLED = _env_bool("LLM_AGENTS_ENABLED", "false")
OUTCOME_WEIGHT_FEEDBACK_ENABLED = _env_bool("OUTCOME_WEIGHT_FEEDBACK_ENABLED", "true")
OUTCOME_WEIGHT_ETA = float(os.getenv("OUTCOME_WEIGHT_ETA", "0.05"))
FORWARD_LABELS_ENABLED = _env_bool("FORWARD_LABELS_ENABLED", "true")
LEGACY_BACKTEST_COSTS_ENABLED = _env_bool("LEGACY_BACKTEST_COSTS_ENABLED", "true")
PIT_FUNDAMENTALS_ENABLED = _env_bool("PIT_FUNDAMENTALS_ENABLED", "true")

# --- Quant Lab research foundation ---
QUANT_LAB_RESEARCH_API_ENABLED = _env_bool("QUANT_LAB_RESEARCH_API_ENABLED", "true")
RESEARCH_MAX_ORDINARY_MODIFIER = float(os.getenv("RESEARCH_MAX_ORDINARY_MODIFIER", "0"))

# --- Phase 7: production hardening ---
JOB_QUEUE_BACKEND = os.getenv("JOB_QUEUE_BACKEND", "sync").lower()  # sync | db | redis
REDIS_URL = os.getenv("REDIS_URL", "").strip()
JOB_QUEUE_REDIS_KEY = os.getenv("JOB_QUEUE_REDIS_KEY", "stockpicker:jobs")
JOB_QUEUE_POLL_SEC = float(os.getenv("JOB_QUEUE_POLL_SEC", "5"))
MODEL_VERSION_STRICT = os.getenv("MODEL_VERSION_STRICT", "false").lower() in (
    "1",
    "true",
    "yes",
)
AUDIT_LOG_ENABLED = _env_bool("AUDIT_LOG_ENABLED", "true")

# --- AkShare (free-market data fallback/primary for testing) ---
AKSHARE_ENABLED = _env_bool("AKSHARE_ENABLED", "true")

# --- Data source roles ---
PRIMARY_PRICE_SOURCE = os.getenv("PRIMARY_PRICE_SOURCE", "finnhub").lower()
PRIMARY_FUNDAMENTALS_SOURCE = os.getenv("PRIMARY_FUNDAMENTALS_SOURCE", "fmp").lower()
PRIMARY_NEWS_SOURCE = os.getenv("PRIMARY_NEWS_SOURCE", "finnhub").lower()

# --- API keys ---
ALPHA_VANTAGE_API_KEY = _api_key("ALPHA_VANTAGE_API_KEY")
FRED_API_KEY = _api_key("FRED_API_KEY")
FRED_API_VERSION = os.getenv("FRED_API_VERSION", "v2")
FINNHUB_API_KEY = _api_key("FINNHUB_API_KEY")
FMP_API_KEY = _api_key("FMP_API_KEY")

# NewsAPI: free tier is dev/test only — disabled in production by default
NEWSAPI_KEY = _api_key("NEWSAPI_KEY")
NEWSAPI_ENABLED = _env_bool(
    "NEWSAPI_ENABLED",
    "false" if APP_ENV == "production" else "true",
)

# --- Per-provider runtime toggles (keys still required in .env) ---
FINNHUB_ENABLED = _env_bool("FINNHUB_ENABLED", "true")
FMP_ENABLED = _env_bool("FMP_ENABLED", "true")
ALPHA_VANTAGE_ENABLED = _env_bool("ALPHA_VANTAGE_ENABLED", "true")
FRED_ENABLED = _env_bool("FRED_ENABLED", "true")
LLM_ENABLED = _env_bool("LLM_ENABLED", "true")
NASDAQ_DATA_LINK_ENABLED = _env_bool("NASDAQ_DATA_LINK_ENABLED", "true")

# Nasdaq Data Link (formerly Quandl) — reference/batch only, not live quotes
NASDAQ_DATA_LINK_API_KEY = _api_key("NASDAQ_DATA_LINK_API_KEY") or _api_key(
    "QUANDL_API_KEY"
) or _api_key("NDL_APIKEY")
QUANDL_API_KEY = NASDAQ_DATA_LINK_API_KEY  # backward compatibility

# --- Reconciliation tolerances (relative difference) ---
RECONCILE_PRICE_TOLERANCE = float(os.getenv("RECONCILE_PRICE_TOLERANCE", "0.01"))
RECONCILE_RATIO_TOLERANCE = float(os.getenv("RECONCILE_RATIO_TOLERANCE", "0.12"))

# --- Strategy versioning ---
STRATEGY_VERSION = os.getenv("STRATEGY_VERSION", "2026-05-eod-v1")

# --- Scheduler (America/New_York, post-close batch Mon–Fri) ---
SCHEDULER_ENABLED = _env_bool("SCHEDULER_ENABLED", "true")
SCHEDULER_TZ = os.getenv("SCHEDULER_TZ", "America/New_York")
SCHEDULER_CRON = os.getenv("SCHEDULER_CRON", "15 20 * * 1-5")
SCHEDULER_MARKET_CALENDAR = os.getenv("SCHEDULER_MARKET_CALENDAR", "XNYS")
# Deprecated: use SCHEDULER_CRON + SCHEDULER_TZ instead
SCHEDULER_HOUR_UTC = int(os.getenv("SCHEDULER_HOUR_UTC", "6"))

# --- Daily portfolio decision (pre-market NY) ---
PORTFOLIO_DECISION_ENABLED = _env_bool("PORTFOLIO_DECISION_ENABLED", "true")
PORTFOLIO_DECISION_CRON = os.getenv("PORTFOLIO_DECISION_CRON", "0 9 * * 1-5")
PORTFOLIO_DECISION_TZ = os.getenv("PORTFOLIO_DECISION_TZ", "America/New_York")

# --- Morning scan email (pre-market NY; independent of SCHEDULER_ENABLED) ---
SCAN_EMAIL_ENABLED = _env_bool("SCAN_EMAIL_ENABLED", "false")
SCAN_EMAIL_PROVIDER = os.getenv("SCAN_EMAIL_PROVIDER", "smtp").strip().lower()
SCAN_EMAIL_TO = os.getenv("SCAN_EMAIL_TO", "").strip()
SCAN_EMAIL_FROM = os.getenv("SCAN_EMAIL_FROM", "StockPick <you@gmail.com>").strip()
SCAN_EMAIL_BUCKETS_RAW = os.getenv("SCAN_EMAIL_BUCKETS", "penny,compounder")
SCAN_EMAIL_TOP_N = int(os.getenv("SCAN_EMAIL_TOP_N", "5"))
SCAN_EMAIL_CRON = os.getenv("SCAN_EMAIL_CRON", "20 9 * * 1-5")
SCAN_EMAIL_TIMEZONE = os.getenv("SCAN_EMAIL_TIMEZONE", "America/New_York")
SCAN_EMAIL_STALE_AFTER_MINUTES = int(os.getenv("SCAN_EMAIL_STALE_AFTER_MINUTES", "1440"))
SCAN_EMAIL_RETRY_DELAY_MINUTES = int(os.getenv("SCAN_EMAIL_RETRY_DELAY_MINUTES", "5"))
SCAN_EMAIL_MAX_RETRIES = int(os.getenv("SCAN_EMAIL_MAX_RETRIES", "3"))
APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "http://127.0.0.1:18730").rstrip("/")

# Gmail / SMTP delivery for morning scan email
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = _api_key("SMTP_PASSWORD")
SMTP_USE_TLS = _env_bool("SMTP_USE_TLS", "true")

# --- Market data refresh during trading hours ---
MARKET_DATA_REFRESH_ENABLED = _env_bool("MARKET_DATA_REFRESH_ENABLED", "true")
MARKET_DATA_REFRESH_CRON = os.getenv("MARKET_DATA_REFRESH_CRON", "*/15 9-16 * * 1-5")
MARKET_DATA_REFRESH_TZ = os.getenv("MARKET_DATA_REFRESH_TZ", "America/New_York")
PENNY_SCAN_REFRESH_CRON = os.getenv("PENNY_SCAN_REFRESH_CRON", "*/30 9-16 * * 1-5")
PENNY_SCAN_REFRESH_TZ = os.getenv("PENNY_SCAN_REFRESH_TZ", "America/New_York")

# --- Official listing master (Nasdaq Trader symbol directories) ---
LISTING_MASTER_ENABLED = _env_bool("LISTING_MASTER_ENABLED", "true")
LISTING_MASTER_FETCH_TIMEOUT = float(os.getenv("LISTING_MASTER_FETCH_TIMEOUT", "20"))
# Long TTL keeps last-known-good snapshot when a refresh fails.
LISTING_MASTER_CACHE_TTL = float(os.getenv("LISTING_MASTER_CACHE_TTL", str(86400 * 365)))

# --- LLM (Proxy-compatible) ---
# Preferred custom proxy vars:
# - GPT_PROXY_API_KEY
# - GPT_PROXY_BASE_URL
# - GPT_PROXY_MODEL
LLM_API_KEY = _api_key("GPT_PROXY_API_KEY") or _api_key("LLM_API_KEY")
LLM_BASE_URL = os.getenv(
    "GPT_PROXY_BASE_URL",
    os.getenv("LLM_BASE_URL", "https://lab.iwhalecloud.com/gpt-proxy/v1"),
)
LLM_MODEL = os.getenv("GPT_PROXY_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "low")
LLM_VERBOSITY = os.getenv("LLM_VERBOSITY", "low")
INVEST_TIME_HORIZON = os.getenv("INVEST_TIME_HORIZON", "1-3 months")
INVEST_RISK_TOLERANCE = os.getenv("INVEST_RISK_TOLERANCE", "medium")
INVEST_MAX_POSITION_SIZE = os.getenv("INVEST_MAX_POSITION_SIZE", "5% of portfolio")
INVEST_ALLOWED_STRATEGIES = os.getenv("INVEST_ALLOWED_STRATEGIES", "stocks only")
INVEST_INTERESTED_SECTORS = os.getenv("INVEST_INTERESTED_SECTORS", "").strip()
INVEST_AVOID_LIST = os.getenv("INVEST_AVOID_LIST", "").strip()

# --- Cache TTL (seconds) ---
PRICE_CACHE_TTL = int(os.getenv("PRICE_CACHE_TTL", "300"))
FUNDAMENTALS_CACHE_TTL = int(os.getenv("FUNDAMENTALS_CACHE_TTL", "604800"))
SCAN_RESULT_TTL = int(os.getenv("SCAN_RESULT_TTL", "900"))
ANALYZE_RESULT_TTL = int(os.getenv("ANALYZE_RESULT_TTL", "1800"))

# --- Route runtime caps (seconds) ---
ANALYZE_ROUTE_TIMEOUT_SECONDS = float(os.getenv("ANALYZE_ROUTE_TIMEOUT_SECONDS", "35"))
WALK_FORWARD_ROUTE_TIMEOUT_SECONDS = float(os.getenv("WALK_FORWARD_ROUTE_TIMEOUT_SECONDS", "600"))
REPORT_ROUTE_TIMEOUT_SECONDS = float(os.getenv("REPORT_ROUTE_TIMEOUT_SECONDS", "45"))
COMPARE_ROUTE_TIMEOUT_SECONDS = float(os.getenv("COMPARE_ROUTE_TIMEOUT_SECONDS", "40"))
STOCK_ROUTE_TIMEOUT_SECONDS = float(os.getenv("STOCK_ROUTE_TIMEOUT_SECONDS", "40"))

# --- Watchlist workload caps ---
WATCHLIST_IMPORT_GENERATE_REPORTS = _env_bool("WATCHLIST_IMPORT_GENERATE_REPORTS", "false")
WATCHLIST_REFRESH_MAX_ITEMS = int(os.getenv("WATCHLIST_REFRESH_MAX_ITEMS", "25"))
WATCHLIST_REFRESH_BUDGET_SECONDS = float(os.getenv("WATCHLIST_REFRESH_BUDGET_SECONDS", "40"))
WATCHLIST_REFRESH_PER_SYMBOL_TIMEOUT_SECONDS = float(
    os.getenv("WATCHLIST_REFRESH_PER_SYMBOL_TIMEOUT_SECONDS", "8")
)
WATCHLIST_REPORT_MAX_ITEMS = int(os.getenv("WATCHLIST_REPORT_MAX_ITEMS", "10"))
WATCHLIST_REPORT_BUDGET_SECONDS = float(os.getenv("WATCHLIST_REPORT_BUDGET_SECONDS", "45"))
WATCHLIST_IMPORT_PER_SYMBOL_TIMEOUT_SECONDS = float(
    os.getenv("WATCHLIST_IMPORT_PER_SYMBOL_TIMEOUT_SECONDS", "10")
)

# --- Penny bucket ---
PENNY_PRICE_MIN = float(os.getenv("PENNY_PRICE_MIN", "0.50"))
PENNY_PRICE_MAX = float(os.getenv("PENNY_PRICE_MAX", "5.0"))
PENNY_MIN_VOLUME = int(os.getenv("PENNY_MIN_VOLUME", "1000000"))
PENNY_MIN_DOLLAR_VOLUME_20D = float(os.getenv("PENNY_MIN_DOLLAR_VOLUME_20D", "1000000"))
PENNY_MARKET_CAP_MIN = float(os.getenv("PENNY_MARKET_CAP_MIN", "100000000"))
PENNY_MARKET_CAP_MAX = float(os.getenv("PENNY_MARKET_CAP_MAX", "300000000"))
PENNY_MIN_DATA_QUALITY_SCORE = float(os.getenv("PENNY_MIN_DATA_QUALITY_SCORE", "45"))
PENNY_MIN_SPREAD_SCORE = float(os.getenv("PENNY_MIN_SPREAD_SCORE", "35"))
# Hard-reject only when intraday range proxy exceeds this % of price (extreme illiquidity).
PENNY_MAX_SPREAD_PCT = float(os.getenv("PENNY_MAX_SPREAD_PCT", "15.0"))

# --- Medium bucket (deprecated — kept for historical data compatibility) ---
MEDIUM_PRICE_MIN = float(os.getenv("MEDIUM_PRICE_MIN", "10.0"))
MEDIUM_PRICE_MAX = float(os.getenv("MEDIUM_PRICE_MAX", "200.0"))
MEDIUM_MIN_VOLUME = int(os.getenv("MEDIUM_MIN_VOLUME", "2000000"))
MEDIUM_MIN_DOLLAR_VOLUME_20D = float(os.getenv("MEDIUM_MIN_DOLLAR_VOLUME_20D", "20000000"))
MEDIUM_MARKET_CAP_MIN = float(os.getenv("MEDIUM_MARKET_CAP_MIN", "2000000000"))
MEDIUM_MARKET_CAP_MAX = float(os.getenv("MEDIUM_MARKET_CAP_MAX", "10000000000"))

# --- Compounder bucket ---
COMPOUNDER_MARKET_CAP_MIN = float(os.getenv("COMPOUNDER_MARKET_CAP_MIN", "10000000000"))
COMPOUNDER_MIN_REVENUE_GROWTH = float(os.getenv("COMPOUNDER_MIN_REVENUE_GROWTH", "0.08"))

# --- Scan limits ---
MAX_CANDIDATES_PER_BUCKET = int(os.getenv("MAX_CANDIDATES_PER_BUCKET", "25"))
UNIVERSE_SCAN_BATCH_SIZE = int(os.getenv("UNIVERSE_SCAN_BATCH_SIZE", "100"))
SCAN_STAGE_B_TOP_N = int(os.getenv("SCAN_STAGE_B_TOP_N", "50"))
SCAN_STAGE_B_TOP_N_FAST = int(os.getenv("SCAN_STAGE_B_TOP_N_FAST", "15"))
SCAN_PRICE_DOWNLOAD_MAX_SECONDS = float(os.getenv("SCAN_PRICE_DOWNLOAD_MAX_SECONDS", "45"))
# Bucket-specific OHLC horizons for two-stage scans (Stage A cheap filter → Stage B deep).
SCAN_PENNY_STAGE_A_PERIOD = os.getenv("SCAN_PENNY_STAGE_A_PERIOD", "6mo")
SCAN_PENNY_STAGE_B_PERIOD = os.getenv("SCAN_PENNY_STAGE_B_PERIOD", "6mo")
SCAN_COMPOUNDER_STAGE_A_PERIOD = os.getenv("SCAN_COMPOUNDER_STAGE_A_PERIOD", "1y")
SCAN_COMPOUNDER_STAGE_B_PERIOD = os.getenv("SCAN_COMPOUNDER_STAGE_B_PERIOD", "5y")
# Reuse reconciled fundamental snapshots when younger than this many calendar days.
FUNDAMENTAL_SNAPSHOT_MAX_AGE_DAYS = int(os.getenv("FUNDAMENTAL_SNAPSHOT_MAX_AGE_DAYS", "1"))
# Stop Stage B deep-scoring after this many seconds and return partial ranked results.
SCAN_STAGE_B_TIME_BUDGET_SECONDS = float(os.getenv("SCAN_STAGE_B_TIME_BUDGET_SECONDS", "0"))

# Per-bucket SCAN_RESULT_TTL overrides. Compounder data changes slowly, so we
# allow operators to keep its "latest" payload warm for much longer than penny.
SCAN_RESULT_TTL_PENNY = int(os.getenv("SCAN_RESULT_TTL_PENNY", str(SCAN_RESULT_TTL)))
SCAN_RESULT_TTL_COMPOUNDER = int(os.getenv("SCAN_RESULT_TTL_COMPOUNDER", "86400"))

# --- Data quality gates (0–100 scale) ---
MIN_DATA_QUALITY_SCORE = float(os.getenv("MIN_DATA_QUALITY_SCORE", "60"))
MIN_HISTORY_BARS = int(os.getenv("MIN_HISTORY_BARS", "252"))

# --- Public demo deployment ---
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")
DEMO_SEED_DATA = os.getenv(
    "DEMO_SEED_DATA",
    "true" if DEMO_MODE else "false",
).lower() in ("1", "true", "yes")
DEMO_MAX_SCAN_SYMBOLS = int(os.getenv("DEMO_MAX_SCAN_SYMBOLS", "75"))
DEMO_MAX_ANALYSIS_SYMBOLS = int(os.getenv("DEMO_MAX_ANALYSIS_SYMBOLS", "1"))
DEMO_MAX_BACKTEST_SYMBOLS = int(os.getenv("DEMO_MAX_BACKTEST_SYMBOLS", "15"))
DEMO_MAX_BACKTEST_DAYS = int(os.getenv("DEMO_MAX_BACKTEST_DAYS", "365"))
DEMO_MAX_QUANT_JOB_SYMBOLS = int(os.getenv("DEMO_MAX_QUANT_JOB_SYMBOLS", "25"))
DEMO_MAX_REQUESTS_PER_MINUTE = int(os.getenv("DEMO_MAX_REQUESTS_PER_MINUTE", "30"))

# CORS — comma-separated exact origins (production); dev localhost defaults when unset.
_ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "").strip()
if _ALLOWED_ORIGINS_RAW:
    ALLOWED_ORIGINS = [o.strip() for o in _ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
elif APP_ENV == "production":
    ALLOWED_ORIGINS = []
else:
    ALLOWED_ORIGINS = [
        "http://localhost:18730",
        "http://127.0.0.1:18730",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# Demo-safe production defaults (override via env when self-hosting).
if DEMO_MODE:
    SCHEDULER_ENABLED = _env_bool("SCHEDULER_ENABLED", "false")
    SCAN_EMAIL_ENABLED = _env_bool("SCAN_EMAIL_ENABLED", "false")
    QUANT_JOBS_ENABLED = _env_bool("QUANT_JOBS_ENABLED", "false")
    LISTING_MASTER_ENABLED = _env_bool("LISTING_MASTER_ENABLED", "false")
    MARKET_DATA_REFRESH_ENABLED = _env_bool("MARKET_DATA_REFRESH_ENABLED", "false")
    PORTFOLIO_DECISION_ENABLED = _env_bool("PORTFOLIO_DECISION_ENABLED", "false")
    UNIVERSE_SCAN_BATCH_SIZE = min(
        UNIVERSE_SCAN_BATCH_SIZE if UNIVERSE_SCAN_BATCH_SIZE > 0 else DEMO_MAX_SCAN_SYMBOLS,
        DEMO_MAX_SCAN_SYMBOLS,
    )
    MAX_CANDIDATES_PER_BUCKET = min(MAX_CANDIDATES_PER_BUCKET, DEMO_MAX_SCAN_SYMBOLS)
