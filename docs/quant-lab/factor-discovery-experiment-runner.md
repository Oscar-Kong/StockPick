# Factor Discovery Experiment Runner (Phase 5)

Orchestration lives in `backend/services/factor_discovery/experiment_runner.py`, wired from `experiment_launch_service._run_factor_discovery`.

## Stages

`validating_request` → `loading_factor_definition` → `compiling_factor` → `resolving_data_snapshot` → `validating_pit_universe` → `executing_factor` → `generating_outcomes` → `resolving_periods` → `validating_discovery` → `validating_holdout` → `running_walk_forward` → `evaluating_acceptance` → `persisting_artifact` → `indexing_result` → `complete`.

Sealed-test computation is **not** included in the normal runner.

## Data provider

`FactorResearchDataProvider` protocol (`backend/services/factor_discovery/data_provider.py`):

- Production runtime: `DisabledFactorResearchDataProvider` → `FACTOR_RESEARCH_DATA_PROVIDER_NOT_CONFIGURED`
- Tests: `FixtureFactorResearchDataProvider` via `fixture_builder` injection
- Empty PIT universe: rejected with `EMPTY_PIT_UNIVERSE` (no passthrough)

## Research Results

Runs index through `adapter_factor_discovery` in `backend/services/factor_discovery/research_run_adapter.py`. Detail payloads load via `research_run_detail_service` for store `factor_discovery_runs`.

## Failure persistence

Every failed stage updates `factor_discovery_runs` and appends to `factor_discovery_attempts`. No synthetic success artifacts.

## Feature flag

`FACTOR_DISCOVERY_ENABLED=false` by default. Enabling allows launch and API routes; it does not modify Scan or OpenAlpha.

A persisted validation pass is research evidence only. It does not authorize paper trading, production Scan use, or production lifecycle promotion.
