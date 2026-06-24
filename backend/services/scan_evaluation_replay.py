"""Historical scan replay for offline evaluation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import pandas as pd

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from data.candidate_builder import build_candidate
from data.history_normalize import normalize_ohlc_history
from models.schemas import Bucket, StockResult
from services.scan_decomposition import build_decomposed_scores
from services.scan_evaluation_metrics import stage_a_recall_metrics
from services.scan_evaluation_pit import (
    assert_no_lookahead,
    build_forward_outcomes,
    truncate_history,
    truncate_price_panel,
)
from services.scan_final_ranking import apply_final_scan_ranking
from services.scan_manager import ScanManager
from services.stage_a_ranking import StageACandidate, rank_stage_a_candidates, select_stage_b_symbols
from services.walk_forward_research_service import universe_for_date

logger = logging.getLogger(__name__)

AlgorithmVersion = Literal[
    "alphabetical_baseline",
    "stage_a_v1",
    "stage_a_v2",
    "scoring_engine_v1",
]

SUPPORTED_ALGORITHM_VERSIONS: tuple[str, ...] = (
    "alphabetical_baseline",
    "stage_a_v1",
    "stage_a_v2",
    "scoring_engine_v1",
)


@dataclass
class ReplayConfig:
    bucket: str
    scan_date: str
    algorithm_version: str = "stage_a_v2"
    stage_b_cap: int = 50
    max_results: int = 25
    forward_horizons: list[int] = field(default_factory=lambda: [1, 5, 20, 60])
    max_universe: int = 80
    apply_penny_friction: bool = True
    spread_bps: float = 50.0
    slippage_bps: float = 25.0
    scoring_version: str = FACTOR_MODEL_VERSION
    strategy_version: str = STRATEGY_VERSION
    stage_a_recall_caps: list[int] = field(default_factory=lambda: [10, 20, 50])


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _resolve_bucket(value: str) -> Bucket:
    return Bucket(value.lower())


def _resolve_scoring_mode(algorithm_version: str) -> str:
    if algorithm_version == "scoring_engine_v1":
        return "engine"
    return "legacy"


def _alphabetical_baseline(
    symbols: list[str],
    *,
    max_results: int,
) -> list[dict[str, Any]]:
    ordered = sorted(symbols)
    rows: list[dict[str, Any]] = []
    for idx, sym in enumerate(ordered[:max_results]):
        score = max(0.0, 100.0 - idx)
        rows.append(
            {
                "symbol": sym,
                "ranking_score": score,
                "alpha_score": score,
                "confidence_score": 50.0,
                "tradability_score": 50.0,
                "score": score,
                "sector": "Unknown",
            }
        )
    return rows


def _stage_a_only_rows(stage_a: list[StageACandidate], *, max_results: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for c in stage_a[:max_results]:
        score = round(float(c.pre_score), 1)
        rows.append(
            {
                "symbol": c.symbol,
                "ranking_score": score,
                "alpha_score": score,
                "confidence_score": float(c.data_quality or 50.0),
                "tradability_score": 50.0,
                "score": score,
                "sector": "Unknown",
                "stage_a_pre_score": score,
                "stage_a_rank": c.rank,
            }
        )
    return rows


def _score_stage_b_candidate_eval(
    *,
    symbol: str,
    bucket: Bucket,
    hist: pd.DataFrame,
    algorithm_version: str,
    screener: Any,
    strategy_version: str,
) -> dict[str, Any] | None:
    """Score one Stage B symbol with PIT history (no provider reconcile)."""
    ctx = build_candidate(
        symbol,
        history=hist,
        history_source="evaluation_replay",
        reconcile=False,
        include_spy=False,
    )
    if ctx is None:
        return None

    from services.scan_scoring import score_stage_b_candidate

    scoring_mode = _resolve_scoring_mode(algorithm_version)
    outcome = score_stage_b_candidate(
        ctx=ctx,
        screener=screener,
        bucket=bucket,
        symbol=symbol,
        quality_score=ctx.info.get("_reconcile_quality"),
        strategy_version=strategy_version,
        quality_filter={},
        scan_id=f"eval-{symbol}",
        scoring_mode=scoring_mode,
    )
    decomposed = build_decomposed_scores(
        raw_score=outcome.raw_score,
        signals=outcome.signals,
        metrics=outcome.metrics,
        bucket=bucket,
        price=float(ctx.price),
        history=ctx.history,
        quality_score=ctx.info.get("_reconcile_quality"),
        hist_len=len(ctx.history) if ctx.history is not None else 0,
    )
    sector = str(outcome.metrics.get("sector") or ctx.info.get("sector") or "Unknown")
    return {
        "symbol": symbol.upper(),
        "ranking_score": decomposed.ranking_score,
        "alpha_score": decomposed.alpha_score,
        "confidence_score": decomposed.confidence_score,
        "tradability_score": decomposed.tradability_score,
        "score": decomposed.ranking_score,
        "sector": sector,
        "metrics": {**outcome.metrics, **decomposed.to_metrics_dict()},
        "signals_count": len(outcome.signals),
    }


def _rows_to_stock_results(rows: list[dict[str, Any]], bucket: Bucket) -> list[StockResult]:
    from models.schemas import RiskLevel

    results: list[StockResult] = []
    for row in rows:
        sym = row["symbol"]
        score = float(row["ranking_score"])
        metrics = dict(row.get("metrics") or {})
        metrics.setdefault("ranking_score", score)
        metrics.setdefault("alpha_score", row.get("alpha_score"))
        metrics.setdefault("confidence_score", row.get("confidence_score"))
        metrics.setdefault("tradability_score", row.get("tradability_score"))
        metrics.setdefault("sector", row.get("sector"))
        results.append(
            StockResult(
                symbol=sym,
                price=1.0,
                score=score,
                alpha_score=row.get("alpha_score"),
                confidence_score=row.get("confidence_score"),
                tradability_score=row.get("tradability_score"),
                ranking_score=score,
                signals=[],
                risk_level=RiskLevel.medium,
                summary="evaluation replay",
                bucket=bucket,
                metrics=metrics,
            )
        )
    return results


def replay_scan_date(
    *,
    price_panel: dict[str, pd.DataFrame],
    config: ReplayConfig,
    screener: Any | None = None,
) -> dict[str, Any]:
    """
    Replay scan selection as-of scan_date using only PIT data.

    price_panel must contain full OHLC through forward horizons (for labels only).
    Features/scores use truncate_history(panel, scan_date).
    """
    if config.algorithm_version not in SUPPORTED_ALGORITHM_VERSIONS:
        raise ValueError(f"Unsupported algorithm_version: {config.algorithm_version}")

    as_of = _parse_date(config.scan_date)
    bucket = _resolve_bucket(config.bucket)
    caveats: list[str] = [
        "Evaluation harness — does not update production scan rankings.",
        "Fundamentals use price-derived info only (reconcile=False) unless PIT rows exist.",
    ]

    universe, universe_source = universe_for_date(bucket.value, as_of, max_symbols=config.max_universe)
    if universe_source == "fallback":
        caveats.append(
            "Universe PIT table empty — using current constituent list; survivorship bias likely."
        )

    pit_panel = truncate_price_panel(
        {sym: price_panel[sym] for sym in universe if sym in price_panel},
        as_of,
    )
    for sym, hist in pit_panel.items():
        assert_no_lookahead(hist, as_of)

    stage_a_result = rank_stage_a_candidates(
        bucket,
        pit_panel,
        universe=list(pit_panel.keys()),
        apply_eligibility=True,
    )
    stage_a_symbols = [c.symbol for c in stage_a_result.ranked]
    stage_b_symbols = select_stage_b_symbols(stage_a_result.ranked, config.stage_b_cap)

    if config.algorithm_version == "alphabetical_baseline":
        scored_rows = _alphabetical_baseline(list(pit_panel.keys()), max_results=config.max_results)
    elif config.algorithm_version == "stage_a_v1":
        scored_rows = _stage_a_only_rows(stage_a_result.ranked, max_results=config.max_results)
    else:
        if screener is None:
            screener = ScanManager()._get_screener(bucket)
        scored_rows = []
        for sym in stage_b_symbols:
            hist = pit_panel.get(sym)
            if hist is None or hist.empty:
                continue
            row = _score_stage_b_candidate_eval(
                symbol=sym,
                bucket=bucket,
                hist=hist,
                algorithm_version=config.algorithm_version,
                screener=screener,
                strategy_version=config.strategy_version,
            )
            if row:
                scored_rows.append(row)

        if scored_rows:
            bulk_for_corr = {r["symbol"]: pit_panel[r["symbol"]] for r in scored_rows if r["symbol"] in pit_panel}
            final = apply_final_scan_ranking(
                _rows_to_stock_results(scored_rows, bucket),
                bucket=bucket,
                max_results=config.max_results,
                bulk_hist=bulk_for_corr,
                previous_results=None,
            )
            scored_rows = []
            for r in final.results:
                m = r.metrics or {}
                scored_rows.append(
                    {
                        "symbol": r.symbol,
                        "ranking_score": float(m.get("ranking_score") or r.score),
                        "alpha_score": r.alpha_score,
                        "confidence_score": r.confidence_score,
                        "tradability_score": r.tradability_score,
                        "score": r.score,
                        "sector": m.get("sector") or "Unknown",
                        "metrics": m,
                        "final_rank": m.get("final_rank"),
                    }
                )

    # Forward outcomes use full panel (future bars allowed for labels only)
    forward_map: dict[str, float] = {}
    candidate_records: list[dict[str, Any]] = []
    for row in scored_rows:
        sym = row["symbol"]
        hist_full = price_panel.get(sym)
        if hist_full is None:
            continue
        normalized = normalize_ohlc_history(hist_full)
        if normalized is not None and not normalized.empty:
            hist_full = normalized
        outcomes = build_forward_outcomes(
            sym,
            hist_full,
            as_of,
            config.forward_horizons,
            bucket=bucket.value,
            metrics=row.get("metrics"),
            apply_friction=config.apply_penny_friction and bucket == Bucket.penny,
            spread_bps=config.spread_bps,
            slippage_bps=config.slippage_bps,
        )
        row = {**row, "forward_outcomes": outcomes["horizons"], "scan_date": config.scan_date}
        h20 = outcomes["horizons"].get("20", {})
        if h20.get("forward_return_pct") is not None:
            forward_map[sym] = float(h20["forward_return_pct"])
        if outcomes["horizons"].get(str(config.forward_horizons[0]), {}).get("delisted_or_incomplete"):
            caveats.append(f"{sym}: incomplete forward window (delist/gap/missing sessions)")
        candidate_records.append(row)

    if bucket == Bucket.penny:
        caveats.extend(
            [
                "Penny returns include configurable spread/slippage/liquidity haircuts when apply_penny_friction=true.",
                "Split-adjustment quality depends on provider/DB; verify anomalies manually.",
            ]
        )

    stage_a_recall = stage_a_recall_metrics(
        stage_a_ranked=stage_a_symbols,
        forward_by_symbol=forward_map,
        stage_b_caps=config.stage_a_recall_caps,
    )

    return {
        "scan_date": config.scan_date,
        "bucket": bucket.value,
        "algorithm_version": config.algorithm_version,
        "scoring_version": config.scoring_version,
        "strategy_version": config.strategy_version,
        "universe_source": universe_source,
        "universe_size": len(pit_panel),
        "stage_a_eligible": len(stage_a_result.ranked),
        "stage_a_excluded": len(stage_a_result.excluded),
        "stage_b_cap": config.stage_b_cap,
        "stage_b_symbols": stage_b_symbols,
        "final_count": len(candidate_records),
        "candidates": candidate_records,
        "stage_a_recall": stage_a_recall,
        "stage_a_diagnostics": stage_a_result.to_diagnostics(advanced_count=len(stage_b_symbols)),
        "caveats": list(dict.fromkeys(caveats)),
    }
