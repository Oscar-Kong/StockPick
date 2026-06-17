"""AI explanation API routes."""
from fastapi import APIRouter, HTTPException

from models.schemas import Bucket, ExplainRequest, ExplainResponse
from screeners.compounder import CompounderScreener
from screeners.penny import PennyScreener
from screeners.penny import PennyScreener
from services.llm_explainer import generate_explanation
from services.market_context import enrich_metrics

router = APIRouter(prefix="/explain", tags=["explain"])

SCREENERS = {
    Bucket.penny: PennyScreener,
    Bucket.medium: PennyScreener,
    Bucket.compounder: CompounderScreener,
}


@router.post("", response_model=ExplainResponse)
def explain_stock(body: ExplainRequest):
    symbol = body.symbol.upper()
    bucket = body.bucket or Bucket.penny
    screener = SCREENERS.get(bucket, PennyScreener)()

    ctx = screener.enrich(symbol)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    from models.schemas import ScanOptions

    score, signals, _, summary, metrics = screener.score(ctx)
    metrics = enrich_metrics(symbol, ctx.info, ctx.fundamentals, metrics, bucket)

    signal_dicts = [
        {"name": s.name, "value": s.value, "contribution": s.contribution} for s in signals
    ]
    result = generate_explanation(
        symbol=symbol,
        bucket=bucket.value,
        score=score,
        summary=summary,
        metrics=metrics,
        signals=signal_dicts,
        news_headlines=metrics.get("news_headlines", []),
        valuation_warnings=metrics.get("valuation_warnings", []),
    )
    return ExplainResponse(
        symbol=symbol,
        explanation=result["text"],
        source=result.get("source", "rules"),
        sections=result.get("sections", {}),
        reasoning=result.get("reasoning", {}),
    )
