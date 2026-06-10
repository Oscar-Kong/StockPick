"""Penny setup classification for scan metrics."""
from __future__ import annotations

from screeners.base import CandidateContext, WeightedSignal

PENNY_SETUP_TYPES = (
    "momentum_breakout",
    "high_volume_reversal",
    "news_catalyst",
    "biotech_event",
    "crypto_beta",
    "avoid_or_watch_only",
)

_CRYPTO_KEYWORDS = ("coin", "crypto", "bitcoin", "blockchain", "digital asset", "mining")
_BIOTECH_SECTORS = ("healthcare", "biotechnology", "biotech", "pharmaceutical")


def _signal_map(signals: list[WeightedSignal]) -> dict[str, float]:
    return {s.name.lower(): s.value for s in signals}


def classify_penny_setup(
    ctx: CandidateContext,
    signals: list[WeightedSignal],
    *,
    score: float,
    data_quality_score: float | None,
    warnings: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Return (setup_type, setup_notes)."""
    notes: list[str] = []
    sm = _signal_map(signals)
    mom = sm.get("5-day momentum", sm.get("momentum", 50.0))
    vol_spike = sm.get("volume spike", sm.get("relative volume", sm.get("volume surge", 50.0)))
    rsi = sm.get("rsi fit", sm.get("rsi", 50.0))
    sentiment = sm.get("social buzz", sm.get("social sentiment", sm.get("sentiment", 50.0)))
    breakout = sm.get("breakout strength", 50.0)

    sector = (ctx.info.get("sector") or "").lower()
    industry = (ctx.info.get("industry") or ctx.info.get("longName") or "").lower()
    days_earn = ctx.info.get("days_until_earnings")

    dq = data_quality_score if data_quality_score is not None else 70.0
    if score < 45 or dq < 40:
        notes.append("Low score or data quality — watch only")
        return "avoid_or_watch_only", notes

    if any(k in industry for k in _CRYPTO_KEYWORDS) or "crypto" in sector:
        notes.append("Crypto-correlated name — higher beta")
        return "crypto_beta", notes

    if sector in _BIOTECH_SECTORS or "biotech" in industry or "pharma" in industry:
        if days_earn is not None and int(days_earn) <= 14:
            notes.append("Biotech with near-term catalyst window")
            return "biotech_event", notes

    if sentiment >= 65 and vol_spike >= 55:
        notes.append("Elevated buzz with volume confirmation")
        return "news_catalyst", notes

    if vol_spike >= 70 and rsi <= 45 and mom >= 45:
        notes.append("Volume reversal off oversold RSI")
        return "high_volume_reversal", notes

    if mom >= 60 and (breakout >= 55 or vol_spike >= 55):
        notes.append("Momentum + range extension")
        return "momentum_breakout", notes

    if warnings:
        notes.extend(warnings[:2])
        return "avoid_or_watch_only", notes

    return "momentum_breakout", notes
