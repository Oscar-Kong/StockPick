"""Human-readable scan row labels: business blurb, theme module, price returns."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

# (keyword fragments in sector+industry text, display label)
_THEME_RULES: list[tuple[tuple[str, ...], str]] = [
    (("semiconductor", "gpu", "chip", "foundry", "wafer", "eda"), "Semiconductors · AI upstream"),
    (("data center", "datacenter", "server", "networking equipment"), "Infrastructure · AI/datacenter"),
    (("software", "saas", "cloud", "cybersecurity", "application"), "Software · Digital"),
    (("biotech", "pharma", "drug", "therapeutic"), "Healthcare · Biopharma"),
    (("bank", "insurance", "asset management"), "Financials"),
    (("oil", "gas", "energy", "pipeline", "refin"), "Energy"),
    (("retail", "restaurant", "consumer"), "Consumer"),
    (("industrial", "machinery", "aerospace", "defense"), "Industrials"),
    (("utility", "power", "electric"), "Utilities · Power"),
    (("reit", "real estate"), "Real estate"),
    (("mining", "metal", "gold", "silver"), "Materials"),
    (("automotive", "auto ", " ev"), "Autos / EV"),
]


def _first_sentence(text: str, max_len: int = 140) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    line = parts[0] if parts else cleaned
    if len(line) > max_len:
        line = line[: max_len - 1].rstrip() + "…"
    return line


def infer_theme_module(sector: str | None, industry: str | None) -> str:
    blob = f"{sector or ''} {industry or ''}".lower()
    for keywords, label in _THEME_RULES:
        if any(k in blob for k in keywords):
            return label
    if industry:
        return industry.strip()
    if sector:
        return sector.strip()
    return "General equity"


def business_line(info: dict, fundamentals: dict | None = None) -> str:
    fundamentals = fundamentals or {}
    desc = (
        info.get("description")
        or fundamentals.get("description")
        or info.get("longBusinessSummary")
        or ""
    )
    sentence = _first_sentence(str(desc), max_len=120)
    if sentence:
        return sentence
    industry = info.get("industry") or fundamentals.get("industry") or ""
    name = info.get("shortName") or info.get("name") or fundamentals.get("name") or ""
    if industry and name:
        return f"{name} — {industry}."
    if industry:
        return f"{industry} operator."
    if name:
        return f"{name}."
    return "US listed equity."


def build_short_summary(info: dict, fundamentals: dict | None, theme_module: str, business: str) -> str:
    """One-line scan summary: what they do + theme bucket."""
    biz = business
    if len(biz) > 90:
        biz = biz[:89].rstrip() + "…"
    return f"{biz} · {theme_module}"


def _pct_change_vs_bars_ago(closes: pd.Series, bars_ago: int) -> float | None:
    """Close-to-close % change vs N trading sessions ago."""
    series = closes.dropna().astype(float)
    if len(series) < bars_ago + 1:
        return None
    current = float(series.iloc[-1])
    prior = float(series.iloc[-1 - bars_ago])
    if prior <= 0:
        return None
    return round((current / prior - 1.0) * 100.0, 2)


_STALE_PERCENTILE_KEYS = ("percentile_day", "percentile_week", "percentile_month")


def result_needs_return_refresh(metrics: dict[str, Any]) -> bool:
    """True when row still has range percentiles or missing return fields."""
    if any(k in metrics for k in _STALE_PERCENTILE_KEYS):
        return True
    return metrics.get("change_pct_1d") is None and metrics.get("change_pct_1w") is None


def refresh_results_return_metrics(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recompute Day/Wk/Mo % change for cached scan rows (local DB only)."""
    if not results:
        return results

    needs_work = any(
        result_needs_return_refresh(r.get("metrics") or {})
        or any(k in (r.get("metrics") or {}) for k in _STALE_PERCENTILE_KEYS)
        for r in results
    )
    if not needs_work:
        return results

    from data.price_service import PriceService

    ps = PriceService()
    patched: list[dict[str, Any]] = []
    for row in results:
        raw_metrics = row.get("metrics") or {}
        metrics = dict(raw_metrics)
        for k in _STALE_PERCENTILE_KEYS:
            metrics.pop(k, None)
        if result_needs_return_refresh(raw_metrics):
            hist = ps.get_history(str(row.get("symbol", "")), period="1mo")
            metrics.update(price_return_metrics(hist))
        patched.append({**row, "metrics": metrics})
    return patched


def price_return_metrics(history: object | None) -> dict[str, float | None]:
    """1d / ~1w (5 sessions) / ~1mo (21 sessions) price % change."""
    out: dict[str, float | None] = {
        "change_pct_1d": None,
        "change_pct_1w": None,
        "change_pct_1m": None,
    }
    if history is None or not isinstance(history, pd.DataFrame) or history.empty:
        return out
    df = history.sort_values("date") if "date" in history.columns else history
    if "close" not in df.columns:
        return out
    closes = df["close"]
    out["change_pct_1d"] = _pct_change_vs_bars_ago(closes, 1)
    out["change_pct_1w"] = _pct_change_vs_bars_ago(closes, 5)
    out["change_pct_1m"] = _pct_change_vs_bars_ago(closes, 21)
    return out


def enrich_scan_display(
    info: dict,
    fundamentals: dict | None,
    history: object | None,
    metrics: dict[str, Any],
    *,
    legacy_summary: str = "",
) -> tuple[str, dict[str, Any]]:
    """Replace trading-jargon summary with business blurb + attach price return metrics."""
    metrics = dict(metrics)
    theme = infer_theme_module(
        info.get("sector") or metrics.get("sector"),
        info.get("industry") or metrics.get("industry"),
    )
    business = business_line(info, fundamentals)
    metrics["theme_module"] = theme
    metrics["business_line"] = business
    metrics.update(price_return_metrics(history))

    summary = build_short_summary(info, fundamentals, theme, business)
    if metrics.get("earnings_soon"):
        summary = f"[Earnings soon] {summary}"
    metrics["legacy_scan_summary"] = legacy_summary
    return summary, metrics
