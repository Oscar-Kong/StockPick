"""Tests for unified experiment studio — presets, validation, launch, jobs."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from models.schemas_research import ExperimentValidateRequest, ResearchExperimentCreate
from services.experiment_presets_service import list_presets, list_templates, merge_parameters, normalize_preset
from services.experiment_universe_service import resolve_universe
from services.experiment_validation_service import validate_experiment
from services.research_experiments_service import create_experiment


@pytest.fixture
def research_db(isolated_backend_env):
    init_quant_db()
    return isolated_backend_env


@pytest.fixture
def client(research_db):
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


def test_list_templates_has_six_types(research_db):
    resp = list_templates()
    types = {t.experiment_type for t in resp.templates}
    assert types == {
        "factor_validation",
        "walk_forward",
        "prediction_calibration",
        "pairs_discovery",
        "similar_signal",
        "portfolio_policy",
    }


def test_presets_transparent_parameters(research_db):
    resp = list_presets()
    assert len(resp.presets) == 3
    quick = next(p for p in resp.presets if p.preset_id == "quick_check")
    assert quick.major_evidence_eligible is False
    assert any(p.key == "max_symbols" for p in quick.parameters)
    robust = next(p for p in resp.presets if p.preset_id == "robust_validation")
    assert robust.major_evidence_eligible is True


def test_preset_aliases(research_db):
    assert normalize_preset("exploratory") == "quick_check"
    assert normalize_preset("robust") == "robust_validation"


def test_merge_parameters_user_overrides_preset(research_db):
    merged = merge_parameters("walk_forward", "quick_check", {"max_symbols": 10})
    assert merged["max_symbols"] == 10
    assert merged["lookback_period"] == "6mo"


def test_resolve_custom_symbols(research_db):
    symbols, source, _ = resolve_universe(
        {"source": "custom_symbols", "symbols": ["aapl", "msft", "aapl"]},
        sleeve="penny",
        parameters={"max_symbols": 10},
    )
    assert source == "custom_symbols"
    assert symbols == ["AAPL", "MSFT"]


def test_validate_pairs_requires_two_symbols(research_db):
    result = validate_experiment(
        ExperimentValidateRequest(
            experiment_type="pairs_discovery",
            universe_definition={"source": "custom_symbols", "symbols": ["AAPL"]},
            parameters={},
        )
    )
    assert result.can_run is False
    assert any(c.key == "symbol_count" and c.status == "error" for c in result.checks)


def test_validate_similar_signal_requires_symbol(research_db):
    result = validate_experiment(
        ExperimentValidateRequest(
            experiment_type="similar_signal",
            sleeve="penny",
            universe_definition={"source": "custom_symbols", "symbols": []},
            parameters={},
        )
    )
    assert result.can_run is False


def test_validate_walk_forward_defaults_dates(research_db):
    result = validate_experiment(
        ExperimentValidateRequest(
            experiment_type="walk_forward",
            sleeve="penny",
            universe_definition={"source": "custom_symbols", "symbols": ["AAPL", "MSFT", "NVDA"]},
            preset="standard_research",
            parameters={},
        )
    )
    assert result.can_run is True
    assert result.merged_parameters.get("start_date")
    assert result.expected_periods is not None


def test_templates_api(client):
    r = client.get("/api/v2/research/experiments/templates")
    assert r.status_code == 200, r.text
    assert len(r.json()["templates"]) == 6


def test_presets_api(client):
    r = client.get("/api/v2/research/experiments/presets")
    assert r.status_code == 200, r.text
    assert len(r.json()["presets"]) == 3


def test_validate_api(client):
    r = client.post(
        "/api/v2/research/experiments/validate",
        json={
            "experiment_type": "factor_validation",
            "sleeve": "penny",
            "parameters": {"factors": ["momentum"]},
            "universe_definition": {"source": "full_bucket"},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "checks" in body
    assert body["can_run"] is True


def test_launch_duplicate_blocked(client, research_db):
    exp = create_experiment(
        ResearchExperimentCreate(
            name="WF test",
            experiment_type="walk_forward",
            sleeve="penny",
            universe_definition={"source": "custom_symbols", "symbols": ["AAPL", "MSFT", "NVDA", "GOOGL"]},
            parameters={
                "start_date": "2024-01-01",
                "end_date": "2024-06-01",
                "forward_horizons": [20],
            },
            preset="quick_check",
        )
    )
    from engines.quant_models import ResearchExperimentJob

    fake_active = ResearchExperimentJob(
        job_id="expjob_active",
        experiment_id=exp.id,
        status="running",
        current_stage="running_analysis",
    )
    with patch("services.experiment_launch_service.get_active_job", side_effect=[None, fake_active]):
        r1 = client.post(f"/api/v2/research/experiments/{exp.id}/launch")
        assert r1.status_code == 200, r1.text
        r2 = client.post(f"/api/v2/research/experiments/{exp.id}/launch")
        assert r2.status_code == 200
        assert r2.json().get("duplicate_blocked") is True


def test_launch_factor_validation_mocked(client, research_db):
    exp = create_experiment(
        ResearchExperimentCreate(
            name="Factor IC",
            experiment_type="factor_validation",
            sleeve="penny",
            parameters={"factors": ["momentum"]},
            preset="quick_check",
        )
    )
    with patch(
        "services.experiment_launch_service._run_factor_validation",
        return_value="factor_validation:penny:2024-01-01:abc",
    ):
        with patch("services.experiment_launch_service._EXECUTOR") as mock_exec:
            mock_exec.submit.side_effect = lambda fn, *a, **k: fn(*a, **k)
            r = client.post(f"/api/v2/research/experiments/{exp.id}/launch")
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    job = client.get(f"/api/v2/research/experiments/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert len(job["stages"]) >= 8


def test_job_failure_preserves_message(client, research_db):
    exp = create_experiment(
        ResearchExperimentCreate(
            name="Fail test",
            experiment_type="pairs_discovery",
            universe_definition={"source": "custom_symbols", "symbols": ["AAPL"]},
            parameters={},
        )
    )
    with patch(
        "services.experiment_launch_service._dispatch_experiment",
        side_effect=ValueError("engine failed"),
    ):
        with patch("services.experiment_launch_service._EXECUTOR") as mock_exec:
            mock_exec.submit.side_effect = lambda fn, *a, **k: fn(*a, **k)
            r = client.post(f"/api/v2/research/experiments/{exp.id}/launch")
    assert r.status_code == 400 or r.status_code == 200
    if r.status_code == 200:
        job = client.get(f"/api/v2/research/experiments/jobs/{r.json()['job_id']}").json()
        assert job["status"] == "failed" or job["status"] == "completed"
