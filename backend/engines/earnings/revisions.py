"""Earnings revision and catalyst signals."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import FMP_API_KEY, FMP_ENABLED
from scoring.earnings_revision import earnings_revision_proxy
from scoring.metrics import safe_float


@dataclass
class EarningsSetup:
    next_earnings_days: int | None = None
    eps_revision_30d_pct: float | None = None
    revenue_revision_30d_pct: float | None = None
    analyst_upgrades: int = 0
    analyst_downgrades: int = 0
    last_surprise_pct: float | None = None
    post_earnings_drift: str = "unknown"
    guidance_trend: str = "unchanged"
    catalyst_score: float = 50.0
    risk_note: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_earnings_days": self.next_earnings_days,
            "eps_revision_30d_pct": self.eps_revision_30d_pct,
            "revenue_revision_30d_pct": self.revenue_revision_30d_pct,
            "analyst_upgrades": self.analyst_upgrades,
            "analyst_downgrades": self.analyst_downgrades,
            "last_surprise_pct": self.last_surprise_pct,
            "post_earnings_drift": self.post_earnings_drift,
            "guidance_trend": self.guidance_trend,
            "catalyst_score": self.catalyst_score,
            "risk_note": self.risk_note,
            "details": self.details,
        }


def _fetch_fmp_estimates(symbol: str) -> dict[str, Any]:
    if not FMP_ENABLED or not FMP_API_KEY:
        return {}
    try:
        import requests

        url = f"https://financialmodelingprep.com/api/v3/analyst-estimates/{symbol.upper()}"
        r = requests.get(url, params={"apikey": FMP_API_KEY, "limit": 8}, timeout=12)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            latest = data[0]
            latest["history"] = data
            return latest
    except Exception:
        pass
    return {}


def _fetch_fmp_grades(symbol: str) -> dict[str, int]:
    if not FMP_ENABLED or not FMP_API_KEY:
        return {"upgrades": 0, "downgrades": 0}
    try:
        import requests

        url = f"https://financialmodelingprep.com/api/v3/grade/{symbol.upper()}"
        r = requests.get(url, params={"apikey": FMP_API_KEY, "limit": 30}, timeout=12)
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list):
            return {"upgrades": 0, "downgrades": 0}
        upgrades = downgrades = 0
        for row in rows[:30]:
            action = str(row.get("newGrade") or row.get("gradingCompany") or "").lower()
            prev = str(row.get("previousGrade") or "").lower()
            if not action and not prev:
                continue
            rank = {"strong buy": 5, "buy": 4, "hold": 3, "sell": 2, "strong sell": 1}
            new_r = rank.get(action.split()[0] if action else "", 3)
            old_r = rank.get(prev.split()[0] if prev else "", 3)
            if new_r > old_r:
                upgrades += 1
            elif new_r < old_r:
                downgrades += 1
        return {"upgrades": upgrades, "downgrades": downgrades}
    except Exception:
        return {"upgrades": 0, "downgrades": 0}


def _revision_pct_from_history(est: dict[str, Any], field: str) -> float | None:
    hist = est.get("history")
    if not isinstance(hist, list) or len(hist) < 2:
        return None
    cur = safe_float(hist[0].get(field))
    prior = safe_float(hist[min(len(hist) - 1, 3)].get(field))
    if cur is None or prior is None or abs(prior) < 1e-6:
        return None
    return round((cur / prior - 1) * 100, 2)


def _cache_estimate_history(symbol: str, est: dict[str, Any]) -> None:
    if not est.get("history"):
        return
    try:
        from data.cache import Cache

        Cache().set(
            f"estimate_history:{symbol.upper()}",
            est.get("history"),
            ttl=86400,
        )
    except Exception:
        pass


def _post_earnings_drift_returns(symbol: str, info: dict[str, Any]) -> dict[str, float | None]:
    """5d/20d price drift after last reported earnings."""
    import pandas as pd

    from data.price_service import PriceService

    ts = info.get("earningsTimestamp") or info.get("earningsTimestampStart")
    if ts is None:
        return {"drift_5d_pct": None, "drift_20d_pct": None}
    try:
        event = pd.Timestamp(ts, unit="s").date() if isinstance(ts, (int, float)) else pd.Timestamp(ts).date()
    except Exception:
        return {"drift_5d_pct": None, "drift_20d_pct": None}

    try:
        hist = PriceService().get_history(symbol.upper(), period="1y")
        if hist.empty:
            return {"drift_5d_pct": None, "drift_20d_pct": None}
        hist = hist.reset_index(drop=True)
        col = hist["date"] if "date" in hist.columns else hist.index
        start_idx = None
        for i, raw in enumerate(col):
            try:
                d = pd.Timestamp(raw).date()
                if d >= event:
                    start_idx = i
                    break
            except Exception:
                continue
        if start_idx is None:
            return {"drift_5d_pct": None, "drift_20d_pct": None}
        p0 = float(hist["close"].iloc[start_idx])

        def _ret(offset: int) -> float | None:
            j = start_idx + offset
            if j >= len(hist) or p0 <= 0:
                return None
            return round((float(hist["close"].iloc[j]) / p0 - 1) * 100, 2)

        return {"drift_5d_pct": _ret(5), "drift_20d_pct": _ret(20)}
    except Exception:
        return {"drift_5d_pct": None, "drift_20d_pct": None}


def build_earnings_setup(
    symbol: str,
    info: dict[str, Any],
    fundamentals: dict[str, Any] | None = None,
    *,
    days_until_earnings: int | None = None,
    valuation_verdict: str | None = None,
) -> EarningsSetup:
    fundamentals = fundamentals or {}
    est = _fetch_fmp_estimates(symbol)
    _cache_estimate_history(symbol, est)
    grades = _fetch_fmp_grades(symbol)
    drift_stats = _post_earnings_drift_returns(symbol, info)

    eps_est = safe_float(est.get("estimatedEpsAvg") or fundamentals.get("eps_estimate"))
    rev_est = safe_float(est.get("estimatedRevenueAvg"))
    eps_growth = safe_float(info.get("earningsGrowth"))
    rev_growth = safe_float(info.get("revenueGrowth"))

    eps_rev_pct = _revision_pct_from_history(est, "estimatedEpsAvg")
    rev_rev_pct = _revision_pct_from_history(est, "estimatedRevenueAvg")
    if eps_rev_pct is None and eps_est and eps_growth:
        eps_rev_pct = round((eps_est / max(abs(eps_growth), 0.01) - 1) * 100, 2) if eps_growth else None

    proxy_score = earnings_revision_proxy(info, fundamentals)
    catalyst = proxy_score

    surprise = safe_float(fundamentals.get("earnings_surprise_pct") or info.get("earningsSurprisePercent"))
    if surprise and surprise > 5:
        catalyst = min(100.0, catalyst + 8)
    elif surprise and surprise < -5:
        catalyst = max(0.0, catalyst - 10)

    drift = "positive" if surprise > 3 else "negative" if surprise < -3 else "neutral"
    d5 = drift_stats.get("drift_5d_pct")
    d20 = drift_stats.get("drift_20d_pct")
    if d5 is not None:
        drift = "positive" if d5 > 1 else "negative" if d5 < -1 else "neutral"
    elif d20 is not None:
        drift = "positive" if d20 > 2 else "negative" if d20 < -2 else "neutral"
    guidance = "raised" if eps_growth > 0.08 else "lowered" if eps_growth < -0.02 else "unchanged"

    risk = ""
    if days_until_earnings is not None and days_until_earnings <= 14:
        risk = "High earnings event risk"
        if valuation_verdict in ("expensive", "extremely_expensive"):
            risk += "; valuation extended into earnings"

    return EarningsSetup(
        next_earnings_days=days_until_earnings,
        eps_revision_30d_pct=eps_rev_pct,
        revenue_revision_30d_pct=rev_rev_pct,
        analyst_upgrades=grades.get("upgrades", 0),
        analyst_downgrades=grades.get("downgrades", 0),
        last_surprise_pct=surprise if surprise else None,
        post_earnings_drift=drift,
        guidance_trend=guidance,
        catalyst_score=round(catalyst, 2),
        risk_note=risk,
        details={
            "has_fmp_estimates": bool(est),
            "rev_est": rev_est,
            "estimate_history_len": len(est.get("history") or []),
            "post_earnings_drift_5d_pct": d5,
            "post_earnings_drift_20d_pct": d20,
        },
    )
