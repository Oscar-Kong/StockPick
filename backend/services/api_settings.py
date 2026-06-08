"""Catalog and apply logic for runtime API / feature toggles."""
from __future__ import annotations

import logging
from typing import Any

import config
from config import (
    ALPHA_VANTAGE_API_KEY,
    FINNHUB_API_KEY,
    FMP_API_KEY,
    FRED_API_KEY,
    LLM_API_KEY,
    NASDAQ_DATA_LINK_API_KEY,
    NEWSAPI_KEY,
    QUANDL_API_KEY,
)
from utils.runtime_flags import get_registry

logger = logging.getLogger(__name__)

_KEY_ATTR: dict[str, str] = {
    "FINNHUB_ENABLED": "FINNHUB_API_KEY",
    "FMP_ENABLED": "FMP_API_KEY",
    "ALPHA_VANTAGE_ENABLED": "ALPHA_VANTAGE_API_KEY",
    "FRED_ENABLED": "FRED_API_KEY",
    "LLM_ENABLED": "GPT_PROXY_API_KEY",
    "NEWSAPI_ENABLED": "NEWSAPI_KEY",
    "NASDAQ_DATA_LINK_ENABLED": "NASDAQ_DATA_LINK_API_KEY",
}

_CATALOG: list[dict[str, Any]] = [
    {
        "id": "data_providers",
        "title": "Data providers",
        "description": "Market data, fundamentals, macro, and news sources.",
        "flags": [
            ("AKSHARE_ENABLED", "AkShare", "Free OHLC / fundamentals fallback"),
            ("FINNHUB_ENABLED", "Finnhub", "Quotes, news, and earnings"),
            ("FMP_ENABLED", "Financial Modeling Prep", "Rich fundamentals and history"),
            ("ALPHA_VANTAGE_ENABLED", "Alpha Vantage", "Fundamentals and history fallback"),
            ("FRED_ENABLED", "FRED", "Macro regime (rates, GDP)"),
            ("NASDAQ_DATA_LINK_ENABLED", "Nasdaq Data Link", "Reference / batch datasets"),
            ("NEWSAPI_ENABLED", "NewsAPI", "Sentiment fallback (dev/test)"),
        ],
    },
    {
        "id": "integrations",
        "title": "Integrations",
        "description": "Optional platforms layered on top of core data.",
        "flags": [
            ("OPENBB_ENABLED", "OpenBB", "SEC filings, insider, governance"),
            ("OPENBB_ON_SCAN", "OpenBB on scan", "Allow slow OpenBB fetches during bulk scans"),
            ("LLM_ENABLED", "LLM / GPT proxy", "AI reports and explanations"),
        ],
    },
    {
        "id": "automation",
        "title": "Automation",
        "description": "Background jobs and scheduled refresh.",
        "flags": [
            ("SCHEDULER_ENABLED", "Daily scheduler", "Post-close quote & fundamentals refresh"),
            ("QUANT_JOBS_ENABLED", "Quant jobs", "IC panel and weight rebalance cron"),
        ],
    },
    {
        "id": "quant_engines",
        "title": "Quant engines",
        "description": "Optional backtest and portfolio libraries.",
        "flags": [
            ("VBT_ENABLED", "vectorbt", "Vectorized backtest engine"),
            ("PYPFOPT_ENABLED", "PyPortfolioOpt", "Portfolio optimizer path"),
            ("QLIB_ENABLED", "Qlib", "Alpha workflow integration"),
            ("FINRL_ENABLED", "FinRL", "Allocation recommender path"),
            ("LEAN_EXPORT_ENABLED", "LEAN export", "QuantConnect handoff"),
            ("REGIME_OVERLAY_ENABLED", "Regime overlay", "Macro-adjusted sleeve scoring"),
        ],
    },
    {
        "id": "quant_v2",
        "title": "Institutional quant v2",
        "description": "Phased factor engine and production features.",
        "flags": [
            ("SCORE_ENGINE_V2_ENABLED", "Score engine v2", "Factor attribution API"),
            ("DYNAMIC_WEIGHTS_ENABLED", "Dynamic weights", "Regime-based factor weights"),
            ("SLEEVE_FACTORS_V3_ENABLED", "Sleeve factors v3", "Expanded factor catalog"),
            ("HARD_FILTERS_V3_ENABLED", "Hard filters v3", "Table-driven exclude rules"),
            ("TRADE_FEEDBACK_ENABLED", "Trade feedback", "Live trade learning loop"),
            ("BACKTEST_INSTITUTIONAL", "Institutional backtest", "Fees, slippage, delisting model"),
            ("AUDIT_LOG_ENABLED", "Audit log", "Persist API / job audit trail"),
        ],
    },
]

_ALL_FLAG_KEYS = frozenset(key for group in _CATALOG for key, _, _ in group["flags"])


def _key_configured(key_env: str | None) -> bool | None:
    if not key_env:
        return None
    mapping = {
        "FINNHUB_API_KEY": FINNHUB_API_KEY,
        "FMP_API_KEY": FMP_API_KEY,
        "ALPHA_VANTAGE_API_KEY": ALPHA_VANTAGE_API_KEY,
        "FRED_API_KEY": FRED_API_KEY,
        "GPT_PROXY_API_KEY": LLM_API_KEY,
        "LLM_API_KEY": LLM_API_KEY,
        "NEWSAPI_KEY": NEWSAPI_KEY,
        "NASDAQ_DATA_LINK_API_KEY": NASDAQ_DATA_LINK_API_KEY or QUANDL_API_KEY,
    }
    val = mapping.get(key_env)
    if val is None:
        val = getattr(config, key_env, "")
    return bool(val)


def _flag_obj(key: str):
    return getattr(config, key)


def list_api_settings() -> dict[str, Any]:
    registry = get_registry()
    groups = []
    for group in _CATALOG:
        items = []
        for key, label, description in group["flags"]:
            key_env = _KEY_ATTR.get(key)
            items.append(
                {
                    "key": key,
                    "label": label,
                    "description": description,
                    "enabled": registry.effective(key),
                    "env_default": registry.default_for(key),
                    "overridden": registry.is_overridden(key),
                    "configured": _key_configured(key_env),
                    "requires_key": key_env,
                }
            )
        groups.append(
            {
                "id": group["id"],
                "title": group["title"],
                "description": group["description"],
                "items": items,
            }
        )
    return {
        "groups": groups,
        "primary_price_source": config.PRIMARY_PRICE_SOURCE,
        "primary_fundamentals_source": config.PRIMARY_FUNDAMENTALS_SOURCE,
        "primary_news_source": config.PRIMARY_NEWS_SOURCE,
        "app_env": config.APP_ENV,
    }


def _apply_side_effects(key: str, enabled: bool) -> None:
    if key == "SCHEDULER_ENABLED":
        from services.scheduler import start_scheduler, stop_scheduler

        if enabled:
            stop_scheduler()
            start_scheduler()
        else:
            stop_scheduler()
        return
    if key == "OPENBB_ENABLED" and enabled:
        try:
            from data.openbb_client import warmup_openbb

            warmup_openbb()
        except Exception as exc:
            logger.warning("OpenBB warmup after enable failed: %s", exc)


def patch_api_settings(updates: dict[str, bool]) -> dict[str, Any]:
    registry = get_registry()
    unknown = set(updates) - _ALL_FLAG_KEYS
    if unknown:
        raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")

    for key, enabled in updates.items():
        flag = _flag_obj(key)
        flag.set(bool(enabled))
        _apply_side_effects(key, bool(enabled))

    return list_api_settings()


def reset_api_settings(keys: list[str] | None = None) -> dict[str, Any]:
    registry = get_registry()
    if keys:
        for key in keys:
            if key not in _ALL_FLAG_KEYS:
                raise ValueError(f"Unknown setting: {key}")
            registry.reset(key)
            _apply_side_effects(key, registry.effective(key))
    else:
        for key in list(registry.list_overrides()):
            registry.reset(key)
            _apply_side_effects(key, registry.effective(key))
    return list_api_settings()
