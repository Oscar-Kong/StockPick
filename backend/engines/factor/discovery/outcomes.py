"""Forward outcome generation for Factor Discovery validation."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from engines.factor.discovery.panel_models import FactorInputPanel
from engines.factor.discovery.sessions import CanonicalSessionCalendar, extract_canonical_sessions
from engines.factor.discovery.validation_errors import OutcomeGenerationError
from engines.factor.discovery.validation_models import FactorValidationConfig


class FactorOutcomePanel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    horizon_sessions: int
    forward_return: Any
    start_price: Any
    end_price: Any
    outcome_valid: Any
    outcome_end_date: dict[str, str]
    eligibility_at_score: Any
    outcome_config_hash: str
    panel_hash: str


def _outcome_config_hash(
    config: FactorValidationConfig,
    horizon: int,
    *,
    canonical_session_hash_value: str | None = None,
) -> str:
    payload = {
        "horizon": horizon,
        "timing": config.execution_timing,
        "config_version": config.config_version,
    }
    if canonical_session_hash_value:
        payload["canonical_session_hash"] = canonical_session_hash_value
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def _hash_outcome_series(
    forward: pd.Series,
    valid: pd.Series,
    *,
    horizon: int,
    config_hash: str,
    panel_hash: str,
) -> str:
    hasher = hashlib.sha256()
    hasher.update(config_hash.encode())
    hasher.update(panel_hash.encode())
    hasher.update(str(horizon).encode())
    for (dt, sym), val in forward.sort_index().items():
        date_s = pd.Timestamp(dt).strftime("%Y-%m-%d")
        cell = "null" if pd.isna(val) else f"{float(val):.15g}"
        hasher.update(f"{date_s}|{sym}|{cell}\n".encode())
    for (dt, sym), val in valid.sort_index().items():
        date_s = pd.Timestamp(dt).strftime("%Y-%m-%d")
        hasher.update(f"V|{date_s}|{sym}|{int(bool(val))}\n".encode())
    return f"sha256:{hasher.hexdigest()}"


def build_factor_outcomes(
    panel: FactorInputPanel,
    *,
    horizon_sessions: int,
    config: FactorValidationConfig,
    calendar: CanonicalSessionCalendar | None = None,
    canonical_session_hash_value: str | None = None,
) -> FactorOutcomePanel:
    """Session-based forward returns from adjusted_close; outcomes isolated from factor inputs."""
    if "adjusted_close" not in panel.frame.columns:
        raise OutcomeGenerationError(
            code="missing_adjusted_close",
            message="outcome generation requires adjusted_close in panel",
        )
    if not panel.prices_adjusted:
        raise OutcomeGenerationError(
            code="unadjusted_prices",
            message="outcomes require adjusted prices",
        )

    cal = calendar or extract_canonical_sessions(panel.frame)
    prices = panel.frame["adjusted_close"]
    eligibility = panel.eligibility.astype(bool)

    forward = pd.Series(np.nan, index=prices.index, dtype=float)
    start_px = pd.Series(np.nan, index=prices.index, dtype=float)
    end_px = pd.Series(np.nan, index=prices.index, dtype=float)
    valid = pd.Series(False, index=prices.index, dtype=bool)
    end_dates: dict[str, str] = {}

    # Score at session t; entry at t+1 when next_session timing
    entry_lag = 1 if config.execution_timing == "next_session" else 0
    outcome_lag = entry_lag + horizon_sessions

    for (dt, sym), p0 in prices.items():
        if pd.isna(p0):
            continue
        sess_idx = cal.index_of(pd.Timestamp(dt))
        if sess_idx is None:
            continue
        start_idx = sess_idx + entry_lag
        end_idx = sess_idx + outcome_lag
        if end_idx >= len(cal.sessions):
            continue
        start_sess = cal.sessions[start_idx]
        end_sess = cal.sessions[end_idx]
        try:
            p_start = prices.loc[(start_sess, sym)]
            p_end = prices.loc[(end_sess, sym)]
        except KeyError:
            continue
        if pd.isna(p_start) or pd.isna(p_end) or float(p_start) <= 0:
            continue
        ret = float(p_end) / float(p_start) - 1.0
        if not np.isfinite(ret):
            continue
        forward.loc[(dt, sym)] = ret
        start_px.loc[(dt, sym)] = float(p_start)
        end_px.loc[(dt, sym)] = float(p_end)
        valid.loc[(dt, sym)] = True
        end_dates[f"{pd.Timestamp(dt).date()}|{sym}"] = str(end_sess.date())

    cfg_hash = _outcome_config_hash(config, horizon_sessions, canonical_session_hash_value=canonical_session_hash_value)
    outcome_hash = _hash_outcome_series(
        forward,
        valid,
        horizon=horizon_sessions,
        config_hash=cfg_hash,
        panel_hash=panel.content_hash,
    )

    return FactorOutcomePanel(
        horizon_sessions=horizon_sessions,
        forward_return=forward,
        start_price=start_px,
        end_price=end_px,
        outcome_valid=valid,
        outcome_end_date=end_dates,
        eligibility_at_score=eligibility,
        outcome_config_hash=cfg_hash,
        panel_hash=outcome_hash,
    )
