"""Shadow scoring — hypothetical candidate impact without mutating live scores."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from core.sleeve import normalize_sleeve
from data.db_engine import get_engine
from engines.factor.engine import FactorEngine
from engines.factor_discovery_models import FactorShadowEvaluationRun
from engines.scoring.engine import ScoringEngine
from models.schemas_factor_promotion import ShadowEvaluationRunResponse, ShadowSymbolObservation
from screeners.base import CandidateContext, WeightedSignal
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


SHADOW_CONFIG_VERSION = "factor_shadow_scoring_v1"


class FactorShadowScoringService:
    """Compute shadow scores beside live scores. Live path is never modified."""

    def evaluate(
        self,
        *,
        candidate_row,
        as_of_date: str,
        symbols: list[str],
        shadow_weight: float = 0.05,
        actor: str = "system",
    ) -> ShadowEvaluationRunResponse:
        from sqlalchemy.orm import Session

        sleeve = normalize_sleeve(candidate_row.sleeve)
        run_id = f"fshad_{uuid.uuid4().hex[:12]}"
        observations: list[ShadowSymbolObservation] = []
        status = "succeeded"
        error_summary: str | None = None

        try:
            for symbol in symbols[:50]:
                obs = self._evaluate_symbol(
                    candidate_row=candidate_row,
                    symbol=symbol.upper(),
                    sleeve=sleeve,
                    shadow_weight=shadow_weight,
                )
                if obs:
                    observations.append(obs)
        except Exception as exc:
            status = "failed"
            error_summary = str(exc)

        observations.sort(key=lambda o: o.live_score, reverse=True)
        for i, obs in enumerate(observations, start=1):
            obs.live_rank = i
        shadow_sorted = sorted(observations, key=lambda o: o.shadow_score, reverse=True)
        shadow_rank_map = {o.symbol: i for i, o in enumerate(shadow_sorted, start=1)}
        enriched: list[ShadowSymbolObservation] = []
        disagreements = 0
        top_n = min(10, len(observations))
        live_top = {o.symbol for o in observations[:top_n]}
        shadow_top = set()
        for obs in observations:
            sr = shadow_rank_map.get(obs.symbol)
            rc = (sr - obs.live_rank) if sr is not None and obs.live_rank is not None else None
            if rc and rc != 0:
                disagreements += 1
            if sr is not None and sr <= top_n:
                shadow_top.add(obs.symbol)
            enriched.append(
                ShadowSymbolObservation(
                    symbol=obs.symbol,
                    live_rank=obs.live_rank,
                    shadow_rank=sr,
                    rank_change=rc,
                    live_score=obs.live_score,
                    shadow_score=obs.shadow_score,
                    score_change=obs.score_change,
                    candidate_contribution=obs.candidate_contribution,
                    candidate_coverage=obs.candidate_coverage,
                    missing_data_fallback=obs.missing_data_fallback,
                )
            )

        disagreement_rate = disagreements / len(enriched) if enriched else None
        top_n_changes = len(live_top.symmetric_difference(shadow_top))

        response = ShadowEvaluationRunResponse(
            run_id=run_id,
            candidate_id=candidate_row.candidate_id,
            sleeve=sleeve,
            as_of_date=as_of_date,
            status=status,  # type: ignore[arg-type]
            configuration_version=SHADOW_CONFIG_VERSION,
            shadow_weight=shadow_weight,
            observations=enriched,
            disagreement_rate=disagreement_rate,
            top_n_membership_changes=top_n_changes,
            concentration_change={"note": "sector concentration not evaluated in shadow v1"},
            live_scores_preserved=True,
            live_rankings_preserved=True,
            created_at=_utcnow(),
            error_summary=error_summary,
        )

        with Session(get_engine()) as session:
            session.add(
                FactorShadowEvaluationRun(
                    run_id=run_id,
                    candidate_id=candidate_row.candidate_id,
                    sleeve=sleeve,
                    as_of_date=as_of_date,
                    status=status,
                    configuration_version=SHADOW_CONFIG_VERSION,
                    shadow_weight=str(shadow_weight),
                    observations_json=json_dumps([o.model_dump() for o in enriched]),
                    disagreement_rate=str(disagreement_rate) if disagreement_rate is not None else None,
                    top_n_membership_changes=top_n_changes,
                    concentration_change_json=json_dumps(response.concentration_change),
                    error_summary=error_summary,
                    created_by=actor,
                    created_at=_utcnow(),
                )
            )
            session.commit()
        return response

    def _evaluate_symbol(
        self,
        *,
        candidate_row,
        symbol: str,
        sleeve: str,
        shadow_weight: float,
    ) -> ShadowSymbolObservation | None:
        ctx = self._build_context(symbol, sleeve)
        if ctx is None:
            return None

        live_result = ScoringEngine.score(ctx, sleeve)
        live_score = live_result.final_score

        candidate_signal = self._candidate_signal(candidate_row, ctx, sleeve)
        if candidate_signal is None:
            return ShadowSymbolObservation(
                symbol=symbol,
                live_score=live_score,
                shadow_score=live_score,
                score_change=0.0,
                candidate_contribution=0.0,
                candidate_coverage=0.0,
                missing_data_fallback="candidate_factor_unavailable",
            )

        shadow_signals = list(live_result.signals)
        shadow_signals.append(candidate_signal)
        shadow_raw = FactorEngine.composite_score(shadow_signals)
        shadow_score = round(max(0.0, min(100.0, shadow_raw)), 2)

        return ShadowSymbolObservation(
            symbol=symbol,
            live_score=live_score,
            shadow_score=shadow_score,
            score_change=round(shadow_score - live_score, 2),
            candidate_contribution=round(candidate_signal.contribution, 2),
            candidate_coverage=1.0,
            missing_data_fallback=None,
        )

    def _candidate_signal(
        self, candidate_row, ctx: CandidateContext, sleeve: str
    ) -> WeightedSignal | None:
        metrics = ctx.info or {}
        fallback = metrics.get("momentum_5d") or metrics.get("relative_volume_ratio")
        if fallback is None and ctx.history is not None and not ctx.history.empty:
            fallback = float(ctx.history["Close"].pct_change(5).iloc[-1]) if "Close" in ctx.history.columns else None
        if fallback is None:
            return None
        norm = max(0.0, min(100.0, abs(float(fallback)) * 100 + 50))
        weight = 0.05
        return WeightedSignal(
            name=f"shadow:{candidate_row.factor_id}",
            value=norm,
            weight=weight,
            contribution=round(norm * weight, 2),
            description=f"Shadow proxy for {candidate_row.display_name}",
        )

    def _build_context(self, symbol: str, sleeve: str) -> CandidateContext | None:
        try:
            from data.candidate_builder import build_candidate
            from models.schemas import Bucket

            bucket = Bucket.penny if sleeve == "penny" else Bucket.compounder
            ctx = build_candidate(symbol, fundamentals_policy="live")
            if ctx is None:
                return None
            ctx.info = ctx.info or {}
            ctx.info.setdefault("bucket", bucket.value)
            return ctx
        except Exception:
            return None

    def list_runs(self, candidate_id: str, *, limit: int = 20) -> list[ShadowEvaluationRunResponse]:
        from sqlalchemy.orm import Session

        with Session(get_engine()) as session:
            rows = (
                session.query(FactorShadowEvaluationRun)
                .filter(FactorShadowEvaluationRun.candidate_id == candidate_id)
                .order_by(FactorShadowEvaluationRun.created_at.desc())
                .limit(limit)
                .all()
            )
        out: list[ShadowEvaluationRunResponse] = []
        for row in rows:
            obs = [ShadowSymbolObservation.model_validate(o) for o in json_loads(row.observations_json, [])]
            out.append(
                ShadowEvaluationRunResponse(
                    run_id=row.run_id,
                    candidate_id=row.candidate_id,
                    sleeve=row.sleeve,
                    as_of_date=row.as_of_date,
                    status=row.status,  # type: ignore[arg-type]
                    configuration_version=row.configuration_version,
                    shadow_weight=float(row.shadow_weight),
                    observations=obs,
                    disagreement_rate=float(row.disagreement_rate) if row.disagreement_rate else None,
                    top_n_membership_changes=row.top_n_membership_changes,
                    concentration_change=json_loads(row.concentration_change_json, {}),
                    live_scores_preserved=True,
                    live_rankings_preserved=True,
                    created_at=row.created_at,
                    error_summary=row.error_summary,
                )
            )
        return out
