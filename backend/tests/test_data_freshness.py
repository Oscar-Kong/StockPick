"""Data freshness and refresh orchestration tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
from unittest.mock import MagicMock, patch

from models.schemas import DashboardFreshnessSummary, DataFreshnessStatus
from services import data_freshness_service as dfs
from services import refresh_orchestrator as ro


def _ts(hours_ago: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.replace(tzinfo=None).isoformat() + "Z"


def test_fresh_prices_do_not_trigger_refresh():
    ro._last_price_refresh_at = None
    with patch("services.refresh_orchestrator.assess_freshness") as assess:
        assess.return_value = DataFreshnessStatus(
            key="latest_prices",
            last_updated_at=_ts(0.01),
            stale_after_seconds=300,
            is_stale=False,
        )
        with patch("services.refresh_orchestrator.get_current_holdings", return_value=[{"symbol": "AMC"}]):
            with patch("services.refresh_orchestrator.PriceService") as ps_cls:
                result = ro.refresh_prices_for_holdings(force=False)
    assert result.get("skipped") is True
    ps_cls.assert_not_called()


def test_stale_prices_trigger_price_refresh():
    ro._last_price_refresh_at = None
    with patch("services.refresh_orchestrator.assess_freshness") as assess:
        assess.return_value = DataFreshnessStatus(key="latest_prices", is_stale=True)
        with patch("services.refresh_orchestrator.get_current_holdings", return_value=[{"symbol": "AMC"}]):
            with patch("services.refresh_orchestrator.PriceService") as ps_cls:
                ps_cls.return_value.get_history.return_value = MagicMock(empty=False)
                with patch("services.refresh_orchestrator.mark_freshness_updated"):
                    result = ro.refresh_prices_for_holdings(force=False)
    assert result.get("refreshed") == 1


def test_stale_holdings_trigger_decision_refresh_chain():
    with patch("services.refresh_orchestrator.assess_freshness") as assess:
        def _side(key):
            if key == "portfolio_holdings":
                return DataFreshnessStatus(key=key, is_stale=True)
            if key == "latest_prices":
                return DataFreshnessStatus(key=key, is_stale=False)
            if key == "penny_scan":
                return DataFreshnessStatus(key=key, is_stale=False)
            if key == "daily_decision":
                return DataFreshnessStatus(key=key, is_stale=True)
            return DataFreshnessStatus(key=key, is_stale=False)

        assess.side_effect = _side
        with patch.object(ro, "_refresh_holdings", return_value={"holdings": 2}) as rh:
            with patch.object(ro, "refresh_prices_for_holdings", return_value={"skipped": True}):
                with patch.object(ro, "refresh_penny_scan_if_needed", return_value={"skipped": True}):
                    with patch.object(ro, "refresh_daily_decision_if_needed", return_value={"status": "ok"}) as rd:
                        with patch.object(ro, "mark_freshness_updated"):
                            result = ro._execute_home_refresh(force=False)
    assert rh.called
    assert rd.called
    assert result["status"] == "ok"


def test_daily_decision_stale_after_holdings_change():
    snap_ts = datetime.now(timezone.utc).replace(tzinfo=None)
    decision_ts = snap_ts - timedelta(hours=2)
    with patch("services.data_freshness_service.get_latest_decision") as gd:
        gd.return_value = {"created_at": decision_ts.isoformat() + "Z", "trigger": "manual"}
        with patch("services.data_freshness_service.get_latest_portfolio_snapshot") as gs:
            gs.return_value = {"created_at": snap_ts.isoformat() + "Z"}
            with patch("services.data_freshness_service.get_current_holdings", return_value=[{"symbol": "X"}]):
                status = dfs.assess_daily_decision()
    assert status.is_stale
    assert "Holdings changed" in status.reason


def test_daily_decision_stale_after_price_update():
    decision_ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    price_ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    with patch("services.data_freshness_service.get_latest_decision") as gd:
        gd.return_value = {"created_at": decision_ts.isoformat() + "Z", "trigger": "manual"}
        with patch("services.data_freshness_service.get_latest_portfolio_snapshot") as gs:
            gs.return_value = {"created_at": decision_ts.isoformat() + "Z"}
            with patch("services.data_freshness_service.get_current_holdings", return_value=[{"symbol": "X"}]):
                with patch("services.data_freshness_service._latest_price_refresh_ts", return_value=price_ts):
                    status = dfs.assess_daily_decision()
    assert status.is_stale
    assert "Prices refreshed" in status.reason


def test_home_dashboard_returns_cached_data_quickly():
    from services.home_dashboard_service import build_daily_dashboard

    with patch("services.home_dashboard_service.assess_all_freshness") as af:
        af.return_value = DashboardFreshnessSummary(overall_status="fresh")
        result = build_daily_dashboard(include_freshness=True)
    assert result.freshness is not None
    assert result.portfolio_value >= 0


def test_background_refresh_does_not_duplicate_jobs():
    ro._home_refresh_running = False
    ro._active_home_job_id = None
    ro._refresh_started_at = None
    gate = threading.Event()

    def _slow_refresh(*args, **kwargs):
        gate.wait(timeout=2)
        return {"status": "ok", "steps": {}}

    with patch.object(ro, "_execute_home_refresh", side_effect=_slow_refresh):
        first = ro.start_home_refresh_async(force=False)
        second = ro.start_home_refresh_async(force=False)
    assert first is not None
    assert second is None
    gate.set()
    ro._home_refresh_running = False
    ro._active_home_job_id = None
    ro._refresh_started_at = None


def test_manual_force_refresh_bypasses_ttl():
    with patch.object(ro, "_price_ttl_ok", return_value=True):
        with patch("services.refresh_orchestrator.get_current_holdings", return_value=[{"symbol": "AMC"}]):
            with patch("services.refresh_orchestrator.PriceService") as ps_cls:
                ps_cls.return_value.get_history.return_value = MagicMock(empty=False)
                with patch("services.refresh_orchestrator.mark_freshness_updated"):
                    result = ro.refresh_prices_for_holdings(force=True)
    assert result.get("refreshed") == 1


def test_no_medium_bucket_refresh():
    with patch.object(dfs, "assess_freshness") as assess:
        assess.return_value = DataFreshnessStatus(key="penny_scan", is_stale=True)
        with patch("services.refresh_orchestrator.scan_manager") as sm:
            sm.create_job.return_value = MagicMock(job_id="j1", results=[])
            with patch("services.refresh_orchestrator.mark_freshness_updated"):
                ro.refresh_penny_scan_if_needed(force=True)
            args = sm.create_job.call_args[0][0]
            assert args.value == "penny"


def test_stale_prices_reduce_decision_confidence():
    from services.portfolio_decision_engine import DecisionInput, compute_holding_decision

    inp = DecisionInput(
        symbol="AMC",
        sleeve="penny",
        shares=10,
        avg_cost=2.0,
        latest_price=2.5,
        alpha_score=75,
        momentum_score=70,
        liquidity_score=60,
        risk_score=40,
        data_quality_score=70,
        current_weight=0.03,
        target_weight=0.05,
        max_allowed_weight=0.05,
        price_stale=True,
    )
    out = compute_holding_decision(inp, total_portfolio_value=1000)
    assert out.final_decision != "buy"
    assert "stale_price" in out.risk_flags


def test_assess_all_freshness_demo_overall():
    with patch("services.data_freshness_service.get_or_create_account", return_value={"source": "demo"}):
        summary = dfs.assess_all_freshness()
    assert summary.overall_status == "demo"


def test_compounder_stale_does_not_make_home_stale():
    fresh = DataFreshnessStatus(key="portfolio_holdings", is_stale=False, last_updated_at=_ts(0.01))
    with patch.object(dfs, "assess_portfolio_holdings", return_value=fresh):
        with patch.object(dfs, "assess_latest_prices", return_value=DataFreshnessStatus(key="latest_prices", is_stale=False)):
            with patch.object(dfs, "assess_daily_decision", return_value=DataFreshnessStatus(key="daily_decision", is_stale=False)):
                with patch.object(
                    dfs,
                    "assess_penny_scan",
                    return_value=DataFreshnessStatus(key="penny_scan", is_stale=False),
                ):
                    with patch.object(
                        dfs,
                        "assess_compounder_scan",
                        return_value=DataFreshnessStatus(key="compounder_scan", is_stale=True, reason="old"),
                    ):
                        with patch.object(dfs, "assess_risk_metrics", return_value=DataFreshnessStatus(key="risk_metrics", is_stale=False)):
                            with patch.object(dfs, "assess_data_quality", return_value=DataFreshnessStatus(key="data_quality", is_stale=False)):
                                with patch.object(
                                    dfs,
                                    "assess_closed_positions",
                                    return_value=DataFreshnessStatus(key="closed_positions", is_stale=False),
                                ):
                                    with patch("services.data_freshness_service.get_or_create_account", return_value={"source": "csv"}):
                                        summary = dfs.assess_all_freshness()
    assert summary.overall_status == "fresh"
    assert summary.refresh_recommended is False


def test_penny_scan_refresh_is_non_blocking():
    with patch.object(dfs, "assess_freshness", return_value=DataFreshnessStatus(key="penny_scan", is_stale=True)):
        with patch("services.refresh_orchestrator.scan_manager") as sm:
            sm.create_job.return_value = MagicMock(job_id="j1", results=[])
            with patch("services.refresh_orchestrator.threading.Thread") as thread_cls:
                thread_cls.return_value.start = MagicMock()
                result = ro.refresh_penny_scan_if_needed(force=True, blocking=False)
    assert result.get("async") is True
    thread_cls.assert_called_once()
    sm.create_job.assert_called_once()
