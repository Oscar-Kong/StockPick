"""Compare current scan results with a previous snapshot for email diffs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScanComparison:
    new_entries: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    rank_improvements: list[dict[str, Any]] = field(default_factory=list)
    rank_declines: list[dict[str, Any]] = field(default_factory=list)
    score_changes: list[dict[str, Any]] = field(default_factory=list)


def _rank_map(results: list[dict[str, Any]]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for idx, row in enumerate(results):
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        metrics = row.get("metrics") or {}
        rank = metrics.get("final_rank")
        ranks[sym] = int(rank) if rank is not None else idx + 1
    return ranks


def _score_map(results: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in results:
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        score = row.get("score")
        if score is not None:
            out[sym] = float(score)
    return out


def compare_scan_results(
    current: list[dict[str, Any]],
    previous: list[dict[str, Any]] | None,
    *,
    top_n: int = 25,
) -> ScanComparison:
    if not previous:
        return ScanComparison()

    cur_top = [str(r.get("symbol") or "").upper() for r in current[:top_n] if r.get("symbol")]
    prev_top = [str(r.get("symbol") or "").upper() for r in previous[:top_n] if r.get("symbol")]
    cur_set = set(cur_top)
    prev_set = set(prev_top)

    comparison = ScanComparison(
        new_entries=[s for s in cur_top if s not in prev_set],
        dropped=[s for s in prev_top if s not in cur_set],
    )

    cur_ranks = _rank_map(current)
    prev_ranks = _rank_map(previous)
    cur_scores = _score_map(current)
    prev_scores = _score_map(previous)

    for sym in cur_set & prev_set:
        delta = prev_ranks.get(sym, 0) - cur_ranks.get(sym, 0)
        if delta >= 3:
            comparison.rank_improvements.append(
                {"symbol": sym, "from_rank": prev_ranks.get(sym), "to_rank": cur_ranks.get(sym), "delta": delta}
            )
        elif delta <= -3:
            comparison.rank_declines.append(
                {"symbol": sym, "from_rank": prev_ranks.get(sym), "to_rank": cur_ranks.get(sym), "delta": delta}
            )

        score_delta = cur_scores.get(sym, 0) - prev_scores.get(sym, 0)
        if abs(score_delta) >= 5:
            comparison.score_changes.append(
                {
                    "symbol": sym,
                    "from_score": round(prev_scores.get(sym, 0), 1),
                    "to_score": round(cur_scores.get(sym, 0), 1),
                    "delta": round(score_delta, 1),
                }
            )

    comparison.rank_improvements.sort(key=lambda x: -x["delta"])
    comparison.rank_declines.sort(key=lambda x: x["delta"])
    comparison.score_changes.sort(key=lambda x: -abs(x["delta"]))
    return comparison
