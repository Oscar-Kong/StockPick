"""Compounder scan — 5y history, cached fundamentals, missing-data confidence."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.candidate_builder import build_candidate
from data.fundamental_snapshot_service import resolve_fundamentals_for_scan
from data.reconciler import ReconcileResult
from models.schemas import Bucket
from scoring.fundamental import revenue_eps_consistency_score
from scoring.technical import smooth_growth_score_with_horizon
from services.scan_history_config import stage_a_period, stage_b_period
from services.scan_manager import _resolve_stage_b_context
from services.scan_data_flow import ScanDataFlowMetrics
from screeners.compounder import CompounderScreener


def _make_history(*, bars: int = 1260, base: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=bars, freq="B")
    closes = [base * (1.001 ** i) for i in range(bars)]
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [2_000_000] * bars,
        }
    )


def test_compounder_stage_b_period_is_five_years():
    assert stage_b_period(Bucket.compounder) == "5y"
    assert stage_a_period(Bucket.compounder) == "1y"


def test_penny_stage_b_does_not_use_five_year_period():
    assert stage_b_period(Bucket.penny) == "6mo"
    assert stage_b_period(Bucket.penny) != "5y"


def test_compounder_stage_b_requests_five_year_history():
    hist_1y = _make_history(bars=260)
    hist_5y = _make_history(bars=1260)
    ps = MagicMock()
    ps.get_history.return_value = hist_5y
    ps.get_info.return_value = {"currentPrice": 150.0, "marketCap": 50_000_000_000}
    ps.get_spy_history.return_value = None
    flow = ScanDataFlowMetrics()

    with patch(
        "data.candidate_builder.resolve_fundamentals_for_scan",
        return_value=MagicMock(
            info={"marketCap": 50e9, "sector": "Technology"},
            fundamentals={},
            reconcile=ReconcileResult(symbol="CMP", quality_score=75.0),
            snapshot_date="2025-06-01",
            source="reconciled",
            from_cache=True,
            refreshed=False,
            missing_fields=["share_dilution"],
            confidence_penalty=3.0,
            warnings=[],
            apply_to_info=lambda info: None,
        ),
    ):
        ctx = _resolve_stage_b_context(
            "CMP",
            stage_b_period="5y",
            stage_a_period="1y",
            include_spy=False,
            price_service=ps,
            bulk_hist={"CMP": hist_1y},
            skipped=[],
            flow=flow,
            bucket=Bucket.compounder,
        )

    assert ctx is not None
    ps.get_history.assert_called_once()
    assert ps.get_history.call_args.kwargs.get("period") == "5y" or ps.get_history.call_args[1].get("period") == "5y" or ps.get_history.call_args[0][1] == "5y"
    assert len(ctx.history) >= 1000


def test_cached_fundamentals_reused_without_live_reconcile():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {
        "info": {"marketCap": 20e9, "revenueGrowth": 0.12, "sector": "Healthcare"},
        "fundamentals": {"profit_margin": 0.18},
        "reconcile": {"quality_score": 82.0, "canonical": {}, "source_audit": {}, "flags": []},
    }
    store = MagicMock()
    store.get_latest_fundamental_snapshot.return_value = {
        "snapshot_date": today,
        "source": "reconciled",
        "payload": payload,
    }

    with patch("data.fundamental_snapshot_service.HistoricalStore", return_value=store):
        with patch("data.fundamental_snapshot_service.DataReconciler") as rec_cls:
            result = resolve_fundamentals_for_scan("COST", policy="cache_first")

    assert result.from_cache is True
    assert result.refreshed is False
    rec_cls.assert_not_called()
    assert result.info.get("revenueGrowth") == 0.12


def test_stale_fundamentals_trigger_controlled_refresh():
    stale_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
    store = MagicMock()
    store.get_latest_fundamental_snapshot.return_value = {
        "snapshot_date": stale_date,
        "source": "reconciled",
        "payload": {"info": {"marketCap": 1e9}, "fundamentals": {}, "reconcile": {}},
    }
    rec = ReconcileResult(symbol="COST", quality_score=70.0)
    rec.info_patch = {}

    with patch("data.fundamental_snapshot_service.HistoricalStore", return_value=store):
        with patch(
            "data.fundamental_snapshot_service.DataReconciler"
        ) as rec_cls:
            rec_cls.return_value.get_canonical_fundamentals.return_value = (
                {"marketCap": 2e9, "revenueGrowth": 0.1},
                {"profit_margin": 0.2},
                rec,
            )
            result = resolve_fundamentals_for_scan("COST", policy="cache_first")

    assert result.from_cache is False
    assert result.refreshed is True
    rec_cls.return_value.get_canonical_fundamentals.assert_called_once()


def test_missing_fundamentals_use_neutral_score_not_zero():
    result = revenue_eps_consistency_score({}, {})
    assert result.score == pytest.approx(50.0)
    assert "revenue_growth" in result.missing_fields
    assert "eps_growth" in result.missing_fields


def test_smooth_growth_uses_full_five_year_window_when_available():
    hist = _make_history(bars=1260)
    out = smooth_growth_score_with_horizon(hist, years=5)
    assert out.label == "5Y smooth growth"
    assert out.bars_used >= 1000
    assert out.years_effective >= 4.9


def test_smooth_growth_label_reflects_shorter_history():
    hist = _make_history(bars=300)
    out = smooth_growth_score_with_horizon(hist, years=5)
    assert "5Y smooth growth" not in out.label or "1." in out.label
    assert out.years_effective < 5.0


def test_compounder_scan_diagnostics_on_candidate():
    hist = _make_history(bars=1260)
    ps = MagicMock()
    ps.get_history.return_value = hist
    ps.get_spy_history.return_value = None

    fund = MagicMock()
    fund.info = {
        "marketCap": 40e9,
        "revenueGrowth": 0.11,
        "sector": "Consumer Defensive",
        "returnOnEquity": 0.25,
    }
    fund.fundamentals = {"profit_margin": 0.12}
    fund.reconcile = ReconcileResult(symbol="COST", quality_score=88.0)
    fund.snapshot_date = "2025-06-20"
    fund.source = "reconciled"
    fund.from_cache = True
    fund.refreshed = False
    fund.missing_fields = ["share_dilution"]
    fund.confidence_penalty = 3.0
    fund.warnings = []
    fund.apply_to_info = lambda info: fund.info.update(
        {
            "_fundamental_snapshot_date": fund.snapshot_date,
            "_fundamental_confidence_penalty": fund.confidence_penalty,
        }
    )

    with patch("data.candidate_builder.resolve_fundamentals_for_scan", return_value=fund):
        ctx = build_candidate(
            "COST",
            history_period="5y",
            reconcile=True,
            fundamentals_policy="cache_first",
            price_service=ps,
        )

    diag = ctx.info.get("_scan_diagnostics") or {}
    assert diag.get("price_history_period") == "5y"
    assert diag.get("fundamental_snapshot_date") == "2025-06-20"
    assert "share_dilution" in diag.get("missing_fundamental_fields", [])


def test_synthetic_compounder_before_after_example():
    """Document before/after: 1y history + sparse info vs 5y + cached fundamentals."""
    hist_1y = _make_history(bars=260)
    hist_5y = _make_history(bars=1260)
    sparse_info = {"currentPrice": 150.0}
    rich_info = {
        "marketCap": 45e9,
        "revenueGrowth": 0.09,
        "earningsGrowth": 0.11,
        "returnOnEquity": 0.28,
        "profitMargins": 0.13,
        "freeCashflow": 5e9,
        "sector": "Consumer Defensive",
    }

    screener = CompounderScreener()
    ctx_before = MagicMock()
    ctx_before.symbol = "SYNTH"
    ctx_before.info = sparse_info
    ctx_before.fundamentals = {}
    ctx_before.history = hist_1y

    ctx_after = MagicMock()
    ctx_after.symbol = "SYNTH"
    ctx_after.info = {
        **rich_info,
        "_fundamental_confidence_penalty": 6.0,
        "_missing_fundamental_fields": ["share_dilution"],
        "_scan_diagnostics": {
            "price_history_period": "5y",
            "price_history_bars": len(hist_5y),
            "fundamental_snapshot_date": "2025-06-20",
            "reconciliation_quality": 85.0,
        },
    }
    ctx_after.fundamentals = {"profit_margin": 0.13}
    ctx_after.history = hist_5y

    score_before, _, _, summary_before, metrics_before = screener.score(ctx_before)
    score_after, signals_after, _, summary_after, metrics_after = screener.score(ctx_after)

    smooth_signal = next(s for s in signals_after if "smooth growth" in s.name.lower())
    example = {
        "before": {
            "history_bars": len(hist_1y),
            "history_period": "1y",
            "fundamentals": "sparse (price only)",
            "score": round(score_before, 1),
            "smooth_growth_label": metrics_before.get("smooth_growth_label"),
            "summary": summary_before,
        },
        "after": {
            "history_bars": len(hist_5y),
            "history_period": "5y",
            "fundamentals": "cached reconciled snapshot",
            "score": round(score_after, 1),
            "smooth_growth_label": smooth_signal.name,
            "smooth_growth_bars": metrics_after.get("smooth_growth_bars_used"),
            "missing_fields": metrics_after.get("missing_fundamental_fields"),
            "confidence_penalty": metrics_after.get("fundamental_confidence_penalty"),
            "diagnostics": metrics_after.get("scan_diagnostics"),
            "summary": summary_after,
        },
    }
    print("COMPOUNDER_BEFORE_AFTER=" + json.dumps(example, indent=2))
    assert example["after"]["history_bars"] > example["before"]["history_bars"]
    assert smooth_signal.name == "5Y smooth growth"
    assert score_after != score_before or metrics_after.get("smooth_growth_bars_used", 0) > 260
