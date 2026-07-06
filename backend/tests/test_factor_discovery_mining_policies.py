"""Policy validation tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.mining.errors import MiningProviderCapabilityError
from services.factor_discovery.mining.policies import validate_session_mode


def test_invalid_session_mode():
    with pytest.raises(MiningProviderCapabilityError):
        validate_session_mode("unbounded_agent")
