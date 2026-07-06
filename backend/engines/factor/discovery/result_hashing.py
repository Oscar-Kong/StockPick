"""Deterministic hashing for Factor Discovery panels and execution results."""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .panel_models import FactorExecutionConfig

EXECUTOR_VERSION = "factor-executor-v1"


def _stable_float(value: float) -> str:
    if np.isnan(value):
        return "null"
    if value == int(value):
        return str(int(value))
    return format(float(value), ".15g")


def _hash_update(hasher: hashlib._Hash, text: str) -> None:
    hasher.update(text.encode("utf-8"))


def hash_panel_content(
    frame: pd.DataFrame,
    *,
    eligibility: pd.Series,
    data_source_policy_id: str,
    provider_id: str,
    prices_adjusted: bool,
    field_provenance: dict[str, Any],
    panel_version: str,
    canonical_session_hash_value: str | None = None,
) -> str:
    """Deterministic SHA-256 over semantic panel content."""
    hasher = hashlib.sha256()
    _hash_update(hasher, f"panel_version:{panel_version}\n")
    _hash_update(hasher, f"policy:{data_source_policy_id}\n")
    _hash_update(hasher, f"provider:{provider_id}\n")
    _hash_update(hasher, f"adjusted:{int(prices_adjusted)}\n")
    if canonical_session_hash_value:
        _hash_update(hasher, f"canonical_session_hash:{canonical_session_hash_value}\n")

    prov_payload = {
        k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
        for k, v in sorted(field_provenance.items())
    }
    _hash_update(hasher, json.dumps(prov_payload, sort_keys=True, separators=(",", ":")))
    _hash_update(hasher, "\n")

    sorted_frame = frame.sort_index()
    for col in sorted(sorted_frame.columns):
        _hash_update(hasher, f"COL:{col}\n")
        series = sorted_frame[col]
        is_numeric = pd.api.types.is_numeric_dtype(series)
        for (dt, sym), val in series.items():
            date_s = pd.Timestamp(dt).strftime("%Y-%m-%d")
            if pd.isna(val):
                cell = "null"
            elif is_numeric:
                cell = _stable_float(float(val))
            else:
                cell = f"S:{val}"
            _hash_update(hasher, f"{date_s}|{sym}|{cell}\n")

    elig = eligibility.sort_index()
    for (dt, sym), val in elig.items():
        date_s = pd.Timestamp(dt).strftime("%Y-%m-%d")
        _hash_update(hasher, f"ELIG|{date_s}|{sym}|{int(bool(val))}\n")

    return f"sha256:{hasher.hexdigest()}"


def execution_hash(
    *,
    plan_hash_value: str,
    panel_content_hash: str,
    config: "FactorExecutionConfig",
    executor_version: str = EXECUTOR_VERSION,
) -> str:
    payload = {
        "plan_hash": plan_hash_value,
        "panel_content_hash": panel_content_hash,
        "executor_version": executor_version,
        "config": config.canonical_payload(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
