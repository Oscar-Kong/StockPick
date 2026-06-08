"""Backtest API routes — multi-horizon with OOS validation."""
from itertools import product

from fastapi import APIRouter, HTTPException, Query

from config import VBT_ENABLED
from data.price_service import PriceService
from data.reconciler import DataReconciler
from data.strategy_registry import StrategyRegistry
from ml.backtest_compounder import run_compounder_backtest
from ml.backtest_medium import run_medium_backtest
from ml.backtest_penny import run_penny_backtest
from ml.entry_strategies import list_entry_variants
from ml.sweep_validation import annotate_sweep_results
from models.schemas import (
    BacktestResult,
    BacktestSweepDiagnostics,
    BacktestSweepItem,
    BacktestSweepRequest,
    BacktestSweepResponse,
    BacktestTearSheet,
    Bucket,
    EntryVariantItem,
    EntryVariantListResponse,
    MultiHorizonBacktestResponse,
)
from services.backtest_analytics import build_tear_sheet

router = APIRouter(prefix="/backtest", tags=["backtest"])

PERIOD_MAP = {"1y": "1y", "3y": "3y", "5y": "5y", "2y": "2y"}


def _get_history(symbol: str, horizon: str):
    ps = PriceService()
    period = PERIOD_MAP.get(horizon, "3y")
    return ps.get_history(symbol.upper(), period=period)


def _normalize_engine(engine: str) -> str:
    selected = (engine or "default").lower()
    if selected not in ("default", "vectorbt"):
        raise HTTPException(status_code=400, detail="engine must be one of: default, vectorbt")
    if selected == "vectorbt" and not VBT_ENABLED:
        raise HTTPException(status_code=400, detail="vectorbt engine is disabled (set VBT_ENABLED=true)")
    return selected


def _enrich_backtest_result(result: dict) -> dict:
    if not isinstance(result, dict):
        return result
    sheet = build_tear_sheet(result)
    result["tear_sheet"] = sheet
    return result


def _as_backtest_result(result: dict) -> BacktestResult:
    result = _enrich_backtest_result(result)
    fields = {k: v for k, v in result.items() if k in BacktestResult.model_fields}
    if result.get("tear_sheet"):
        fields["tear_sheet"] = BacktestTearSheet(**result["tear_sheet"])
    return BacktestResult(**fields)


def _run_bucket_backtest(
    *,
    bucket: str,
    symbol: str,
    stock_df,
    spy_df,
    horizon: str,
    multi_horizon: bool,
    engine: str,
    hold_days_override: int | None = None,
    stop_pct_override: float | None = None,
    target_pct_override: float | None = None,
    entry_variant: str | None = None,
):
    if bucket == "medium":
        return run_medium_backtest(
            stock_df,
            spy_df,
            horizon=horizon,
            multi_horizon=multi_horizon,
            engine=engine,
            hold_days_override=hold_days_override,
            stop_pct_override=stop_pct_override,
            target_pct_override=target_pct_override,
            entry_variant=entry_variant,
        )
    if bucket == "penny":
        return run_penny_backtest(
            stock_df,
            spy_df,
            horizon=horizon,
            multi_horizon=multi_horizon,
            engine=engine,
            hold_days_override=hold_days_override,
            stop_pct_override=stop_pct_override,
            target_pct_override=target_pct_override,
            entry_variant=entry_variant,
        )

    info, fundamentals, _ = DataReconciler().get_canonical_fundamentals(symbol)
    return run_compounder_backtest(
        stock_df,
        spy_df,
        info=info,
        fundamentals=fundamentals,
        horizon=horizon,
        multi_horizon=multi_horizon,
        engine=engine,
        hold_days_override=hold_days_override,
        stop_pct_override=stop_pct_override,
        target_pct_override=target_pct_override,
        entry_variant=entry_variant,
    )


@router.get("/entry-variants/{bucket}", response_model=EntryVariantListResponse)
def list_bucket_entry_variants(bucket: str):
    if bucket not in ("penny", "medium", "compounder"):
        raise HTTPException(status_code=400, detail="Invalid bucket")
    variants = [EntryVariantItem(**v) for v in list_entry_variants(bucket)]
    return EntryVariantListResponse(bucket=Bucket(bucket), variants=variants)


def _default_sweep_values(bucket: str, request: BacktestSweepRequest):
    cfg = StrategyRegistry().get_active(bucket)
    params = cfg.backtest_params

    base_hold = int(params.get("hold_days", 20))
    base_stop = float(params.get("stop_pct", 0.07))
    base_target = params.get("target_pct")
    if base_target is not None:
        base_target = float(base_target)

    hold_days = sorted(set(request.hold_days or [max(2, int(base_hold * 0.6)), base_hold, int(base_hold * 1.4)]))
    stop_pct = sorted(
        set(
            request.stop_pct
            or [round(max(0.01, base_stop * 0.75), 4), round(base_stop, 4), round(min(0.50, base_stop * 1.25), 4)]
        )
    )
    if request.target_pct:
        target_pct = list(dict.fromkeys(request.target_pct))
    elif base_target is None:
        target_pct = [None]
    else:
        target_pct = [
            round(max(0.01, base_target * 0.75), 4),
            round(base_target, 4),
            round(min(1.0, base_target * 1.25), 4),
        ]
    target_pct = list(dict.fromkeys(target_pct))
    return hold_days, stop_pct, target_pct


@router.get("/medium/{symbol}")
def backtest_medium(
    symbol: str,
    horizon: str = Query("3y", pattern="^(1y|2y|3y|5y)$"),
    multi_horizon: bool = Query(False),
    engine: str = Query("default", pattern="^(default|vectorbt)$"),
    hold_days: int | None = Query(None, ge=1, le=400),
    stop_pct: float | None = Query(None, gt=0, lt=1),
    target_pct: float | None = Query(None, gt=0, lt=2),
    entry_variant: str | None = Query(None),
):
    symbol = symbol.upper()
    stock_df = _get_history(symbol, horizon)
    spy_df = PriceService().get_spy_history(period=horizon if horizon != "2y" else "2y")
    if stock_df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    selected_engine = _normalize_engine(engine)

    if multi_horizon:
        result = _run_bucket_backtest(
            bucket="medium",
            symbol=symbol,
            stock_df=stock_df,
            spy_df=spy_df,
            horizon=horizon,
            multi_horizon=True,
            engine=selected_engine,
            hold_days_override=hold_days,
            stop_pct_override=stop_pct,
            target_pct_override=target_pct,
            entry_variant=entry_variant,
        )
        return MultiHorizonBacktestResponse(**result)

    result = _run_bucket_backtest(
        bucket="medium",
        symbol=symbol,
        stock_df=stock_df,
        spy_df=spy_df,
        horizon=horizon,
        multi_horizon=False,
        engine=selected_engine,
        hold_days_override=hold_days,
        stop_pct_override=stop_pct,
        target_pct_override=target_pct,
        entry_variant=entry_variant,
    )
    return _as_backtest_result(result)


@router.get("/penny/{symbol}")
def backtest_penny(
    symbol: str,
    horizon: str = Query("1y", pattern="^(1y|3y)$"),
    multi_horizon: bool = Query(False),
    engine: str = Query("default", pattern="^(default|vectorbt)$"),
    hold_days: int | None = Query(None, ge=1, le=400),
    stop_pct: float | None = Query(None, gt=0, lt=1),
    target_pct: float | None = Query(None, gt=0, lt=2),
    entry_variant: str | None = Query(None),
):
    symbol = symbol.upper()
    stock_df = _get_history(symbol, horizon)
    spy_df = PriceService().get_spy_history(period=horizon)
    if stock_df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    selected_engine = _normalize_engine(engine)

    if multi_horizon:
        result = _run_bucket_backtest(
            bucket="penny",
            symbol=symbol,
            stock_df=stock_df,
            spy_df=spy_df,
            horizon=horizon,
            multi_horizon=True,
            engine=selected_engine,
            hold_days_override=hold_days,
            stop_pct_override=stop_pct,
            target_pct_override=target_pct,
            entry_variant=entry_variant,
        )
        return MultiHorizonBacktestResponse(**result)

    result = _run_bucket_backtest(
        bucket="penny",
        symbol=symbol,
        stock_df=stock_df,
        spy_df=spy_df,
        horizon=horizon,
        multi_horizon=False,
        engine=selected_engine,
        hold_days_override=hold_days,
        stop_pct_override=stop_pct,
        target_pct_override=target_pct,
        entry_variant=entry_variant,
    )
    return _as_backtest_result(result)


@router.get("/compounder/{symbol}")
def backtest_compounder(
    symbol: str,
    horizon: str = Query("5y", pattern="^(3y|5y)$"),
    multi_horizon: bool = Query(False),
    engine: str = Query("default", pattern="^(default|vectorbt)$"),
    hold_days: int | None = Query(None, ge=1, le=400),
    stop_pct: float | None = Query(None, gt=0, lt=1),
    target_pct: float | None = Query(None, gt=0, lt=2),
    entry_variant: str | None = Query(None),
):
    symbol = symbol.upper()
    stock_df = _get_history(symbol, horizon)
    spy_df = PriceService().get_spy_history(period=horizon)
    if stock_df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    selected_engine = _normalize_engine(engine)

    if multi_horizon:
        result = _run_bucket_backtest(
            bucket="compounder",
            symbol=symbol,
            stock_df=stock_df,
            spy_df=spy_df,
            horizon=horizon,
            multi_horizon=True,
            engine=selected_engine,
            hold_days_override=hold_days,
            stop_pct_override=stop_pct,
            target_pct_override=target_pct,
            entry_variant=entry_variant,
        )
        return MultiHorizonBacktestResponse(**result)

    result = _run_bucket_backtest(
        bucket="compounder",
        symbol=symbol,
        stock_df=stock_df,
        spy_df=spy_df,
        horizon=horizon,
        multi_horizon=False,
        engine=selected_engine,
        hold_days_override=hold_days,
        stop_pct_override=stop_pct,
        target_pct_override=target_pct,
        entry_variant=entry_variant,
    )
    return _as_backtest_result(result)


@router.get("/strategy-version/{bucket}")
def backtest_strategy_version(bucket: str):
    if bucket not in ("penny", "medium", "compounder"):
        raise HTTPException(status_code=400, detail="Invalid bucket")
    cfg = StrategyRegistry().get_active(bucket)
    return {"version_id": cfg.version_id, "backtest_params": cfg.backtest_params}


@router.post("/{bucket}/{symbol}/sweep", response_model=BacktestSweepResponse)
def sweep_backtest_params(
    bucket: str,
    symbol: str,
    request: BacktestSweepRequest,
    engine: str = Query("default", pattern="^(default|vectorbt)$"),
):
    if bucket not in ("penny", "medium", "compounder"):
        raise HTTPException(status_code=400, detail="Invalid bucket")

    symbol = symbol.upper()
    selected_engine = _normalize_engine(engine)

    horizon = request.horizon or ("1y" if bucket == "penny" else "5y" if bucket == "compounder" else "3y")
    allowed = {"penny": {"1y", "3y"}, "medium": {"1y", "2y", "3y", "5y"}, "compounder": {"3y", "5y"}}
    if horizon not in allowed[bucket]:
        raise HTTPException(status_code=400, detail=f"Invalid horizon for {bucket}: {horizon}")

    stock_df = _get_history(symbol, horizon)
    if stock_df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    spy_df = PriceService().get_spy_history(period=horizon if horizon != "2y" else "2y")

    hold_days, stop_pct, target_pct = _default_sweep_values(bucket, request)
    combos = list(product(hold_days, stop_pct, target_pct))[: request.max_trials]

    entry_variant = request.entry_variant
    entries: list[dict] = []
    strategy_cfg = StrategyRegistry().get_active(bucket)

    for hold, stop, target in combos:
        result = _run_bucket_backtest(
            bucket=bucket,
            symbol=symbol,
            stock_df=stock_df,
            spy_df=spy_df,
            horizon=horizon,
            multi_horizon=False,
            engine=selected_engine,
            hold_days_override=hold,
            stop_pct_override=stop,
            target_pct_override=target,
            entry_variant=entry_variant,
        )
        entries.append(
            {
                "hold_days": int(hold),
                "stop_pct": float(stop),
                "target_pct": float(target) if target is not None else None,
                "total_return_pct": float(result.get("total_return_pct", 0)),
                "annualized_return_pct": result.get("annualized_return_pct"),
                "sharpe_ratio": float(result.get("sharpe_ratio", 0)),
                "max_drawdown_pct": float(result.get("max_drawdown_pct", 0)),
                "win_rate_pct": float(result.get("win_rate_pct", 0)),
                "trade_count": int(result.get("trade_count", 0)),
                "validation_passed": result.get("validation_passed"),
                "validation_notes": result.get("validation_notes", []),
                "backtest_engine": result.get("backtest_engine", selected_engine),
            }
        )

    annotated = annotate_sweep_results(entries, n_trials=len(combos))
    sweep_entries = [BacktestSweepItem(**e) for e in annotated["entries"]]
    sweep_entries.sort(
        key=lambda item: (
            item.deflated_sharpe or 0,
            1 if item.validation_passed else 0,
            item.total_return_pct,
            item.sharpe_ratio,
        ),
        reverse=True,
    )
    top_results = sweep_entries[: request.top_k]
    best_item = top_results[0] if top_results else None
    diag = annotated.get("diagnostics") or {}

    return BacktestSweepResponse(
        symbol=symbol,
        bucket=Bucket(bucket),
        horizon=horizon,
        engine=selected_engine,
        entry_variant=entry_variant,
        strategy_version=strategy_cfg.version_id,
        trials=len(combos),
        best=best_item,
        results=top_results,
        sweep_diagnostics=BacktestSweepDiagnostics(**diag) if diag else None,
        message="Parameter sweep complete — prefer high deflated Sharpe and OOS pass.",
    )
