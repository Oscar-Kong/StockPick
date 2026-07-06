# Factor Discovery Audit — Quant Lab & Repository Baseline

**Phase:** Pre-implementation audit (no factor-discovery runtime shipped)  
**Date:** 2026-07-01  
**Scope:** Evidence-based inventory of existing Quant Lab, Scan, data, validation, and reusable code for a future LLM-assisted factor research workflow.

---

## 1. Repository structure

### Frontend

| Area | Path | Notes |
|------|------|-------|
| Framework | `frontend/` | Next.js (App Router), React, Tailwind, Recharts |
| Quant Lab route | `frontend/src/app/quant-lab/page.tsx` | Renders `QuantLabPage` |
| Page shell | `frontend/src/components/QuantLabPage.tsx` | Section tabs + sleeve selector |
| Navigation | `frontend/src/lib/quantLabNavigation.ts` | `?section=` routing (`overview`, `ideas`, `experiments`, `factor-discovery`, `results`, `model-monitor`, `legacy`); `section=models` redirects to `model-monitor` |
| Experiment Studio | `frontend/src/components/quant-lab/ExperimentStudio.tsx` | Wizard: Choose → Configure → Review → Run → Status → Result |
| Ideas | `frontend/src/components/quant-lab/IdeasBoardTab.tsx` | CRUD + generate-from-brief |
| Results | `frontend/src/components/quant-lab/ResultsTab.tsx` | Paginated runs, detail, compare |
| Legacy tabs | `frontend/src/components/quant-lab/LegacyQuantLabTabs.tsx` | Factor performance, walk-forward, predictions, pairs |
| Scan eval UI (partial) | `frontend/src/components/quant-lab/ScanEvaluationResultPanel.tsx`, `ScanEvaluationConfigFields.tsx` | Result panel exists; **not wired into Experiment Studio templates** |
| API client | `frontend/src/lib/api.ts` | Research + v2 endpoints |
| E2E | `frontend/e2e/quant-lab.spec.ts` | Playwright smoke |

### Backend routes

| Router | File | Prefix | Role |
|--------|------|--------|------|
| Research (direct) | `backend/api/routes_research.py` | `/research` | Walk-forward, pairs |
| Research Lab | `backend/api/routes_research_lab.py` | `/api/v2/research` | Ideas, experiments, runs, evidence, proposals |
| Quant v2 | `backend/api/routes_v2.py` | `/api/v2` | IC panel jobs, factor performance, quant-lab evidence, portfolio backtest |
| Backtest (symbol) | `backend/api/routes_backtest.py` | `/backtest` | Per-symbol ML backtests (not unified Quant Lab runs) |
| Scan | `backend/api/routes_scan.py` | `/scan` | `POST /scan/penny`, `POST /scan/compounder` |

Registered in `backend/main.py`.

### Experiment & research services

| Module | Key symbols |
|--------|-------------|
| `services/experiment_launch_service.py` | `launch_experiment()`, `_dispatch_experiment()`, `_run_job()` |
| `services/experiment_job_service.py` | `create_job()`, `fail_job()`, `STAGE_ORDER` |
| `services/research_experiments_service.py` | Experiment CRUD |
| `services/research_run_service.py` | `upsert_run_index()`, `index_run_from_store()`, adapters per run type |
| `services/research_run_detail_service.py` | `get_run_detail()`, `load_detail_payload()` |
| `services/research_overview_service.py` | `get_research_overview()` |
| `services/quant_lab_summary_service.py` | `get_quant_lab_evidence()` |
| `services/experiment_presets_service.py` | `list_templates()`, `list_presets()`, `merge_parameters()` |
| `services/change_proposals_service.py` | Reviewable drafts; **never auto-applied** |
| `services/research_decision_boundary.py` | `apply_research_evidence_to_score()` — bounded, display-first |
| `services/evidence_impact_policy.py` | `evaluate_evidence_impact()`, `RESEARCH_MAX_ORDINARY_MODIFIER` |

### Factor & scoring engines

| Module | Key symbols |
|--------|-------------|
| `engines/factor/engine.py` | `FactorEngine.build_signals()`, `composite_score()` |
| `engines/factor/catalog.py` | `FACTOR_CATALOG`, `active_factor_catalog()`, `FactorSpec` |
| `engines/factor/catalog_v3.py` | `FACTOR_CATALOG_V3` (flag-gated) |
| `engines/factor/expr.py` | `AlphaFormula`, `load_registry()`, `evaluate_formula()` — **OpenAlpha JSON only** |
| `engines/factor/openalpha_registry.json` | Experimental formula metadata + expression strings |
| `engines/scoring/engine.py` | `ScoringEngine.score()` |
| `engines/weighting/ic_panel.py` | `run_ic_panel()`, `persist_ic_row()` |
| `engines/weighting/weight_store.py` | `WeightStore.load()`, `rebalance_sleeve()` |
| `scoring/*.py` | Raw factor math (technical, fundamental, penny_factors, etc.) |

### Backtesting & evaluation

| Module | Role |
|--------|------|
| `services/walk_forward_research_service.py` | PIT walk-forward ranking research |
| `services/scan_evaluation_service.py` | Offline scan replay harness |
| `services/scan_evaluation_experiment_runner.py` | Quant Lab adapter (**runner exists; launch wiring incomplete**) |
| `engines/backtest/metrics.py` | Sharpe, drawdown, turnover, alpha/beta |
| `engines/backtest/institutional.py` | Portfolio policy backtest with costs |
| `ml/backtest_engine.py` | Legacy trade simulation (70/30 OOS split) |
| `scripts/factor_validation.py` | CLI factor IC |
| `scripts/run_scan_evaluation.py` | CLI scan evaluation |

### Database models

Defined in `backend/engines/quant_models.py`, initialized by `engines/quant_db.py::init_quant_db()`:

- **Research:** `ResearchIdea`, `ResearchExperiment`, `ResearchExperimentJob`, `ResearchRunIndex`, `EvidenceMemory`, `ChangeProposal`, `FactorLineage`
- **Factors:** `FactorDefinition`, `FactorIcHistory`, `FactorDecileHistory`, `FactorWeight`
- **Runs:** `BacktestRun`, `PairsResearchRun`
- **PIT:** `UniversePit`, `FundamentalsPit`, `FeatureProvenance`, `ForwardReturnLabel`
- **Attribution:** `ScoreAttribution`, `FactorSnapshot` (in `historical_store.py`)

### Background jobs

| Job | Trigger | Handler |
|-----|---------|---------|
| Penny scan refresh | `PENNY_SCAN_REFRESH_CRON` | `scheduler` → `portfolio_jobs.run_scheduled_penny_scan_refresh()` |
| Daily quant pipeline | `QUANT_IC_CRON` / `SCHEDULER_CRON` | `quant_jobs.run_daily_quant_jobs()` — IC panel, weight rebalance |
| IC panel (manual) | `POST /api/v2/jobs/ic-panel` | `run_ic_panel()` |
| Experiment launch | `POST /api/v2/research/experiments/{id}/launch` | Thread pool in `experiment_launch_service` |

### LLM clients

| Module | Role | In research path? |
|--------|------|-------------------|
| `services/llm_explainer.py` | Structured stock analysis JSON | No (scan/workspace) |
| `services/report_narrative.py` | AI report v2 narrative | No (`GET /api/v2/report/{symbol}`) |
| `services/research_run_interpretation_service.py` | `_optional_llm_prose()` | **Optional, default off** (`use_llm=False` on run detail API) |
| `services/research_idea_generation_service.py` | Ideas from brief | **Deterministic only** |
| `services/research_brief_service.py` | Overview findings | **Rule-based only** |

### Data providers

`backend/data/`: `price_service.py`, `market_data_client.py`, `akshare_client.py`, `finnhub_client.py`, `fmp_client.py`, `openbb_client.py`, `fred_client.py`, `quandl_client.py`, `reconciler.py`, `listing_master.py`, `universe.py`

### Tests

| Area | Files |
|------|-------|
| Research foundation | `tests/test_research_foundation.py` |
| Quant Lab integration | `tests/test_quant_lab_integration.py` |
| Walk-forward | `tests/test_walk_forward_research_service.py` |
| Scan evaluation | `tests/test_scan_evaluation.py` |
| Scan eval Quant Lab | `tests/test_scan_evaluation_quant_lab.py` — **collection error (pre-existing)** |
| Experiment studio | `tests/test_experiment_studio.py` |
| Contracts | `tests/test_quant_lab_contracts.py` |
| Frontend | `frontend/src/components/quant-lab/*.test.tsx`, `frontend/e2e/quant-lab.spec.ts` |

### Documentation & rules

- `docs/QUANT_LAB.md`, `docs/SCAN_EVALUATION.md`, `docs/INSTITUTIONAL_QUANT_ARCHITECTURE.md`
- `.cursor/rules/pickerquant-ui.mdc`, `.cursor/rules/quant-stock-picker.mdc`
- `design-system/pages/quant-lab.md`

---

## 2. Existing Quant Lab end-to-end workflow

### User inputs

| Surface | Inputs |
|---------|--------|
| Overview | Sleeve filter; read-only evidence cards |
| Ideas | Title, hypothesis, sleeve, priority, notes; generate-from-brief |
| Experiment Studio | Template, preset (`quick_check` / `standard_research` / `robust_validation`), parameters, universe source |
| Legacy tabs | Sleeve, date ranges, symbol lists, run buttons |
| Results | Filters, compare, export, notes, archive |

### Experiment types (`schemas_research.py::ExperimentType`)

```
factor_validation | walk_forward | prediction_calibration | pairs_discovery | similar_signal | portfolio_policy
```

**Not in schema but partially implemented:** `scan_evaluation` (runner + UI components + tests; **not in `experiment_launch_service` or `ExperimentType`**).

### Execution flow

```
POST /api/v2/research/experiments/{id}/launch
  → launch_experiment()                    [experiment_launch_service.py]
  → validate_experiment()
  → create_job()                           [experiment_job_service.py]
  → ThreadPoolExecutor → _run_job()
      stages: validating → resolving_universe → … → running_analysis → persisting_result → complete
  → _dispatch_experiment() by experiment_type
  → notify_run_persisted() → research_runs index
```

| Template | Engine | Persistence |
|----------|--------|-------------|
| `factor_validation` | `run_ic_panel()` + `get_factor_performance()` | `factor_ic_history`, synthetic `backtest_runs` |
| `walk_forward` | `run_walk_forward_research()` | `backtest_runs` (`run_type=walk_forward_research`) |
| `prediction_calibration` | `build_forward_labels()`, `resolve_prediction_outcomes()` | `prediction_snapshots` |
| `pairs_discovery` | `run_pairs_research()` | `pairs_research_runs` (max 20 runs retained) |
| `similar_signal` | `run_similar_signal_backtest()` | `backtest_runs` |
| `portfolio_policy` | `run_portfolio_backtest()` | `backtest_runs` |

### Results storage

| Store | Table / path | Indexed via |
|-------|--------------|-------------|
| Walk-forward / policy / similar-signal | `backtest_runs` | `ResearchRunIndex` |
| Pairs | `pairs_research_runs` | `ResearchRunIndex` |
| Factor IC | `factor_ic_history`, `factor_decile_history` | Synthetic run `ic_panel:{sleeve}:{date}` |
| Scan evaluation | `data/scan_eval/{run_id}/` | **Adapter not in `research_run_service` today** |
| Jobs | `research_experiment_jobs` | Job status API |

### Charts & metrics

- Walk-forward: rank IC, Pearson IC, hit rate, quintile spread, turnover (`cross_section_metrics()`)
- Factor validation: IC, IR (heuristic), hit rate, deciles (`ic_panel._pooled_ic()`)
- Pairs: cointegration p-value, half-life, z-score stats
- Results detail: `research_run_detail_service.build_charts()`, interpretation via `build_interpretation()`

### Reproducibility

| Aspect | Status |
|--------|--------|
| Experiment parameters | Persisted in `ResearchExperiment.parameters_json` |
| Run config | `BacktestRun.config_json`, `metrics_json` |
| Version pins | `FACTOR_MODEL_VERSION`, `STRATEGY_VERSION` in config and run index |
| Deterministic ideas/brief | Yes — no LLM in idea generation |
| LLM interpretation | Optional prose only; verdict/reliability deterministic |

### Failed experiment retention

| Layer | Behavior |
|-------|----------|
| `research_experiment_jobs` | `fail_job()` retains `error_message`, `last_success_run_id`; **no pruning** |
| Payload tables | Failed analysis runs generally **not written** to `backtest_runs` / `pairs_research_runs` |
| Pairs | `load_latest_pairs_run()` filters `status == "completed"` only |
| Run index | `archive_run()` soft-hides; no hard delete |
| Ideas | `source_type="failed_experiment"` via `create_follow_up_idea()` |

**Gap:** Failed runs are visible at job level but often absent from unified Results index.

### LLM involvement today

- **None** in experiment execution, scoring, or validation math
- **Optional** prose rewrite in run interpretation (`use_llm=False` default)
- **None** in idea generation or research brief

### Effect on Scan / portfolio

| Surface | Affects live rankings? |
|---------|------------------------|
| Quant Lab experiments | **No** — documented in `docs/QUANT_LAB.md`, `EvidenceToActionBoundary` UI |
| `research_decision_boundary` | Bounded score modifier only when `RESEARCH_MAX_ORDINARY_MODIFIER > 0` (default **0**) |
| `change_proposals_service` | Manual review; `approved_for_staging` required for major impacts |
| Dynamic weights | Updated by scheduled `WeightStore.rebalance_sleeve()` from IC panel — **separate from experiments** |

### Incomplete / duplicated / broken areas

| Issue | Evidence |
|-------|----------|
| `scan_evaluation` not in `ExperimentType` or `experiment_launch_service` | `grep` shows runner exists but no dispatch |
| `test_scan_evaluation_quant_lab.py` import error | Missing `stage_order_for_experiment` in `experiment_job_service.py` |
| `adapter_scan_evaluation` referenced in tests, not in `research_run_service.py` | Test/collection failure |
| IC paths duplicated | Pearson pooled (`ic_panel`) vs Spearman cross-section (`cross_section_metrics`) |
| `factor_values` table | In `docs/schemas/quant_v2_tables.sql` only — not wired |
| OpenAlpha `expression` strings | Metadata only; evaluation dispatches to hardcoded `OPENALPHA_SCORERS` |
| Pairs retention | Max 20 runs — older evidence pruned regardless of status |

---

## 3. Scan relationship (summary)

See [factor-discovery-architecture.md](./factor-discovery-architecture.md) § Scan integration for production gate design.

**Live scan pipeline:**

```
POST /scan/{penny|compounder}
  → ScanManager.run_scan()
  → get_universe(bucket)                    [data/universe.py]
  → Stage A: rank_stage_a_candidates()      [services/stage_a_ranking.py]
  → Stage B: score_stage_b_candidate()      [services/scan_scoring.py → ScoringEngine]
  → apply_final_scan_ranking()              [services/scan_final_ranking.py]
  → save_scan_results() + save_factor_snapshot()
```

**Production factor registration:**

- Static catalogs: `engines/factor/catalog.py`, `catalog_v3.py` (flag `SLEEVE_FACTORS_V3_ENABLED`)
- Experimental: `openalpha_registry.json` + `OPENALPHA_FACTORS_ENABLED` + per-formula `enabled_live`
- Dynamic weights: `FactorWeight` table keyed by `FACTOR_MODEL_VERSION`

**Research isolation:** Quant Lab does not write to `FactorWeight` or scan cache. Future discovered factors must pass `ChangeProposal` → staging flags before catalog merge.

---

## 4. Data readiness (summary)

Full field inventory: [factor-discovery-data-inventory.md](./factor-discovery-data-inventory.md).

**Research-ready today:** `daily_quotes` OHLCV, truncated PIT prices, `factor_snapshots`, `forward_return_labels`, walk-forward cross-section metrics.

**Partial PIT:** `fundamentals_pit` (sparse FMP ingest), `universe_pit` (manual seed), `feature_provenance`.

**Not PIT-safe for research:** `fundamental_snapshots` (daily ingest snapshot), live reconciler output.

---

## 5. Validation capabilities (summary)

Full matrix: [factor-discovery-architecture.md](./factor-discovery-architecture.md) § Validation reuse.

**Strongest paths:** `walk_forward_research_service.cross_section_metrics()`, `scan_evaluation_metrics`, `engines/backtest/metrics.py`.

**Weakest paths:** `ic_panel._pooled_ic()` (Pearson-only, non-standard IR), `ml/backtest_engine` (single 70/30 split, optional costs).

---

## 6. Reusable code (summary)

| Need | Reuse |
|------|-------|
| Cross-section IC / deciles | `walk_forward_research_service.cross_section_metrics()` |
| PIT price truncation | `scan_evaluation_pit.truncate_history()` |
| Forward labels | `scan_evaluation_pit.build_forward_outcomes()`, `quant_core/labels.py` |
| Winsorization / percentiles | `stage_a_ranking._percentile_scores()` |
| Experiment lifecycle | `experiment_launch_service`, `research_run_service` |
| Run interpretation | `research_run_interpretation_service.build_interpretation()` |
| Chart adapters | `research_run_detail_service.build_charts()`, `scan_evaluation_charts.charts_from_artifact()` |
| LLM structured output | `llm_explainer.py` patterns + `sanitize_llm_prose()` |
| Approval gate | `change_proposals_service`, `major_evidence_gate` |
| Factor registry pattern | `catalog.py` + `FactorDefinition` model |

**Avoid duplicating:** New experiment runner (extend `_dispatch_experiment`), new IC math (unify on `cross_section_metrics`), new job staging (`experiment_job_service`).

---

## 7. Risk summary

Full register: [factor-discovery-risk-register.md](./factor-discovery-risk-register.md).

**Critical:** Survivorship when `universe_pit` empty; mixed price adjustment across providers; experimental factors gated only by env flags; failed runs not indexed.

---

## 8. Baseline verification (2026-07-01)

### Commands executed

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_research_foundation.py tests/test_quant_lab_integration.py \
  tests/test_walk_forward_research_service.py tests/test_scan_evaluation.py \
  tests/test_quant_lab_contracts.py tests/test_experiment_studio.py -q
python -m pytest tests/ --ignore=tests/test_scan_evaluation_quant_lab.py -q
cd frontend && npm run lint && npm run typecheck
```

### Results

| Check | Result |
|-------|--------|
| Quant Lab targeted pytest (6 files) | **77 passed** |
| Full backend pytest (excluding broken file) | **480 passed**, 2 skipped, **1 failed** |
| Frontend lint | **Pass** (1 warning: unused `BACKEND_PORT` in playwright config) |
| Frontend typecheck | **Pass** |

### Pre-existing failures

| Test | Error |
|------|-------|
| `tests/test_scan_evaluation_quant_lab.py` | Collection: `ImportError: cannot import name 'stage_order_for_experiment'` |
| `tests/test_smtp_email_provider.py::test_smtp_missing_credentials` | Assertion failure (missing SMTP env) |

### Test gaps

- No unit tests for `ic_panel.py`, `factor_lifecycle.py`, `ml/sweep_validation.py`, `ml/backtest_engine` OOS logic
- `engines/factors/performance.py` — shape test only
- No integration test for LLM interpretation path
- `scan_evaluation` Quant Lab wiring untested (collection blocked)

### Environment blockers

None for audit phase. SMTP test requires credentials; not relevant to factor discovery.

---

## Related documents

- [factor-discovery-architecture.md](./factor-discovery-architecture.md)
- [factor-discovery-data-inventory.md](./factor-discovery-data-inventory.md)
- [factor-discovery-risk-register.md](./factor-discovery-risk-register.md)
- [factor-discovery-implementation-plan.md](./factor-discovery-implementation-plan.md)
- [../QUANT_LAB.md](../QUANT_LAB.md)
- [../SCAN_EVALUATION.md](../SCAN_EVALUATION.md)
