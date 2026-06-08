"""Stock detail API routes."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from fastapi import APIRouter, HTTPException

from config import FINNHUB_API_KEY, STOCK_ROUTE_TIMEOUT_SECONDS
from data.cache import Cache
from data.candidate_builder import build_candidate
from data.earnings import get_next_earnings_date
from data.finnhub_client import FinnhubClient
from data.price_service import PriceService
from data.reconciler import DataReconciler
from data.strategy_registry import StrategyRegistry
from ml.backtest_medium import run_medium_backtest
from models.schemas import Bucket, OHLCPoint, StockDetail
from scoring.valuation import valuation_warnings
from screeners.compounder import CompounderScreener
from screeners.medium import MediumScreener
from screeners.penny import PennyScreener
from services.llm_explainer import generate_explanation
from services.market_context import enrich_metrics

router = APIRouter(prefix="/stock", tags=["stock"])
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="stock-routes")

SCREENERS = {
    Bucket.penny: PennyScreener,
    Bucket.medium: MediumScreener,
    Bucket.compounder: CompounderScreener,
}


@router.get("/{symbol}", response_model=StockDetail)
def get_stock(symbol: str, bucket: Bucket | None = None, include_backtest: bool = False):
    symbol = symbol.upper()
    bucket = bucket or Bucket.medium
    cache_key = f"stock:{symbol}:{bucket.value}:{int(include_backtest)}"
    cached = Cache().get(cache_key)
    try:
        stock = _EXECUTOR.submit(_build_stock_detail, symbol, bucket, include_backtest).result(
            timeout=max(1.0, STOCK_ROUTE_TIMEOUT_SECONDS)
        )
        Cache().set(cache_key, stock.model_dump(), ttl_seconds=900)
        return stock
    except FuturesTimeout as exc:
        if cached:
            return StockDetail(**cached)
        raise HTTPException(status_code=504, detail=f"Stock route timed out for {symbol}") from exc
    except HTTPException:
        if cached:
            return StockDetail(**cached)
        raise


def _build_stock_detail(symbol: str, bucket: Bucket, include_backtest: bool) -> StockDetail:
    symbol = symbol.upper()

    ps = PriceService()
    hist = ps.get_history(symbol, period="1y")
    if hist.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    info, fundamentals, rec = DataReconciler().get_canonical_fundamentals(symbol)
    price = info.get("currentPrice") or float(hist["close"].iloc[-1])
    strategy = StrategyRegistry().get_active(bucket.value)

    if FINNHUB_API_KEY:
        earnings = FinnhubClient().get_earnings(symbol)
        news = FinnhubClient().news_summary(symbol)
    else:
        earnings = get_next_earnings_date(symbol)
        news = {"headlines": [], "categories": {}}

    warnings = valuation_warnings(info, fundamentals)

    ohlc = [
        OHLCPoint(
            date=r["date"].strftime("%Y-%m-%d"),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
        )
        for _, r in hist.tail(252).iterrows()
    ]

    scores: dict[str, float] = {}
    explanation = ""
    signals_list = []
    metrics: dict = {}

    if bucket in SCREENERS:
        screener = SCREENERS[bucket]()
        ctx = screener.enrich(symbol)
        if ctx:
            score, signals, _, summary, metrics = screener.score(ctx)
            metrics = enrich_metrics(symbol, ctx.info, ctx.fundamentals, metrics, bucket)
            warnings = metrics.get("valuation_warnings", warnings)
            signals_list = signals
            scores = {s.name: s.value for s in signals}
            scores["composite"] = score
            explanation = summary

    ai_result = generate_explanation(
        symbol,
        bucket.value,
        scores.get("composite", 50),
        explanation,
        metrics,
        [{"name": s.name, "value": s.value} for s in signals_list],
        news.get("headlines", []),
        warnings,
    )

    backtest = None
    if include_backtest and bucket == Bucket.medium:
        spy = ps.get_spy_history(period="3y")
        stock3y = ps.get_history(symbol, period="3y")
        if not stock3y.empty:
            backtest = run_medium_backtest(stock3y, spy, horizon="3y", multi_horizon=True)

    return StockDetail(
        symbol=symbol,
        price=float(price),
        ohlc=ohlc,
        fundamentals={**info, **fundamentals},
        scores=scores,
        explanation=explanation,
        ai_explanation=ai_result["text"],
        bucket=bucket,
        earnings_date=earnings.get("earnings_date"),
        days_until_earnings=int(earnings["days_until"])
        if earnings.get("days_until") is not None
        else None,
        earnings_soon=bool(earnings.get("earnings_soon")),
        valuation_warnings=warnings,
        news_headlines=news.get("headlines", []),
        news_categories=news.get("categories", {}),
        backtest=backtest,
        data_quality_score=rec.quality_score,
        strategy_version=strategy.version_id,
    )
