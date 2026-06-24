"""Convert scan evaluation chart JSON artifacts to Quant Lab ChartSeries."""
from __future__ import annotations

from typing import Any

from models.schemas_research import ChartSeries


def _safe_points(rows: list[dict[str, Any]], *, x_key: str, y_key: str, series_name: str) -> list[dict[str, Any]]:
    data = []
    for row in rows:
        y = row.get(y_key)
        if y is None:
            continue
        try:
            yf = float(y)
        except (TypeError, ValueError):
            continue
        x = row.get(x_key)
        data.append({"x": str(x), "y": yf, "label": str(x)})
    return [{"name": series_name, "data": data}] if data else []


def charts_from_artifact(detail: dict[str, Any]) -> list[ChartSeries]:
    """Build ChartSeries list from persisted scan evaluation payload."""
    charts: list[ChartSeries] = []
    raw = detail.get("charts") or {}
    if not raw and detail.get("artifact_paths", {}).get("charts"):
        try:
            import json
            from pathlib import Path

            path = Path(detail["artifact_paths"]["charts"])
            if path.is_file():
                raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}

    # Comparison mode charts
    recall_rows = raw.get("recall_by_version") or []
    if recall_rows:
        for metric, label in (
            ("recall_at_10", "Recall@10"),
            ("recall_at_20", "Recall@20"),
            ("recall_at_50", "Recall@50"),
        ):
            series = _safe_points(
                [{"x": r.get("version"), "y": r.get(metric)} for r in recall_rows],
                x_key="x",
                y_key="y",
                series_name=label,
            )
            charts.append(
                ChartSeries(
                    chart_id=f"scan_recall_{metric}",
                    title=f"Stage A {label} by algorithm",
                    chart_type="bar",
                    series=series,
                    empty_reason=None if series else f"No {label} data",
                )
            )

    hit_rows = raw.get("hit_rate_by_horizon") or []
    if hit_rows:
        by_version: dict[str, list[dict[str, Any]]] = {}
        for row in hit_rows:
            ver = str(row.get("version") or "run")
            by_version.setdefault(ver, []).append(row)
        multi_series = []
        for ver, rows in sorted(by_version.items()):
            pts = [
                {"x": str(r.get("horizon")), "y": r.get("hit_rate")}
                for r in rows
                if r.get("hit_rate") is not None
            ]
            if pts:
                multi_series.append({"name": ver, "data": [{"x": p["x"], "y": float(p["y"])} for p in pts]})
        charts.append(
            ChartSeries(
                chart_id="scan_hit_rate_horizon",
                title="Hit rate by horizon",
                chart_type="line",
                series=multi_series,
                empty_reason=None if multi_series else "No hit rate data",
            )
        )

    ic_rows = raw.get("mean_rank_ic_by_horizon") or detail.get("quant_lab", {}).get("horizons")
    if isinstance(ic_rows, list):
        ic_pts = ic_rows
    else:
        ic_pts = raw.get("mean_rank_ic_by_horizon") or []
    if ic_pts:
        series = _safe_points(
            [{"x": f"{r.get('version', '')} h{r.get('horizon')}", "y": r.get("mean_rank_ic")} for r in ic_pts],
            x_key="x",
            y_key="y",
            series_name="Rank IC",
        )
        charts.append(
            ChartSeries(
                chart_id="scan_rank_ic",
                title="Mean rank IC by horizon",
                chart_type="bar",
                series=series,
                empty_reason=None if series else "No rank IC data",
            )
        )

    decile_pts = raw.get("decile_forward_returns") or []
    if decile_pts:
        by_ver: dict[str, list[dict[str, Any]]] = {}
        for pt in decile_pts:
            ver = str(pt.get("version") or "run")
            by_ver.setdefault(ver, []).append(pt)
        multi = []
        for ver, pts in sorted(by_ver.items()):
            decile_map: dict[int, float] = {}
            for p in pts:
                d = p.get("decile")
                y = p.get("avg_forward_return_pct")
                if d is not None and y is not None:
                    decile_map[int(d)] = float(y)
            if decile_map:
                data = [{"x": str(k), "y": v} for k, v in sorted(decile_map.items())]
                multi.append({"name": ver, "data": data})
        charts.append(
            ChartSeries(
                chart_id="scan_decile_returns",
                title="Avg forward return by score decile",
                chart_type="line",
                x_label="Decile",
                y_label="Return %",
                series=multi,
                empty_reason=None if multi else "No decile data",
            )
        )

    # Single-run fallback from build_chart_series shape
    if not charts and raw.get("decile_forward_returns"):
        pts = raw["decile_forward_returns"]
        decile_map: dict[str, float] = {}
        for p in pts:
            key = str(p.get("decile") or p.get("date"))
            y = p.get("avg_forward_return_pct")
            if y is not None:
                decile_map[key] = float(y)
        if decile_map:
            charts.append(
                ChartSeries(
                    chart_id="scan_decile_returns",
                    title="Avg forward return by score decile",
                    chart_type="line",
                    series=[
                        {
                            "name": "Decile avg",
                            "data": [{"x": k, "y": v} for k, v in sorted(decile_map.items())],
                        }
                    ],
                )
            )

    return charts
