"""Trader strategy intelligence routes (public-source profiles)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from data import cache as cache_module
from data.price_service import PriceService
from data.reconciler import DataReconciler
from data.strategy_registry import StrategyRegistry
from ml.backtest_compounder import run_compounder_backtest
from ml.backtest_penny import run_penny_backtest
from models.schemas import (
    Bucket,
    TraderBacktestVariantResult,
    TraderPresetResponse,
    TraderProfileItem,
    TraderProfileListResponse,
    TraderQuickCompareResponse,
)
from services.trader_intel import (
    build_trader_preset,
    get_trader_profile,
    list_trader_profiles,
    trader_collection_meta,
)

router = APIRouter(prefix="/trader-intel", tags=["trader-intel"])


@router.get("", response_model=TraderProfileListResponse)
def list_profiles():
    meta = trader_collection_meta()
    return TraderProfileListResponse(
        collected_at_utc=meta["collected_at_utc"],
        notes=meta["notes"],
        profiles=[TraderProfileItem(**x) for x in list_trader_profiles()],
    )


@router.get("/{slug}", response_model=TraderProfileItem)
def get_profile(slug: str):
    row = get_trader_profile(slug)
    if not row:
        raise HTTPException(status_code=404, detail="Trader profile not found")
    return TraderProfileItem(**row)


def _extract_variant(result: dict, overrides: dict) -> TraderBacktestVariantResult:
    return TraderBacktestVariantResult(
        hold_days=int(overrides.get("hold_days", 0)),
        stop_pct=float(overrides.get("stop_pct", 0)),
        target_pct=float(overrides["target_pct"]) if overrides.get("target_pct") is not None else None,
        total_return_pct=float(result.get("total_return_pct", 0)),
        sharpe_ratio=float(result.get("sharpe_ratio", 0)),
        max_drawdown_pct=float(result.get("max_drawdown_pct", 0)),
        win_rate_pct=float(result.get("win_rate_pct", 0)),
        trade_count=int(result.get("trade_count", 0)),
        annualized_return_pct=result.get("annualized_return_pct"),
        validation_passed=result.get("validation_passed"),
        backtest_engine=result.get("backtest_engine", "default"),
    )


@router.get("/{slug}/preset/{bucket}", response_model=TraderPresetResponse)
def get_preset(slug: str, bucket: Bucket):
    preset = build_trader_preset(slug, bucket.value)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    return TraderPresetResponse(
        slug=slug,
        bucket=bucket,
        scan_options=preset["scan_options"],
        backtest_overrides=preset["backtest_overrides"],
        horizon=preset.get("horizon"),
        notes=preset.get("notes", []),
    )


@router.get("/{slug}/quick-compare/{bucket}", response_model=TraderQuickCompareResponse)
def quick_compare(slug: str, bucket: Bucket):
    preset = build_trader_preset(slug, bucket.value)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    latest = cache_module.list_saved_scans(bucket=bucket.value, limit=1)
    if not latest or not latest[0].get("results"):
        raise HTTPException(status_code=404, detail="No saved scan results for this bucket")
    symbol = str(latest[0]["results"][0].get("symbol", "")).upper()
    if not symbol:
        raise HTTPException(status_code=404, detail="No symbol found in latest saved scan")

    horizon = preset.get("horizon") or ("1y" if bucket == Bucket.penny else "5y")
    ps = PriceService()
    stock_df = ps.get_history(symbol, period=horizon if horizon != "2y" else "2y")
    spy_df = ps.get_spy_history(period=horizon if horizon != "2y" else "2y")
    if stock_df.empty:
        raise HTTPException(status_code=404, detail=f"No history for {symbol}")

    baseline_overrides = {"hold_days": 0, "stop_pct": 0.0, "target_pct": None}
    trader_overrides = preset["backtest_overrides"]
    if bucket == Bucket.penny:
        base = run_penny_backtest(stock_df, spy_df, horizon=horizon)
        tuned = run_penny_backtest(
            stock_df,
            spy_df,
            horizon=horizon,
            hold_days_override=trader_overrides.get("hold_days"),
            stop_pct_override=trader_overrides.get("stop_pct"),
            target_pct_override=trader_overrides.get("target_pct"),
        )
    else:
        info, fundamentals, _ = DataReconciler().get_canonical_fundamentals(symbol)
        base = run_compounder_backtest(stock_df, spy_df, info=info, fundamentals=fundamentals, horizon=horizon)
        tuned = run_compounder_backtest(
            stock_df,
            spy_df,
            info=info,
            fundamentals=fundamentals,
            horizon=horizon,
            hold_days_override=trader_overrides.get("hold_days"),
            stop_pct_override=trader_overrides.get("stop_pct"),
            target_pct_override=trader_overrides.get("target_pct"),
        )

    bt_cfg = StrategyRegistry().get_active(bucket.value).backtest_params
    strategy_cfg = {
        "hold_days": int(bt_cfg.get("hold_days", 20)),
        "stop_pct": float(bt_cfg.get("stop_pct", 0.07)),
        "target_pct": bt_cfg.get("target_pct"),
    }
    baseline_variant = _extract_variant(base, strategy_cfg if strategy_cfg["hold_days"] else baseline_overrides)
    trader_variant = _extract_variant(tuned, trader_overrides)
    return TraderQuickCompareResponse(
        slug=slug,
        bucket=bucket,
        symbol=symbol,
        horizon=horizon,
        baseline=baseline_variant,
        trader_style=trader_variant,
        delta_total_return_pct=round(trader_variant.total_return_pct - baseline_variant.total_return_pct, 4),
        delta_sharpe_ratio=round(trader_variant.sharpe_ratio - baseline_variant.sharpe_ratio, 4),
        notes=[
            "Comparison uses latest saved scan top symbol as quick proxy.",
            "Treat as research preview; run a multi-symbol sweep before deployment.",
        ],
    )
