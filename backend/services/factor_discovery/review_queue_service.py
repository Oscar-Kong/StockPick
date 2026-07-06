"""Aggregated review queue for Factor Discovery mining sessions."""
from __future__ import annotations

from data.db_engine import get_engine
from engines.factor_discovery_models import FactorLlmCandidate, FactorMiningLineage, FactorMiningSession
from services.factor_discovery.llm.models import CandidateType, ReviewStatus
from services.factor_discovery.mining.models import LineageStatus
from services.research_json import json_loads
from sqlalchemy.orm import Session


class FactorReviewQueueService:
    def list_queue(
        self,
        *,
        review_type: str | None = None,
        session_id: str | None = None,
        research_family_id: str | None = None,
        promising_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        items: list[dict] = []

        with Session(get_engine()) as session:
            q = session.query(FactorLlmCandidate).filter(
                FactorLlmCandidate.review_status == ReviewStatus.PENDING_REVIEW.value,
                FactorLlmCandidate.candidate_type.in_(
                    [CandidateType.HYPOTHESIS.value, CandidateType.FORMULA.value]
                ),
            )
            if research_family_id:
                q = q.filter(FactorLlmCandidate.research_family_id == research_family_id)
            candidates = q.order_by(FactorLlmCandidate.created_at.asc()).all()

            for c in candidates:
                ctype = "hypothesis" if c.candidate_type == CandidateType.HYPOTHESIS.value else "formula"
                if review_type and review_type != ctype:
                    continue
                sid, sname, sv = self._resolve_session(session, c.candidate_id)
                if session_id and sid != session_id:
                    continue
                data = json_loads(c.candidate_json, {})
                name = data.get("candidate_name") or data.get("proposed_factor_name") or c.candidate_id
                items.append(
                    {
                        "review_type": ctype,
                        "candidate_id": c.candidate_id,
                        "candidate_name": name,
                        "session_id": sid,
                        "session_name": sname,
                        "state_version": sv,
                        "research_family_id": c.research_family_id,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "review_reason": "Human review required",
                        "warning_count": len(data.get("known_risks", []) or data.get("compiler_warnings", [])),
                        "risk_level": "medium",
                    }
                )

            if not review_type or review_type == "revision":
                rev_candidates = (
                    session.query(FactorLlmCandidate)
                    .filter(
                        FactorLlmCandidate.review_status == ReviewStatus.PENDING_REVIEW.value,
                        FactorLlmCandidate.candidate_type == CandidateType.FORMULA.value,
                    )
                    .all()
                )
                for c in rev_candidates:
                    proposal = None
                    from engines.factor_discovery_models import FactorMiningRevisionProposal

                    proposal = (
                        session.query(FactorMiningRevisionProposal)
                        .filter(FactorMiningRevisionProposal.child_formula_candidate_id == c.candidate_id)
                        .one_or_none()
                    )
                    if proposal is None:
                        continue
                    sid, sname, sv = self._resolve_session(session, c.candidate_id)
                    if session_id and sid != session_id:
                        continue
                    data = json_loads(c.candidate_json, {})
                    items.append(
                        {
                            "review_type": "revision",
                            "candidate_id": c.candidate_id,
                            "candidate_name": data.get("proposed_factor_name") or c.candidate_id,
                            "session_id": sid,
                            "session_name": sname,
                            "state_version": sv,
                            "research_family_id": c.research_family_id,
                            "created_at": c.created_at.isoformat() if c.created_at else None,
                            "review_reason": "Revision approval required",
                            "warning_count": 0,
                            "risk_level": "medium",
                        }
                    )

            if promising_only or not review_type or review_type == "promising":
                promising = (
                    session.query(FactorMiningLineage)
                    .filter(FactorMiningLineage.status == LineageStatus.PROMISING_FOR_HUMAN_REVIEW.value)
                    .all()
                )
                for lin in promising:
                    sess = session.get(FactorMiningSession, lin.session_id)
                    if session_id and lin.session_id != session_id:
                        continue
                    if research_family_id and sess and sess.research_family_id != research_family_id:
                        continue
                    items.append(
                        {
                            "review_type": "promising",
                            "candidate_id": lin.lineage_id,
                            "candidate_name": f"Promising lineage {lin.lineage_id[:8]}",
                            "session_id": lin.session_id,
                            "session_name": sess.research_objective[:80] if sess else None,
                            "state_version": sess.state_version if sess else None,
                            "research_family_id": sess.research_family_id if sess else None,
                            "lineage_id": lin.lineage_id,
                            "artifact_id": lin.best_artifact_id,
                            "created_at": lin.updated_at.isoformat() if lin.updated_at else None,
                            "review_reason": "Promising research evidence — human review",
                            "warning_count": 0,
                            "risk_level": "low",
                        }
                    )

        items.sort(key=lambda x: x.get("created_at") or "")
        page = items[offset : offset + limit]
        return {"items": page, "total": len(items), "limit": limit, "offset": offset}

    def _resolve_session(self, session, candidate_id: str) -> tuple[str | None, str | None, int | None]:
        lineages = session.query(FactorMiningLineage).filter(
            (FactorMiningLineage.origin_hypothesis_candidate_id == candidate_id)
            | (FactorMiningLineage.current_formula_candidate_id == candidate_id)
        ).all()
        if not lineages:
            return None, None, None
        sid = lineages[0].session_id
        row = session.get(FactorMiningSession, sid)
        if row is None:
            return sid, None, None
        return sid, row.research_objective[:80], row.state_version
