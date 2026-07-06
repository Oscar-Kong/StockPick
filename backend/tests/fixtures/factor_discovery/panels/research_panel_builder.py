"""Build deterministic research panels for Factor Discovery execution tests."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from engines.factor.discovery.panel_models import FactorInputPanel
from engines.factor.discovery.provenance import PanelFieldProvenance, PanelFieldSourceType, PitProvenanceState


def _trading_dates(n: int, start: date = date(2024, 1, 2)) -> list[date]:
    out: list[date] = []
    cur = start
    while len(out) < n:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def build_research_panel(*, n_days: int = 40) -> FactorInputPanel:
    """Multi-symbol panel with PIT fundamentals, eligibility, and edge cases."""
    symbols = ["AAA", "BBB", "CCC", "DDD"]
    dates = _trading_dates(n_days)
    rows: list[dict] = []
    rng = np.random.default_rng(42)

    for i, d in enumerate(dates):
        for j, sym in enumerate(symbols):
            price = 100.0 + i * 0.5 + j * 10 + rng.normal(0, 0.2)
            vol = 1_000_000 + i * 1000 + (0 if sym == "DDD" and i == 5 else 5000)
            mcap = price * 1_000_000
            sector = "TECH" if sym != "DDD" else "SOLO"
            industry = f"IND_{sector}"
            eligible = not (sym == "CCC" and i >= 30)
            if sym == "BBB" and i < 3:
                eligible = False
            rows.append(
                {
                    "date": pd.Timestamp(d),
                    "symbol": sym,
                    "adjusted_close": price,
                    "volume": vol,
                    "market_cap": mcap,
                    "sector": sector,
                    "industry": industry,
                    "eligible": eligible,
                }
            )

    frame = pd.DataFrame(rows).set_index(["date", "symbol"]).sort_index()

    fcf_rows = []
    pub_date = date(2024, 1, 20)
    lag_sessions = 45
    pub_idx = dates.index(pub_date) if pub_date in dates else 20
    effective_idx = min(pub_idx + lag_sessions, len(dates) - 1)
    effective_date = dates[effective_idx]
    for d in dates:
        for sym in symbols:
            val = np.nan
            if d >= effective_date:
                val = 5_000_000.0 + hash(sym) % 1000
            fcf_rows.append({"date": pd.Timestamp(d), "symbol": sym, "free_cash_flow": val})
    fcf = pd.DataFrame(fcf_rows).set_index(["date", "symbol"]).sort_index()
    frame = frame.join(fcf, how="left")

    eligibility = frame["eligible"].astype(bool)
    frame = frame.drop(columns=["eligible"])

    policy = "research_adjusted_daily_v1"
    provider = "fixture_provider_v1"
    provenance = {
        "adjusted_close": PanelFieldProvenance(
            field_id="adjusted_close",
            source_type=PanelFieldSourceType.SUPPLIED_PRIMITIVE,
            pit_state=PitProvenanceState.VERIFIED_PIT,
            provider_id=provider,
            source_policy_id=policy,
            is_adjusted=True,
        ),
        "volume": PanelFieldProvenance(
            field_id="volume",
            source_type=PanelFieldSourceType.SUPPLIED_PRIMITIVE,
            pit_state=PitProvenanceState.VERIFIED_PIT,
            provider_id=provider,
            source_policy_id=policy,
        ),
        "market_cap": PanelFieldProvenance(
            field_id="market_cap",
            source_type=PanelFieldSourceType.EXPOSURE,
            pit_state=PitProvenanceState.VERIFIED_PIT,
            provider_id=provider,
            source_policy_id=policy,
        ),
        "sector": PanelFieldProvenance(
            field_id="sector",
            source_type=PanelFieldSourceType.CLASSIFICATION,
            pit_state=PitProvenanceState.VERIFIED_PIT,
            provider_id=provider,
            source_policy_id=policy,
        ),
        "industry": PanelFieldProvenance(
            field_id="industry",
            source_type=PanelFieldSourceType.CLASSIFICATION,
            pit_state=PitProvenanceState.VERIFIED_PIT,
            provider_id=provider,
            source_policy_id=policy,
        ),
        "free_cash_flow": PanelFieldProvenance(
            field_id="free_cash_flow",
            source_type=PanelFieldSourceType.PIT_ALIGNED_FUNDAMENTAL,
            pit_state=PitProvenanceState.VERIFIED_PIT,
            provider_id=provider,
            source_policy_id=policy,
            publication_lag_sessions_applied=lag_sessions,
            earliest_valid_date=effective_date.isoformat(),
        ),
    }

    return FactorInputPanel(
        frame=frame,
        eligibility=eligibility,
        data_source_policy_id=policy,
        provider_id=provider,
        prices_adjusted=True,
        field_provenance=provenance,
    )
