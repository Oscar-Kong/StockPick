"""UI-safe LLM interaction detail for Factor Discovery transparency."""
from __future__ import annotations

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorLlmCandidate
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.llm.interaction_repository import FactorLlmInteractionRepository
from services.research_json import json_loads
from sqlalchemy.orm import Session


class FactorLlmInteractionDetailService:
    def __init__(self) -> None:
        self._interactions = FactorLlmInteractionRepository()

    def get_detail(self, interaction_id: str) -> dict:
        row = self._interactions.get(interaction_id)
        if row is None:
            raise FactorDiscoveryError("INTERACTION_NOT_FOUND", interaction_id)
        with Session(get_engine()) as session:
            candidates = (
                session.query(FactorLlmCandidate)
                .filter(FactorLlmCandidate.interaction_id == interaction_id)
                .all()
            )
        candidate_links = [
            {
                "candidate_id": c.candidate_id,
                "candidate_type": c.candidate_type,
                "review_status": c.review_status,
            }
            for c in candidates
        ]
        structured_output = None
        if candidates:
            structured_output = json_loads(candidates[0].candidate_json, {})
        return {
            "interaction_id": interaction_id,
            "operation_type": row.operation_type,
            "provider_id": row.provider_id,
            "model_id": row.model_id,
            "prompt_template_id": row.prompt_template_id,
            "prompt_template_version": row.prompt_template_version,
            "structured_output_mode": row.response_schema_version,
            "input_token_count": row.input_token_count,
            "output_token_count": row.output_token_count,
            "total_token_count": row.total_token_count,
            "retry_count": row.retry_count,
            "finish_reason": row.finish_reason,
            "status": row.status,
            "error_code": row.error_code,
            "error_summary": row.error_summary,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "prompt_hashes": {
                "system_prompt_hash": row.system_prompt_hash,
                "user_prompt_hash": row.user_prompt_hash,
                "structured_input_hash": row.structured_input_hash,
                "structured_output_hash": row.structured_output_hash,
                "request_payload_hash": row.request_payload_hash,
            },
            "structured_output": structured_output,
            "candidate_links": candidate_links,
            "ai_generated_label": "AI-generated research content",
            "no_raw_secrets": True,
        }
