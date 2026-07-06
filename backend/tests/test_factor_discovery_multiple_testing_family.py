"""Multiple-testing growth and staleness tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.multiple_testing_service import is_correction_stale


def test_staleness_when_family_grows():
    assert is_correction_stale(family_size_at_evaluation=1, current_derived_size=2) is True
    assert is_correction_stale(family_size_at_evaluation=2, current_derived_size=2) is False
