"""Stock Picker FastAPI application."""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from utils.datetime_util import utc_iso_z

# Serialize all naive UTC datetimes in JSON responses with Z suffix.
import fastapi.encoders as _fe

_orig_jsonable_encoder = _fe.jsonable_encoder


def _jsonable_encoder_with_utc_z(obj, *args, **kwargs):
    custom = dict(kwargs.pop("custom_encoder", None) or {})
    custom.setdefault(datetime, utc_iso_z)
    return _orig_jsonable_encoder(obj, *args, custom_encoder=custom, **kwargs)


_fe.jsonable_encoder = _jsonable_encoder_with_utc_z

from api.routes_analyze import router as analyze_router
from api.routes_allocation import router as allocation_router
from api.routes_backtest import router as backtest_router
from api.routes_data import router as data_router
from api.routes_explain import router as explain_router
from api.routes_lean import router as lean_router
from api.routes_ml import router as ml_router
from api.routes_brokerage import router as brokerage_router, router_portfolio as portfolio_holdings_router
from api.routes_home import router as home_router
from api.routes_portfolio_decision import router as portfolio_decision_router
from api.routes_portfolio import router as portfolio_router
from api.routes_scan import router as scan_router
from api.routes_saved import router as saved_router
from api.routes_stock import router as stock_router
from api.routes_trades import router as trades_router
from api.routes_trader_intel import router as trader_intel_router
from api.routes_research import router as research_router
from api.routes_research_lab import router as research_lab_router
from api.routes_ops_notifications import router as ops_notifications_router
from api.routes_settings import router as settings_router
from api.routes_v2 import router as v2_router
from api.routes_watchlist import router as watchlist_router
from config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_ENABLED,
    APP_ENV,
    DEMO_MODE,
    FMP_API_KEY,
    FMP_ENABLED,
    FINNHUB_API_KEY,
    FINNHUB_ENABLED,
    FRED_API_KEY,
    FRED_ENABLED,
    LLM_API_KEY,
    LLM_ENABLED,
    NASDAQ_DATA_LINK_API_KEY,
    NASDAQ_DATA_LINK_ENABLED,
    NEWSAPI_ENABLED,
    NEWSAPI_KEY,
    OPENBB_ENABLED,
    PRIMARY_FUNDAMENTALS_SOURCE,
    PRIMARY_NEWS_SOURCE,
    PRIMARY_PRICE_SOURCE,
    QUANDL_API_KEY,
    SCHEDULER_ENABLED,
    SCAN_EMAIL_ENABLED,
)
from data.cache import init_db
from models.schemas import HealthResponse
from utils.cors_origins import get_cors_allow_origins, validate_origin_config
from utils.exception_handlers import register_exception_handlers
from utils.rate_limit import category_for_path, check_rate_limit

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Stock Picker API",
    version="1.1.0",
    docs_url=None if (APP_ENV == "production" and DEMO_MODE) else "/docs",
    redoc_url=None if (APP_ENV == "production" and DEMO_MODE) else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Strategy-Version", "X-Factor-Model-Version"],
)

register_exception_handlers(app)


@app.middleware("http")
async def demo_rate_limit_middleware(request: Request, call_next):
    if DEMO_MODE:
        category = category_for_path(request.url.path, request.method)
        if category:
            from utils.rate_limit import client_key_from_request

            client = client_key_from_request(request)
            try:
                check_rate_limit(category, client)
            except Exception as exc:
                if hasattr(exc, "status_code") and hasattr(exc, "detail"):
                    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
                raise
    return await call_next(request)


app.include_router(scan_router)
app.include_router(saved_router)
app.include_router(stock_router)
app.include_router(watchlist_router)
app.include_router(trades_router)
app.include_router(trader_intel_router)
app.include_router(backtest_router)
app.include_router(explain_router)
app.include_router(data_router)
app.include_router(analyze_router)
app.include_router(portfolio_router)
app.include_router(portfolio_decision_router)
app.include_router(portfolio_holdings_router)
app.include_router(brokerage_router)
app.include_router(home_router)
app.include_router(ml_router)
app.include_router(allocation_router)
app.include_router(lean_router)
app.include_router(v2_router)
app.include_router(research_router)
app.include_router(research_lab_router)
app.include_router(settings_router)
app.include_router(ops_notifications_router)


def _deferred_startup() -> None:
    """Heavy work off the main thread so /health responds immediately."""
    if DEMO_MODE:
        logging.info("Demo mode — skipping listing master, universe seed, and scheduler startup")
        return

    try:
        from config import LISTING_MASTER_ENABLED
        from data.listing_master import refresh_listing_master_async

        if LISTING_MASTER_ENABLED:
            refresh_listing_master_async()
    except Exception as exc:
        logging.warning("Listing master startup refresh skipped: %s", exc)

    try:
        from scripts.seed_universe import fetch_sp500_symbols
        from data.cache import Cache

        cache = Cache()
        if not cache.get("universe:sp500"):
            symbols = fetch_sp500_symbols()
            cache.set("universe:sp500", {"symbols": symbols}, ttl_seconds=86400 * 7)
            logging.info("Seeded S&P 500 universe (%s symbols)", len(symbols))
    except Exception as exc:
        logging.warning("Universe seed skipped: %s", exc)

    if OPENBB_ENABLED:
        try:
            from data.openbb_client import warmup_openbb

            warmup_openbb()
        except Exception as exc:
            logging.warning("OpenBB warmup skipped: %s", exc)

    if SCHEDULER_ENABLED or SCAN_EMAIL_ENABLED:
        try:
            from services.scheduler import start_scheduler

            start_scheduler()
        except Exception as exc:
            logging.warning("Scheduler startup skipped: %s", exc)


@app.on_event("startup")
def startup():
    validate_origin_config()
    init_db()
    try:
        from engines.quant_db import init_quant_db

        init_quant_db()
    except Exception as exc:
        logging.warning("Quant DB init skipped: %s", exc)
    try:
        from services.demo_seed_service import seed_demo_data_if_needed

        seed_demo_data_if_needed()
    except Exception as exc:
        logging.warning("Demo seed skipped: %s", exc)
    threading.Thread(target=_deferred_startup, name="deferred-startup", daemon=True).start()
    logging.info("API ready — demo_mode=%s app_env=%s", DEMO_MODE, APP_ENV)


@app.on_event("shutdown")
def shutdown():
    try:
        from services.scheduler import stop_scheduler

        stop_scheduler()
    except Exception:
        pass


def _database_status() -> str:
    try:
        from sqlalchemy import text
        from data.db_engine import get_engine

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return "available"
    except Exception:
        return "unavailable"


@app.get("/health", response_model=HealthResponse, response_model_exclude_none=True)
def health():
    """Lightweight liveness check — no external providers or heavy work."""
    base = HealthResponse(
        status="ok",
        environment=APP_ENV,
        demo_mode=DEMO_MODE,
        database=_database_status(),
        version=app.version,
    )
    if DEMO_MODE or APP_ENV == "production":
        return base

    from data.openbb_client import openbb_ready
    from services.version_pin import pinned_versions

    versions = pinned_versions()
    return base.model_copy(
        update={
            "alpha_vantage_configured": bool(ALPHA_VANTAGE_API_KEY) and bool(ALPHA_VANTAGE_ENABLED),
            "fred_configured": bool(FRED_API_KEY) and bool(FRED_ENABLED),
            "newsapi_configured": bool(NEWSAPI_KEY) and bool(NEWSAPI_ENABLED),
            "finnhub_configured": bool(FINNHUB_API_KEY) and bool(FINNHUB_ENABLED),
            "fmp_configured": bool(FMP_API_KEY) and bool(FMP_ENABLED),
            "llm_configured": bool(LLM_API_KEY) and bool(LLM_ENABLED),
            "quandl_configured": bool(NASDAQ_DATA_LINK_API_KEY or QUANDL_API_KEY)
            and bool(NASDAQ_DATA_LINK_ENABLED),
            "openbb_enabled": bool(OPENBB_ENABLED) and openbb_ready(),
            "scheduler_enabled": bool(SCHEDULER_ENABLED),
            "app_env": APP_ENV,
            "primary_price_source": PRIMARY_PRICE_SOURCE,
            "primary_fundamentals_source": PRIMARY_FUNDAMENTALS_SOURCE,
            "primary_news_source": PRIMARY_NEWS_SOURCE,
            "database_dialect": versions["database_dialect"],
            "job_queue_backend": versions["job_queue_backend"],
            "redis_connected": versions["redis_connected"],
            "strategy_version": versions["strategy_version"],
            "factor_model_version": versions["factor_model_version"],
        }
    )


@app.get("/health/ready", response_model=HealthResponse, response_model_exclude_none=True)
def health_ready():
    status = _database_status()
    return HealthResponse(
        status="ok" if status == "available" else "degraded",
        environment=APP_ENV,
        demo_mode=DEMO_MODE,
        database=status,
        version=app.version,
    )
