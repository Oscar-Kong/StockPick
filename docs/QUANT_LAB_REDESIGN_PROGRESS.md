# Quant Lab Redesign — Progress & Architecture Audit

**Branch:** `quant-lab-workbench`  
**Phase 1 completed:** 2026-06-20  
**Phase 3 completed:** 2026-06-20  
**Phase 4 completed:** 2026-06-20  
**Status:** Unified Experiment Studio shipped; legacy tab runners remain under `section=legacy`.

Quant Lab is a **research and validation console** for US equities. It must not silently update live scan rankings, portfolio recommendations, or orders. Proposed model changes require reviewable **Change Proposals** (not yet implemented).

---

## Phase 1 summary

| Area | Finding |
|------|---------|
| **Frontend** | Six feature tabs + collapsible evidence panel; client-side Research Reliability layer; no Ideas/Experiments/Results/Model Monitor navigation yet |
| **Backend** | Mature v2 quant engines; walk-forward and pairs persist runs; factor IC and predictions read from history tables; no unified `research_runs` index |
| **Persistence** | `backtest_runs`, `pairs_research_runs`, `factor_ic_history`, `prediction_snapshots`/`prediction_outcomes`, `job_logs`/`job_queue` — adaptable to a common contract via thin metadata rows |
| **Gaps** | No `ideas` / `experiments` / `change_proposals` tables; PBO/CPCV/deflated Sharpe; factor decile/regime/sector breakdowns hidden in UI; job trigger buttons missing in Quant Lab |
| **Tests** | Backend Quant Lab: **36 passed, 1 skipped**; Frontend Quant Lab unit: **61 passed** |

---

## 1. Current frontend component map

```
frontend/src/app/quant-lab/page.tsx          → route entry
frontend/src/components/QuantLabPage.tsx     → tab shell, evidence + product panels

frontend/src/components/quant-lab/
  QuantLabTabs.tsx              → re-exports six tabs
  QuantLabTabShell.tsx          → shared layout (loading, errors, bucket select, reliability slot)
  ResearchReliabilityCard.tsx   → 0–100 score display per tab
  QuantLabTrustBadge.tsx        → fresh/stale/insufficient_sample badges
  FactorLifecycleBadge.tsx      → Promote/Keep/Watch/Retire per factor
  QuantLabLastRunCard.tsx       → evidence overview card
  QuantLabEvidencePanel.tsx     → loads GET /api/v2/quant-lab/evidence
  FactorPerformanceTab.tsx      → factor IC table (top 12 factors)
  WalkForwardTab.tsx            → run + hydrate latest persisted WF
  PredictionsTab.tsx            → snapshots + feedback summary
  PairsTab.tsx                  → run + hydrate latest persisted pairs
  DataQualityTab.tsx            → QuantHealthCard + scheduler status
  ModelAdminTab.tsx             → version, weights, audit, factors admin

frontend/src/components/product/
  EvidenceToActionBoundary.tsx       → static boundary copy (no auto-apply)
  QuantLabScanRelationshipPanel.tsx  → product flow diagram
  ApplyChangesNotice.tsx             → used in WF + Model Admin (confirm gate placeholder)

frontend/src/lib/
  api.ts                    → all Quant Lab HTTP clients (no frontend/src/lib/api/ subtree)
  researchReliability.ts    → per-tab reliability + factor lifecycle + WF overfitting warnings
  quantLabNormalizers.ts    → defensive API normalizers
  quantLabFormatters.ts     → dates, symbols, horizon text
  quantLabLastRun.ts        → evidence card normalization
  quantLabStability.ts      → IC staleness, WF localStorage hint, scheduler failed-job count
  predictions.ts            → prediction resolve/stale helpers

Tests:
  frontend/src/components/quant-lab/*.test.tsx (3 files, 33 tests)
  frontend/src/lib/quantLab*.test.ts, researchReliability.test.ts (28 tests)
  frontend/e2e/quant-lab.spec.ts (Playwright, 8 scenarios)
```

**Navigation today:** URL query `?tab=` among `factor-performance | walk-forward | predictions | pairs | data-quality | model-admin`. Evidence panel is collapsible below tabs, not a top-level route.

---

## 2. Current endpoint map

### Quant Lab–primary

| Method | Path | Consumer | Purpose |
|--------|------|----------|---------|
| GET | `/api/v2/quant-lab/evidence?sleeve=` | `QuantLabEvidencePanel` | Latest cards: factor IC, WF, predictions, pairs, jobs |
| GET | `/api/v2/factors/performance` | `FactorPerformanceTab` | IC panel + deciles (by_regime/by_sector in payload) |
| GET | `/api/v2/factors/ic` | alias | Same as performance |
| POST | `/api/v2/jobs/ic-panel` | RUNBOOK curl only | Recompute IC panel |
| POST | `/research/walk-forward` | `WalkForwardTab` | Run WF research (504 on timeout) |
| GET | `/research/walk-forward/latest?sleeve=` | `WalkForwardTab`, evidence | Last persisted WF summary |
| GET | `/research/walk-forward/{run_id}` | `WalkForwardTab` | Full WF config + summary JSON |
| POST | `/research/pairs` | `PairsTab` | Pairs cointegration research |
| GET | `/research/pairs/latest` | `PairsTab`, evidence | Last pairs summary |
| GET | `/research/pairs/{run_id}` | `PairsTab` | Full pairs run (bounded rows) |
| GET | `/api/v2/predictions` | `PredictionsTab` | Recent prediction snapshots |
| GET | `/api/v2/feedback/summary` | `PredictionsTab` | Outcome aggregates |
| GET | `/data/scheduler/status` | `DataQualityTab` | Scheduler + recent job_logs |
| GET | `/api/v2/version` | `ModelAdminTab` | Pinned strategy/factor versions |
| GET | `/api/v2/weights/{sleeve}` | `ModelAdminTab` | Dynamic weights |
| GET | `/api/v2/audit` | `ModelAdminTab` | Quant audit log |
| GET | `/api/v2/factors/admin` | `ModelAdminTab` | Factor catalog admin view |

### Related v2 (not in Quant Lab UI)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v2/jobs/rebalance` | Monthly weight rebalance |
| POST | `/api/v2/jobs/resolve-outcomes` | Mentioned in i18n; no Quant Lab button |
| POST | `/api/v2/jobs/forward-labels` | Forward return labels job |
| POST | `/api/v2/jobs/outcome-weights` | Outcome weight feedback |
| POST | `/api/v2/jobs/pit-fundamentals` | PIT fundamentals ingest |
| GET | `/api/v2/jobs/queue` | Job queue listing |
| POST | `/api/v2/jobs/enqueue/{job_name}` | `enqueueV2Job` in api.ts; unused in Quant Lab |
| GET | `/api/v2/admin/round2-stats` | Round-2 ops stats; unused in Quant Lab |
| GET | `/api/v2/similar-signal/{symbol}` | Workspace drawer only |
| POST | `/data/scheduler/run` | Settings / ops |

---

## 3. Existing database tables (quant-relevant)

Initialized via `engines/quant_db.init_quant_db()` (`QuantBase.metadata.create_all` after full `quant_models` import).

| Table | Role in Quant Lab |
|-------|-------------------|
| `factor_ic_history` | Factor Performance evidence + IC panel output |
| `factor_decile_history` | Decile spreads (API returns; UI does not render) |
| `factor_definitions` | Model Admin catalog |
| `factor_weights` | Model Admin dynamic weights |
| `market_regimes` | Regime classifier output |
| `backtest_runs` | Walk-forward (`run_type=walk_forward_research`) + other backtests |
| `backtest_equity_points` | Equity curves (not shown in Quant Lab) |
| `pairs_research_runs` | Pairs research persistence (max 20 runs, 50 pairs/run) |
| `prediction_snapshots` | Prediction Outcomes tab + evidence |
| `prediction_outcomes` | Resolved forward returns |
| `trade_predictions` / `trade_outcomes` | Trade feedback loop |
| `job_queue` | Async job metadata |
| `job_logs` (historical_store) | Scheduler / quant_daily_jobs logs |
| `quant_audit_logs` | Model Admin audit |
| `score_attribution` | WF may write research snapshots |
| `feature_provenance` | PIT feature lineage (ops) |
| `forward_return_labels` | Label builder job |
| `universe_pit` | WF PIT universe filter |

**Not present:** `research_ideas`, `research_experiments`, `research_runs` (unified index), `change_proposals`, `historical_analysis_memory`.

Migrations: ad-hoc column adds in `quant_db._migrate_quant_columns()`; no Alembic. Proposed SQL reference: `docs/schemas/quant_v2_tables.sql`.

---

## 4. Existing persisted run types

| run_type / source | Storage | Written by | Retention |
|-------------------|---------|------------|-----------|
| `walk_forward_research` | `backtest_runs` | `persist_walk_forward_run` | Unbounded |
| `pairs_*` (UUID) | `pairs_research_runs` | `persist_pairs_run` | Last 20 runs pruned |
| IC panel (implicit run) | `factor_ic_history` rows keyed by `as_of_date` | `run_ic_panel` | Append per date |
| Prediction batch | `prediction_snapshots` + `prediction_outcomes` | v2 score + `resolve_prediction_outcomes` | Append |
| `quant_daily_jobs` | `job_logs` + audit | `run_daily_quant_jobs` | Log retention |
| Queue jobs | `job_queue` | `enqueue_job` | Listed, not pruned in UI |

Walk-forward UI sets `persist_snapshots: false` on manual Run (snapshots to attribution optional); full run still persisted to `backtest_runs` when not DEMO_MODE.

---

## 5. Existing quantitative calculations

| Engine | Module | Outputs used by Quant Lab |
|--------|--------|----------------------------|
| IC panel | `engines/weighting/ic_panel.py` | IC, IR, hit_rate, sample_n, deciles → `factor_ic_history` |
| Factor performance | `engines/factors/performance.py` | Aggregates IC + deciles by horizon/regime/sector |
| Walk-forward | `services/walk_forward_research_service.py` | PIT universe, ScoringEngine, rank IC, turnover, aggregate horizons |
| Pairs | `services/pairs_research_service.py` + `engines/pairs/*` | Engle-Granger, hedge ratio, half-life, z-score |
| Predictions | `engines/prediction/snapshots.py` | Snapshot list, outcome resolution vs SPY/sector |
| Trade feedback | `services/trade_feedback_service.py` | Mean forecast error, recent outcomes |
| Regime | `engines/weighting/regime_classifier.py` | SPY regime (daily job) |
| Weight rebalance | `engines/weighting/weight_store.py` | Monthly smooth rebalance (job) |
| Reliability (client) | `frontend/src/lib/researchReliability.ts` | 0–100 scores, lifecycle, WF overfitting warnings |
| Quant health | backend health service | Data freshness sections (via `QuantHealthCard`) |

**Explicitly not implemented:** PBO, CPCV, deflated Sharpe, trial-count metadata, server-persisted reliability scores.

---

## 6. Existing jobs and scheduler behavior

**`services/quant_jobs.run_daily_quant_jobs`** (when `QUANT_JOBS_ENABLED`):

1. Classify SPY regime → `market_regimes`
2. IC panel → `factor_ic_history`
3. On first trading day of month (or `force_rebalance`): weight rebalance + trade feedback learning
4. Resolve prediction outcomes
5. Optional: forward labels, outcome weight feedback, PIT fundamentals

**Job queue handlers** (`engines/jobs/handlers.py`): `quant_daily_jobs`, `daily_pipeline`, portfolio/scan refresh jobs — no `ic_panel` standalone handler (IC triggered via `POST /api/v2/jobs/ic-panel`).

**Scheduler** (`services/scheduler.py` via `/data/scheduler/*`): quote/fundamental refresh, daily pipeline; status surfaced in Data Quality tab.

**Quant Lab does not trigger:** IC panel, resolve-outcomes, rebalance, enqueue jobs — user must use curl, Settings, or future UI.

---

## 7. Functional features

| Feature | Status |
|---------|--------|
| Evidence overview on load | ✅ `GET /api/v2/quant-lab/evidence` |
| Factor Performance tab + reliability | ✅ |
| Walk-forward run + latest hydrate | ✅ |
| Pairs run + latest hydrate | ✅ |
| Predictions + feedback (partial failure tolerant) | ✅ |
| Data Quality (health + scheduler) | ✅ |
| Model Admin (version/weights/audit/factors) | ✅ |
| Research Reliability per tab | ✅ client-side |
| Evidence → action boundary | ✅ copy only |
| Feature flags (503 when disabled) | ✅ tested |
| Demo mode guards on heavy POSTs | ✅ |
| i18n en/zh for Quant Lab | ✅ |
| Playwright E2E scaffolding | ✅ |

---

## 8. Incomplete features

| Gap | Detail |
|-----|--------|
| Ideas / Experiments / Results / Model Monitor IA | Current tabs map 1:1 to old names only |
| Unified run history list | Only per-type latest + detail endpoints |
| Change Proposals | No persistence or UI |
| Evidence impact / Major Evidence Gate | Not modeled server-side |
| IC panel / resolve-outcomes in UI | Documented in i18n; no buttons |
| Factor decile / regime / sector charts | Normalized in API; not rendered |
| WF period-level drill-down | `periods[]` in summary; UI shows aggregates only |
| PBO / CPCV / deflated Sharpe | Warnings only (`pboNotImplemented`) |
| Similar historical cases | `similar-signal` API exists; not in Quant Lab |
| `API_REFERENCE.md` | Referenced in docs but **file missing** from repo |
| Sleeve default inconsistency | Evidence panel defaults `penny`; docs mention `medium` |
| Apply weights from Quant Lab | Explicitly blocked; no proposal workflow |
| Server-persisted reliability | Recomputed every render |

---

## 9. Backend outputs hidden by the UI

| Payload field / endpoint | Hidden from |
|--------------------------|-------------|
| `FactorPerformanceResponse.by_horizon` | Factor Performance tab |
| `by_regime`, `by_sector` | Factor Performance tab |
| Per-factor `deciles[]` | Factor Performance tab |
| `WalkForwardResearchResponse.periods[]` | Walk-forward tab (aggregate only) |
| `mean_turnover`, `snapshots_written` | Walk-forward tab |
| `weights_updated` flag | Walk-forward tab |
| Pairs `notes[]`, `excluded[]`, per-pair warnings | Partially shown |
| `GET /api/v2/jobs/queue` | Entire endpoint |
| `GET /api/v2/admin/round2-stats` | Entire endpoint |
| `POST /api/v2/jobs/*` job triggers | No Quant Lab controls |
| `backtest_equity_points` | No chart |
| Audit payload JSON details | Truncated list in Model Admin |
| `weights_by_regime` on weights response | Model Admin shows flat weights only |

---

## 10. Duplicated or obsolete components

| Item | Notes |
|------|-------|
| `getV2FactorIc` vs `getV2FactorPerformance` | Alias endpoints; duplicate client wrappers |
| `QuantLabEvidencePanel` vs tab last-run hints | Overlapping “latest run” UX (panel + per-tab hydrate) |
| `ResearchWarning` + `ResearchOnlyBadge` + `EvidenceToActionBoundary` | Three overlapping “research only” surfaces |
| `PortfolioResearch` vs Quant Lab | Portfolio research tab is basket what-if; not duplicate of Quant Lab |
| `QuantHealthCard` in Settings + Data Quality | Shared component (good); not obsolete |
| Legacy `medium` bucket in tests/seeds | UI deprecates medium; Quant Lab seeds still use `medium` in contracts |
| `quant-lab-wf-last-run` localStorage | Parallel to server persisted WF; minor duplication |

No fully obsolete Quant Lab components identified for removal in Phase 1.

---

## 11. API compatibility risks

| Risk | Mitigation |
|------|------------|
| Tab URL `?tab=` values | Keep redirects when renaming to Overview/Experiments/… |
| `QuantLabLastRunSummary` shape | Extend, don’t break — evidence panel depends on it |
| `GET /api/v2/quant-lab/evidence` | Add fields optionally; keep `factor_ic`…`jobs` keys |
| `/research/walk-forward` POST body | Preserve `WalkForwardResearchRequest` |
| `/research/pairs` response | `PairsResearchResponse` used by normalizers |
| Feature flag 503 behavior | Contract tests must stay green |
| `persist_snapshots: false` default in UI | Changing default affects DB growth |
| Missing `API_REFERENCE.md` | Add in Phase 2+ when endpoints consolidate |
| Thin `research_runs` index | Point `result_reference` to existing JSON tables — no payload duplication |

---

## 12. Migration strategy

### Principles

1. **Adapters over rewrites** — wrap `walk_forward_research_service`, `pairs_research_service`, `ic_panel`, prediction snapshots.
2. **Thin index, fat payloads** — new `research_runs` row holds contract metadata; full results stay in existing tables.
3. **No silent live updates** — `evidence_impact` defaults to `informational`; `major_*` requires gate + Change Proposal.
4. **URL compatibility** — `/quant-lab?tab=factor-performance` → `/quant-lab/experiments?…` redirects during transition.
5. **Deterministic tests** — extend `backend/tests/fixtures/quant_lab_fixtures.py`; no live market in CI.

### Persistence phases

| Step | Action |
|------|--------|
| P2a | Add `research_ideas`, `research_experiments` tables + SQLAlchemy models + migration helper in `quant_db` |
| P2b | Add `research_runs` index table (common contract columns, `result_reference` JSON pointer) |
| P2c | Backfill adapter: on WF/pairs/IC panel completion, upsert index row |
| P3 | Optional `change_proposals` table linked to `experiment_id` |
| P4 | Deprecate tab-centric evidence IDs gradually; evidence API returns unified run summaries |

### `result_reference` pointer shape (design)

```json
{
  "store": "backtest_runs | pairs_research_runs | factor_ic_history | prediction_snapshots | job_logs",
  "run_id": "uuid-or-composite",
  "detail_path": "/research/walk-forward/{run_id}"
}
```

---

## 13. Target information architecture

```
Quant Lab (/quant-lab)
├── Overview          ← evidence cards, trust badges, activity feed, reliability rollup
├── Ideas             ← hypotheses, tags, links to symbols/factors (new)
├── Experiments       ← configure + launch runs (WF, pairs, IC panel, outcome resolution)
├── Results           ← unified run history + detail views (per run_type viewers)
└── Model Monitor     ← data quality, scheduler, versions, weights, audit, factor lifecycle
```

### Feature → destination map

| Existing feature | Target nav |
|------------------|------------|
| Evidence Overview | **Overview** + **Results** (latest) |
| Factor Performance | **Experiments** (IC panel job), **Results**, **Model Monitor** |
| Walk-Forward | **Experiments**, **Results** |
| Prediction Outcomes | **Experiments** (resolve job), **Results**, **Model Monitor** |
| Pairs Trading | **Experiments**, **Results** |
| Data Quality | **Model Monitor** |
| Model Admin | **Model Monitor** |

---

## 14. Common research-run contract (design)

Typed contract for index rows and API list responses. Full payloads remain in existing stores.

```typescript
type EvidenceImpact =
  | "informational"
  | "supporting"
  | "contradicting"
  | "major_positive"
  | "major_negative"
  | "integrity_blocker";

type ResearchRunStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

interface ResearchRunContract {
  run_id: string;
  experiment_id: string | null;
  idea_id: string | null;
  run_type: string; // walk_forward | pairs | factor_ic_panel | prediction_outcomes | data_quality | ...
  name: string;
  status: ResearchRunStatus;
  verdict: string | null; // e.g. pass | fail | inconclusive | blocked
  evidence_impact: EvidenceImpact;
  reliability: { score_0_to_100: number; status: string } | null; // optional server mirror of client scoring
  sleeve: string | null;
  universe: string[] | null;
  parameters: Record<string, unknown>;
  strategy_version: string;
  factor_model_version: string;
  data_cutoff: string | null; // as-of / end_date
  sample_size: number | null;
  primary_metrics: { label: string; value: string | number }[];
  warnings: string[];
  blockers: string[];
  started_at: string | null;
  completed_at: string | null;
  result_reference: {
    store: string;
    run_id: string;
    detail_path?: string;
  };
}
```

### Evidence impact rules (design)

| Level | Meaning |
|-------|---------|
| `informational` | Default; does not affect scan/ranking |
| `supporting` | Small capped positive contribution after review |
| `contradicting` | Small capped negative contribution after review |
| `major_positive` / `major_negative` | Requires Major Evidence Gate + Change Proposal |
| `integrity_blocker` | Data/risk failure; may block decisions faster than alpha |

### Table adaptation (no full payload duplication)

| Existing table | Maps to contract |
|----------------|------------------|
| `backtest_runs` | `run_id`, `run_type`, `config_json` → parameters/sleeve/universe, `metrics_json` → primary_metrics/verdict, timestamps |
| `pairs_research_runs` | `run_id`, `config_json`, `summary_json`, `pairs_json` via reference |
| `factor_ic_history` (aggregate) | Composite `run_id = ic_panel:{sleeve}:{as_of_date}` |
| `prediction_snapshots` (batch) | Composite run per resolve job or daily batch |
| `job_logs` / `job_queue` | `run_type=quant_job`, status from job row |

New columns on `research_runs` only: `experiment_id`, `idea_id`, `evidence_impact`, `verdict`, `reliability_json`, `result_reference_json`.

---

## 15. Source → target matrix

| Existing feature | Current component | Current endpoint | Current persistence | New destination | Action | Required tests |
|------------------|-------------------|------------------|---------------------|-----------------|--------|----------------|
| Evidence overview | `QuantLabEvidencePanel` | `GET /api/v2/quant-lab/evidence` | Aggregated from IC/WF/pairs/jobs | **Overview** | Extend | `test_quant_lab_evidence_contract`, evidence panel tests |
| Factor IC view | `FactorPerformanceTab` | `GET /api/v2/factors/performance` | `factor_ic_history` | **Results**, **Model Monitor** | Extend (show deciles/regime) | contract + reliability tests |
| IC panel job | RUNBOOK curl | `POST /api/v2/jobs/ic-panel` | `factor_ic_history` | **Experiments** | Wire UI button | new contract test for job enqueue |
| Walk-forward | `WalkForwardTab` | `POST/GET /research/walk-forward*` | `backtest_runs` | **Experiments**, **Results** | Reuse | WF service + contract tests |
| Pairs research | `PairsTab` | `POST/GET /research/pairs*` | `pairs_research_runs` | **Experiments**, **Results** | Reuse | pairs + contract tests |
| Predictions | `PredictionsTab` | `GET /api/v2/predictions`, `/feedback/summary` | `prediction_snapshots`, `prediction_outcomes` | **Results**, **Model Monitor** | Extend | predictions contract tests |
| Resolve outcomes | i18n hint only | `POST /api/v2/jobs/resolve-outcomes` | `prediction_outcomes` | **Experiments** | Add UI | job contract test |
| Data quality | `DataQualityTab` | `getQuantHealthSummary`, `/data/scheduler/status` | `job_logs`, health meta | **Model Monitor** | Move tab | DataQuality tab tests |
| Model admin | `ModelAdminTab` | `/api/v2/version`, `/weights`, `/audit`, `/factors/admin` | `factor_weights`, `quant_audit_logs` | **Model Monitor** | Move tab | Model Admin tab tests |
| Research reliability | `ResearchReliabilityCard` | (client-only) | — | All views | Reuse; optional server mirror | `researchReliability.test.ts` |
| Evidence boundary | `EvidenceToActionBoundary` | — | — | **Overview** footer | Reuse | E2E boundary test |
| Change proposals | — | — | — | **Model Monitor** / **Ideas** | **New** | new proposal CRUD tests |
| Ideas | — | — | — | **Ideas** | **New** | idea CRUD tests |
| Experiments registry | — | — | — | **Experiments** | **New** | experiment + run linkage tests |
| Unified run list | — | — | — | **Results** | **New** | `GET /api/v2/research/runs` contract |
| Similar signal | `StockDetailDrawer` | `GET /api/v2/similar-signal/{symbol}` | computed | **Results** (optional) | Extend | existing backend tests |
| Job queue | — | `GET /api/v2/jobs/queue` | `job_queue` | **Model Monitor** | Wire UI | queue contract test |
| Tab shell | `QuantLabPage` | `?tab=` | — | Route-based nav | Replace | E2E update + redirects |

---

## 16. Phase-by-phase implementation checklist

### Phase 1 — Architecture audit ✅ (this document)

- [x] Map frontend, endpoints, tables, jobs, calculations
- [x] Identify gaps, hidden outputs, compatibility risks
- [x] Design common research-run contract
- [x] Define target IA and source→target matrix
- [x] Establish test baseline
- [x] Single docs commit

### Phase 2 — Common contract + backend aggregation ✅

- [x] `ResearchRunSummary` Pydantic model (`models/schemas_research.py`)
- [x] Tables: `research_ideas`, `research_experiments`, `research_runs`, `evidence_memory`, `factor_lineage`, `change_proposals`
- [x] `research_run_service.py` adapters (WF, pairs, IC panel, predictions, portfolio policy, similar_signal, jobs)
- [x] `GET /api/v2/research/runs`, `/runs/{run_id}`, `/runs/compare`
- [x] Ideas, experiments, evidence memory, factor lineage, change proposals CRUD
- [x] `evidence_impact_policy.py` + `major_evidence_gate.py` (deterministic)
- [x] Persist hooks: walk-forward, pairs, portfolio backtest
- [x] `docs/API_REFERENCE.md` created
- [x] Tests: `tests/test_research_foundation.py` (19 tests)
- [x] Full backend suite: **339 passed, 2 skipped**

**Files added:** `backend/models/schemas_research.py`, `backend/api/routes_research_lab.py`, `backend/services/research_*.py`, `backend/services/evidence_*.py`, `backend/services/major_evidence_gate.py`, `backend/services/change_proposals_service.py`, `backend/services/factor_lineage_service.py`

**Env:** `QUANT_LAB_RESEARCH_API_ENABLED`, `RESEARCH_MAX_ORDINARY_MODIFIER`

### Phase 3 — Overview + Ideas (navigation shell)

- [x] Top-level nav: Overview, Ideas, Experiments, Results, Model Monitor (+ Legacy tools)
- [x] URL query `?section=` with default `overview`; `?tab=` redirects to `section=legacy`
- [x] `GET /api/v2/research/overview` — bounded rollup (confidence, freshness, brief, ideas, activity, maintenance)
- [x] Deterministic research brief (`research_brief_service.py`) + idea generation with dedup
- [x] Overview UI: state summary, brief, recommended ideas, activity, evidence maintenance (real job endpoints)
- [x] Ideas board UI: search/filter, manual create, generate, edit/notes/priority, archive, duplicate, configure experiment
- [x] Legacy six tabs preserved under `section=legacy`
- [x] i18n keys (en + zh)
- [x] Tests: `test_research_overview.py`, frontend nav/overview/ideas tests
- [ ] Link ideas to symbols/factors/sleeves (metadata only) — deferred to Phase 4+

### Phase 4 — Unified Experiment Studio

- [x] `ExperimentStudio` replaces experiments section hub (legacy runners under Legacy tools)
- [x] Six templates: factor validation, walk-forward, prediction calibration, pairs, similar-signal, portfolio policy
- [x] Shared flow: choose → configure → review → run → status → result (URL `step=` query)
- [x] Presets: Quick Check, Standard Research, Robust Validation (+ custom) with visible parameters
- [x] `POST /experiments/validate` pre-run checks; `POST /experiments/{id}/launch` with staged jobs
- [x] `GET /experiments/templates`, `/presets`, `/jobs/{job_id}`
- [x] Universe resolver: scan, saved scan, watchlist, holdings, bucket, custom symbols
- [x] Idea → experiment studio navigation from Ideas board
- [x] Tests: `test_experiment_studio.py`, frontend studio tests
- [ ] Results detail router (Phase 5) — studio links to results section only

### Phase 5 — Results unified history

- [ ] Results list from `GET /api/v2/research/runs`
- [ ] Detail routers: WF viewer, pairs viewer, IC snapshot viewer, prediction batch viewer
- [ ] Surface hidden fields: deciles, regime/sector, WF `periods[]`
- [ ] Historical case notes (optional link to similar-signal)
- [ ] Tests: list pagination, detail hydration, normalizers

### Phase 6 — Model Monitor

- [ ] Merge Data Quality + Model Admin into Model Monitor sub-sections
- [ ] Factor lifecycle dashboard (promote/keep/watch/retire from server factors)
- [ ] Job queue panel + trigger buttons (IC panel, resolve-outcomes, quant_daily_jobs)
- [ ] Integrity blockers section (`integrity_blocker` runs)
- [ ] Tests: tab merge without regression, job triggers in demo guard

### Phase 7 — Change Proposals + evidence gates

- [ ] `change_proposals` table + API (draft → review → approved/rejected)
- [ ] Major Evidence Gate: server rules for `major_positive` / `major_negative` / `integrity_blocker`
- [ ] UI: proposal builder from Results; explicit apply confirmation (still no silent scan update)
- [ ] Persist reviewer notes + linked `run_id`s
- [ ] Full E2E: idea → experiment → run → result → proposal
- [ ] Update `docs/INSTITUTIONAL_QUANT_ARCHITECTURE.md`, `docs/RESEARCH_RELIABILITY.md`, `README.md`

---

## 17. Reusable functions (keep)

### Backend

- `services/walk_forward_research_service.py` — full WF pipeline
- `services/pairs_research_service.py` / `pairs_research_store.py`
- `services/quant_lab_summary_service.py` — evidence card builders
- `engines/weighting/ic_panel.py` — IC/decile persistence
- `engines/factors/performance.py` — performance API
- `engines/prediction/snapshots.py` — predictions + resolve
- `services/quant_jobs.py` — scheduled quant maintenance
- `engines/jobs/queue.py` — job dispatch
- `models/schemas_v2.py` — `QuantLabLastRunSummary`, WF/pairs schemas

### Frontend

- `researchReliability.ts` — all `compute*Reliability` functions
- `quantLabNormalizers.ts` / `quantLabFormatters.ts` / `quantLabLastRun.ts`
- `QuantLabTabShell.tsx`, `ResearchReliabilityCard.tsx`
- `api.ts` research client functions
- `EvidenceToActionBoundary.tsx`, `ApplyChangesNotice.tsx`

---

## 18. Missing functions (build)

| Capability | Priority |
|------------|----------|
| `research_ideas` / `research_experiments` CRUD | P3 |
| `research_runs` index + list API | P2 |
| Run adapters (existing stores → contract) | P2 |
| `change_proposals` workflow | P7 |
| Major Evidence Gate (server) | P7 |
| Unified Results detail router | P5 |
| Experiment presets (exploratory / robust) | P4 |
| Historical analysis memory / similar cases in Lab | P5+ |
| Server-side reliability persistence (optional) | P6 |
| PBO/CPCV/deflated Sharpe backends | Future |
| `docs/API_REFERENCE.md` | P2 |

---

## 19. Main migration risks

1. **Tab URL breaking changes** — mitigated by redirects and dual routing during transition.
2. **Dual evidence sources** — evidence API vs unified runs; consolidate in Phase 5.
3. **Sleeve defaults** (`penny` vs `medium` in docs/seeds) — align in Phase 3.
4. **WF DB growth** — `persist_snapshots` and unbounded `backtest_runs`; add retention policy in Phase 2.
5. **Incomplete `init_quant_db` imports** — module load registers all models; document any new tables in `quant_db.py`.
6. **Missing API_REFERENCE.md** — downstream doc links broken until Phase 2.
7. **Client-only reliability** — server contract should not require reliability for list API initially.
8. **DEMO_MODE** — pairs/WF persistence disabled; test both modes in contracts.

---

## 20. Test baseline (Phase 3)

Recorded: **2026-06-20** after Phase 3.

### Backend (full suite)

```bash
cd backend && python -m pytest -q
```

**Result:** `347 passed, 2 skipped`

### Backend (research overview)

```bash
cd backend && python -m pytest tests/test_research_overview.py -q
```

**Result:** `8 passed`

### Frontend (Quant Lab + new nav)

```bash
cd frontend && npm test -- --run src/components/quant-lab src/lib/quantLabNavigation.test.ts src/lib/researchOverviewNormalizers.test.ts
```

**Result:** `60 passed` (53 quant-lab component + 7 lib)

### Frontend (full suite)

```bash
cd frontend && npm test -- --run
```

**Result:** `166 passed`

## 20 (archived). Test baseline (Phase 2)

Recorded: **2026-06-20** after Phase 2.

### Backend (full suite)

```bash
cd backend && python -m pytest -q
```

**Result:** `339 passed, 2 skipped`

### Backend (research foundation)

```bash
cd backend && python -m pytest tests/test_research_foundation.py -q
```

**Result:** `19 passed`

### Backend (Phase 1 Quant Lab)

```bash
cd backend && python -m pytest \
  tests/test_quant_lab_contracts.py \
  tests/test_quant_lab_integration.py \
  tests/test_walk_forward_research_service.py \
  tests/test_pairs_research.py -q
```

**Result:** `36 passed, 1 skipped`

### Frontend (unchanged in Phase 2)

```bash
cd frontend && npm test -- --run \
  src/components/quant-lab \
  src/lib/quantLabNormalizers.test.ts \
  src/lib/quantLabFormatters.test.ts \
  src/lib/quantLabLastRun.test.ts \
  src/lib/researchReliability.test.ts
```

**Result:** `61 passed` (Phase 1 baseline)

## 20 (archived). Test baseline (Phase 1)

Recorded: **2026-06-20** on branch `quant-lab-workbench`.

### Backend

```bash
cd backend && python -m pytest \
  tests/test_quant_lab_contracts.py \
  tests/test_quant_lab_integration.py \
  tests/test_walk_forward_research_service.py \
  tests/test_pairs_research.py -q
```

**Result:** `36 passed, 1 skipped, 7 warnings in 11.62s`

### Frontend

```bash
cd frontend && npm test -- --run \
  src/components/quant-lab \
  src/lib/quantLabNormalizers.test.ts \
  src/lib/quantLabFormatters.test.ts \
  src/lib/quantLabLastRun.test.ts \
  src/lib/researchReliability.test.ts
```

**Result:** `7 files, 61 passed in 1.20s`

### Not run in Phase 1

- Playwright E2E (`frontend/e2e/quant-lab.spec.ts`) — requires `scripts/quant-lab-e2e-up.sh`
- Full backend suite (`pytest` entire `tests/`)

---

## 21. Phase 1 files changed

| File | Change |
|------|--------|
| `docs/QUANT_LAB_REDESIGN_PROGRESS.md` | Created (this audit) |

No application code changes in Phase 1.

---

## 22. Remaining work (summary)

Phases 2–7 per checklist above. Immediate next step: **Phase 2** — implement `research_runs` index + adapters without UI redesign.

---

## Related docs

- [QUANT_LAB.md](./QUANT_LAB.md) — current user-facing behavior
- [RESEARCH_RELIABILITY.md](./RESEARCH_RELIABILITY.md) — client reliability scoring
- [INSTITUTIONAL_QUANT_ARCHITECTURE.md](./INSTITUTIONAL_QUANT_ARCHITECTURE.md) — quant engine map
- [RUNBOOK.md](./RUNBOOK.md) — ops (IC panel, WF timeout)
- [QUANT_LAB_FUNCTIONAL_TEST_REPORT.md](./QUANT_LAB_FUNCTIONAL_TEST_REPORT.md) — prior test pass
