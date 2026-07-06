# Phase 0–11 Traceability Matrix

Status key: ✅ complete · 🟡 partial · ❌ not shipped

| Phase | Requirement | Implementation | Tests | Documentation | Status | Evidence / limitation |
|-------|-------------|----------------|-------|---------------|--------|------------------------|
| **0** | Scan evaluation Quant Lab wiring | `experiment_launch_service.py`, `research_run_service.py` | `test_scan_evaluation_quant_lab.py` | `docs/SCAN_EVALUATION.md` | ✅ | 14 scan-eval tests pass |
| **1** | Factor discovery contracts | `models/schemas_factor_discovery.py` | `test_factor_discovery_contracts.py` | `docs/quant-lab/factor-discovery-dsl.md` | ✅ | `FACTOR_DISCOVERY_ENABLED` default off |
| **2** | Controlled DSL parser/compiler | `engines/factor/discovery/` | `test_factor_discovery_dsl_parser.py` | DSL docs | ✅ | No string `eval()` |
| **3** | Deterministic panel executor | `engines/factor/discovery/executor.py` | `test_factor_discovery_executor.py` | execution-engine doc | ✅ | Hash-stable execution |
| **4** | Validation engine + acceptance | `validation_engine.py`, `acceptance.py` | `test_factor_discovery_validation_engine.py` | validation-engine doc | ✅ | Rank IC primary |
| **5** | Registry + ledger | `factor_discovery_models.py`, repositories | `test_factor_discovery_registry*.py` | registry-and-ledger doc | ✅ | Separate from live `FactorDefinition` |
| **6B** | LLM research layer (human gates) | `services/factor_discovery/llm/` | `test_factor_discovery_llm_*.py` | llm-architecture doc | ✅ | Flags default off |
| **7** | Mining loop + recovery | `mining/orchestrator.py`, `recovery_service.py` | `test_factor_discovery_mining_*.py` | mining-loop doc | ✅ | Bounded auto gated |
| **8B** | Quant Lab Factor Discovery UI | `FactorDiscoveryWorkspace.tsx` | mining API tests | workspace doc | ✅ | No production promotion UI copy |
| **9A** | Results / integrity UI | `ResultsTab.tsx`, `useResearchRuns.ts` | `test_factor_discovery_phase9a_api.py` | results-ui doc | ✅ | AbortController teardown preserved |
| **9B.1** | Staging preflight + supervised pipeline | `preflight_service.py`, `run_suite.py` | `test_factor_discovery_staging_*.py` | staging-validation doc | ✅ | **Corrected history:** aborted shell commands were debugging only; recursion + universe-audit bottlenecks fixed; real DB preflight ~4s, no blockers; import→snapshot→supervised→repro succeeded; status `READY_FOR_EXTENDED_STAGING` |
| **9B.2** | Extended staging matrix | `extended_staging_runner.py`, `promotion_readiness_gate.py` | `test_factor_discovery_extended_staging.py` | `FACTOR_MINING_EXTENDED_STAGING.md` | ✅ | 30/30 cells; `READY_FOR_PROMOTION_REVIEW` |
| **10** | Promotion governance + shadow | `promotion/candidate_service.py`, `shadow_scoring.py` | `test_factor_promotion_governance.py` | `FACTOR_PROMOTION_GOVERNANCE.md` | ✅ | Advisory only; no live mutation |
| **11** | Final acceptance + isolation | `acceptance/final_acceptance.py`, `isolation_audit.py` | `test_factor_research_acceptance.py`, `test_factor_research_isolation.py` | This doc + `FACTOR_RESEARCH_FINAL_ACCEPTANCE.md` | ✅ | `run_factor_research_acceptance.py` |

## Phase 9B.1 corrected record

Prior conversation debugging (aborted commands, recursion between `mining_readiness` and preflight) was **infrastructure debugging**, not acceptance failure. Fixes shipped:

- Recursion removed from readiness/preflight chain
- Universe audit optimized (SQL aggregates vs per-date loops)
- Real-database preflight ~4s, zero blockers
- Full pipeline: import → snapshot → supervised run → reproducibility
- Final status: **`READY_FOR_EXTENDED_STAGING`**

## Deferred (explicitly not Phase 11)

| Item | Reason |
|------|--------|
| Production Scan adapter (`scan_adapter.py`) | Requires separate manual integration after governance approval |
| `factor_drift_monitor_service.py` | Post-release monitoring; not blocking research workflow |
| Full panel shadow executor on single-symbol contexts | Shadow v1 uses proxy signal |
| Factor-discovery Playwright E2E | Manual Quant Lab checklist covers workflow |

## Acceptance command

```bash
python backend/scripts/run_factor_research_acceptance.py --mode fixture   # CI
python backend/scripts/run_factor_research_acceptance.py --mode real      # local DB
```
