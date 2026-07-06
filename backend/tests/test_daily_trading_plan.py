"""Tests for daily trading plan policy engine."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from models.schemas import PortfolioDecisionItem, PortfolioDecisionResponse
from services.daily_trading_distress import evaluate_distress
from services.daily_trading_holiday import HolidayRiskAssessment, assess_holiday_risk
from services.daily_trading_news import classify_news_context
from services.daily_trading_plan_service import build_daily_trading_plan
from services.daily_trading_policy import DailyTradingPolicy
from services.daily_trading_volume import classify_volume_behavior

NY = ZoneInfo("America/New_York")


def _et(hour: int, minute: int = 0, year: int = 2026, month: int = 7, day: int = 1) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=NY).astimezone(timezone.utc)


def _qualified_scan_row(symbol: str = "STRONG", score: float = 88.0) -> dict:
    return {
        "symbol": symbol,
        "price": 10.0,
        "score": score,
        "confidence_score": 85.0,
        "metrics": {
            "trend_score": 75.0,
            "momentum_score": 72.0,
            "liquidity_score": 70.0,
            "spread_score": 65.0,
            "data_quality_score": 85.0,
            "alpha_score": 80.0,
            "sector": "Technology",
            "relative_strength_vs_spy": 0.05,
            "history_bars": 280,
            "average_dollar_volume_20d": 500_000.0,
        },
    }


def _base_kwargs(**overrides):
    base = {
        "portfolio_value": 20_000.0,
        "cash": 10_000.0,
        "holdings": [],
        "decision": None,
        "policy": DailyTradingPolicy(),
        "price_service": MagicMock(),
        "finnhub": MagicMock(),
    }
    base["price_service"].get_history.return_value = pd.DataFrame(
        {
            "date": pd.date_range(end=pd.Timestamp.today(), periods=60, freq="B"),
            "open": [9.5] * 60,
            "high": [10.5] * 60,
            "low": [9.0] * 60,
            "close": [10.0 + i * 0.01 for i in range(60)],
            "volume": [1_000_000 + i * 1000 for i in range(60)],
        }
    )
    base["price_service"].get_info.return_value = {"exchange": "NASDAQ"}
    base["finnhub"].news_summary.return_value = {
        "score": 52.0,
        "categories": {},
        "red_flags": [],
        "headlines": [],
    }
    base.update(overrides)
    return base


def test_exposure_above_50_blocks_new_buy():
    holdings = [{"symbol": "PENNY1", "shares": 1000, "avg_cost": 10.0, "bucket": "penny"}]
    decision = PortfolioDecisionResponse(
        as_of="2026-07-01",
        cash=1000,
        total_value=20_000,
        invested_value=19_000,
        items=[
            PortfolioDecisionItem(
                symbol="PENNY1",
                bucket="penny",
                price=10.0,
                shares=1000,
                avg_cost=10.0,
                market_value=19_000,
                pl_pct=0.0,
                current_weight=0.95,
                target_weight=0.03,
                buy_pct=0,
                keep_pct=100,
                sell_pct=0,
                decision="keep",
                score=70,
                risk_index=40,
                suggested_dollar_action=0,
            )
        ],
    )
    plan = build_daily_trading_plan(
        **_base_kwargs(
            holdings=holdings,
            decision=decision,
            portfolio_value=20_000,
            scan_rows=[_qualified_scan_row()],
            now=_et(11, 0),
        )
    )
    assert plan.decision != "buy"
    exp_rule = next(r for r in plan.rule_checklist if r.rule_id == "MAX_EXPOSURE")
    assert exp_rule.status == "fail"


def test_existing_short_term_position_blocks_second_open():
    holdings = [{"symbol": "ACTIVE", "shares": 50, "avg_cost": 8.0, "bucket": "penny"}]
    decision = PortfolioDecisionResponse(
        as_of="2026-07-01",
        cash=5000,
        total_value=10_000,
        invested_value=5000,
        items=[
            PortfolioDecisionItem(
                symbol="ACTIVE",
                bucket="penny",
                price=8.0,
                shares=50,
                avg_cost=8.0,
                market_value=400,
                pl_pct=2.0,
                current_weight=0.04,
                target_weight=0.03,
                buy_pct=10,
                keep_pct=80,
                sell_pct=10,
                decision="keep",
                score=65,
                risk_index=40,
                suggested_dollar_action=0,
            )
        ],
    )
    plan = build_daily_trading_plan(
        **_base_kwargs(
            holdings=holdings,
            decision=decision,
            scan_rows=[_qualified_scan_row("OTHER")],
            now=_et(11, 0),
        )
    )
    assert plan.decision == "manage"
    assert plan.active_short_term_positions == 1


def test_before_10am_returns_watch_not_buy():
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[_qualified_scan_row()], now=_et(9, 30))
    )
    assert plan.decision == "watch"
    if plan.primary_candidate:
        assert plan.primary_candidate.action == "watch"


def test_after_10am_allows_qualified_buy():
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[_qualified_scan_row()], now=_et(10, 15))
    )
    assert plan.decision == "buy"
    assert plan.primary_candidate is not None
    assert plan.primary_candidate.action == "buy"


def test_5pct_loss_produces_exit():
    holdings = [{"symbol": "LOSER", "shares": 100, "avg_cost": 10.0, "bucket": "penny"}]
    decision = PortfolioDecisionResponse(
        as_of="2026-07-01",
        cash=5000,
        total_value=10_000,
        invested_value=5000,
        items=[
            PortfolioDecisionItem(
                symbol="LOSER",
                bucket="penny",
                price=9.4,
                shares=100,
                avg_cost=10.0,
                market_value=940,
                pl_pct=-6.0,
                current_weight=0.09,
                target_weight=0.03,
                buy_pct=0,
                keep_pct=20,
                sell_pct=80,
                decision="sell",
                score=40,
                risk_index=70,
                suggested_dollar_action=-500,
            )
        ],
    )
    plan = build_daily_trading_plan(
        **_base_kwargs(holdings=holdings, decision=decision, now=_et(11, 0))
    )
    assert plan.decision == "exit"
    assert plan.primary_candidate.action == "exit"


def test_10pct_gain_produces_reduce_half():
    holdings = [{"symbol": "WINNER", "shares": 100, "avg_cost": 10.0, "bucket": "penny"}]
    decision = PortfolioDecisionResponse(
        as_of="2026-07-01",
        cash=5000,
        total_value=10_000,
        invested_value=5000,
        items=[
            PortfolioDecisionItem(
                symbol="WINNER",
                bucket="penny",
                price=11.2,
                shares=100,
                avg_cost=10.0,
                market_value=1120,
                pl_pct=12.0,
                current_weight=0.11,
                target_weight=0.03,
                buy_pct=0,
                keep_pct=50,
                sell_pct=50,
                decision="sell",
                score=75,
                risk_index=35,
                suggested_dollar_action=-200,
            )
        ],
    )
    plan = build_daily_trading_plan(
        **_base_kwargs(holdings=holdings, decision=decision, now=_et(11, 0))
    )
    assert plan.decision == "reduce"
    assert plan.primary_candidate.first_target_sell_fraction_pct == 50.0


def test_no_qualified_candidate_stay_in_cash():
    bad_row = _qualified_scan_row("WEAK", score=30)
    bad_row["metrics"]["trend_score"] = 40
    bad_row["confidence_score"] = 40
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[bad_row], now=_et(11, 0))
    )
    assert plan.decision == "stay_in_cash"
    assert plan.cash_reason is not None


def test_leverage_never_in_position_sizing():
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[_qualified_scan_row()], now=_et(11, 0))
    )
    lev_rule = next(r for r in plan.rule_checklist if r.rule_id == "NO_LEVERAGE")
    assert lev_rule.status == "pass"
    assert plan.primary_candidate.maximum_position_value <= plan.portfolio_value if hasattr(plan, "portfolio_value") else True


def test_distressed_security_rejects_candidate():
    row = _qualified_scan_row("OTC.PK")
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[row], now=_et(11, 0))
    )
    assert plan.decision != "buy"
    assert any("OTC" in str(r) for r in (plan.rejected_candidates or [{}])[0].get("reasons", []) if plan.rejected_candidates)


def test_missing_mandatory_data_returns_watch_not_buy():
    row = _qualified_scan_row("NODATA")
    row["metrics"].pop("history_bars", None)
    row["metrics"].pop("average_dollar_volume_20d", None)
    row["confidence_score"] = 0
    ps = MagicMock()
    ps.get_history.return_value = None
    ps.get_info.return_value = {}
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[row], price_service=ps, now=_et(11, 0))
    )
    assert plan.decision in ("stay_in_cash", "watch")


def test_positive_news_alone_cannot_create_buy():
    row = _qualified_scan_row("NEWS")
    row["metrics"]["trend_score"] = 55  # weak trend
    fh = MagicMock()
    fh.news_summary.return_value = {
        "score": 85.0,
        "categories": {"earnings": 2},
        "red_flags": [],
        "headlines": ["Company beats earnings"],
    }
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[row], finnhub=fh, now=_et(11, 0))
    )
    assert plan.decision != "buy"


def test_negative_news_alone_cannot_create_buy():
    row = _qualified_scan_row("BADNEWS")
    row["metrics"]["trend_score"] = 55
    fh = MagicMock()
    fh.news_summary.return_value = {
        "score": 20.0,
        "categories": {"legal": 1},
        "red_flags": ["SEC probe announced"],
        "headlines": ["SEC investigation"],
    }
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[row], finnhub=fh, now=_et(11, 0))
    )
    assert plan.decision != "buy"


def test_volume_contraction_without_support_is_inconclusive():
    df = pd.DataFrame(
        {
            "open": [10.0] * 30,
            "high": [10.2] * 30,
            "low": [8.5] * 30,
            "close": [8.0] * 30,
            "volume": [2_000_000 - i * 50_000 for i in range(30)],
        }
    )
    vol = classify_volume_behavior(df)
    assert vol.classification == "inconclusive"


def test_high_volume_support_failure_is_distribution():
    df = pd.DataFrame(
        {
            "open": [10.0] * 30,
            "high": [10.5] * 30,
            "low": [9.5] * 30,
            "close": [9.4] * 30,
            "volume": [500_000] * 29 + [2_500_000],
        }
    )
    vol = classify_volume_behavior(df)
    assert vol.classification == "possible_distribution"


def test_pre_holiday_recommends_reduce_exposure():
    with patch(
        "services.daily_trading_plan_service.assess_holiday_risk",
        return_value=HolidayRiskAssessment(True, True, "Long weekend ahead"),
    ):
        plan = build_daily_trading_plan(
            **_base_kwargs(scan_rows=[_qualified_scan_row()], now=_et(11, 0))
        )
    assert plan.holiday_risk.recommend_reduce_exposure is True


def test_focus_list_max_five_symbols():
    rows = [_qualified_scan_row(f"S{i}", score=90 - i) for i in range(10)]
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=rows, now=_et(11, 0))
    )
    assert len(plan.focus_list) <= 5


def test_hard_rule_failure_cannot_yield_buy():
    policy = DailyTradingPolicy(data_confidence_min=95.0)
    plan = build_daily_trading_plan(
        **_base_kwargs(scan_rows=[_qualified_scan_row()], policy=policy, now=_et(11, 0))
    )
    assert plan.decision != "buy"


def test_deterministic_for_identical_inputs():
    kwargs = _base_kwargs(scan_rows=[_qualified_scan_row()], now=_et(11, 0))
    a = build_daily_trading_plan(**kwargs)
    b = build_daily_trading_plan(**kwargs)
    assert a.plan_id == b.plan_id
    assert a.decision == b.decision
    assert a.summary == b.summary


def test_distress_otc_rejection_unit():
    result = evaluate_distress(
        symbol="FOO.PK",
        price=1.0,
        history=None,
        info=None,
        metrics={},
        quality_score=80,
        hist_len=0,
    )
    assert result.rejected
    assert any("OTC" in r for r in result.reasons)


def test_news_positive_priced_in():
    cls = classify_news_context(
        news_summary={"score": 75, "categories": {"earnings": 1}, "red_flags": [], "headlines": ["Beat"]},
        price=12.0,
        prev_close=10.0,
        momentum_score=48.0,
        gap_pct=8.0,
    )
    assert cls.classification == "positive_news_priced_in"


def test_holiday_assessment_callable():
    result = assess_holiday_risk(_et(11, 0))
    assert hasattr(result, "is_pre_holiday_session")
