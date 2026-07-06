# Factor Discovery — bounded mining loop (Phase 7)

> The mining loop automates bounded research iteration only. It does **not** establish live alpha, authorize sealed-test access, approve factor lifecycle transitions beyond explicit compile/research experiment start, or affect production Scan.

## Phase 8A — Orchestrator completion (shipped)

Phase 8A completes the backend mining loop:

- Full session state machine including `RUNNING_EXPERIMENTS`, `CRITIQUING_RESULTS`, `PREPARING_REVISIONS`, `READY_TO_RELAUNCH`
- Post-validation decision engine (`post_validation_decision.py`)
- Promising-for-human-review policy (`promising_policy.py`)
- Worker leases (`lease_service.py`)
- Launch/monitor separation (`monitor_step.py`)
- Revision generation (`revision_generation.py`)
- Session detail API contracts (`session_detail_service.py`)
- Integrity verification (`integrity_service.py`)

> Phase 8A completes bounded research orchestration. It does not validate a factor for investment use, reveal sealed-test performance, promote lifecycle status, or affect production Scan.

Phase 8B will add the Quant Lab Factor Discovery workspace UI.

## Overview

Phase 7 adds a **human-authorized, budget-bound workflow state machine** under `backend/services/factor_discovery/mining/`. Clients call `advance_mining_session()` with a hard cap of **10 internal steps** per request — there is no unbounded background agent.

```text
authorize session → generate hypotheses → review → translate formulas → review
→ create definition → launch closed experiment → analyze → critique / revision (bounded) → stop
```

## Session modes

| Mode | Config | Behavior |
|------|--------|----------|
| `disabled` | `FACTOR_DISCOVERY_LOOP_MODE=disabled` | All mining routes return 503 |
| `supervised` | Default when loop enabled | Requires human approval before experiments and revisions; pause triggers include `BEFORE_EACH_EXPERIMENT` and `BEFORE_EACH_REVISION` |
| `bounded_auto` | Explicit authorization only | May auto-launch within immutable session policy when `auto_policy` permits; never upgrades from supervised silently |

## Feature flags

| Flag | Default |
|------|---------|
| `FACTOR_DISCOVERY_LOOP_ENABLED` | `false` |
| `FACTOR_DISCOVERY_LOOP_MODE` | `disabled` |
| `FACTOR_DISCOVERY_ENABLED` | `false` (required) |
| `FACTOR_DISCOVERY_LLM_ENABLED` | `false` (required) |

Enabling the loop does **not** enable sealed-test access or Scan integration.

## Persistence

| Table | Entity |
|-------|--------|
| `factor_mining_sessions` | Immutable authorized config, budgets, usage, summary |
| `factor_mining_lineages` | Hypothesis → formula revision chain |
| `factor_mining_events` | Append-only workflow audit |
| `factor_mining_evaluations` | Session ↔ run ↔ artifact links |
| `factor_mining_exposures` | Validation-data exposure ledger |

ORM: `backend/engines/factor_discovery_models.py`

## Session state machine

States include `DRAFT`, `AWAITING_AUTHORIZATION`, `AUTHORIZED`, `GENERATING_HYPOTHESES`, `AWAITING_HYPOTHESIS_REVIEW`, `TRANSLATING_FORMULAS`, `AWAITING_FORMULA_REVIEW`, `READY_TO_LAUNCH`, `RUNNING_EXPERIMENTS`, `ANALYZING_RESULTS`, `AWAITING_REVISION_REVIEW`, `PAUSED`, `BUDGET_EXHAUSTED`, `COMPLETED`, `CANCELLED`, `FAILED`.

Authoritative transitions: `mining/state_machine.py`. Terminal states cannot resume except via explicit recovery policy on non-terminal interruptions.

## API

Base: `/api/v2/research/factor-discovery/mining/sessions` (503 when loop disabled).

See [API_REFERENCE.md](../API_REFERENCE.md) — Factor Discovery mining section.

## Orchestrator

`FactorMiningOrchestrator.advance()` coordinates existing Phase 6B LLM services and `FactorDiscoveryExperimentRunner` — it does not reimplement parser, compiler, validation, or lifecycle promotion.

## Phase 7 non-goals

- Frontend workspace
- Sealed-test opening
- Automatic lifecycle promotion (`PROMISING`, `VALIDATED`, `PAPER`, `PRODUCTION`)
- Production Scan integration
- Unbounded provider calls or dynamic budget increases

## Phase 8 prerequisites

- Read-only mining session UI with hypothesis/formula review cards
- Event timeline and pause/resume controls
- No automatic sealed access or lifecycle promotion from UI

## Related

- [factor-discovery-mining-budgets.md](./factor-discovery-mining-budgets.md)
- [factor-discovery-validation-exposure-policy.md](./factor-discovery-validation-exposure-policy.md)
- [factor-discovery-revision-policy.md](./factor-discovery-revision-policy.md)
- [factor-discovery-mining-recovery.md](./factor-discovery-mining-recovery.md)
