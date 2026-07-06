"""State machine tests for mining sessions."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.mining.errors import MiningSessionStateError
from services.factor_discovery.mining.models import MiningSessionStatus
from services.factor_discovery.mining.state_machine import TERMINAL_SESSION_STATES, validate_session_transition


def test_terminal_states_cannot_transition():
    with pytest.raises(MiningSessionStateError):
        validate_session_transition(MiningSessionStatus.COMPLETED, MiningSessionStatus.GENERATING_HYPOTHESES)


def test_no_draft_to_running_experiments():
    with pytest.raises(MiningSessionStateError):
        validate_session_transition(MiningSessionStatus.DRAFT, MiningSessionStatus.RUNNING_EXPERIMENTS)


def test_authorized_to_generating_hypotheses():
    validate_session_transition(MiningSessionStatus.AUTHORIZED, MiningSessionStatus.GENERATING_HYPOTHESES)


def test_terminal_set():
    assert MiningSessionStatus.CANCELLED in TERMINAL_SESSION_STATES
