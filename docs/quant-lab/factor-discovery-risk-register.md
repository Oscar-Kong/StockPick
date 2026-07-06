# Factor Discovery — Risk Register

Evidence-based risks from repository audit. Severity: **Critical** | **High** | **Medium** | **Low**.

---

## Look-ahead & temporal integrity

| ID | Risk | Severity | Evidence | Mitigation (architecture) |
|----|------|----------|----------|---------------------------|
| R-L01 | Forward returns used in factor computation | **Critical** | `scan_evaluation_pit` separates labels; walk-forward scores with `_truncate_history()` | **Phase 2:** `FactorFieldRegistry` forbids outcome fields (`ForbiddenFieldError`); DSL v1 has no arbitrary field access |
| R-L02 | Live fundamentals at historical rebalance dates | **High** | `fundamental_snapshots` is daily ingest, not filing-lag aware | Tier C DSL fields require `fundamentals_pit`; reject runs with coverage < threshold |
| R-L03 | Macro/regime uses latest FRED value at all dates | **Medium** | `fred_client.get_latest()` — no as-of series | Exclude macro from DSL v1; document in hypothesis review |
| R-L04 | Sentiment/news fetched live during walk-forward | **High** | `scoring/sentiment.py` live API calls | Exclude from DSL v1; Tier D hypothesis-only |
| R-L05 | ScoringEngine walk-forward may use non-PIT info | **Medium** | `_score_symbol_as_of()` truncates prices; info may be current | Discovery engine uses own data loaders, not full `ScoringEngine` for custom factors |
| R-L06 | No sealed-test enforcement today | **High** | Walk-forward uses single window; IC panel pools all dates | **Phase 4:** `SealedTestAccess` contract + no sealed metrics without explicit access; Phase 5 persists receipts |

---

## Survivorship & universe

| ID | Risk | Severity | Evidence | Mitigation |
|----|------|----------|----------|------------|
| R-S01 | Live scan uses current listing master | **High** | `universe.py` intersects `get_active_listing_symbols()` | Research runs require `universe_pit` seed or explicit survivorship caveat in metrics |
| R-S02 | Empty `universe_pit` = no filter | **Critical** | `active_symbols_on_date()` passthrough when empty | Block factor discovery launch if PIT empty and `require_pit=true` (default) |
| R-S03 | Curated seed lists omit delisted winners | **High** | Thematic seeds in `universe.py` | Document in run caveats; prefer PIT-seeded SP500 subset for validation |
| R-S04 | FMP screener `isActivelyTrading=true` | **Medium** | `fmp_client.screener()` | Do not use FMP screener for research universe |
| R-S05 | Alphabetical / max-universe truncation | **Medium** | Scan eval `--max-universe` | Deterministic sort before cap; log excluded symbols in ledger |

---

## Data quality & adjustment

| ID | Risk | Severity | Evidence | Mitigation |
|----|------|----------|----------|------------|
| R-D01 | Mixed adjusted/unadjusted OHLC in `daily_quotes` | **Critical** | yfinance adjusted vs AkShare unadjusted; `adjusted=1` flag only | Pin `price_source` per experiment; reject multi-provider merge in discovery engine |
| R-D02 | Restatement / revised fundamentals | **High** | Reconciler uses latest provider values | PIT table with `filing_date`; no overwrite of sealed-test era rows |
| R-D03 | Missing publication delays | **High** | `available_to_model_at` sparsely populated | v1: conservative lag config (e.g. T+45 for fundamentals); document assumption |
| R-D04 | Sparse PIT fundamental coverage | **High** | FMP ingest ~40 symbols | Pre-flight coverage report; restrict universe to covered symbols |
| R-D05 | `factor_values` table not implemented | **Low** | Schema doc only | Use `FactorDiscoveryRun` + parquet export pattern from `factor_research_export.py` |

---

## Data snooping & validation

| ID | Risk | Severity | Evidence | Mitigation |
|----|------|----------|----------|------------|
| R-V01 | Repeated use of same test window | **High** | No sealed holdout in IC panel | Discovery / validation / sealed-test dates enforced in config |
| R-V02 | Multiple testing without correction | **Medium** | No Bonferroni in existing IC paths | Ledger tracks experiment count; apply simple correction in validation service |
| R-V03 | IC panel pools time-series (not cross-section) | **Medium** | `ic_panel._pooled_ic()` stacks windows | Discovery validation uses `cross_section_metrics()` only |
| R-V04 | Non-standard IR heuristic | **Medium** | `ir = ic / max(0.05, abs(spread)+0.01)` | Report rank IC + standard IR separately in discovery runs |
| R-V05 | Walk-forward too few periods → weak evidence | **Low** | `build_research_brief` warns | Reuse `major_evidence_gate` sample checks |
| R-V06 | 70/30 OOS in trade backtests mistaken for factor validation | **Medium** | `ml/backtest_engine.run_backtest_with_oos()` | Do not route factor discovery through trade backtest engine |

---

## Execution realism

| ID | Risk | Severity | Evidence | Mitigation |
|----|------|----------|----------|------------|
| R-E01 | Transaction costs optional in legacy backtest | **Medium** | `LEGACY_BACKTEST_COSTS_ENABLED` gate | Factor IC v1 is cost-free; penny sleeve optional `apply_penny_friction` on labels |
| R-E02 | Vectorbt path fees=0 | **Medium** | `ml/backtest_vectorbt.py` | Not used for factor discovery |
| R-E03 | Unrealistic fill timing | **Low** | Scan assumes EOD scores | Document EOD assumption in experiment metadata |
| R-E04 | Institutional costs not in IC metrics | **Low** | Costs in `institutional.py` only | Portfolio policy template separate from factor discovery |

---

## LLM & code execution

| ID | Risk | Severity | Evidence | Mitigation |
|----|------|----------|----------|------------|
| R-A01 | Arbitrary code execution from LLM | **Critical** | OpenAlpha dispatches to hardcoded scorers (safe today) | Closed AST + compiler; no `eval()`; reject raw Python |
| R-A02 | LLM overrides verdict/reliability | **Medium** | `sanitize_llm_prose()` in interpretation service | Same sanitizer; LLM prose only; deterministic verdict |
| R-A03 | Unbounded LLM revision loops | **High** | No revision cap in ideas flow | `FACTOR_DISCOVERY_MAX_REVISIONS`; human launch required |
| R-A04 | LLM accesses future outcome fields | **Critical** | If prompt includes run metrics from sealed test | Prompt builder excludes sealed-test metrics during discovery-phase revisions |
| R-A05 | LLM approves production factors | **Critical** | No LLM in `change_proposals_service` | Approval API requires human action; LLM cannot call promote endpoint |

---

## Experiment lifecycle & audit

| ID | Risk | Severity | Evidence | Mitigation |
|----|------|----------|----------|------------|
| R-X01 | Failed analysis runs not in Results index | **High** | `fail_job()` retains job; no `backtest_runs` row | Always insert `FactorDiscoveryRun` with `status=failed` |
| R-X02 | Pairs runs pruned (max 20) | **Medium** | `pairs_research_store.MAX_RUNS_RETAINED` | No pruning on discovery ledger |
| R-X03 | Silent formula mutation | **High** | No AST hash today | `formula_hash` immutable per run |
| R-X04 | Experiment deletion | **Low** | Ideas/experiments have DELETE API | Soft-delete only for discovery runs; archive pattern from `archive_run()` |
| R-X05 | scan_evaluation wiring incomplete | **Resolved (Phase 0)** | `adapter_scan_evaluation`, `_run_scan_evaluation` in `experiment_launch_service.py` |
| R-X06 | `test_scan_evaluation_quant_lab.py` broken | **Resolved (Phase 0)** | `stage_order_for_experiment()` in `experiment_job_service.py` |

---

## Production / research coupling

| ID | Risk | Severity | Evidence | Mitigation |
|----|------|----------|----------|------------|
| R-P01 | Experimental factors in live scan via env flag | **Critical** | `OPENALPHA_FACTORS_ENABLED` merges experimental tier | Separate `PRODUCTION_DISCOVERED_FACTORS_ENABLED`; default false |
| R-P02 | Dynamic weights update from IC panel independently | **High** | `WeightStore.rebalance_sleeve()` scheduled | Discovered factors do not write `FactorWeight` until approved |
| R-P03 | Research evidence modifies live scores | **Medium** | `RESEARCH_MAX_ORDINARY_MODIFIER` default 0 | Keep default 0; major impacts require approved proposal |
| R-P04 | Missing formula versioning in scan | **High** | `FactorSpec.formula_version` static string | Bump `FACTOR_MODEL_VERSION` on production merge |
| R-P05 | Non-deterministic scan scoring mode parity | **Medium** | `SCAN_SCORING_MODE=parity_sample` | Discovery runs pin scoring mode in metadata; no parity in experiment engine |

---

## Non-determinism

| ID | Risk | Severity | Evidence | Mitigation |
|----|------|----------|----------|------------|
| R-N01 | Thread pool experiment launch | **Low** | `ThreadPoolExecutor` in launch service | Single-thread panel compute per job; seed documented |
| R-N02 | Provider API non-determinism | **Medium** | Live sentiment fetches | Cache inputs per run_id in artifact dir |
| R-N03 | Float tolerance in IC | **Low** | numpy correlation | Golden tests with fixed fixtures |

---

## Risk heat map (implementation priority)

```
Critical (must address before any LLM factor discovery):
  R-L01, R-S02, R-D01, R-A01, R-A04, R-A05, R-P01

High (must address in phase 1–4):
  R-L02, R-L04, R-L06, R-S01, R-S03, R-D02, R-D03, R-D04,
  R-V01, R-A03, R-X01, R-X03, R-P02, R-P04

Medium (phase 5–8 or v2):
  R-L03, R-L05, R-S04, R-S05, R-V02–R-V06, R-E01–R-E02,
  R-A02, R-P03, R-P05, R-X02, R-X05, R-N02

Low (hardening):
  R-L05, R-D05, R-E03–R-E04, R-V05, R-X04, R-X06, R-N01, R-N03
```

---

## Phase 6A status (2026-07)

| Item | Status |
|------|--------|
| R-S02 empty PIT passthrough | **Mitigated** in Factor Discovery — `EMPTY_PIT_UNIVERSE` at snapshot/runner |
| R-L06 sealed test | **Mitigated** — reservation before metrics; failed receipt policy |
| R-P02 multiple testing | **Mitigated** — `distinct_formula_evaluations_v1` + staleness + revalidation service |
| R-D02 adjusted prices | **Partial** — historical provider requires `adjusted=1`; fundamentals/sector still blocked |
| SQLite lifecycle locking | **Documented** — unique constraints; see [concurrency doc](./factor-discovery-concurrency-and-idempotency.md) |

Phase 6A does **not** enable LLM workflows or production Scan integration.

---

## Phase 6B status (2026-07)

| Item | Status |
|------|--------|
| R-A01 arbitrary code execution | **Mitigated** — closed DSL + parser/compiler; LLM cannot bypass |
| R-A04 sealed metrics in prompts | **Mitigated** — closed artifacts strip sealed metrics; evidence validator |
| R-A05 LLM approves production | **Mitigated** — human review gates; no lifecycle routes in LLM namespace |
| R-A03 unbounded revision loops | **Mitigated Phase 7** — `FactorMiningOrchestrator` with immutable budgets, max advance steps, exposure ledger |

LLM layer gated by `FACTOR_DISCOVERY_LLM_ENABLED=false`. See [factor-discovery-llm-security.md](./factor-discovery-llm-security.md).

---

## Related

- [factor-discovery-architecture.md](./factor-discovery-architecture.md)
- [factor-discovery-implementation-plan.md](./factor-discovery-implementation-plan.md)
- [factor-discovery-data-provider.md](./factor-discovery-data-provider.md)
- [factor-discovery-operations.md](./factor-discovery-operations.md)
- [factor-discovery-audit.md](./factor-discovery-audit.md)
