"""FRED macro data client."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests

from config import FRED_API_KEY, FRED_ENABLED

logger = logging.getLogger(__name__)


class FredClient:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key or FRED_API_KEY) if FRED_ENABLED else ""

    def get_latest(self, series_id: str) -> float | None:
        if not self.api_key:
            return None

        end = datetime.utcnow()
        start = end - timedelta(days=90)
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start.strftime("%Y-%m-%d"),
            "observation_end": end.strftime("%Y-%m-%d"),
            "sort_order": "desc",
            "limit": 5,
        }
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            observations = response.json().get("observations", [])
            for obs in observations:
                val = obs.get("value")
                if val not in (None, ".", ""):
                    return float(val)
        except Exception as exc:
            logger.warning("FRED fetch failed for %s: %s", series_id, exc)
        return None

    def macro_regime_score(self) -> float:
        """Higher score = more favorable for long-term compounders."""
        try:
            from data.openbb_client import is_available, macro_regime_score as obb_macro

            if is_available():
                obb_score = obb_macro()
                if obb_score is not None:
                    return obb_score
        except Exception:
            pass

        if not self.api_key:
            return 50.0

        fed_funds = self.get_latest("FEDFUNDS")
        unemployment = self.get_latest("UNRATE")
        treasury_10y = self.get_latest("DGS10")

        score = 50.0
        if fed_funds is not None and fed_funds < 4.0:
            score += 10
        elif fed_funds is not None and fed_funds > 5.0:
            score -= 10

        if unemployment is not None and unemployment < 5.0:
            score += 10
        elif unemployment is not None and unemployment > 6.0:
            score -= 10

        if treasury_10y is not None and 3.0 <= treasury_10y <= 5.0:
            score += 5

        return max(0.0, min(100.0, score))
