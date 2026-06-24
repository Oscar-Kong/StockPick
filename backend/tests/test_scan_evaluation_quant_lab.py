"""Quant Lab integration tests for scan_evaluation experiment type."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from engines.quant_models import BacktestRun
from models.schemas_research import ExperimentValidateRequest, ResearchExperimentCreate
from services.experiment_job_service import stage_order_for_experiment
from services.experiment_presets_service import list_presets, list_templates, merge_parameters
from services.experiment_validation_service import validate_experiment
from services.research_experiments_service import create_experiment
from services.research_run_detail_service import build_charts, load_detail_payload
from services.research_run_service import adapter_scan_evaluation, index_run_from_store
from services.scan_evaluation_experiment_runner import (
    ScanEvaluationExperimentRunner,
    build_comparison_charts,
    validate_scan_evaluation_params,
)
from data.db_engine import get_engine
from sqlalchemy.orm import Session


@pytest.fixture
def research_db(isolated_backend_env):
    init_quant_db()
    return isolated_backend_env


@pytest.fixture
def client(research_db):
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


def test_scan_evaluation_in_templates(research_db):
    resp = list_templates()
    types = {t.experiment_type for t in resp.templates}
    assert "scan_evaluation" in types
    scan = next(t for t in resp.templates if t.experiment_type == "scan_evaluation")
    assert "algorithm_versions" in scan.required_fields


def test_scan_eval_smoke_preset_listed(research_db):
    resp = list_presets()
    ids = {p.preset_id for p in resp.presets}
    assert "scan_eval_smoke" in ids
    smoke = next(p for p in resp.presets if p.preset_id == "scan_eval_smoke")
    assert smoke.major_evidence_eligible is False


def test_scan_eval_stage_order(research_db):
    stages = stage_order_for_experiment("scan_evaluation")
    assert stages[0] == "validating"
    assert "replaying_scans" in stages
    assert "generating_charts" in stages
    assert stages[-1] == "complete"


def test_validate_scan_evaluation_rejects_bad_dates(research_db):
    result = validate_experiment(
        ExperimentValidateRequest(
            experiment_type="scan_evaluation",
            sleeve="penny",
            preset="scan_eval_smoke",
            parameters={
                "start_date": "2024-06-01",
                "end_date": "2024-03-01",
                "algorithm_versions": ["alphabetical_baseline", "stage_a_v2"],
            },
        )
    )
    assert result.can_run is False
    assert any(c.status == "error" for c in result.checks)


def test_validate_scan_evaluation_unsupported_algorithm(research_db):
    result = validate_experiment(
        ExperimentValidateRequest(
            experiment_type="scan_evaluation",
            sleeve="penny",
            parameters={
                "start_date": "2024-01-01",
                "end_date": "2024-06-01",
                "algorithm_versions": ["not_a_real_version"],
            },
        )
    )
    assert result.can_run is False


def test_validate_scan_evaluation_defaults_algorithms(research_db):
    result = validate_experiment(
        ExperimentValidateRequest(
            experiment_type="scan_evaluation",
            sleeve="penny",
            preset="scan_eval_smoke",
            parameters={"start_date": "2024-03-01", "end_date": "2024-05-01"},
        )
    )
    assert "alphabetical_baseline" in str(result.merged_parameters.get("algorithm_versions"))
    assert any(
        "Evaluation experiments do not automatically modify" in m for m in result.major_limitations
    )


def test_validate_scan_evaluation_params_direct(research_db):
    assert not validate_scan_evaluation_params(
        {"bucket": "penny", "start_date": "2024-01-01", "end_date": "2024-06-01", "algorithm_versions": ["stage_a_v2"]}
    )
    errs = validate_scan_evaluation_params(
        {"bucket": "invalid", "start_date": "2024-01-01", "end_date": "2024-06-01"}
    )
    assert any("bucket" in e for e in errs)


def test_runner_calls_harness_not_production_scan(research_db, tmp_path):
    merged = merge_parameters(
        "scan_evaluation",
        "scan_eval_smoke",
        {"start_date": "2024-03-01", "end_date": "2024-05-01", "output_dir": str(tmp_path / "scan_eval")},
    )
    mock_comparison = {
        "comparison_id": "cmp1",
        "created_at": "2024-06-01T00:00:00",
        "runs": {
            "alphabetical_baseline": {
                "rebalance_count": 2,
                "stage_a_recall": {"mean_recall_at_10": 0.1, "mean_recall_at_20": 0.2, "mean_recall_at_50": 0.3},
                "horizons": {"5": {"mean_hit_rate": 0.5, "mean_rank_ic": 0.02}},
            },
            "stage_a_v2": {
                "rebalance_count": 2,
                "stage_a_recall": {"mean_recall_at_10": 0.4, "mean_recall_at_20": 0.5, "mean_recall_at_50": 0.6},
                "horizons": {"5": {"mean_hit_rate": 0.6, "mean_rank_ic": 0.08}},
            },
        },
        "full_runs": {
            "alphabetical_baseline": {"experiment_id": "baseline", "summary": {}, "candidates": [], "caveats": []},
            "stage_a_v2": {"experiment_id": "stage_a_v2", "summary": {}, "candidates": [], "caveats": []},
        },
    }
    stages: list[str] = []
    with patch(
        "services.scan_evaluation_experiment_runner.compare_algorithm_versions",
        return_value=mock_comparison,
    ) as mock_compare:
        payload = ScanEvaluationExperimentRunner().run(
            bucket="penny",
            merged=merged,
            on_stage=lambda s, st, m: stages.append(s),
        )
    mock_compare.assert_called_once()
    assert payload["run_type"] == "scan_evaluation"
    assert payload["quant_lab"]["mode"] == "comparison"
    charts_path = Path(payload["artifact_paths"]["charts"])
    assert charts_path.is_file()
    charts = json.loads(charts_path.read_text())
    assert charts.get("recall_by_version")


def test_build_charts_from_artifact(research_db):
    comparison = {
        "runs": {
            "alphabetical_baseline": {
                "stage_a_recall": {"mean_recall_at_10": 0.1, "mean_recall_at_20": 0.2, "mean_recall_at_50": 0.3},
                "horizons": {"5": {"mean_hit_rate": 0.5, "mean_rank_ic": 0.02}},
            },
            "stage_a_v2": {
                "stage_a_recall": {"mean_recall_at_10": 0.4, "mean_recall_at_20": 0.5, "mean_recall_at_50": 0.6},
                "horizons": {"5": {"mean_hit_rate": 0.6, "mean_rank_ic": 0.08}},
            },
        },
        "full_runs": {
            "alphabetical_baseline": {"summary": {}},
            "stage_a_v2": {"summary": {}},
        },
    }
    raw = build_comparison_charts(comparison, ["alphabetical_baseline", "stage_a_v2"])
    detail = {"charts": raw, "quant_lab": {"mode": "comparison"}}
    charts = build_charts("scan_evaluation", MagicMock(), detail)
    assert charts
    assert any(c.chart_id.startswith("scan_recall") for c in charts)


def test_persist_and_index_scan_evaluation(research_db):
    run_id = "scan_evaluation:test123"
    metrics = {
        "run_id": run_id,
        "quant_lab": {
            "mode": "comparison",
            "comparison_table": [
                {"algorithm_version": "stage_a_v2", "recall_at_10": 0.4, "rebalance_count": 2},
            ],
            "rebalance_count": 2,
        },
        "caveats": ["Evaluation experiments do not automatically modify the production scan configuration."],
        "algorithm_versions": ["alphabetical_baseline", "stage_a_v2"],
    }
    engine = get_engine()
    with Session(engine) as session:
        session.add(
            BacktestRun(
                run_id=run_id,
                run_type="scan_evaluation",
                config_json=json.dumps({"parameters": {"bucket": "penny", "start_date": "2024-03-01"}}),
                metrics_json=json.dumps(metrics),
            )
        )
        session.commit()
    summary = index_run_from_store(run_id, store="backtest_runs")
    assert summary is not None
    assert summary.run_type == "scan_evaluation"
    assert summary.primary_metrics


def test_adapter_scan_evaluation(research_db):
    run_id = "scan_evaluation:adapter1"
    engine = get_engine()
    with Session(engine) as session:
        session.add(
            BacktestRun(
                run_id=run_id,
                run_type="scan_evaluation",
                config_json=json.dumps({"parameters": {"bucket": "penny"}}),
                metrics_json=json.dumps(
                    {
                        "quant_lab": {
                            "mode": "single",
                            "recall_at_10": 0.25,
                            "rebalance_count": 3,
                        }
                    }
                ),
            )
        )
        session.commit()
    summary = adapter_scan_evaluation(run_id)
    assert summary is not None
    assert summary.run_type == "scan_evaluation"


def test_launch_scan_evaluation_mocked(client, research_db, tmp_path):
    exp = create_experiment(
        ResearchExperimentCreate(
            name="Scan eval test",
            experiment_type="scan_evaluation",
            sleeve="penny",
            preset="scan_eval_smoke",
            universe_definition={"source": "full_bucket"},
            parameters={"start_date": "2024-01-01", "end_date": "2024-06-01"},
        )
    )
    fake_payload = {
        "run_id": "scan_evaluation:mock01",
        "run_type": "scan_evaluation",
        "quant_lab": {"mode": "comparison", "comparison_table": [], "rebalance_count": 1},
        "artifact_paths": {"root": str(tmp_path), "charts": str(tmp_path / "charts.json")},
        "caveats": [],
    }
    (tmp_path / "charts.json").write_text("{}")
    with patch(
        "services.scan_evaluation_experiment_runner.ScanEvaluationExperimentRunner.run",
        return_value=fake_payload,
    ):
        with patch("services.experiment_launch_service._EXECUTOR") as mock_exec:
            mock_exec.submit.side_effect = lambda fn, *a, **k: fn(*a, **k)
            r = client.post(f"/api/v2/research/experiments/{exp.id}/launch")
    assert r.status_code == 200, r.text
    job = client.get(f"/api/v2/research/experiments/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "completed"
    assert job["run_id"] == "scan_evaluation:mock01"
    assert any(s["stage"] == "replaying_scans" for s in job["stages"])


def test_failed_scan_evaluation_exposes_error(client, research_db):
    exp = create_experiment(
        ResearchExperimentCreate(
            name="Scan eval fail",
            experiment_type="scan_evaluation",
            sleeve="penny",
            universe_definition={"source": "full_bucket"},
            parameters={
                "start_date": "2024-01-01",
                "end_date": "2024-06-01",
                "algorithm_versions": ["alphabetical_baseline", "stage_a_v2"],
            },
        )
    )
    with patch(
        "services.scan_evaluation_experiment_runner.ScanEvaluationExperimentRunner.run",
        side_effect=RuntimeError("no overlapping trading dates"),
    ):
        with patch("services.experiment_launch_service._EXECUTOR") as mock_exec:
            mock_exec.submit.side_effect = lambda fn, *a, **k: fn(*a, **k)
            r = client.post(f"/api/v2/research/experiments/{exp.id}/launch")
    assert r.status_code == 200
    job = client.get(f"/api/v2/research/experiments/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "failed"
    assert "overlapping" in (job.get("error_message") or "").lower()


def test_no_lookahead_still_active(research_db):
    from datetime import date

    from services.scan_evaluation_pit import assert_no_lookahead, truncate_history
    import pandas as pd

    hist = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=10).date,
            "close": range(10),
        }
    )
    trimmed = truncate_history(hist, date(2024, 1, 10))
    assert_no_lookahead(trimmed, date(2024, 1, 10))
