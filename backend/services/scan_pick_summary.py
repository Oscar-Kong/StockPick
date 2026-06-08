"""Short AI (or rule-based) scan pick blurb — background + why it ranked."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from config import LLM_ENABLED, LLM_API_KEY
from data.cache import Cache

logger = logging.getLogger(__name__)

_BANNED = re.compile(
    r"\b(buy|sell|strong buy|strong sell|recommend|target price)\b",
    re.IGNORECASE,
)


def _top_signals(signals: list[dict[str, Any]], n: int = 4) -> list[str]:
    ranked = sorted(
        signals,
        key=lambda s: abs(float(s.get("contribution") or s.get("value") or 0)),
        reverse=True,
    )
    out: list[str] = []
    for s in ranked[:n]:
        name = str(s.get("name") or s.get("factor_id") or "signal").replace("_", " ")
        val = s.get("value")
        if val is not None:
            out.append(f"{name} ({float(val):.0f})")
        else:
            out.append(name)
    return out


def _rule_based_summary(
    *,
    symbol: str,
    bucket: str,
    score: float,
    summary: str,
    signals: list[dict[str, Any]],
    metrics: dict[str, Any],
    locale: str = "en",
) -> dict[str, Any]:
    business = str(metrics.get("business_line") or summary or f"{symbol} is a US-listed equity.")
    theme = str(metrics.get("theme_module") or metrics.get("sector") or "General equity")
    partial = bool(metrics.get("provider_limited_partial_data"))
    top = _top_signals(signals)
    zh = locale.lower().startswith("zh")

    if zh:
        pick_bits: list[str] = [f"量化评分 {score:.0f}/100（{bucket} 策略桶）。"]
        if top:
            pick_bits.append(f"主要信号：{', '.join(top)}。")
        if metrics.get("change_pct_1w") is not None:
            pick_bits.append(f"近一周涨跌 {metrics['change_pct_1w']:+.1f}%。")
        if metrics.get("earnings_soon"):
            pick_bits.append("财报窗口临近。")
        if partial:
            pick_bits.append("数据有限条件下的候选 — 请核实基本面。")
        background = f"{business} 主题：{theme}。"
        why_picked = " ".join(pick_bits)
        why_label = "入选原因"
    else:
        pick_bits = [f"Quant score {score:.0f}/100 in the {bucket} sleeve."]
        if top:
            pick_bits.append(f"Leading signals: {', '.join(top)}.")
        if metrics.get("change_pct_1w") is not None:
            pick_bits.append(f"1-week price change {metrics['change_pct_1w']:+.1f}%.")
        if metrics.get("earnings_soon"):
            pick_bits.append("Earnings event is approaching.")
        if partial:
            pick_bits.append("Ranked under provider-limited data — confirm fundamentals before acting.")
        background = f"{business} Theme: {theme}."
        why_picked = " ".join(pick_bits)
        why_label = "Why it ranked"

    return {
        "symbol": symbol.upper(),
        "bucket": bucket,
        "background": background,
        "why_picked": why_picked,
        "text": f"{background}\n\n{why_label}: {why_picked}",
        "source": "rules",
    }


def _cache_key(symbol: str, bucket: str, score: float, summary: str, signals: list, locale: str) -> str:
    blob = json.dumps(
        {
            "s": symbol,
            "b": bucket,
            "score": round(score, 1),
            "summary": summary[:120],
            "sig": signals[:6],
            "locale": locale,
        },
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(blob.encode()).hexdigest()[:16]
    return f"scan_pick_summary:{bucket}:{symbol.upper()}:{digest}"


def generate_scan_pick_summary(
    *,
    symbol: str,
    bucket: str,
    score: float,
    summary: str = "",
    signals: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
    locale: str = "en",
) -> dict[str, Any]:
    """Return {background, why_picked, text, source} — not a full research report."""
    signals = signals or []
    metrics = metrics or {}
    sym = symbol.upper()
    loc = "zh" if str(locale).lower().startswith("zh") else "en"
    key = _cache_key(sym, bucket, score, summary, signals, loc)
    cached = Cache().get(key)
    if cached and isinstance(cached, dict) and cached.get("text"):
        return cached

    fallback = _rule_based_summary(
        symbol=sym,
        bucket=bucket,
        score=score,
        summary=summary,
        signals=signals,
        metrics=metrics,
        locale=loc,
    )

    if not LLM_ENABLED or not LLM_API_KEY:
        Cache().set(key, fallback, ttl_seconds=3600)
        return fallback

    business = metrics.get("business_line") or summary
    theme = metrics.get("theme_module") or ""
    signal_lines = _top_signals(signals, 5)
    partial_note = (
        "注意：候选股在数据有限条件下入选。"
        if loc == "zh" and metrics.get("provider_limited_partial_data")
        else "Note: candidate ranked with limited provider data."
        if metrics.get("provider_limited_partial_data")
        else ""
    )

    if loc == "zh":
        prompt = f"""为股票 {sym}（{bucket} 策略桶，评分 {score:.0f}/100）写一段简短的筛选说明。

请严格输出两段（不要标题、不要列表）：
1）背景 — 公司业务、行业/主题（{theme}），结合：{business}
2）入选原因 — 引用量化信号：{', '.join(signal_lines) or '动量/成交量启发式'}
{partial_note}

规则：不得出现买入/卖出/推荐等措辞。总共不超过 120 字。使用简体中文。"""
    else:
        prompt = f"""Write a brief scan note for ticker {sym} ({bucket} bucket, score {score:.0f}/100).

Return exactly two short paragraphs (no headings, no bullet lists):
1) Background — what the company does, sector/theme ({theme}), one sentence on business ({business}).
2) Why it ranked — cite quantitative fit using these signals: {', '.join(signal_lines) or 'momentum/volume heuristics'}.
{partial_note}

Rules: No buy/sell/hold language. Max 120 words total. Plain English for a watchlist screen."""

    try:
        from services.llm_explainer import _call_llm

        raw = _call_llm(
            [{"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0.25,
        )
        if _BANNED.search(raw):
            Cache().set(key, fallback, ttl_seconds=3600)
            return fallback
        parts = [p.strip() for p in re.split(r"\n\s*\n", raw.strip()) if p.strip()]
        background = parts[0] if parts else business
        why_picked = parts[1] if len(parts) > 1 else fallback["why_picked"]
        result = {
            "symbol": sym,
            "bucket": bucket,
            "background": background,
            "why_picked": why_picked,
            "text": f"{background}\n\n{why_picked}",
            "source": "llm",
        }
        Cache().set(key, result, ttl_seconds=86400)
        return result
    except Exception as exc:
        logger.debug("scan pick summary LLM failed %s: %s", sym, exc)
        Cache().set(key, fallback, ttl_seconds=1800)
        return fallback
