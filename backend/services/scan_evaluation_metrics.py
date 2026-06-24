"""Ranking quality and Stage A recall metrics for scan evaluation."""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from services.walk_forward_research_service import _rank_correlation, cross_section_metrics, turnover_rate

AlgorithmVersion = str


def recall_at_k(retained: set[str], oracle_ordered: list[str], k: int) -> float | None:
    """Fraction of oracle top-K captured in retained set."""
    if not oracle_ordered:
        return None
    oracle_k = set(oracle_ordered[:k])
    if not oracle_k:
        return None
    hit = len(retained & oracle_k)
    return round(hit / len(oracle_k), 4)


def oracle_top_symbols(
    forward_by_symbol: dict[str, float],
    *,
    k: int,
    min_return: float | None = None,
) -> list[str]:
    """Symbols with highest forward return (ties broken by symbol)."""
    pairs = [(sym, ret) for sym, ret in forward_by_symbol.items() if ret is not None]
    if min_return is not None:
        pairs = [(s, r) for s, r in pairs if r >= min_return]
    pairs.sort(key=lambda x: (-x[1], x[0]))
    return [sym for sym, _ in pairs[:k]]


def stage_a_recall_metrics(
    *,
    stage_a_ranked: list[str],
    forward_by_symbol: dict[str, float],
    stage_b_caps: list[int],
    recall_k_values: list[int] | None = None,
    oracle_percentile: float = 0.90,
) -> dict[str, Any]:
    """
    Measure Stage A retention vs eventual high-forward-return names.

    Oracle set = top (1-oracle_percentile) fraction by forward return among
    symbols with valid labels in the evaluated universe.
    """
    recall_k_values = recall_k_values or [10, 20, 50]
    valid = {s: r for s, r in forward_by_symbol.items() if r is not None}
    if not valid:
        return {"sufficient": False, "reason": "no_forward_labels"}

    rets = np.array(list(valid.values()), dtype=float)
    threshold = float(np.quantile(rets, oracle_percentile)) if len(rets) >= 5 else max(rets)
    oracle_set = {s for s, r in valid.items() if r >= threshold}
    oracle_sorted = oracle_top_symbols(valid, k=max(recall_k_values))

    out: dict[str, Any] = {
        "sufficient": True,
        "oracle_count": len(oracle_set),
        "oracle_return_threshold_pct": round(threshold, 4),
        "recall_at_k": {},
        "cap_sweep": {},
        "high_return_excluded_by_stage_a": [],
    }

    stage_a_set = set(stage_a_ranked)
    excluded_oracle = [s for s in oracle_sorted if s not in stage_a_set]
    out["high_return_excluded_by_stage_a"] = excluded_oracle[:20]

    for k in recall_k_values:
        oracle_k_list = oracle_top_symbols(valid, k=k)
        retained_k = set(stage_a_ranked[:k])
        out["recall_at_k"][str(k)] = recall_at_k(retained_k, oracle_k_list, k)

    for cap in stage_b_caps:
        retained = set(stage_a_ranked[:cap])
        out["cap_sweep"][str(cap)] = {
            "stage_b_retained": len(retained),
            "oracle_in_cap": len(retained & oracle_set),
            "oracle_capture_rate": round(len(retained & oracle_set) / max(len(oracle_set), 1), 4),
            "recall_at_10": recall_at_k(retained, oracle_top_symbols(valid, k=10), 10),
            "recall_at_20": recall_at_k(retained, oracle_top_symbols(valid, k=20), 20),
        }

    return out


def score_decile_breakdown(
    scores: list[float],
    forward_returns: list[float],
    *,
    n_deciles: int = 10,
) -> dict[str, Any]:
    """Average/median forward return, hit rate, downside by score decile."""
    if len(scores) < n_deciles or len(scores) != len(forward_returns):
        return {"sufficient": False, "reason": "insufficient_sample", "sample_n": len(scores)}

    df = pd.DataFrame({"score": scores, "fwd": forward_returns})
    try:
        df["decile"] = pd.qcut(df["score"], n_deciles, labels=False, duplicates="drop")
    except ValueError:
        return {"sufficient": False, "reason": "decile_bin_failed", "sample_n": len(scores)}

    rows: list[dict[str, Any]] = []
    for decile, grp in df.groupby("decile"):
        fwd = grp["fwd"].astype(float)
        rows.append(
            {
                "decile": int(decile) + 1,
                "count": int(len(grp)),
                "avg_score": round(float(grp["score"].mean()), 2),
                "avg_forward_return_pct": round(float(fwd.mean()), 4),
                "median_forward_return_pct": round(float(fwd.median()), 4),
                "hit_rate": round(float((fwd > 0).mean()), 4),
                "downside_return_pct": round(
                    float(fwd[fwd < 0].mean()) if (fwd < 0).any() else 0.0,
                    4,
                ),
                "avg_mae_pct": None,
                "avg_mfe_pct": None,
            }
        )
    rows.sort(key=lambda r: r["decile"])
    top = rows[-1] if rows else None
    bottom = rows[0] if rows else None
    spread = None
    if top and bottom:
        spread = round(top["avg_forward_return_pct"] - bottom["avg_forward_return_pct"], 4)

    return {
        "sufficient": True,
        "sample_n": len(scores),
        "deciles": rows,
        "top_minus_bottom_spread_pct": spread,
    }


def enrich_deciles_with_excursions(
    decile_breakdown: dict[str, Any],
    candidate_rows: list[dict[str, Any]],
    *,
    horizon: int,
) -> dict[str, Any]:
    """Attach MAE/MFE averages per decile when candidate rows include them."""
    if not decile_breakdown.get("sufficient"):
        return decile_breakdown

    hkey = str(horizon)
    df = pd.DataFrame(
        [
            {
                "score": r.get("ranking_score") or r.get("score"),
                "mae": (r.get("forward_outcomes") or {}).get(hkey, {}).get("mae_pct"),
                "mfe": (r.get("forward_outcomes") or {}).get(hkey, {}).get("mfe_pct"),
            }
            for r in candidate_rows
            if r.get("ranking_score") is not None or r.get("score") is not None
        ]
    )
    if df.empty or df["score"].isna().all():
        return decile_breakdown

    try:
        df["decile"] = pd.qcut(df["score"].astype(float), len(decile_breakdown["deciles"]), labels=False, duplicates="drop")
    except ValueError:
        return decile_breakdown

    mae_by = df.groupby("decile")["mae"].mean()
    mfe_by = df.groupby("decile")["mfe"].mean()
    for row in decile_breakdown["deciles"]:
        d = row["decile"] - 1
        if d in mae_by.index and not np.isnan(mae_by[d]):
            row["avg_mae_pct"] = round(float(mae_by[d]), 4)
        if d in mfe_by.index and not np.isnan(mfe_by[d]):
            row["avg_mfe_pct"] = round(float(mfe_by[d]), 4)
    return decile_breakdown


def aggregate_ranking_quality(
    candidate_rows: list[dict[str, Any]],
    *,
    horizon: int,
    prev_top_symbols: set[str] | None = None,
) -> dict[str, Any]:
    """Cross-sectional ranking quality for one rebalance date and horizon."""
    hkey = str(horizon)
    scores: list[float] = []
    fwd: list[float] = []
    sectors: list[str] = []

    for row in candidate_rows:
        sc = row.get("ranking_score") if row.get("ranking_score") is not None else row.get("score")
        fo = (row.get("forward_outcomes") or {}).get(hkey, {})
        ret = fo.get("forward_return_pct")
        if sc is None or ret is None:
            continue
        scores.append(float(sc))
        fwd.append(float(ret))
        sectors.append(str(row.get("sector") or "Unknown"))

    cs = cross_section_metrics(scores, fwd)
    deciles = score_decile_breakdown(scores, fwd, n_deciles=min(10, max(len(scores) // 2, 2)))

    curr_top = {r["symbol"] for r in sorted(candidate_rows, key=lambda x: -(x.get("ranking_score") or x.get("score") or 0))[: max(1, len(candidate_rows) // 5)]}
    stability = None
    if prev_top_symbols is not None:
        stability = {
            "turnover": turnover_rate(prev_top_symbols, curr_top),
            "overlap_count": len(prev_top_symbols & curr_top),
        }

    sector_counts = Counter(sectors)
    top_sector = sector_counts.most_common(1)[0] if sector_counts else ("Unknown", 0)

    mae_vals = [
        (row.get("forward_outcomes") or {}).get(hkey, {}).get("mae_pct")
        for row in candidate_rows
        if (row.get("forward_outcomes") or {}).get(hkey, {}).get("mae_pct") is not None
    ]
    mfe_vals = [
        (row.get("forward_outcomes") or {}).get(hkey, {}).get("mfe_pct")
        for row in candidate_rows
        if (row.get("forward_outcomes") or {}).get(hkey, {}).get("mfe_pct") is not None
    ]

    return {
        "horizon_sessions": horizon,
        "cross_section": cs,
        "deciles": enrich_deciles_with_excursions(deciles, candidate_rows, horizon=horizon),
        "median_forward_return_pct": round(float(np.median(fwd)), 4) if fwd else None,
        "avg_forward_return_pct": round(float(np.mean(fwd)), 4) if fwd else None,
        "avg_mae_pct": round(float(np.mean(mae_vals)), 4) if mae_vals else None,
        "avg_mfe_pct": round(float(np.mean(mfe_vals)), 4) if mfe_vals else None,
        "sector_concentration": {
            "top_sector": top_sector[0],
            "top_sector_count": top_sector[1],
            "unique_sectors": len(sector_counts),
        },
        "stability": stability,
    }


def aggregate_experiment_summary(
    snapshots: list[dict[str, Any]],
    *,
    horizons: list[int],
) -> dict[str, Any]:
    """Pool metrics across rebalance dates."""
    by_horizon: dict[str, dict[str, list[float]]] = {
        str(h): {"rank_ic": [], "hit_rate": [], "top_spread": [], "avg_return": [], "turnover": []}
        for h in horizons
    }
    recall_10: list[float] = []
    recall_20: list[float] = []

    for snap in snapshots:
        rq = snap.get("ranking_quality") or {}
        sa = snap.get("stage_a_recall") or {}
        for k in ("10", "20"):
            val = (sa.get("recall_at_k") or {}).get(k)
            if val is not None:
                (recall_10 if k == "10" else recall_20).append(float(val))

        for h in horizons:
            hkey = str(h)
            block = rq.get(hkey) or {}
            cs = block.get("cross_section") or {}
            if cs.get("sufficient"):
                rank_ic = cs.get("rank_ic")
                hit_rate = cs.get("hit_rate")
                if rank_ic is not None:
                    by_horizon[hkey]["rank_ic"].append(float(rank_ic))
                if hit_rate is not None:
                    by_horizon[hkey]["hit_rate"].append(float(hit_rate))
                spread = cs.get("top_minus_bottom_spread")
                if spread is not None:
                    by_horizon[hkey]["top_spread"].append(float(spread))
            if block.get("avg_forward_return_pct") is not None:
                by_horizon[hkey]["avg_return"].append(float(block["avg_forward_return_pct"]))
            stab = block.get("stability") or {}
            if stab.get("turnover") is not None:
                by_horizon[hkey]["turnover"].append(float(stab["turnover"]))

    def _mean(vals: list[float]) -> float | None:
        return round(float(np.mean(vals)), 4) if vals else None

    horizon_summary = {
        h: {
            "mean_rank_ic": _mean(by_horizon[str(h)]["rank_ic"]),
            "mean_hit_rate": _mean(by_horizon[str(h)]["hit_rate"]),
            "mean_top_minus_bottom_spread_pct": _mean(by_horizon[str(h)]["top_spread"]),
            "mean_avg_forward_return_pct": _mean(by_horizon[str(h)]["avg_return"]),
            "mean_turnover": _mean(by_horizon[str(h)]["turnover"]),
            "rebalance_count": len(snapshots),
        }
        for h in horizons
    }

    return {
        "rebalance_count": len(snapshots),
        "horizons": horizon_summary,
        "stage_a_recall": {
            "mean_recall_at_10": _mean(recall_10),
            "mean_recall_at_20": _mean(recall_20),
        },
    }
