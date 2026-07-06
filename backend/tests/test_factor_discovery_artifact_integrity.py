"""Artifact integrity verification tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.artifact_integrity import ArtifactIntegrityError, load_and_verify_artifact_record
from services.factor_discovery.repositories import FactorValidationArtifactRepository
from services.research_json import json_dumps


def test_unknown_schema_version_rejected(isolated_backend_env):
    aid = FactorValidationArtifactRepository().create_closed(
        run_id="run_x",
        artifact_schema_version="unknown-schema",
        validation_engine_version="v1",
        artifact_json=json_dumps({"schema_version": "unknown-schema"}),
        formula_hash="fh",
        plan_hash="ph",
        panel_hash="pn",
        canonical_session_hash="sh",
        execution_hash="eh",
        outcome_hashes_json="{}",
        period_hash="pr",
        validation_config_hash="vc",
        validation_artifact_hash="vah",
        acceptance_status="FAIL",
        multiple_testing_method="bonferroni",
    )
    row = FactorValidationArtifactRepository().get(aid)
    with pytest.raises(ArtifactIntegrityError) as exc:
        load_and_verify_artifact_record(row)
    assert exc.value.code == "ARTIFACT_INTEGRITY_FAILURE"
