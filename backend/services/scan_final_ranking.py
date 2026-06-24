"""Final scan ranking — diversification, persistence, exclusion diagnostics."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from config import (
    SCAN_CORRELATION_CLUSTER_THRESHOLD,
    SCAN_MAX_PER_CORRELATION_CLUSTER,
    SCAN_MAX_PER_SECTOR,
    SCAN_MIN_RESULTS_AFTER_DIVERSIFICATION,
    SCAN_PENNY_LOW_CONFIDENCE_MAX,
    SCAN_PENNY_LOW_CONFIDENCE_THRESHOLD,
    SCAN_PERSISTENCE_DELTA,
)
from models.schemas import Bucket, StockResult
from services.scan_decomposition import passes_persistence_safety
from services.scan_issuer import issuer_key

logger = logging.getLogger(__name__)

EXCLUDED_BY_SECTOR_LIMIT = "excluded_by_sector_limit"
EXCLUDED_BY_CORRELATION_LIMIT = "excluded_by_correlation_limit"
EXCLUDED_BY_SHARE_CLASS = "excluded_by_share_class"
EXCLUDED_BY_LOW_CONFIDENCE_PENNY_CAP = "excluded_by_low_confidence_penny_cap"
REPLACED_BY_HIGHER_CONFIDENCE = "replaced_by_higher_confidence_candidate"
RETAINED_BY_PERSISTENCE = "retained_by_persistence_rule"


@dataclass
class RankedCandidate:
    result: StockResult
    ranking_score: float
    alpha_score: float
    confidence_score: float
    tradability_score: float
    sector: str
    issuer: str
    cluster_id: str

    @property
    def symbol(self) -> str:
        return self.result.symbol.upper()


@dataclass
class RankingExclusion:
    symbol: str
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"symbol": self.symbol, "reason": self.reason, "detail": self.detail}


@dataclass
class FinalRankingResult:
    results: list[StockResult]
    exclusions: list[RankingExclusion] = field(default_factory=list)
    persistence_applied: list[str] = field(default_factory=list)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "exclusions": [e.to_dict() for e in self.exclusions],
            "persistence_retained": list(self.persistence_applied),
            "exclusion_counts": _count_by_reason(self.exclusions),
        }


def _count_by_reason(exclusions: list[RankingExclusion]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ex in exclusions:
        counts[ex.reason] = counts.get(ex.reason, 0) + 1
    return counts


def _sector_label(result: StockResult) -> str:
    m = result.metrics or {}
    sector = m.get("sector") or m.get("theme_module") or "Unknown"
    return str(sector).strip().title() or "Unknown"


def _scores_from_result(result: StockResult) -> tuple[float, float, float, float]:
    m = result.metrics or {}
    ranking = float(m.get("ranking_score") or result.score)
    alpha = float(m.get("alpha_score") or ranking)
    confidence = float(m.get("confidence_score") or m.get("data_quality_score") or 50.0)
    tradability = float(m.get("tradability_score") or 50.0)
    return ranking, alpha, confidence, tradability


def _return_series(symbol: str, bulk_hist: dict[str, pd.DataFrame] | None) -> pd.Series | None:
    if not bulk_hist:
        return None
    df = bulk_hist.get(symbol.upper())
    if df is None or df.empty or "close" not in df.columns:
        return None
    ret = df["close"].astype(float).pct_change().dropna()
    return ret if len(ret) >= 15 else None


def assign_correlation_clusters(
    candidates: list[RankedCandidate],
    bulk_hist: dict[str, pd.DataFrame] | None,
    *,
    threshold: float = SCAN_CORRELATION_CLUSTER_THRESHOLD,
) -> dict[str, str]:
    """Greedy cluster ids from pairwise return correlation."""
    symbols = [c.symbol for c in candidates]
    series: dict[str, pd.Series] = {}
    for sym in symbols:
        s = _return_series(sym, bulk_hist)
        if s is not None:
            series[sym] = s

    cluster_of: dict[str, str] = {sym: sym for sym in symbols}
    if len(series) < 2:
        return cluster_of

    syms = list(series.keys())
    for i, a in enumerate(syms):
        for b in syms[i + 1 :]:
            joined = pd.concat([series[a], series[b]], axis=1).dropna()
            if len(joined) < 15:
                continue
            corr = float(joined.corr().iloc[0, 1])
            if np.isnan(corr) or corr < threshold:
                continue
            ca, cb = cluster_of[a], cluster_of[b]
            merged = min(ca, cb)
            for sym, cid in list(cluster_of.items()):
                if cid in (ca, cb):
                    cluster_of[sym] = merged
    return cluster_of


def to_ranked_candidates(
    results: list[StockResult],
    bulk_hist: dict[str, pd.DataFrame] | None,
) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for r in results:
        ranking, alpha, confidence, tradability = _scores_from_result(r)
        m = r.metrics or {}
        ranked.append(
            RankedCandidate(
                result=r,
                ranking_score=ranking,
                alpha_score=alpha,
                confidence_score=confidence,
                tradability_score=tradability,
                sector=_sector_label(r),
                issuer=str(m.get("_issuer_key") or issuer_key(r.symbol, {"sector": m.get("sector")})),
                cluster_id=r.symbol,
            )
        )
    clusters = assign_correlation_clusters(ranked, bulk_hist)
    for c in ranked:
        c.cluster_id = clusters.get(c.symbol, c.symbol)
    ranked.sort(key=lambda c: (-c.ranking_score, c.symbol))
    return ranked


def _can_add_candidate(
    candidate: RankedCandidate,
    selected: list[RankedCandidate],
    *,
    bucket: Bucket,
    sector_counts: dict[str, int],
    cluster_counts: dict[str, int],
    issuer_seen: set[str],
    low_conf_penny_count: int,
) -> tuple[bool, str, str]:
    if candidate.issuer in issuer_seen:
        return False, EXCLUDED_BY_SHARE_CLASS, f"issuer={candidate.issuer}"

    if sector_counts.get(candidate.sector, 0) >= SCAN_MAX_PER_SECTOR:
        return False, EXCLUDED_BY_SECTOR_LIMIT, f"sector={candidate.sector}"

    if cluster_counts.get(candidate.cluster_id, 0) >= SCAN_MAX_PER_CORRELATION_CLUSTER:
        return False, EXCLUDED_BY_CORRELATION_LIMIT, f"cluster={candidate.cluster_id}"

    if (
        bucket == Bucket.penny
        and candidate.confidence_score < SCAN_PENNY_LOW_CONFIDENCE_THRESHOLD
        and low_conf_penny_count >= SCAN_PENNY_LOW_CONFIDENCE_MAX
    ):
        return False, EXCLUDED_BY_LOW_CONFIDENCE_PENNY_CAP, f"confidence={candidate.confidence_score:.0f}"

    return True, "", ""


def _select_diversified(
    ranked: list[RankedCandidate],
    *,
    bucket: Bucket,
    max_results: int,
) -> tuple[list[RankedCandidate], list[RankingExclusion]]:
    selected: list[RankedCandidate] = []
    exclusions: list[RankingExclusion] = []
    sector_counts: dict[str, int] = {}
    cluster_counts: dict[str, int] = {}
    issuer_seen: set[str] = set()
    low_conf_penny = 0

    for candidate in ranked:
        if len(selected) >= max_results:
            exclusions.append(
                RankingExclusion(candidate.symbol, "excluded_by_rank_cutoff", "beyond max_results")
            )
            continue
        ok, reason, detail = _can_add_candidate(
            candidate,
            selected,
            bucket=bucket,
            sector_counts=sector_counts,
            cluster_counts=cluster_counts,
            issuer_seen=issuer_seen,
            low_conf_penny_count=low_conf_penny,
        )
        if not ok:
            exclusions.append(RankingExclusion(candidate.symbol, reason, detail))
            continue
        selected.append(candidate)
        issuer_seen.add(candidate.issuer)
        sector_counts[candidate.sector] = sector_counts.get(candidate.sector, 0) + 1
        cluster_counts[candidate.cluster_id] = cluster_counts.get(candidate.cluster_id, 0) + 1
        if bucket == Bucket.penny and candidate.confidence_score < SCAN_PENNY_LOW_CONFIDENCE_THRESHOLD:
            low_conf_penny += 1

    if len(selected) < min(max_results, len(ranked), SCAN_MIN_RESULTS_AFTER_DIVERSIFICATION):
        for candidate in ranked:
            if candidate in selected:
                continue
            if len(selected) >= max(max_results, SCAN_MIN_RESULTS_AFTER_DIVERSIFICATION):
                break
            if candidate.symbol in {s.symbol for s in selected}:
                continue
            ok, reason, _detail = _can_add_candidate(
                candidate,
                selected,
                bucket=bucket,
                sector_counts=sector_counts,
                cluster_counts=cluster_counts,
                issuer_seen=issuer_seen,
                low_conf_penny_count=low_conf_penny,
            )
            if not ok and reason in (
                EXCLUDED_BY_SHARE_CLASS,
                EXCLUDED_BY_LOW_CONFIDENCE_PENNY_CAP,
                EXCLUDED_BY_CORRELATION_LIMIT,
            ):
                continue
            if not ok and reason != EXCLUDED_BY_SECTOR_LIMIT:
                continue
            selected.append(candidate)
            issuer_seen.add(candidate.issuer)
            sector_counts[candidate.sector] = sector_counts.get(candidate.sector, 0) + 1
            cluster_counts[candidate.cluster_id] = cluster_counts.get(candidate.cluster_id, 0) + 1
            if bucket == Bucket.penny and candidate.confidence_score < SCAN_PENNY_LOW_CONFIDENCE_THRESHOLD:
                low_conf_penny += 1
            logger.info(
                "Relaxing diversification to preserve minimum results — added %s",
                candidate.symbol,
            )

    selected.sort(key=lambda c: (-c.ranking_score, c.symbol))
    return selected, exclusions


def _previous_incumbents(previous_results: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in previous_results:
        sym = str(row.get("symbol") or "").upper()
        if sym and sym not in out:
            out.append(sym)
    return out


def apply_persistence(
    selected: list[RankedCandidate],
    ranked: list[RankedCandidate],
    *,
    bucket: Bucket,
    max_results: int,
    previous_results: list[dict[str, Any]] | None,
    delta: float = SCAN_PERSISTENCE_DELTA,
) -> tuple[list[RankedCandidate], list[RankingExclusion], list[str]]:
    if not previous_results:
        return selected, [], []

    by_symbol = {c.symbol: c for c in ranked}
    selected_syms = {c.symbol for c in selected}
    exclusions: list[RankingExclusion] = []
    retained: list[str] = []

    for sym in _previous_incumbents(previous_results):
        incumbent = by_symbol.get(sym)
        if incumbent is None or sym in selected_syms:
            continue
        if not passes_persistence_safety(
            bucket=bucket,
            confidence_score=incumbent.confidence_score,
            tradability_score=incumbent.tradability_score,
            metrics=incumbent.result.metrics or {},
        ):
            continue

        weakest_idx = min(range(len(selected)), key=lambda i: selected[i].ranking_score)
        weakest = selected[weakest_idx]
        if incumbent.ranking_score <= weakest.ranking_score:
            continue
        if incumbent.ranking_score < weakest.ranking_score + delta:
            continue

        selected[weakest_idx] = incumbent
        selected_syms.discard(weakest.symbol)
        selected_syms.add(sym)
        retained.append(sym)
        exclusions.append(
            RankingExclusion(
                weakest.symbol,
                REPLACED_BY_HIGHER_CONFIDENCE,
                f"replaced by persisted {sym} (incumbent {incumbent.ranking_score:.1f} vs {weakest.ranking_score:.1f})",
            )
        )
        m = dict(incumbent.result.metrics or {})
        m["ranking_note"] = RETAINED_BY_PERSISTENCE
        incumbent.result.metrics = m

    selected.sort(key=lambda c: (-c.ranking_score, c.symbol))
    return selected[:max_results], exclusions, retained


def apply_final_scan_ranking(
    results: list[StockResult],
    *,
    bucket: Bucket,
    max_results: int,
    bulk_hist: dict[str, pd.DataFrame] | None = None,
    previous_results: list[dict[str, Any]] | None = None,
) -> FinalRankingResult:
    """Rank, diversify, and apply persistence hysteresis."""
    if not results:
        return FinalRankingResult(results=[])

    ranked = to_ranked_candidates(results, bulk_hist)
    selected, div_exclusions = _select_diversified(ranked, bucket=bucket, max_results=max_results)
    selected, persist_exclusions, retained = apply_persistence(
        selected,
        ranked,
        bucket=bucket,
        max_results=max_results,
        previous_results=previous_results,
    )

    final_results: list[StockResult] = []
    for idx, cand in enumerate(selected[:max_results]):
        r = cand.result
        r.score = round(cand.ranking_score, 1)
        m = dict(r.metrics or {})
        m["ranking_score"] = round(cand.ranking_score, 1)
        m["alpha_score"] = round(cand.alpha_score, 1)
        m["confidence_score"] = round(cand.confidence_score, 1)
        m["tradability_score"] = round(cand.tradability_score, 1)
        m["final_rank"] = idx + 1
        r.metrics = m
        final_results.append(r)

    return FinalRankingResult(
        results=final_results,
        exclusions=div_exclusions + persist_exclusions,
        persistence_applied=retained,
    )
