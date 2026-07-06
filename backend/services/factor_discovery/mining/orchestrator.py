"""Bounded mining loop orchestrator."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import config as app_config
from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit, FactorLifecycleStatus
from services.factor_discovery.artifact_integrity import load_and_verify_artifact_record
from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.definition_service import FactorDefinitionFromLlmService
from services.factor_discovery.llm.hypothesis_service import FactorHypothesisGenerationService
from services.factor_discovery.llm.models import FactorResearchRequest, ReviewStatus
from services.factor_discovery.lifecycle_service import FactorLifecycleService, LifecycleTransitionRequest
from services.factor_discovery.mining.budget_service import check_budget, load_usage, reserve_usage
from services.factor_discovery.mining.deduplication import MiningDeduplicationService
from services.factor_discovery.mining.errors import (
    MiningBudgetExceededError,
    MiningPauseRequiredError,
    MiningSessionNotFoundError,
    MiningSessionStateError,
    MiningValidationExposureExceededError,
)
from services.factor_discovery.mining.exposure_service import MiningExposureService
from services.factor_discovery.mining.lease_service import MiningLeaseService
from services.factor_discovery.mining.models import (
    ContextTier,
    FactorMiningAutoPolicy,
    FactorMiningBudgetPolicy,
    FactorMiningPausePolicy,
    FactorMiningStoppingPolicy,
    LineageStatus,
    MiningAdvanceResult,
    MiningSessionStatus,
    PauseTrigger,
    PostValidationAction,
)
from services.factor_discovery.mining.monitor_step import MiningMonitorStep
from services.factor_discovery.mining.policies import require_mining_capabilities
from services.factor_discovery.mining.post_validation_decision import decide_post_validation
from services.factor_discovery.mining.repositories import (
    FactorMiningEvaluationRepository,
    FactorMiningEventRepository,
    FactorMiningLineageRepository,
    FactorMiningRevisionProposalRepository,
    FactorMiningSessionRepository,
)
from services.factor_discovery.mining.revision_generation import MiningRevisionGenerationService
from services.factor_discovery.mining.session_detail_service import FactorMiningSessionDetailService
from services.factor_discovery.mining.state_machine import is_lineage_active
from services.factor_discovery.mining.stopping_service import MiningStoppingService
from services.factor_discovery.mining.summary_service import FactorMiningSummaryService
from services.factor_discovery.multiple_testing_service import derive_family_size
from services.factor_discovery.repositories import (
    FactorAttemptLedgerRepository,
    FactorDiscoveryRunRepository,
    FactorValidationArtifactRepository,
)
from services.research_json import json_dumps, json_loads


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactorMiningOrchestrator:
    MAX_STEPS = 10

    def __init__(
        self,
        *,
        hypothesis_service=None,
        formula_service=None,
        experiment_runner=None,
        llm_client=None,
    ) -> None:
        self._sessions = FactorMiningSessionRepository()
        self._events = FactorMiningEventRepository()
        self._lineages = FactorMiningLineageRepository()
        self._evaluations = FactorMiningEvaluationRepository()
        self._proposals = FactorMiningRevisionProposalRepository()
        self._candidates = FactorLlmCandidateRepository()
        self._runs = FactorDiscoveryRunRepository()
        self._attempts = FactorAttemptLedgerRepository()
        self._hypothesis = hypothesis_service or FactorHypothesisGenerationService(llm_client=llm_client)
        self._formula = formula_service
        self._runner = experiment_runner
        self._dedup = MiningDeduplicationService()
        self._exposure = MiningExposureService()
        self._stopping = MiningStoppingService()
        self._summary = FactorMiningSummaryService()
        self._lifecycle = FactorLifecycleService()
        self._monitor = MiningMonitorStep()
        self._revision_gen = MiningRevisionGenerationService()
        self._detail = FactorMiningSessionDetailService()
        self._lease = MiningLeaseService()

    def advance(
        self,
        session_id: str,
        *,
        maximum_steps: int = 1,
        actor: str = "api",
        expected_state_version: int | None = None,
        worker_id: str | None = None,
    ) -> MiningAdvanceResult:
        require_mining_capabilities()
        maximum_steps = min(max(maximum_steps, 1), min(self.MAX_STEPS, app_config.FACTOR_DISCOVERY_LOOP_MAX_ADVANCE_STEPS))
        row = self._sessions.get(session_id)
        if row is None:
            raise MiningSessionNotFoundError("SESSION_NOT_FOUND", session_id)
        if expected_state_version is not None and row.state_version != expected_state_version:
            from services.factor_discovery.mining.errors import MiningConcurrencyConflictError

            raise MiningConcurrencyConflictError("STATE_VERSION_CONFLICT", str(expected_state_version))
        if row.status in {s.value for s in (
            MiningSessionStatus.COMPLETED,
            MiningSessionStatus.CANCELLED,
            MiningSessionStatus.BUDGET_EXHAUSTED,
            MiningSessionStatus.FAILED,
        )}:
            raise MiningSessionStateError("SESSION_TERMINAL", row.status)

        prior_status = row.status
        lease_token = None
        wid = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        try:
            lease_token = self._lease.acquire(session_id, worker_id=wid)
            events: list[str] = []
            steps_attempted = 0
            steps = 0
            paused = False
            pause_reason = None
            state_version = row.state_version
            runs_launched = 0

            while steps < maximum_steps:
                steps_attempted += 1
                row = self._sessions.get(session_id)
                if row is None:
                    break
                if row.status == MiningSessionStatus.CANCELLED.value:
                    break
                status = row.status
                budget = FactorMiningBudgetPolicy.model_validate(json_loads(row.budget_policy_json, {}))
                stopping = FactorMiningStoppingPolicy.model_validate(json_loads(row.stopping_policy_json, {}))
                pause_policy = FactorMiningPausePolicy.model_validate(json_loads(row.pause_policy_json, {}))
                auto = FactorMiningAutoPolicy.model_validate(json_loads(row.auto_policy_json, {}))
                usage = load_usage(row.usage_json)

                try:
                    if status == MiningSessionStatus.GENERATING_HYPOTHESES.value:
                        self._step_generate_hypotheses(row, budget, usage, auto, actor)
                        state_version = self._transition(session_id, status, MiningSessionStatus.AWAITING_HYPOTHESIS_REVIEW.value, state_version, actor)
                        if PauseTrigger.EVERY_HYPOTHESIS in pause_policy.triggers or row.session_mode == "supervised":
                            paused, pause_reason = True, "hypothesis_review_required"
                            break
                    elif status == MiningSessionStatus.AWAITING_HYPOTHESIS_REVIEW.value:
                        if not self._has_approved_hypothesis(session_id):
                            paused, pause_reason = True, "awaiting_hypothesis_approval"
                            break
                        state_version = self._transition(session_id, status, MiningSessionStatus.TRANSLATING_FORMULAS.value, state_version, actor)
                    elif status == MiningSessionStatus.TRANSLATING_FORMULAS.value:
                        self._step_translate_formulas(row, budget, usage, actor)
                        state_version = self._transition(session_id, status, MiningSessionStatus.AWAITING_FORMULA_REVIEW.value, state_version, actor)
                        if PauseTrigger.EVERY_FORMULA in pause_policy.triggers or row.session_mode == "supervised":
                            paused, pause_reason = True, "formula_review_required"
                            break
                    elif status == MiningSessionStatus.AWAITING_FORMULA_REVIEW.value:
                        if not self._has_approved_formula(session_id):
                            paused, pause_reason = True, "awaiting_formula_approval"
                            break
                        self._step_create_definitions(row, actor, auto)
                        state_version = self._transition(session_id, status, MiningSessionStatus.READY_TO_LAUNCH.value, state_version, actor)
                        if PauseTrigger.BEFORE_EACH_EXPERIMENT in pause_policy.triggers or row.session_mode == "supervised":
                            paused, pause_reason = True, "experiment_launch_approval_required"
                            break
                    elif status in {MiningSessionStatus.READY_TO_LAUNCH.value, MiningSessionStatus.READY_TO_RELAUNCH.value}:
                        launched = self._step_launch_experiment(row, budget, usage, actor)
                        events.append("experiment_launched")
                        runs_launched += 1
                        state_version = self._transition(session_id, status, MiningSessionStatus.RUNNING_EXPERIMENTS.value, state_version, actor)
                    elif status == MiningSessionStatus.RUNNING_EXPERIMENTS.value:
                        done = self._step_monitor_experiments(row, session_cancelled=row.status == MiningSessionStatus.CANCELLED.value)
                        if not done:
                            break
                        events.append("experiment_monitored")
                        state_version = self._transition(session_id, status, MiningSessionStatus.ANALYZING_RESULTS.value, state_version, actor)
                    elif status == MiningSessionStatus.ANALYZING_RESULTS.value:
                        next_status, lineage_events = self._step_analyze_results(row, actor, auto, pause_policy, budget)
                        events.extend(lineage_events)
                        state_version = self._transition(session_id, status, next_status, state_version, actor)
                        if next_status == MiningSessionStatus.PAUSED.value:
                            paused, pause_reason = True, row.pause_reason or "policy_pause"
                            break
                        if next_status == MiningSessionStatus.AWAITING_REVISION_REVIEW.value and row.session_mode == "supervised":
                            paused, pause_reason = True, "revision_review_required"
                            break
                    elif status == MiningSessionStatus.CRITIQUING_RESULTS.value:
                        state_version = self._transition(session_id, status, MiningSessionStatus.PREPARING_REVISIONS.value, state_version, actor)
                    elif status == MiningSessionStatus.PREPARING_REVISIONS.value:
                        self._step_prepare_revisions(row, budget, auto, actor)
                        events.append("revision_proposed")
                        target = MiningSessionStatus.READY_TO_RELAUNCH.value if auto.auto_launch_revisions and auto.auto_approve_revisions else MiningSessionStatus.AWAITING_REVISION_REVIEW.value
                        state_version = self._transition(session_id, status, target, state_version, actor)
                        if target == MiningSessionStatus.AWAITING_REVISION_REVIEW.value and row.session_mode == "supervised":
                            paused, pause_reason = True, "revision_review_required"
                            break
                    elif status == MiningSessionStatus.AWAITING_REVISION_REVIEW.value:
                        if not self._has_approved_revision(session_id):
                            paused, pause_reason = True, "awaiting_revision_approval"
                            break
                        self._step_apply_approved_revision(row, actor, auto)
                        state_version = self._transition(session_id, status, MiningSessionStatus.READY_TO_RELAUNCH.value, state_version, actor)
                        if row.session_mode == "supervised":
                            paused, pause_reason = True, "experiment_launch_approval_required"
                            break
                    else:
                        break

                    steps += 1
                    row = self._sessions.get(session_id)
                    if row:
                        decision = self._stopping.evaluate(
                            session_id=session_id,
                            session_status=row.status,
                            stopping_policy=stopping,
                            budget=budget,
                            usage=load_usage(row.usage_json),
                        )
                        if decision.should_stop and decision.session_terminal_status:
                            state_version = self._transition(
                                session_id,
                                row.status,
                                decision.session_terminal_status.value,
                                state_version,
                                actor,
                                completed_at=_utcnow(),
                                terminal_reason=decision.reason_codes[0] if decision.reason_codes else "complete",
                            )
                            self._summary.build_summary(session_id)
                            return self._result(session_id, prior_status, state_version, steps_attempted, steps, events, paused, pause_reason, terminal=True, runs_launched=runs_launched)
                        if decision.should_pause and not paused:
                            paused, pause_reason = True, decision.reason_codes[0] if decision.reason_codes else "policy_pause"
                            self._sessions.set_pause_reason(session_id, pause_reason)
                            break
                except MiningBudgetExceededError as exc:
                    state_version = self._transition(session_id, row.status, MiningSessionStatus.BUDGET_EXHAUSTED.value, state_version, actor, terminal_reason=str(exc.message)[:500])
                    return self._result(session_id, prior_status, state_version, steps_attempted, steps, events, False, None, terminal=True, terminal_reason=str(exc.message), runs_launched=runs_launched)
                except MiningPauseRequiredError as exc:
                    paused, pause_reason = True, exc.message
                    break
                except MiningValidationExposureExceededError as exc:
                    paused, pause_reason = True, str(exc.message)
                    self._sessions.set_pause_reason(session_id, pause_reason)
                    break

            row = self._sessions.get(session_id)
            terminal = row.status in {MiningSessionStatus.COMPLETED.value, MiningSessionStatus.BUDGET_EXHAUSTED.value, MiningSessionStatus.CANCELLED.value, MiningSessionStatus.FAILED.value} if row else False
            if row and not terminal and not paused and self._session_idle(session_id):
                state_version = self._transition(session_id, row.status, MiningSessionStatus.COMPLETED.value, state_version, actor, completed_at=_utcnow())
                self._summary.build_summary(session_id)
                terminal = True
            return self._result(session_id, prior_status, state_version, steps_attempted, steps, events, paused, pause_reason, terminal=terminal, runs_launched=runs_launched)
        finally:
            if lease_token:
                try:
                    self._lease.release(session_id, worker_id=wid, lease_token=lease_token)
                except Exception:
                    pass

    def _result(self, session_id, prior_status, state_version, steps_attempted, steps_executed, events, paused, pause_reason, *, terminal=False, terminal_reason=None, runs_launched=0):
        detail = self._detail.get_session_detail(session_id)
        return MiningAdvanceResult(
            session_id=session_id,
            prior_status=prior_status,
            status=detail["status"],
            state_version=state_version,
            steps_attempted=steps_attempted,
            steps_executed=steps_executed,
            events=events,
            paused=paused,
            pause_reason=pause_reason,
            terminal=terminal,
            terminal_reason=terminal_reason,
            active_lineages=detail["active_lineage_count"],
            pending_review_count=detail["pending_approval_count"],
            runs_awaiting_completion=sum(1 for l in detail["lineages"] if l["status"] == LineageStatus.RUNNING.value),
            budget_remaining=detail["budget_remaining"],
            next_allowed_actions=[k for k, v in detail["allowed_actions"].items() if v],
        )

    def _transition(self, session_id: str, prev: str, new: str, version: int, actor: str, **updates) -> int:
        new_version = self._sessions.transition(session_id, new_status=new, expected_version=version, **updates)
        self._events.append(
            session_id=session_id,
            event_type="STATE_TRANSITION",
            actor_type="system",
            actor_identifier=actor,
            previous_state=prev,
            new_state=new,
        )
        return new_version

    def _session_idle(self, session_id: str) -> bool:
        lineages = self._lineages.list_for_session(session_id)
        return not any(is_lineage_active(l.status) for l in lineages)

    def _step_generate_hypotheses(self, row, budget, usage, auto, actor) -> None:
        check_budget(budget, usage, operation="hypothesis_generation")
        norm = json_loads(row.normalized_request_json, {})
        req = FactorResearchRequest(
            research_objective=norm["research_objective"],
            intended_universe=norm.get("intended_universe", "research"),
            holding_period_sessions=norm.get("holding_period_sessions"),
            rebalance_frequency=norm.get("rebalance_frequency"),
            candidate_count=norm.get("candidate_count", 5),
            actor=actor,
        )
        result = self._hypothesis.generate(req, research_family_id=row.research_family_id)
        usage = reserve_usage(usage, "hypothesis_generation")
        usage = reserve_usage(usage, "hypothesis")
        usage = reserve_usage(usage, "llm")
        for cid in result.get("candidate_ids", []):
            self._lineages.create(session_id=row.session_id, origin_hypothesis_candidate_id=cid, status=LineageStatus.HYPOTHESIS_PENDING.value)
            if auto.auto_accept_executable_hypotheses:
                cand = self._candidates.get(cid)
                if cand and cand.validation_status == "EXECUTABLE":
                    from services.factor_discovery.llm.review_service import FactorLlmReviewService

                    FactorLlmReviewService().approve_hypothesis(cid, actor=actor, reason="auto_accept_executable per session policy")
                    usage = reserve_usage(usage, "hypothesis_approved")
        self._sessions.update_usage(row.session_id, usage.model_dump())

    def _step_translate_formulas(self, row, budget, usage, actor) -> None:
        from services.factor_discovery.llm.formula_translation_service import FactorFormulaTranslationService

        formula_svc = self._formula or FactorFormulaTranslationService()
        for lin in self._lineages.list_for_session(row.session_id):
            hyp = self._candidates.get(lin.origin_hypothesis_candidate_id)
            if hyp is None or hyp.review_status != ReviewStatus.APPROVED.value:
                continue
            check_budget(budget, usage, operation="formula")
            out = formula_svc.translate(lin.origin_hypothesis_candidate_id, actor=actor)
            usage = reserve_usage(usage, "formula")
            usage = reserve_usage(usage, "llm")
            self._lineages.update(lin.lineage_id, current_formula_candidate_id=out.get("formula_candidate_id"), status=LineageStatus.FORMULA_REVIEW_PENDING.value)
        self._sessions.update_usage(row.session_id, usage.model_dump())

    def _step_create_definitions(self, row, actor, auto) -> None:
        for lin in self._lineages.list_for_session(row.session_id):
            cid = lin.current_formula_candidate_id
            if not cid:
                continue
            cand = self._candidates.get(cid)
            if cand is None or cand.review_status != ReviewStatus.APPROVED.value or cand.validation_status != "COMPILED_FOR_REVIEW":
                continue
            fid = f"mine_{lin.lineage_id[-8:]}"
            FactorDefinitionFromLlmService().create_definition(cid, factor_id=fid, version="1.0.0", actor=actor, reason="mining session approved formula")
            if auto.auto_compile_definitions:
                def_row = __import__("services.factor_discovery.repositories", fromlist=["FactorDefinitionRepository"]).FactorDefinitionRepository().get(fid, "1.0.0")
                if def_row:
                    self._lifecycle.transition(
                        LifecycleTransitionRequest(
                            factor_id=fid,
                            factor_version="1.0.0",
                            target_status=FactorLifecycleStatus.COMPILED,
                            actor_type="system",
                            actor_identifier=actor,
                            reason=f"mining session {row.session_id} auto-compile",
                            expected_formula_hash=def_row.formula_hash,
                        )
                    )
            self._lineages.update(lin.lineage_id, status=LineageStatus.READY_TO_LAUNCH.value)

    def _step_launch_experiment(self, row, budget, usage, actor) -> dict:
        check_budget(budget, usage, operation="evaluation")
        period = DiscoveryPeriodSplit.model_validate(json_loads(row.period_split_json, {}))
        vconfig = FactorValidationConfig.model_validate(json_loads(row.validation_config_json, {}))
        attempts = self._attempts.list_for_family(row.research_family_id)
        family = derive_family_size(attempts, primary_horizon_sessions=row.primary_horizon_sessions, validation_config_family_id="default_v1")
        for lin in self._lineages.list_for_session(row.session_id):
            if lin.status not in {LineageStatus.READY_TO_LAUNCH.value, LineageStatus.READY_TO_RELAUNCH.value, LineageStatus.REVISION_APPROVED.value}:
                continue
            cand = self._candidates.get(lin.current_formula_candidate_id or "")
            if cand is None or cand.review_status != ReviewStatus.APPROVED.value:
                continue
            data = json_loads(cand.candidate_json, {})
            meta = data.get("compile_meta", {})
            formula_hash_value = meta.get("formula_hash")
            if not formula_hash_value:
                continue
            dup = self._dedup.check_formula_hash(session_id=row.session_id, lineage_id=lin.lineage_id, formula_hash_value=formula_hash_value, revision_round=lin.revision_depth)
            if dup.is_duplicate:
                usage = reserve_usage(usage, "duplicate")
                self._evaluations.create(
                    session_id=row.session_id,
                    lineage_id=lin.lineage_id,
                    formula_candidate_id=cand.candidate_id,
                    formula_hash=formula_hash_value,
                    validation_config_hash=row.validation_config_hash,
                    revision_round=lin.revision_depth,
                    is_duplicate=True,
                    duplicate_of_evaluation_id=dup.existing_evaluation_id,
                )
                self._lineages.update(lin.lineage_id, status=LineageStatus.STOPPED.value, terminal_reason="duplicate_formula")
                self._sessions.update_usage(row.session_id, usage.model_dump())
                continue
            fid = f"mine_{lin.lineage_id[-8:]}"
            idem = f"mining:{row.session_id}:{lin.lineage_id}:{formula_hash_value}:{lin.revision_depth}"
            runner = self._runner or FactorDiscoveryExperimentRunner(
                fixture_builder=lambda: __import__(
                    "tests.fixtures.factor_discovery.validation.validation_panel_builder",
                    fromlist=["build_validation_context"],
                ).build_validation_context()["panel"]
            )
            run = runner.run(
                FactorDiscoveryRunRequest(
                    experiment_id=None,
                    job_id=None,
                    factor_id=fid,
                    factor_version="1.0.0",
                    research_family_id=row.research_family_id,
                    period_split=period,
                    validation_config=vconfig,
                    created_by=actor,
                    idempotency_key=idem,
                    snapshot_id=row.snapshot_id,
                )
            )
            usage = reserve_usage(usage, "evaluation")
            self._evaluations.create(
                session_id=row.session_id,
                lineage_id=lin.lineage_id,
                formula_candidate_id=cand.candidate_id,
                factor_id=fid,
                factor_version="1.0.0",
                run_id=run.get("run_id"),
                artifact_id=run.get("artifact_id"),
                formula_hash=formula_hash_value,
                plan_hash=meta.get("plan_hash"),
                snapshot_id=row.snapshot_id,
                validation_config_hash=row.validation_config_hash,
                revision_round=lin.revision_depth,
                family_size_at_evaluation=family.effective_family_size + 1,
                acceptance_status=run.get("recommended_status"),
            )
            self._lineages.update(lin.lineage_id, status=LineageStatus.RUNNING.value, best_artifact_id=run.get("artifact_id"), root_formula_hash=formula_hash_value)
            self._sessions.update_usage(row.session_id, usage.model_dump())
            return {"run_id": run.get("run_id")}
        raise MiningSessionStateError("NO_LAUNCHABLE_CANDIDATE", "no approved compiled formula")

    def _step_monitor_experiments(self, row, *, session_cancelled: bool) -> bool:
        for lin in self._lineages.list_for_session(row.session_id):
            if lin.status != LineageStatus.RUNNING.value:
                continue
            eval_row = next((e for e in self._evaluations.list_for_lineage(row.session_id, lin.lineage_id) if e.run_id), None)
            if eval_row is None:
                continue
            monitor = self._monitor.inspect_run(eval_row.run_id)
            if not monitor.get("complete") and not monitor.get("failed"):
                return False
            if session_cancelled and monitor.get("complete"):
                self._lineages.update(lin.lineage_id, status=LineageStatus.COMPLETED_AFTER_SESSION_CANCELLATION.value)
                return True
            status = self._monitor.lineage_status_for_monitor(monitor, session_cancelled=session_cancelled)
            self._lineages.update(lin.lineage_id, status=status, best_artifact_id=monitor.get("artifact_id") or lin.best_artifact_id)
        return True

    def _step_analyze_results(self, row, actor, auto, pause_policy, budget) -> tuple[str, list[str]]:
        events: list[str] = []
        next_status = MiningSessionStatus.COMPLETED.value
        usage = load_usage(row.usage_json)
        for lin in self._lineages.list_for_session(row.session_id):
            if lin.status not in {LineageStatus.VALIDATION_COMPLETED.value, LineageStatus.RUN_FAILED.value}:
                continue
            eval_row = next((e for e in self._evaluations.list_for_lineage(row.session_id, lin.lineage_id) if e.artifact_id and not e.is_duplicate), None)
            if eval_row is None:
                self._lineages.update(lin.lineage_id, status=LineageStatus.STOPPED.value, terminal_reason="no_evaluation")
                continue
            artifact_row = FactorValidationArtifactRepository().get(eval_row.artifact_id)
            if artifact_row is None:
                self._lineages.update(lin.lineage_id, status=LineageStatus.STOPPED.value, terminal_reason="artifact_missing")
                continue
            try:
                artifact = load_and_verify_artifact_record(artifact_row)
                integrity_ok = True
            except Exception:
                integrity_ok = False
                artifact = None
            if artifact is None:
                self._lineages.update(lin.lineage_id, status=LineageStatus.STOPPED.value, terminal_reason="integrity_failure")
                events.append("integrity_failure")
                continue
            exposure_available = True
            try:
                self._exposure.check_exposure(
                    session_id=row.session_id,
                    lineage_id=lin.lineage_id,
                    formula_hash=lin.root_formula_hash,
                    budget=budget,
                    context_tier=ContextTier.DISCOVERY_PLUS_VALIDATION_SUMMARY,
                )
            except MiningValidationExposureExceededError:
                exposure_available = False
            decision = decide_post_validation(
                lineage_id=lin.lineage_id,
                evaluation_id=eval_row.evaluation_id,
                artifact=artifact,
                artifact_integrity_ok=integrity_ok,
                revision_depth=lin.revision_depth,
                budget=budget,
                usage_formulas_evaluated=usage.formulas_evaluated,
                exposure_available=exposure_available,
            )
            if decision.recommended_action == PostValidationAction.PAUSE_PROMISING:
                self._lineages.update(lin.lineage_id, status=LineageStatus.PROMISING_FOR_HUMAN_REVIEW.value)
                if pause_policy.pause_on_promising:
                    self._sessions.set_pause_reason(row.session_id, "promising_candidate")
                    return MiningSessionStatus.PAUSED.value, events + ["promising_pause"]
                events.append("promising")
                continue
            if decision.recommended_action == PostValidationAction.REQUEST_CRITIQUE:
                self._lineages.update(lin.lineage_id, status=LineageStatus.CRITIQUE_PENDING.value)
                if lin.revision_depth < budget.max_revision_rounds_per_lineage and exposure_available:
                    return MiningSessionStatus.PREPARING_REVISIONS.value, events + ["critique_path"]
                self._lineages.update(lin.lineage_id, status=LineageStatus.STOPPED.value, terminal_reason="revision_budget_exhausted")
                continue
            if decision.recommended_action == PostValidationAction.STOP_LINEAGE:
                self._lineages.update(lin.lineage_id, status=LineageStatus.STOPPED.value, terminal_reason=decision.reason_codes[0] if decision.reason_codes else "stopped")
                events.append("lineage_stopped")
                continue
            self._lineages.update(lin.lineage_id, status=LineageStatus.STOPPED.value, terminal_reason="no_action")
        if not self._session_idle(row.session_id):
            return MiningSessionStatus.ANALYZING_RESULTS.value, events
        return MiningSessionStatus.COMPLETED.value, events

    def _step_prepare_revisions(self, row, budget, auto, actor) -> None:
        for lin in self._lineages.list_for_session(row.session_id):
            if lin.status != LineageStatus.CRITIQUE_PENDING.value:
                continue
            cand = self._candidates.get(lin.current_formula_candidate_id or "")
            if cand is None:
                continue
            data = json_loads(cand.candidate_json, {})
            parent_dsl = data.get("dsl_source") or data.get("proposed_dsl") or "rank(return_126d)"
            parent_hash = data.get("compile_meta", {}).get("formula_hash") or lin.root_formula_hash or ""
            from services.factor_discovery.mining.critique_step import derive_failure_categories

            artifact_row = FactorValidationArtifactRepository().get(lin.best_artifact_id) if lin.best_artifact_id else None
            categories = []
            if artifact_row:
                artifact = load_and_verify_artifact_record(artifact_row)
                categories = derive_failure_categories(artifact)
            self._revision_gen.propose_from_categories(
                session_id=row.session_id,
                lineage_id=lin.lineage_id,
                parent_candidate_id=cand.candidate_id,
                parent_dsl=parent_dsl,
                parent_formula_hash=parent_hash,
                revision_round=lin.revision_depth + 1,
                categories=categories,
                budget=budget,
            )
            self._lineages.update(
                lin.lineage_id,
                status=LineageStatus.REVISION_REVIEW_PENDING.value if not auto.auto_approve_revisions else LineageStatus.REVISION_APPROVED.value,
                revision_depth=lin.revision_depth + 1,
            )

    def _step_apply_approved_revision(self, row, actor, auto) -> None:
        for lin in self._lineages.list_for_session(row.session_id):
            if lin.status != LineageStatus.REVISION_APPROVED.value:
                continue
            proposals = self._proposals.list_for_lineage(row.session_id, lin.lineage_id)
            if not proposals:
                continue
            prop = proposals[-1]
            proposal = json_loads(prop.proposal_json, {})
            dsl = proposal.get("proposed_dsl")
            if not dsl:
                continue
            from services.factor_discovery.llm.formula_translation_service import FactorFormulaTranslationService
            from engines.factor.discovery.parser import parse_factor_expression
            from engines.factor.discovery.compiler import compile_factor_expression
            from models.schemas_factor_discovery import formula_hash

            parsed = parse_factor_expression(dsl)
            compiled = compile_factor_expression(parsed)
            child_hash = formula_hash(parsed)
            cid = self._candidates.create(
                interaction_id=f"mining_rev_{prop.proposal_id}",
                research_family_id=row.research_family_id,
                candidate_type="FORMULA",
                candidate_sequence=lin.revision_depth,
                candidate_json=json_dumps({"dsl_source": dsl, "compile_meta": {"formula_hash": child_hash, "plan_hash": compiled.plan_hash}}),
                candidate_content_hash=child_hash,
                review_status=ReviewStatus.APPROVED.value,
                validation_status="COMPILED_FOR_REVIEW",
            )
            self._lineages.update(lin.lineage_id, current_formula_candidate_id=cid, status=LineageStatus.READY_TO_RELAUNCH.value)
            if auto.auto_compile_definitions:
                fid = f"mine_{lin.lineage_id[-8:]}"
                FactorDefinitionFromLlmService().create_definition(cid, factor_id=fid, version=f"1.0.{lin.revision_depth}", actor=actor, reason="mining revision")

    def _has_approved_hypothesis(self, session_id: str) -> bool:
        for lin in self._lineages.list_for_session(session_id):
            hyp = self._candidates.get(lin.origin_hypothesis_candidate_id)
            if hyp and hyp.review_status == ReviewStatus.APPROVED.value:
                return True
        return False

    def _has_approved_formula(self, session_id: str) -> bool:
        for lin in self._lineages.list_for_session(session_id):
            if not lin.current_formula_candidate_id:
                continue
            cand = self._candidates.get(lin.current_formula_candidate_id)
            if cand and cand.review_status == ReviewStatus.APPROVED.value and cand.validation_status == "COMPILED_FOR_REVIEW":
                return True
        return False

    def _has_approved_revision(self, session_id: str) -> bool:
        for lin in self._lineages.list_for_session(session_id):
            if lin.status == LineageStatus.REVISION_APPROVED.value:
                return True
            if lin.status == LineageStatus.REVISION_REVIEW_PENDING.value:
                cand = self._candidates.get(lin.current_formula_candidate_id or "")
                if cand and cand.review_status == ReviewStatus.APPROVED.value:
                    self._lineages.update(lin.lineage_id, status=LineageStatus.REVISION_APPROVED.value)
                    return True
        return False
