"""Artifact integrity verification for persisted Factor Discovery validation artifacts."""
from __future__ import annotations

from engines.factor.discovery.validation_hashing import validation_artifact_hash, validation_config_hash
from engines.factor.discovery.validation_models import FactorValidationArtifact, SealedTestAccess
from services.factor_discovery.errors import ArtifactIntegrityError
from services.research_json import json_loads


def load_and_verify_artifact_record(row) -> FactorValidationArtifact:
    if row.artifact_schema_version not in {
        "factor-validation-v1",
        "factor-validation-v2",
        "factor-validation-artifact-v1",
    }:
        raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "unsupported artifact schema version")
    payload = json_loads(row.artifact_json, {})
    artifact = FactorValidationArtifact.model_validate(payload)

    if artifact.schema_version != row.artifact_schema_version:
        raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "schema version mismatch")

    for field, expected in (
        ("formula_hash", row.formula_hash),
        ("plan_hash", row.plan_hash),
        ("panel_hash", row.panel_hash),
        ("execution_hash", row.execution_hash),
        ("validation_config_hash", row.validation_config_hash),
        ("period_resolution_hash", row.period_hash),
        ("validation_artifact_hash", row.validation_artifact_hash),
    ):
        if getattr(artifact, field) != expected:
            raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", f"{field} mismatch")

    if row.canonical_session_hash and artifact.canonical_session_hash != row.canonical_session_hash:
        raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "canonical_session_hash mismatch")

    if row.open_state == "CLOSED":
        if artifact.sealed_test_metrics is not None:
            raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "closed artifact contains sealed metrics")
        if artifact.sealed_test.opened:
            raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "closed artifact marked sealed opened")

    sealed_access = None
    if artifact.sealed_test.opened and row.open_state == "SEALED_OPENED":
        sealed_access = SealedTestAccess(
            authorization_type="manual_research",
            reason="persisted",
            requested_by="system",
            approval_reference="persisted",
            expected_formula_hash=artifact.formula_hash,
            expected_plan_hash=artifact.plan_hash,
        )

    recomputed = validation_artifact_hash(
        formula_hash=artifact.formula_hash,
        plan_hash=artifact.plan_hash,
        execution_hash=artifact.execution_hash,
        outcome_hashes=artifact.outcome_panel_hashes,
        period_resolution_hash=artifact.period_resolution_hash,
        validation_config_hash_value=artifact.validation_config_hash,
        sealed_opened=row.open_state == "SEALED_OPENED",
        sealed_access=sealed_access,
    )
    if recomputed != artifact.validation_artifact_hash:
        raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "validation artifact hash mismatch")

    return artifact


def verify_config_hash(config, stored_hash: str) -> None:
    if validation_config_hash(config) != stored_hash:
        raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "validation config hash mismatch")
