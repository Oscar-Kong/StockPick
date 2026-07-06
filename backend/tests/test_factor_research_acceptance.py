"""Phase 11 acceptance runner tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.acceptance.final_acceptance import FactorResearchAcceptanceRunner


def test_fixture_acceptance_passes(isolated_backend_env):
    report = FactorResearchAcceptanceRunner(mode="fixture").run()
    assert report.mode == "fixture"
    failing = [c for c in report.checks if c.status == "fail"]
    assert not failing, [(c.check_id, c.message) for c in failing]
    assert report.status == "PHASE_11_COMPLETE"


def test_acceptance_persist(tmp_path, isolated_backend_env, monkeypatch):
    runner = FactorResearchAcceptanceRunner(mode="fixture")
    monkeypatch.setattr(runner, "ARTIFACT_ROOT", tmp_path)
    report = runner.run()
    path = runner.persist(report)
    assert path.exists()
    latest = tmp_path / "latest.json"
    assert latest.exists()
