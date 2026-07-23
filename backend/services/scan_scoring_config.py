"""Scan Stage B scoring mode — legacy, engine-only, or sampled parity."""
from __future__ import annotations

import hashlib
import logging
from typing import Literal

from config import SCAN_PARITY_SAMPLE_RATE, SCAN_SCORING_MODE, USE_SCORING_ENGINE_IN_SCAN

logger = logging.getLogger(__name__)

ScanScoringMode = Literal["legacy", "engine", "parity_sample"]

VALID_SCAN_SCORING_MODES: frozenset[str] = frozenset({"legacy", "engine", "parity_sample"})


def resolve_scan_scoring_mode() -> ScanScoringMode:
    """Resolve effective scoring mode from env (engine is the canonical default).

    ``USE_SCORING_ENGINE_IN_SCAN`` is a deprecated alias used only when
    ``SCAN_SCORING_MODE`` is empty/invalid. When both are set and disagree, log a warning.
    """
    explicit = (SCAN_SCORING_MODE or "").strip().lower()
    if explicit in VALID_SCAN_SCORING_MODES:
        if USE_SCORING_ENGINE_IN_SCAN and explicit == "legacy":
            logger.warning(
                "SCAN_SCORING_MODE=legacy disagrees with USE_SCORING_ENGINE_IN_SCAN=true; "
                "using SCAN_SCORING_MODE (canonical). Remove USE_SCORING_ENGINE_IN_SCAN after migration."
            )
        if not USE_SCORING_ENGINE_IN_SCAN and explicit in ("engine", "parity_sample"):
            # Common: .env.example sets engine + USE=false — not a conflict worth warning every call.
            pass
        return explicit  # type: ignore[return-value]
    if USE_SCORING_ENGINE_IN_SCAN:
        logger.warning(
            "SCAN_SCORING_MODE unset/invalid; using deprecated USE_SCORING_ENGINE_IN_SCAN → engine"
        )
        return "engine"
    # Canonical default when mode is empty/invalid.
    return "engine"


def primary_scorer_is_engine(mode: ScanScoringMode) -> bool:
    return mode in ("engine", "parity_sample")


def engine_path_enabled(mode: ScanScoringMode) -> bool:
    return mode in ("engine", "parity_sample")


def legacy_path_enabled(mode: ScanScoringMode) -> bool:
    return mode == "legacy"


def parity_sample_included(
    scan_id: str,
    symbol: str,
    *,
    sample_rate: float | None = None,
) -> bool:
    """Deterministic parity sample — hash(scan_id:symbol) vs configured rate."""
    rate = SCAN_PARITY_SAMPLE_RATE if sample_rate is None else float(sample_rate)
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    key = f"{scan_id}:{symbol.upper()}".encode("utf-8")
    digest = int(hashlib.sha256(key).hexdigest()[:8], 16)
    bucket = digest / 0xFFFFFFFF
    return bucket < rate


def legacy_parity_comparison_enabled(
    mode: ScanScoringMode,
    scan_id: str,
    symbol: str,
    *,
    sample_rate: float | None = None,
) -> bool:
    """Legacy scorer runs for production (legacy mode) or parity sampling only."""
    if mode == "legacy":
        return True
    if mode == "engine":
        return False
    return parity_sample_included(scan_id, symbol, sample_rate=sample_rate)
