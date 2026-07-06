"""Canonical trading-session calendar for Factor Discovery panels."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engines.factor.discovery.panel_models import FactorInputPanel


@dataclass(frozen=True)
class CanonicalSessionCalendar:
    """Ordered session dates derived from the panel union calendar."""

    sessions: tuple[pd.Timestamp, ...]
    calendar_id: str
    version: str = "factor-sessions-v1"

    def index_of(self, dt: pd.Timestamp) -> int | None:
        ts = pd.Timestamp(dt).normalize()
        for i, s in enumerate(self.sessions):
            if s == ts:
                return i
        return None

    def forward_session(self, start: pd.Timestamp, horizon: int) -> pd.Timestamp | None:
        idx = self.index_of(start)
        if idx is None:
            return None
        end_idx = idx + horizon
        if end_idx >= len(self.sessions):
            return None
        return self.sessions[end_idx]

    def to_hash_payload(self) -> list[str]:
        return [s.strftime("%Y-%m-%d") for s in self.sessions]


def extract_canonical_sessions(frame: pd.DataFrame) -> CanonicalSessionCalendar:
    dates = frame.index.get_level_values(0).unique()
    ordered = tuple(sorted(pd.Timestamp(d).normalize() for d in dates))
    return CanonicalSessionCalendar(sessions=ordered, calendar_id="panel_union_v1")


def align_panel_to_canonical_sessions(
    panel: FactorInputPanel,
    *,
    calendar: CanonicalSessionCalendar | None = None,
) -> tuple[FactorInputPanel, CanonicalSessionCalendar, int]:
    """Reindex panel to full (session × symbol) grid; missing rows become NaN."""
    cal = calendar or extract_canonical_sessions(panel.frame)
    symbols = sorted(panel.frame.index.get_level_values(1).unique())
    full_index = pd.MultiIndex.from_product(
        [list(cal.sessions), symbols],
        names=["date", "symbol"],
    )
    frame = panel.frame.reindex(full_index)
    eligibility = panel.eligibility.reindex(full_index, fill_value=False)
    missing_rows = int(frame.isna().all(axis=1).sum())
    aligned = FactorInputPanel(
        frame=frame.sort_index(),
        eligibility=eligibility.sort_index(),
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
        panel_version=f"{panel.panel_version}+aligned",
        timezone=panel.timezone,
        has_universe_membership=panel.has_universe_membership,
    )
    return aligned, cal, missing_rows
