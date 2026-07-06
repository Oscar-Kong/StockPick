# Factor Discovery — Implementation Plan

Phased plan minimizing unused abstractions. Adjustments from repository state are called out explicitly.

---

## Sequence overview

| Phase | Focus | Repo adjustment |
|-------|-------|-----------------|
| 0 | Baseline fixes & docs | Fix broken scan_eval test import; complete scan_eval wiring **or** defer explicitly |
| 1 | Contracts & lifecycle | Extend existing `ResearchIdea` / `ResearchExperiment`, not parallel system |
| 2 | Controlled DSL & compiler | **Do not** extend `expr.py` string eval — new AST module |
| 3 | Deterministic factor engine | Extend `quant_core/features.py`, not new pandas framework |
| 4 | Experiment & validation engine | Extend `experiment_launch_service`, reuse `cross_section_metrics()` |
| 5 | Registry & experiment ledger | Extend `FactorDefinition` + `ResearchRunIndex` |
| 6 | LLM research layer | New package; flags default off |
| 7 | Controlled revision loop | Cap revisions; human gate |
| 8 | Quant Lab UI | Extend Experiment Studio |
| 9 | Paper integration | Mirror OpenAlpha gating |
| 10 | Production Scan integration | Extend `FactorEngine` adapter only |
| 11 | Hardening & release gate | Tests, drift monitor, docs |

**Deferred from generic sequence:** Phase 0 added because `scan_evaluation` Quant Lab integration was half-wired and tests failed collection — **resolved 2026-07-01**.

---

## Status (2026-07-01)

| Phase | Status | Notes |
|-------|--------|-------|
| **0** | ✅ Complete | `stage_order_for_experiment()`, full scan_evaluation wiring, 14 tests in `test_scan_evaluation_quant_lab.py` |
| **1** | ✅ Complete | `schemas_factor_discovery.py`, golden fixtures, `FACTOR_DISCOVERY_ENABLED=false`, disabled launch behavior |
| **2** | ✅ Complete | `engines/factor/discovery/` parser, formatter, field registry, compiler; DSL golden fixtures; 116 new tests |
| **3** | ✅ Complete | `compute_factor_panel`, panel contract, derived fields, operator execution, provenance, hashing |
| **4** | ✅ Complete | Validation engine, outcomes, periods, IC/quantile/portfolio/walk-forward, acceptance gate, sealed-test contracts |
| **6B** | ✅ Complete | LLM layer: hypothesis/critique/DSL/interpretation; human review gates; `FACTOR_DISCOVERY_LLM_ENABLED=false` |
| **7** | ✅ Complete | Mining loop, recovery, budgets |
| **8B** | ✅ Complete | Factor Discovery workspace UI |
| **9A** | ✅ Complete | Results integrity, validation UI |
| **9B.1** | ✅ Complete | Staging preflight, supervised pipeline, ~4s real DB preflight, `READY_FOR_EXTENDED_STAGING` |
| **9B.2** | ✅ Complete | Extended staging matrix, `READY_FOR_PROMOTION_REVIEW` |
| **10** | ✅ Complete | Promotion governance + shadow scoring (advisory) |
| **11** | ✅ Complete | Acceptance runner, isolation audit, docs — `PHASE_11_COMPLETE` |

See [FACTOR_RESEARCH_FINAL_ACCEPTANCE.md](../FACTOR_RESEARCH_FINAL_ACCEPTANCE.md).

---

## Phase 0 — Baseline hygiene (1–2 days) ✅ DONE

**Goal:** Trustworthy test baseline and consistent experiment patterns.

### Tasks

1. Fix `tests/test_scan_evaluation_quant_lab.py` import (`stage_order_for_experiment` or update test to use `STAGE_ORDER`).
2. Either wire `scan_evaluation` into `experiment_launch_service._dispatch_experiment()` + `ExperimentType` + `adapter_scan_evaluation`, **or** mark tests `@pytest.mark.skip` with issue reference and document deferral in `SCAN_EVALUATION.md`.
3. Ensure failed experiment jobs appear in Results UI (read `research_experiment_jobs` where `status=failed`).

### Deliverables

- ✅ Green scan_eval Quant Lab tests (`tests/test_scan_evaluation_quant_lab.py` — 14 passed)
- ✅ `adapter_scan_evaluation` in `research_run_service.py`
- ✅ `_run_scan_evaluation` in `experiment_launch_service.py`

### Do not

- Add factor discovery code
- Add migrations

---

## Phase 1 — Contracts & lifecycle (3–5 days) ✅ DONE

**Goal:** Immutable data contracts for hypothesis → definition → run.

### Shipped

1. `backend/models/schemas_factor_discovery.py` — `FactorHypothesis`, discriminated `AstNode`, `FactorDefinition`, `DiscoveryPeriodSplit`, lifecycle helpers, `formula_hash()`
2. `ExperimentType` includes `factor_discovery` (launch disabled) and `scan_evaluation` (enabled)
3. `FACTOR_DISCOVERY_ENABLED` in `config.py` / `.env.example` (default `false`)
4. Golden fixtures: `backend/tests/fixtures/factor_discovery/`
5. Tests: `backend/tests/test_factor_discovery_contracts.py` (29 tests)

### Not in Phase 1 (deferred)

- SQLAlchemy `FactorDiscoveryRun` migration
- Pydantic-only; no DB persistence for discovery runs yet

---

## Phase 1 (original spec) — Contracts & lifecycle (3–5 days)

**Goal:** Immutable data contracts for hypothesis → definition → run.

### Tasks

1. Add `models/schemas_factor_discovery.py`:
   - `FactorHypothesis`, `FactorExpressionAST`, `FactorDiscoveryExperimentConfig`
   - `DiscoveryPeriodSplit` (discovery_end, validation_start, sealed_test_start, sealed_test_end)
2. Extend `ExperimentType` with `factor_discovery`.
3. Extend `ResearchRunType` with `factor_discovery`.
4. Add SQLAlchemy model `FactorDiscoveryRun` in `quant_models.py` (+ `init_quant_db()` migration in implementation PR).
5. Document lifecycle states: `proposed → translated → testing → validated → rejected | approved`.

### Reuse

- `schemas_research.py` patterns
- `ResearchIdea` table (link via `idea_id`)

### Tests

- Pydantic contract round-trip tests
- Lifecycle state transition validation (no LLM)

### Gates

- No runtime LLM
- No Scan changes

---

## Phase 2 — Controlled DSL & compiler (5–8 days) ✅ DONE

**Goal:** Parse and compile a closed expression language — no code execution.

### Shipped

1. `backend/engines/factor/discovery/` — `errors.py`, `limits.py`, `tokenizer.py`, `parser.py`, `formatter.py`, `field_registry.py`, `compiler.py`
2. DSL version `factor-dsl-v1`; `CompiledFactorPlan` (non-executable)
3. Field registry + `research_adjusted_daily_v1` data-source policy contract
4. Golden DSL fixtures alongside JSON AST fixtures
5. Tests: `test_factor_discovery_dsl_parser.py`, `test_factor_discovery_compiler.py`, `test_factor_discovery_field_registry.py`
6. Docs: [factor-discovery-dsl.md](./factor-discovery-dsl.md)

### Contract fixes (Phase 2)

- `min_sealed_test_days` / `embargo_days` (calendar semantics)
- `RollingNode.right` for `ROLLING_CORRELATION`
- `winsorize_lower` / `winsorize_upper`; `CONDITIONAL` deferred in DSL v1

### Do not (unchanged)

- Wire to Scan
- Call LLM
- Enable `FACTOR_DISCOVERY_ENABLED`

---

## Phase 2 (original spec) — Controlled DSL & compiler (5–8 days)

**Goal:** Parse and compile a closed expression language — no code execution.

### Tasks

1. `engines/factor/discovery/ast.py` — node types, JSON serde, `formula_hash()`.
2. `engines/factor/discovery/dsl.py` — field/op whitelist from [data inventory](./factor-discovery-data-inventory.md).
3. `engines/factor/discovery/parser.py` — parse DSL text → AST (hand-written or Lark if approved).
4. `engines/factor/discovery/compiler.py` — AST → `CompiledFactorPlan`.
5. Golden tests: 10+ expressions covering rolling, cross-section, lag.

### Reuse

- `openalpha_registry.json` expressions as **test vectors** (expected to fail until scorers mapped to AST)
- `quant_core/features.py` for rolling ops

### Do not

- Wire to Scan
- Call LLM

### Risk mitigations

- R-A01, R-D01 (pin price source in compile context)

---

## Phase 3 — Deterministic factor engine (5–7 days)

**Goal:** Cross-sectional panel computation with PIT inputs.

### Tasks

1. `engines/factor/discovery/engine.py`:
   - `compute_factor_panel(plan, symbols, dates, price_source)`
   - Truncate via `scan_evaluation_pit.truncate_history()`
2. Normalization: reuse `stage_a_ranking._percentile_scores()`.
3. Optional Tier C fundamentals via `get_pit_metric()` with coverage report.
4. Export helper mirroring `scripts/factor_research_export.py`.

### Tests

- Fixed OHLCV fixture → deterministic panel hash
- Lookahead rejection test (`assert_no_lookahead`)

### Gates

- Engine callable from CLI script only (no API yet)

---

## Phase 4 — Experiment & validation engine (7–10 days)

**Goal:** End-to-end discovery run with chronological periods.

### Tasks

1. `services/factor_discovery_experiment_service.py`:
   - `run_factor_discovery_experiment(config) → run_id`
   - Period split enforcement
   - Discovery: compute + `cross_section_metrics()` per rebalance
   - Validation: frozen AST, same metrics
   - Sealed test: single pass, persist only
2. Extend `experiment_launch_service._dispatch_experiment()` for `factor_discovery`.
3. `services/factor_discovery_validation_service.py` — aggregate metrics, Bonferroni counter, caveats.
4. Failed runs: always write `FactorDiscoveryRun` with error.
5. `research_run_service.adapter_factor_discovery()`.

### Reuse

- `walk_forward_research_service.rebalance_dates()`, `universe_for_date()`
- `cross_section_metrics()`, `turnover_rate()`
- `experiment_job_service` stages
- `notify_run_persisted()`

### Tests

- Synthetic panel integration test (mirrors `test_quant_lab_integration.py`)
- Failed compile → failed run row exists
- Sealed test not used in revision prompts

### API (behind flag)

- `FACTOR_DISCOVERY_ENABLED=false` (default)
- Launch via existing experiment endpoint when enabled

---

## Phase 5 — Registry & experiment ledger (3–5 days)

**Goal:** Queryable history of all attempts; dedup by formula hash.

### Tasks

1. `engines/factor/discovery/registry.py`:
   - `register_experimental()`, `get_by_hash()`, `list_runs_for_hypothesis()`
2. Extend `factor_lineage_service.py` to sync discovery factor metadata.
3. Results API: list/filter by `run_type=factor_discovery`, include failed.
4. UI data shape in `ResearchRunDetailResponse` extension.

### Reuse

- `ResearchRunIndex`, `FactorLineage`
- `ResultsTab.tsx` patterns

### Do not

- Merge into production catalog

---

## Phase 6 — LLM research layer (5–7 days)

**Goal:** Hypothesis generation and DSL translation with strict guards.

### Tasks

1. `services/factor_discovery_llm/hypothesis.py` — structured output schema.
2. `services/factor_discovery_llm/translator.py` — hypothesis → DSL text → parser → AST.
3. `services/factor_discovery_llm/critic.py` — failure analysis prose + suggested AST patch (validated through parser).
4. Config: `FACTOR_DISCOVERY_LLM_ENABLED`, model from existing `LLM_*` env vars.
5. Reuse `sanitize_llm_prose()` for any narrative.

### Tests

- Mock LLM responses; verify schema rejection
- Verify translator cannot emit forbidden fields
- No network tests in CI

### Gates

- LLM off by default
- No auto-launch after LLM output

---

## Phase 7 — Bounded mining loop ✅ (shipped)

**Goal:** Human-authorized, budget-bound hypothesis → formula → experiment → critique/revision loop without sealed access or lifecycle auto-promotion.

### Delivered

1. `backend/services/factor_discovery/mining/` — orchestrator, state machine, budgets, exposure, deduplication, revision diff, recovery, session service
2. Persistence: `factor_mining_sessions`, `factor_mining_lineages`, `factor_mining_events`, `factor_mining_evaluations`, `factor_mining_exposures`
3. API routes under `/api/v2/research/factor-discovery/mining/sessions`
4. Flags: `FACTOR_DISCOVERY_LOOP_ENABLED=false`, `FACTOR_DISCOVERY_LOOP_MODE=disabled|supervised|bounded_auto`
5. Docs: [factor-discovery-mining-loop.md](./factor-discovery-mining-loop.md) and related policy docs

### Tests

- `tests/test_factor_discovery_mining_*.py` (24 tests)
- Supervised e2e through closed experiment with fixture LLM + panel

### Non-goals (deferred to Phase 8+)

- Frontend workspace, sealed-test opening, lifecycle promotion, Scan integration

---

## Phase 8 — Quant Lab UI (5–8 days)

**Goal:** Factor discovery workflow in `/quant-lab`.

### Tasks

1. New template in Experiment Studio OR `?section=factor-discovery`.
2. Screens: hypothesis review, AST preview, period config, job status, results (IC charts).
3. Failed run prominent state (reuse job error + run detail).
4. Read `design-system/pages/quant-lab.md` before styling.

### Reuse

- `ExperimentStudio.tsx` wizard framework
- `ResearchReliabilityCard`, `WalkForwardTab` chart patterns
- `experimentStudio.ts` URL helpers

### Tests

- Component tests with fixture run detail
- `frontend/e2e/quant-lab.spec.ts` smoke extension

---

## Phase 9 — Paper integration (3–5 days)

**Goal:** Approved factors visible in analyze, not Scan.

### Tasks

1. `lifecycle_state=paper` in registry.
2. Env `PAPER_FACTORS_ENABLED` (default false).
3. Extend `append_openalpha_signals()` pattern → `append_paper_discovery_signals()`.
4. Workspace analyze shows paper factor scores with badge.

### Reuse

- OpenAlpha two-gate pattern (`OPENALPHA_FACTORS_ENABLED` + `enabled_live`)

### Gates

- `enabled_live=false` for paper tier always

---

## Phase 10 — Production Scan integration (5–7 days)

**Goal:** Approved factors enter Scan only through human approval.

### Tasks

1. `services/factor_discovery_approval_service.py`:
   - Requires `ChangeProposal` status `approved_for_staging`
   - Inserts `FactorDefinition`, bumps `FACTOR_MODEL_VERSION`
2. `engines/factor/discovery/scan_adapter.py` — production tier only.
3. Hook in `FactorEngine.build_signals()` behind `PRODUCTION_DISCOVERED_FACTORS_ENABLED`.
4. Audit log + `docs/API_REFERENCE.md` update.

### Tests

- Scan integration test: flag off → no discovery signals
- Flag on + production entry → signal present
- Experimental run does not affect scan (regression)

### Release gate

- Manual checklist in `QUANT_LAB_MANUAL_TEST_CHECKLIST.md`
- `major_evidence_gate` passed on sealed test run

---

## Phase 11 — Hardening & release (ongoing)

### Tasks

1. `services/factor_drift_monitor_service.py` — IC decay vs discovery baseline.
2. Unify IC reporting: rank IC primary everywhere.
3. Redundancy matrix (pairwise IC) — v2.
4. Full pytest + frontend build in CI.
5. Update `INSTITUTIONAL_QUANT_ARCHITECTURE.md`, `QUANT_LAB.md`, `API_REFERENCE.md`.

### Tests to add

- `ic_panel` vs `cross_section_metrics` parity documentation test
- `factor_lifecycle` with discovery factors
- LLM prompt injection / override attempts

---

## Decision log (required before Phase 6)

| Decision | Options | Recommendation |
|----------|---------|----------------|
| Parser library | Hand-written vs Lark | Hand-written v1 (no new dep) |
| Price source for research | yfinance-only vs pinned config | Pin per run in config JSON |
| Min PIT universe | Block vs warn | **Block** launch if empty (R-S02) |
| Sealed test length | 20% of timeline vs fixed 6mo | Fixed 6mo minimum sessions |
| LLM provider | Existing `LLM_BASE_URL` | Reuse; no new provider |
| Paper factor UI | Analyze only vs Quant Lab badge | Analyze tab + research badge |

---

## Effort estimate

| Phase | Days (eng) |
|-------|------------|
| 0 | 1–2 |
| 1 | 3–5 |
| 2 | 5–8 |
| 3 | 5–7 |
| 4 | 7–10 |
| 5 | 3–5 |
| 6 | 5–7 |
| 7 | 2–4 |
| 8 | 5–8 |
| 9 | 3–5 |
| 10 | 5–7 |
| 11 | 5+ |
| **Total** | **~50–70 days** |

Phases 1–4 deliver value without LLM (manual hypothesis + DSL).

---

## Next Cursor phase recommendation

**Start Phase 0 + Phase 1:**

1. Fix `test_scan_evaluation_quant_lab.py` collection error.
2. Add `schemas_factor_discovery.py` contracts (no DB migration yet — Pydantic only).
3. Add `factor_discovery` to `ExperimentType` as **disabled** stub in validation only.
4. Write compiler golden tests with fixture AST JSON (no parser UI yet).

**Do not start:** LLM services, Scan adapter, or database migrations until Phase 1 contracts reviewed.

---

## Related

- [factor-discovery-audit.md](./factor-discovery-audit.md)
- [factor-discovery-architecture.md](./factor-discovery-architecture.md)
- [factor-discovery-risk-register.md](./factor-discovery-risk-register.md)
- [factor-discovery-data-inventory.md](./factor-discovery-data-inventory.md)
