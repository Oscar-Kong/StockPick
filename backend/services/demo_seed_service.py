"""Idempotent demo portfolio and watchlist seeding for public deployments."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from data import cache as cache_module
from data.portfolio_store import (
    DEFAULT_ACCOUNT_ID,
    SessionLocal,
    _ensure_default_account,
    get_current_holdings,
    get_or_create_account,
    save_holdings,
    update_account_source,
)
from models.schemas import Bucket, PortfolioHolding

logger = logging.getLogger(__name__)
_SEED_LOCK = threading.Lock()
_SEED_MARKER = "demo:seed_completed_v1"

_DEMO_HOLDINGS = [
    PortfolioHolding(symbol="AAPL", shares=12, avg_cost=178.5, bucket=Bucket.compounder),
    PortfolioHolding(symbol="MSFT", shares=8, avg_cost=385.0, bucket=Bucket.compounder),
    PortfolioHolding(symbol="NVDA", shares=6, avg_cost=118.0, bucket=Bucket.compounder),
    PortfolioHolding(symbol="SOFI", shares=250, avg_cost=11.8, bucket=Bucket.penny),
    PortfolioHolding(symbol="PLTR", shares=40, avg_cost=23.5, bucket=Bucket.penny),
]

_DEMO_WATCHLIST = [
    ("AMD", Bucket.penny, "Semiconductor momentum watch"),
    ("COST", Bucket.compounder, "Quality compounder example"),
    ("TSLA", Bucket.medium, "High-beta swing candidate"),
]


def _portfolio_needs_seed() -> bool:
    account = get_or_create_account()
    holdings = get_current_holdings()
    if account.get("source") == "demo" and holdings:
        return False
    if account.get("source") in ("csv", "snaptrade") and holdings:
        return False
    return not holdings


def seed_demo_data_if_needed() -> bool:
    """Seed fictional sample data when DEMO_MODE and database is empty. Returns True if seeded."""
    import config

    if not config.DEMO_MODE or not config.DEMO_SEED_DATA:
        return False

    cache = cache_module.Cache()
    if cache.get(_SEED_MARKER):
        return False

    with _SEED_LOCK:
        if cache.get(_SEED_MARKER):
            return False
        if not _portfolio_needs_seed():
            cache.set(_SEED_MARKER, {"ok": True}, ttl_seconds=86400 * 30)
            return False

        session = SessionLocal()
        try:
            acct = _ensure_default_account(session)
            acct.label = "Demo Portfolio"
            acct.source = "demo"
            acct.cash_balance = 12450.0
            acct.reserved_cash = 500.0
            acct.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            session.commit()
        finally:
            session.close()

        update_account_source("demo", cash=12450.0)
        save_holdings(DEFAULT_ACCOUNT_ID, _DEMO_HOLDINGS, source="demo")

        for symbol, bucket, notes in _DEMO_WATCHLIST:
            try:
                cache_module.add_to_watchlist(symbol, bucket.value, notes=notes)
            except Exception as exc:
                logger.debug("Watchlist seed skip %s: %s", symbol, exc)
        cache.set(_SEED_MARKER, {"ok": True}, ttl_seconds=86400 * 30)
        logger.info("Demo seed completed — sample portfolio and watchlist ready")
        return True
