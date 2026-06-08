"""Curated trader-profile intelligence and integration recipes."""
from __future__ import annotations

from utils.datetime_util import utc_iso_z, utc_now

_COLLECTED_AT = utc_iso_z(utc_now())


def _profiles() -> list[dict]:
    return [
        {
            "slug": "keith-gill",
            "name": "Keith Gill",
            "aliases": ["Roaring Kitty", "DeepFuckingValue"],
            "profile_type": "individual trader",
            "data_reliability": "medium",
            "summary": (
                "High-conviction, concentrated long-equity style with optional-call leverage around "
                "deep value + crowding/catalyst narratives."
            ),
            "strategy_principles": [
                "Concentrated conviction bets instead of broad diversification",
                "Fundamental undervaluation thesis plus event/catalyst timing",
                "Selective options use to express asymmetric upside",
                "Tolerance for high volatility and narrative-driven flows",
            ],
            "known_observations": [
                {
                    "observation": "Publicly documented long GameStop thesis and position updates",
                    "confidence": "high",
                },
                {
                    "observation": "Public SEC Schedule 13G/13G-A filings tied to Chewy stake",
                    "confidence": "high",
                },
            ],
            "integration_recipe": {
                "style": "concentrated_value_catalyst",
                "bucket_bias": ["medium", "compounder"],
                "scan_tilt": {
                    "max_results": 12,
                    "min_volume": 500000,
                    "prefer_high_short_interest": True,
                    "prefer_clear_catalyst": True,
                },
                "risk_controls": [
                    "Hard stop loss required",
                    "Max 10-15% capital per position",
                    "Avoid averaging down without thesis revalidation",
                ],
            },
            "sources": [
                {
                    "title": "Keith Gill profile (context timeline)",
                    "url": "https://en.wikipedia.org/wiki/Keith_Gill_(investor)",
                    "source_type": "reference",
                },
                {
                    "title": "SEC Schedule 13G filing (Chewy)",
                    "url": "https://www.sec.gov/Archives/edgar/data/1766502/000110465924076457/tm2418581d1_sc13g.htm",
                    "source_type": "regulatory",
                },
                {
                    "title": "SEC Schedule 13G/A amendment",
                    "url": "https://www.sec.gov/Archives/edgar/data/1766502/000110465924112245/tm2427027d1_sc13ga.htm",
                    "source_type": "regulatory",
                },
            ],
        },
        {
            "slug": "serenity-aleabitoreddit",
            "name": "Serenity",
            "aliases": ["@aleabitoreddit"],
            "profile_type": "anonymous public commentator/trader",
            "data_reliability": "low_to_medium",
            "summary": (
                "Theme-driven AI supply-chain chokepoint hunting with concentrated bets. "
                "Most track record claims are self-reported and not regulatory-audited."
            ),
            "strategy_principles": [
                "Map bottlenecks in AI hardware supply chains",
                "Focus on underfollowed suppliers versus obvious mega-cap winners",
                "Act early before institutional positioning is visible",
                "Concentrated positions with high drawdown risk",
            ],
            "known_observations": [
                {
                    "observation": "No public fund filings/13F under this handle",
                    "confidence": "medium",
                },
                {
                    "observation": "Public writeups describe chokepoint framework; returns are largely self-reported",
                    "confidence": "medium",
                },
            ],
            "integration_recipe": {
                "style": "thematic_chokepoint",
                "bucket_bias": ["medium", "compounder"],
                "scan_tilt": {
                    "max_results": 20,
                    "prefer_sector_focus": ["Semiconductors", "AI Infrastructure", "Power"],
                    "prefer_revenue_acceleration": True,
                    "prefer_supply_chain_moat": True,
                },
                "risk_controls": [
                    "Cap exposure to single theme",
                    "Use trailing stops on momentum legs",
                    "Validate claims with independent fundamentals before entry",
                ],
            },
            "sources": [
                {
                    "title": "Serenity profile discussion (Substack)",
                    "url": "https://singularityresearchfund.substack.com/p/inside-the-mind-of-serenity-aleabitoreddit",
                    "source_type": "commentary",
                },
                {
                    "title": "Serenity strategy summary",
                    "url": "https://www.kucoin.com/news/flash/who-is-serenity-understanding-the-investment-logic-of-the-ai-supply-chain-guru",
                    "source_type": "media",
                },
            ],
        },
        {
            "slug": "leopold-aschenbrenner",
            "name": "Leopold Aschenbrenner",
            "aliases": ["Situational Awareness LP"],
            "profile_type": "fund manager (13F-reporting)",
            "data_reliability": "high_for_reported_13f_long_book",
            "summary": (
                "Quarterly disclosed 13F long/option book under Situational Awareness LP; "
                "can be replicated as delayed institutional-style factor overlay."
            ),
            "strategy_principles": [
                "Concentrated thematic exposure around AI infrastructure chain",
                "Use options and directional hedges as part of portfolio expression",
                "Quarterly rebalance cadence aligned to 13F availability",
                "Top-position concentration with macro/thematic narrative",
            ],
            "known_observations": [
                {
                    "observation": "SEC 13F-HR filings available under CIK 0002045724",
                    "confidence": "high",
                },
                {
                    "observation": "13F only captures U.S. reportable longs/listed options, not full book",
                    "confidence": "high",
                },
            ],
            "integration_recipe": {
                "style": "institutional_13f_overlay",
                "bucket_bias": ["compounder", "medium"],
                "scan_tilt": {
                    "max_results": 25,
                    "prefer_market_cap": "mid_to_large",
                    "rebalance_frequency": "quarterly",
                    "delay_days_after_quarter_end": 45,
                },
                "risk_controls": [
                    "Treat 13F as delayed signal, not real-time copy trade",
                    "Blend with your own risk model before action",
                    "Cap net exposure to any single crowded theme",
                ],
            },
            "sources": [
                {
                    "title": "SEC 13F filing detail (Q1 2026)",
                    "url": "https://www.sec.gov/Archives/edgar/data/2045724/000204572426000008/0002045724-26-000008-index.htm",
                    "source_type": "regulatory",
                },
                {
                    "title": "SEC 13F filing detail (Q1 2025)",
                    "url": "https://www.sec.gov/Archives/edgar/data/2045724/000204572425000002/0002045724-25-000002-index.html",
                    "source_type": "regulatory",
                },
                {
                    "title": "13F filing history index",
                    "url": "https://13f.info/manager/0002045724-situational-awareness-lp",
                    "source_type": "aggregator",
                },
            ],
        },
        {
            "slug": "dan-zanger",
            "name": "Dan Zanger",
            "aliases": ["ChartPattern.com", "Zanger Report"],
            "profile_type": "technical momentum trader",
            "data_reliability": "medium",
            "summary": (
                "Classic breakout momentum/chart-pattern framework (flags, pennants, cup-and-handle, "
                "ascending triangles) with strong emphasis on volume confirmation."
            ),
            "strategy_principles": [
                "Trade breakout patterns from high-tight bases",
                "Require relative volume expansion on breakout",
                "Prefer strong earnings/revenue acceleration names",
                "Concentrate in strongest momentum regimes and reduce activity in weak markets",
            ],
            "known_observations": [
                {
                    "observation": "Widely cited historical audited record during late-1990s bubble era",
                    "confidence": "medium",
                },
                {
                    "observation": "Later performance records are less consistently independently audited",
                    "confidence": "medium",
                },
            ],
            "integration_recipe": {
                "style": "momentum_breakout",
                "bucket_bias": ["penny", "medium"],
                "scan_tilt": {
                    "max_results": 20,
                    "min_volume": 1000000,
                    "prefer_breakout_pattern": True,
                    "prefer_relative_volume_gt": 2.0,
                },
                "risk_controls": [
                    "Cut failed breakouts quickly",
                    "Avoid trading against broad market regime",
                    "Use partial profit-taking into extended moves",
                ],
            },
            "sources": [
                {
                    "title": "Dan Zanger background and style summary",
                    "url": "https://www.chartpattern.com/about.cfm",
                    "source_type": "primary_profile",
                },
                {
                    "title": "Independent review and caveats",
                    "url": "https://investor.com/trading/dan-zanger-review-world-record-returns",
                    "source_type": "media",
                },
                {
                    "title": "Interview notes on stock selection process",
                    "url": "https://tradingresourcehub.substack.com/p/dan-zanger-finding-the-biggest-movers",
                    "source_type": "interview_summary",
                },
            ],
        },
    ]


def list_trader_profiles() -> list[dict]:
    return _profiles()


def get_trader_profile(slug: str) -> dict | None:
    key = slug.strip().lower()
    for profile in _profiles():
        if profile["slug"] == key:
            return profile
    return None


def build_trader_preset(slug: str, bucket: str) -> dict | None:
    profile = get_trader_profile(slug)
    if not profile:
        return None
    style = profile["integration_recipe"]["style"]
    b = bucket.lower()
    if b not in ("penny", "medium", "compounder"):
        return None

    default_horizon = {"penny": "1y", "medium": "3y", "compounder": "5y"}[b]
    preset = {
        "slug": slug,
        "bucket": b,
        "scan_options": {
            "max_results": int(profile["integration_recipe"]["scan_tilt"].get("max_results", 20)),
        },
        "backtest_overrides": {},
        "horizon": default_horizon,
        "notes": [],
    }

    if style == "momentum_breakout":
        preset["scan_options"]["min_volume"] = 1_000_000
        preset["backtest_overrides"] = {"hold_days": 15, "stop_pct": 0.08, "target_pct": 0.18}
        preset["notes"] = ["Breakout style: faster turnover, tighter stop, higher volatility."]
    elif style == "concentrated_value_catalyst":
        preset["scan_options"]["min_volume"] = 500_000
        preset["backtest_overrides"] = {"hold_days": 30, "stop_pct": 0.12, "target_pct": 0.35}
        preset["notes"] = ["Catalyst value style: wider stop and larger upside target."]
    elif style == "thematic_chokepoint":
        preset["scan_options"]["min_volume"] = 750_000
        preset["backtest_overrides"] = {"hold_days": 35, "stop_pct": 0.10, "target_pct": 0.30}
        preset["notes"] = ["Thematic style: hold through trend cycles with controlled downside."]
    elif style == "institutional_13f_overlay":
        preset["scan_options"]["min_volume"] = 1_500_000
        preset["backtest_overrides"] = {"hold_days": 63, "stop_pct": 0.15, "target_pct": 0.25}
        preset["horizon"] = "5y" if b == "compounder" else "3y"
        preset["notes"] = ["13F overlay: delayed signal; longer hold windows are more realistic."]

    return preset


def trader_collection_meta() -> dict:
    return {
        "collected_at_utc": _COLLECTED_AT,
        "notes": [
            "This dataset is curated from public sources and is not investment advice.",
            "Claims without regulatory backing should be treated as hypotheses.",
            "Use this as strategy inspiration, then validate through your own backtests.",
        ],
    }
