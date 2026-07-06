"""Factor definition registry for Factor Discovery UI."""
from __future__ import annotations

from data.db_engine import get_engine
from engines.factor_discovery_models import (
    FactorDefinitionRecord,
    FactorDiscoveryRun,
    FactorValidationArtifactRecord,
)
from services.factor_discovery.errors import FactorDiscoveryError
from services.research_json import json_loads
from sqlalchemy import func
from sqlalchemy.orm import Session


class FactorRegistryService:
    def list_factors(
        self,
        *,
        search: str | None = None,
        lifecycle_status: str | None = None,
        research_family_id: str | None = None,
        direction: str | None = None,
        promising_only: bool = False,
        has_validation: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        with Session(get_engine()) as session:
            subq = (
                session.query(
                    FactorDefinitionRecord.factor_id,
                    func.max(FactorDefinitionRecord.created_at).label("latest_at"),
                )
                .group_by(FactorDefinitionRecord.factor_id)
                .subquery()
            )
            q = session.query(FactorDefinitionRecord).join(
                subq,
                (FactorDefinitionRecord.factor_id == subq.c.factor_id)
                & (FactorDefinitionRecord.created_at == subq.c.latest_at),
            )
            if lifecycle_status:
                q = q.filter(FactorDefinitionRecord.lifecycle_status == lifecycle_status)
            if direction:
                q = q.filter(FactorDefinitionRecord.expected_direction == direction)
            if search:
                needle = f"%{search.lower()}%"
                q = q.filter(
                    (func.lower(FactorDefinitionRecord.display_name).like(needle))
                    | (func.lower(FactorDefinitionRecord.factor_id).like(needle))
                    | (func.lower(FactorDefinitionRecord.canonical_dsl).like(needle))
                )
            rows = q.order_by(FactorDefinitionRecord.created_at.desc()).offset(offset).limit(limit).all()
            total = q.count()

        items = []
        for r in rows:
            fields = json_loads(r.required_fields_json, [])
            latest_run, latest_artifact, acceptance, promising = self._latest_run_artifact(r.factor_id, r.version)
            if has_validation is True and not latest_artifact:
                continue
            if promising_only and not promising:
                continue
            items.append(
                {
                    "factor_id": r.factor_id,
                    "latest_version": r.version,
                    "display_name": r.display_name,
                    "lifecycle_status": r.lifecycle_status,
                    "expected_direction": r.expected_direction,
                    "canonical_dsl_summary": r.canonical_dsl[:120],
                    "required_fields": fields,
                    "research_family_id": None,
                    "hypothesis_id": r.hypothesis_id,
                    "latest_run_id": latest_run,
                    "latest_artifact_id": latest_artifact,
                    "latest_acceptance_status": acceptance,
                    "latest_promising_status": promising,
                    "version_count": self._version_count(r.factor_id),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.created_at.isoformat() if r.created_at else None,
                }
            )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def get_factor_detail(self, factor_id: str) -> dict:
        with Session(get_engine()) as session:
            versions = (
                session.query(FactorDefinitionRecord)
                .filter(FactorDefinitionRecord.factor_id == factor_id)
                .order_by(FactorDefinitionRecord.created_at.asc())
                .all()
            )
        if not versions:
            raise FactorDiscoveryError("FACTOR_NOT_FOUND", factor_id)
        latest = versions[-1]
        return {
            "factor_id": factor_id,
            "display_name": latest.display_name,
            "lifecycle_status": latest.lifecycle_status,
            "hypothesis_id": latest.hypothesis_id,
            "versions": [
                {
                    "version": v.version,
                    "canonical_dsl": v.canonical_dsl,
                    "formula_hash": v.formula_hash,
                    "expected_direction": v.expected_direction,
                    "required_fields": json_loads(v.required_fields_json, []),
                    "lifecycle_status": v.lifecycle_status,
                    "parent_factor_id": v.parent_factor_id,
                    "parent_version": v.parent_version,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ],
            "no_production_activation": True,
        }

    def get_factor_version(self, factor_id: str, version: str) -> dict:
        with Session(get_engine()) as session:
            row = (
                session.query(FactorDefinitionRecord)
                .filter(FactorDefinitionRecord.factor_id == factor_id, FactorDefinitionRecord.version == version)
                .one_or_none()
            )
        if row is None:
            raise FactorDiscoveryError("FACTOR_VERSION_NOT_FOUND", f"{factor_id}@{version}")
        latest_run, latest_artifact, acceptance, promising = self._latest_run_artifact(factor_id, version)
        return {
            "factor_id": factor_id,
            "version": version,
            "display_name": row.display_name,
            "lifecycle_status": row.lifecycle_status,
            "canonical_dsl": row.canonical_dsl,
            "canonical_ast": json_loads(row.canonical_ast_json, {}),
            "formula_hash": row.formula_hash,
            "expected_direction": row.expected_direction,
            "required_fields": json_loads(row.required_fields_json, []),
            "data_source_policy_id": row.data_source_policy_id,
            "latest_run_id": latest_run,
            "latest_artifact_id": latest_artifact,
            "latest_acceptance_status": acceptance,
            "latest_promising_status": promising,
            "no_production_activation": True,
        }

    def _version_count(self, factor_id: str) -> int:
        with Session(get_engine()) as session:
            return session.query(FactorDefinitionRecord).filter(FactorDefinitionRecord.factor_id == factor_id).count()

    def _latest_run_artifact(
        self, factor_id: str, version: str
    ) -> tuple[str | None, str | None, str | None, bool]:
        with Session(get_engine()) as session:
            run = (
                session.query(FactorDiscoveryRun)
                .filter(FactorDiscoveryRun.factor_id == factor_id, FactorDiscoveryRun.factor_version == version)
                .order_by(FactorDiscoveryRun.created_at.desc())
                .first()
            )
            if run is None:
                return None, None, None, False
            artifact = None
            if run.closed_artifact_hash:
                artifact = (
                    session.query(FactorValidationArtifactRecord)
                    .filter(FactorValidationArtifactRecord.validation_artifact_hash == run.closed_artifact_hash)
                    .one_or_none()
                )
            acceptance = artifact.acceptance_status if artifact else None
            promising = False
            if artifact and artifact.acceptance_status == "PASS":
                promising = True
            return run.run_id, artifact.artifact_id if artifact else None, acceptance, promising
