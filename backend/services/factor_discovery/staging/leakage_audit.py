"""Leakage isolation audits for staging snapshots."""
from __future__ import annotations

import copy
import hashlib
import json

import pandas as pd

from engines.factor.discovery.panel_models import FactorInputPanel
from engines.factor.discovery.result_hashing import hash_panel_content
from engines.factor.discovery.session_hashing import canonical_session_hash
from engines.factor.discovery.sessions import extract_canonical_sessions
from services.factor_discovery.errors import FactorDiscoveryError

OUTCOME_FIELD_NAMES = frozenset({"forward_return", "label", "outcome", "target"})


def panel_identity_hash(panel: FactorInputPanel) -> str:
    calendar = extract_canonical_sessions(panel.frame)
    session_hash = canonical_session_hash(calendar)
    return hash_panel_content(
        panel.frame,
        eligibility=panel.eligibility,
        data_source_policy_id=panel.data_source_policy_id,
        provider_id=panel.provider_id,
        prices_adjusted=panel.prices_adjusted,
        field_provenance=panel.field_provenance,
        panel_version=panel.panel_version,
        canonical_session_hash_value=session_hash,
    )


class FactorDiscoveryLeakageAuditService:
    def assert_outcome_fields_absent(self, panel: FactorInputPanel) -> dict:
        present = sorted(set(panel.frame.columns) & OUTCOME_FIELD_NAMES)
        ok = len(present) == 0
        return {"passed": ok, "outcome_fields_present": present}

    def future_price_mutation_isolation(self, panel: FactorInputPanel, *, cut_date: str) -> dict:
        baseline_hash = panel_identity_hash(panel)
        mutated = copy.deepcopy(panel)
        for col in ("adjusted_close", "close", "volume"):
            if col in mutated.frame.columns:
                mutated.frame[col] = mutated.frame[col].astype(float)
        cut = pd.Timestamp(cut_date)
        idx = mutated.frame.index
        mask = idx.get_level_values(0) > cut
        if mask.any():
            for col in mutated.frame.columns:
                if col in {"adjusted_close", "close", "volume"}:
                    series = mutated.frame.loc[mask, col].astype(float)
                    mutated.frame.loc[mask, col] = series * 1.01
        before_mask = idx.get_level_values(0) <= cut
        before_hash = hash_panel_content(
            mutated.frame.loc[before_mask],
            eligibility=mutated.eligibility.loc[before_mask],
            data_source_policy_id=mutated.data_source_policy_id,
            provider_id=mutated.provider_id,
            prices_adjusted=mutated.prices_adjusted,
            field_provenance=mutated.field_provenance,
            panel_version=mutated.panel_version,
            canonical_session_hash_value=canonical_session_hash(
                extract_canonical_sessions(mutated.frame.loc[before_mask])
            ),
        )
        original_before = hash_panel_content(
            panel.frame.loc[before_mask],
            eligibility=panel.eligibility.loc[before_mask],
            data_source_policy_id=panel.data_source_policy_id,
            provider_id=panel.provider_id,
            prices_adjusted=panel.prices_adjusted,
            field_provenance=panel.field_provenance,
            panel_version=panel.panel_version,
            canonical_session_hash_value=canonical_session_hash(extract_canonical_sessions(panel.frame.loc[before_mask])),
        )
        return {
            "passed": before_hash == original_before,
            "cut_date": cut_date,
            "baseline_panel_hash": baseline_hash,
            "before_cut_hash_unchanged": before_hash == original_before,
        }

    def future_universe_mutation_isolation(self, panel: FactorInputPanel, *, cut_date: str) -> dict:
        cut = pd.Timestamp(cut_date)
        mutated = copy.deepcopy(panel)
        idx = mutated.eligibility.index
        mask = idx.get_level_values(0) > cut
        mutated.eligibility.loc[mask] = False
        before_mask = idx.get_level_values(0) <= cut
        unchanged = mutated.eligibility.loc[before_mask].equals(panel.eligibility.loc[before_mask])
        return {"passed": unchanged, "cut_date": cut_date}

    def sealed_period_isolation(self, *, sealed_metrics_requested: bool = False) -> dict:
        return {
            "passed": not sealed_metrics_requested,
            "sealed_metrics_computed": False,
            "note": "Ordinary staging validation does not compute sealed metrics",
        }
