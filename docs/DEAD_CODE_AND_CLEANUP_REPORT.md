# Dead Code and Cleanup Report

**Date:** 2026-06-05  
**Method:** Read-only repo audit with ripgrep import/reference tracing (backend `*.py`, frontend `src/**/*`, docs `*.md`).  
**Rules followed:** No deletions, renames, or import changes in this pass.  
**Companion:** [POST_UPDATE_PROJECT_AUDIT.md](POST_UPDATE_PROJECT_AUDIT.md)

---

## Classification legend

| Class | Meaning |
|-------|---------|
| **ACTIVE_RUNTIME** | Imported by running backend or frontend app code |
| **ACTIVE_API_ONLY** | HTTP route or CLI exists; no frontend consumer |
| **ACTIVE_FRONTEND_ONLY** | UI exists; backend missing, stubbed, or partial |
| **TEST_ONLY** | Production code does not import; tests do |
| **DOC_ONLY** | Referenced in docs/README only |
| **STUB** | Placeholder, pass-through, fake integration, or heuristic labeled as ML |
| **FLAG_ONLY** | Config flag with no meaningful runtime branch |
| **DUPLICATE** | Overlaps another active module |
| **LEGACY_COMPAT** | Old path kept for bookmarks, v1 API, or gradual migration |
| **DEAD** | No imports, routes, scripts, tests, or documented reason |

---

## 1. Import / reference map (summary)

### Backend API → services (runtime entrypoints)

All routers mounted in `backend/main.py`. Key chains:

| Router | Primary services / engines |
|--------|---------------------------|
| `routes_scan.py` | `scan_manager` → `scan_scoring` → screener **or** `ScoringEngine` |
| `routes_analyze.py` | `analyze_service`, `research_report_v2` / `research_report`, `time_series_diagnostics_service` |
| `routes_v2.py` | `quant_v2_service`, `quant_jobs`, `quant_risk_sizing_service`, `research_report_v2`, lazy engine jobs |
| `routes_backtest.py` | `ml/backtest_*`, `backtest_analytics` |
| `routes_portfolio.py` | `portfolio_optimizer`, `institutional_backtest_service`, `factor_exposure_service` |
| `routes_research.py` | `walk_forward_research_service`, `pairs_research_service` |
| `routes_ml.py` | `qlib_integration` |
| `routes_allocation.py` | `allocation_recommender` |
| `routes_lean.py` | `lean_handoff` |
| `routes_explain.py` | `llm_explainer` + screeners |

### Backend layering (who imports whom)

```text
screeners/*.py ──► screener.score() [legacy scan default]
                 └► engines/factor/sleeve_signals ──► scoring/* signal math

engines/scoring/engine.py ──► FactorEngine ──► scoring/* + engines/factor/*
                          └► quant_v2_service, scan_scoring (flag)

ml/backtest_*.py ──► ml/backtest_engine ──► engines/backtest/metrics, cost_model
engines/backtest/institutional.py ──► services/policy_backtest ──► same metrics

scoring/data_quality.py ◄── engines/scoring/data_quality.py (wrapper + dq_multiplier)
```

### Frontend import map

```text
app/layout.tsx ──► Nav, ApiStatus, Providers, CommandPalette
app/workspace/page.tsx ──► WorkspacePage ──► AnalysisPanel, Round2Panel, …
app/scan/page.tsx ──► ScanHub ──► BucketPage ──► StockTable, StockDetailDrawer
lib/api.ts ──► (single HTTP client; ~38 exports used, ~12 unused)
```

**Component tree:** 41/41 `components/*.tsx` files are reachable from routes (no orphan components).

---

## 2. Master table — suspicious and cleanup targets

Evidence uses ripgrep: importers = files that `import` or lazy-import the module; `grep count 1` = definition site only.

### Backend — special attention targets

| file_or_module | classification | evidence | risk_if_deleted | recommendation | safe_next_action |
|----------------|----------------|----------|-----------------|----------------|------------------|
| `backend/scoring/data_quality.py` | **ACTIVE_RUNTIME** | Importers: `scan_manager`, `scan_scoring`, `analyze_service`, `watchlist_scanner`; re-exported by `engines/scoring/data_quality.py` | **High** — breaks scan DQ filter and score adjustment | **Keep** — canonical DQ helpers | Document as canonical; do not merge blindly |
| `backend/engines/scoring/data_quality.py` | **DUPLICATE** (intentional wrapper) | Re-exports `scoring.data_quality`; adds `dq_multiplier`; importers: `engines/scoring/engine`, `quant_v2_service`, `engines/sizing/engine`, tests | **High** if deleted without moving `dq_multiplier` | **Keep** — v2 multiplier layer | Later: inline `dq_multiplier` only here or only in `scoring/` |
| `backend/engines/scoring/engine.py` | **ACTIVE_RUNTIME** | `quant_v2_service`, `scan_scoring` (flag), `walk_forward_research_service` | **High** | **Keep** | Enable scan flag in staging first |
| `backend/screeners/*.py` + `screener.score()` | **ACTIVE_RUNTIME** + **LEGACY_COMPAT** | `scan_manager` Stage B default path; `analyze_service`, `routes_explain`, `quant_v2_service.enrich` | **High** — default scan rankings | **Keep** until `USE_SCORING_ENGINE_IN_SCAN=true` validated | Parity tests already exist |
| `backend/scoring/*` signal modules | **ACTIVE_RUNTIME** | `technical.py` hub (10+ importers); factors via `sleeve_signals`, reports, `factor_series` | **High** | **Keep** — factor math library | Not duplicate of `engines/factor/` (compute vs registry) |
| `backend/engines/factor/*` | **ACTIVE_RUNTIME** | `FactorEngine` ← `ScoringEngine`; catalog used by IC panel, jobs | **High** | **Keep** | Rename plural `engines/factors/` in docs to avoid confusion |
| `backend/ml/backtest_engine.py` | **ACTIVE_RUNTIME** | Imported by `backtest_medium/compounder/penny.py`; uses `engines/backtest/metrics` | **High** | **Keep** — symbol-level backtest core | Unify docs: when to use ml vs institutional |
| `backend/ml/backtest_{medium,penny,compounder}.py` | **ACTIVE_RUNTIME** | `routes_backtest.py`, `routes_stock.py`, `routes_trader_intel.py` | **High** | **Keep** | — |
| `backend/ml/backtest_vectorbt.py` | **ACTIVE_RUNTIME** (conditional) | Imported by all three `backtest_*.py`; gated by `VBT_ENABLED` | **Medium** — vectorbt path breaks | **Keep** | Install quant extras only when needed |
| `backend/engines/backtest/institutional.py` | **ACTIVE_RUNTIME** | `institutional_backtest_service`, `routes_v2` portfolio backtest | **High** | **Keep** | Different product surface than ml backtests |
| `backend/services/research_report.py` | **LEGACY_COMPAT** | `routes_analyze.py:127` (when `AI_REPORT_SCHEMA != v2`); `watchlist_scanner:184`; `routes_watchlist` report batch | **Medium** — v1 report + watchlist batch | **Keep** until watchlist uses v2 | Migrate watchlist to v2 report |
| `backend/services/research_report_v2.py` | **ACTIVE_RUNTIME** | `routes_analyze` (v2), `routes_v2/report`; default `AI_REPORT_SCHEMA=v2` | **High** | **Keep** — primary report | — |
| `backend/quant/contracts.py` | **REMOVED** ✅ | Deleted 2026-06-05; had zero importers | — | — | — |
| `backend/quant/__init__.py` | **REMOVED** ✅ | Deleted with contracts.py | — | — | — |
| `backend/config.py` → `BT_ENABLED` | **REMOVED** ✅ | Was FLAG_ONLY; deleted 2026-06-05 | — | — | — |
| `backend/services/qlib_integration.py` | **STUB** | `routes_ml.py`; `QLIB_ENABLED` toggles metadata; rule-proxy alpha, no Qlib SDK | **Low** for API contract | **Keep** API; rename docs to "alpha proxy" | Wire real Qlib or rename endpoint |
| `backend/services/allocation_recommender.py` | **STUB** | `routes_allocation.py`; uses `portfolio_optimizer`; `FINRL_ENABLED` changes notes only | **Low** | **Keep** API-only | Add UI or rename `finrl_allocator` label |
| `backend/services/lean_handoff.py` | **ACTIVE_API_ONLY** | `routes_lean.py`; JSON export works; `LEAN_EXPORT_ENABLED` metadata | **Low** | **Keep** | Frontend UI optional |
| `backend/config.py` → `FINRL_ENABLED` | **FLAG_ONLY** (partial) | Read in `allocation_recommender.py` for notes/enabled field only; no `finrl` import | **Low** | **Keep** until real FinRL or honest rename | — |
| `backend/config.py` → `QLIB_ENABLED` | **STUB** (partial) | Read in `qlib_integration`, screeners when building alpha proxy | **Low** | **Keep** | — |
| `backend/config.py` → `VBT_ENABLED` | **ACTIVE_RUNTIME** | `routes_backtest`, `ml/backtest_*`, `api_settings` | **Medium** | **Keep** | — |
| `backend/quant_core/features.py` | **TEST_ONLY** (prod) | No prod `from quant_core.features`; tests + `quant_core/__init__.py` re-export | **Low** | **Keep** for library growth | Wire into factor research or mark experimental |
| `backend/quant_core/labels.py` | **TEST_ONLY** (prod) | Same pattern; `engines/labels/forward_returns.py` is separate DB job | **Low** | **Keep** | Document distinction vs `engines/labels/` |
| `backend/quant_core/validation.py` | **TEST_ONLY** (prod) | Used by `quant_core/labels.py` + tests only | **Low** | **Keep** | — |
| `backend/quant_core/returns.py`, `diagnostics.py` | **ACTIVE_RUNTIME** | `quant_v2_service`, risk engines, diagnostics service, factor exposure, pairs | **Medium** | **Keep** | — |
| `backend/services/agents/__init__.py` | **DEAD** | Empty; no imports | **Low** | **Delete** empty file | Trivial |
| `backend/scoring/__init__.py` | **DEAD** | Docstring only | **Low** | **Delete** or add explicit exports | Trivial |
| `backend/services/__init__.py` | **DEAD** | Empty | **Low** | **Delete** | Trivial |
| `backend/engines/pairs/__init__.py` | **DEAD** | Empty package marker | **Low** | **Keep** (package) or delete if imports use full paths | Low priority |
| `backend/scripts/alpha_batch_eval.py` | **DOC_ONLY** + CLI | No importers; OpenAlpha research | **Low** | **Keep** CLI | Document in OPENALPHA_INTEGRATION |
| `backend/scripts/alpha_combo_optimizer.py` | **DOC_ONLY** + CLI | Same | **Low** | **Keep** | — |
| `backend/scripts/factor_research_export.py` | **DOC_ONLY** + CLI | Same | **Low** | **Keep** | — |
| `backend/scripts/verify_openbb.py` | **DOC_ONLY** + CLI | Smoke test | **Low** | **Keep** | — |
| `backend/scripts/seed_universe.py` | **ACTIVE_RUNTIME** | `main.py:107` deferred startup | **High** | **Keep** | — |
| `backend/scripts/run_walk_forward_research.py` | **ACTIVE_API_ONLY** | CLI twin of `POST /research/walk-forward` | **Low** | **Keep** | — |
| `backend/data/quandl_client.py` | **ACTIVE_RUNTIME** (narrow) | Only `routes_data.py` | **Low** | **Keep** | Narrow surface OK |

### Backend — dual-path / misleading (not dead, but cleanup-worthy)

| file_or_module | classification | evidence | risk_if_deleted | recommendation | safe_next_action |
|----------------|----------------|----------|-----------------|----------------|------------------|
| `backend/services/scan_scoring.py` | **ACTIVE_RUNTIME** | Sole bridge ScanManager ↔ ScoringEngine; flag `USE_SCORING_ENGINE_IN_SCAN=false` default | **High** | **Keep** | Flip flag in staging |
| `backend/services/analyze_service.py` | **ACTIVE_RUNTIME** + **DUPLICATE** path | v1 analyze; parallel to `quant_v2_service` for Insights | **High** | **Keep**; converge read path | Route Quant tab to v2 read-only |
| `backend/services/llm_explainer.py` | **ACTIVE_RUNTIME** | `/explain`, `/stock`; dual prompt (legacy + quant context via `report_narrative`) | **Medium** | **Keep** | Merge prompts in later commit |
| `backend/services/report_narrative.py` | **ACTIVE_RUNTIME** | `research_report_v2`, `llm_explainer` quant path | **Medium** | **Keep** | — |
| `backend/ml/` vs `backend/engines/backtest/` | **DUPLICATE** (domain split) | Shared `metrics.py`; different simulators (trade-list vs policy) | **High** if merged wrong | **Keep both**; document boundaries | Already unified metrics |

### Frontend — special attention targets

| file_or_module | classification | evidence | risk_if_deleted | recommendation | safe_next_action |
|----------------|----------------|----------|-----------------|----------------|------------------|
| `frontend/src/lib/buckets.ts` → `BUCKET_META` | **REMOVED** ✅ | Deleted 2026-06-05; grep confirmed zero consumers | — | — | — |
| `frontend/src/lib/api.ts` → `getMediumBacktest` | **REMOVED** ✅ | Deleted 2026-06-05 | — | — | — |
| `frontend/src/lib/api.ts` → `getTraderIntelProfile` | **REMOVED** ✅ | Deleted 2026-06-05 | — | — | — |
| `frontend/src/lib/api.ts` → `updateTrade` | **REMOVED** ✅ | Deleted 2026-06-05 | — | — | — |
| `frontend/src/lib/api.ts` → `getLatestAlpha`, `ingestAlphaPredictions` | **ACTIVE_API_ONLY** (client stub) | No component imports; backend `/ml/alpha/*` exists | **Low** | **Keep** or remove pair with backend | Add ML admin UI or remove |
| `frontend/src/lib/api.ts` → `getAllocationRecommendation` | **ACTIVE_API_ONLY** | No UI; backend stub | **Low** | **Keep** API client | Portfolio widget later |
| `frontend/src/lib/api.ts` → `exportToLean`, `getLeanExport`, `importLeanSummary` | **ACTIVE_API_ONLY** | No UI | **Low** | **Keep** | LEAN export button later |
| `frontend/src/lib/api.ts` → `listSavedAnalyze`, `getLatestSavedAnalyze` | **ACTIVE_API_ONLY** | No UI; backend `/saved/analyze` | **Low** | **Keep** or wire Library | — |
| `frontend/src/lib/api.ts` → `getV2UnifiedRisk` | **ACTIVE_RUNTIME** | Wired in Workspace Insights (2026-06-05) | — | **Keep** | — |
| `frontend/src/lib/api.ts` → `getSymbolDiagnostics` | **ACTIVE_RUNTIME** | Wired in Workspace Insights (2026-06-05) | — | **Keep** | — |
| `frontend/src/lib/api.ts` → `getPortfolioFactorExposure` | **ACTIVE_RUNTIME** | Wired in Portfolio exposure tab (2026-06-05) | — | **Keep** | — |
| `frontend/src/app/{penny,medium,compounder}/page.tsx` | **LEGACY_COMPAT** | Redirect to `/scan?bucket=`; trader-intel uses `/${bucket}` URLs | **Medium** if removed | **Keep** redirects | — |
| `frontend/src/app/{trades,reports,scans,watchlist,analyze}/page.tsx` | **LEGACY_COMPAT** | Redirects; `Nav.tsx` pathname matching | **Medium** | **Keep** | — |
| `frontend/src/app/trader-intel/page.tsx` | **ACTIVE_RUNTIME** (hidden) | Not in main nav; Command Palette + API | **Low** | **Keep**; improve discoverability | Add nav link |
| All 41 `components/*.tsx` | **ACTIVE_RUNTIME** | Full import chains to routes | **High** | **Keep** | — |
| `TradeJournal.tsx` `qualityTone()` | **DUPLICATE** | Same thresholds as `DataQualityBadge` | **Low** | **Merge** into `lib/tone.ts` | Refactor-only commit |
| `StockTable.tsx` `riskBadge()` + peers | **DUPLICATE** | Copied in `AnalysisPanel`, `ComparePanel`, `trader-intel` | **Low** | **Merge** shared helper | Refactor-only commit |
| `frontend/src/lib/i18n/messages/*.ts` (orphan keys) | **REMOVED** ✅ | `round2Quant`, `validationPassed/Failed`, `common.results/save/symbols`, `journal.exitTime` — removed 2026-06-05 | — | — | — |
| Research endpoints in UI | **ACTIVE_RUNTIME** | Walk-forward/pairs still API-only; factor exposure wired in Portfolio tab | **N/A** | **Add** Research hub later | Partial UI done |

### Docs-only / script references (not runtime)

| file_or_module | classification | evidence | risk_if_deleted | recommendation | safe_next_action |
|----------------|----------------|----------|-----------------|----------------|------------------|
| `docs/CODEBASE_AUDIT_FOR_QUANT_ROADMAP.md` | **DEAD** (file) | Referenced in audit brief but **not in repo** | **None** | **Ignore** or recreate from POST_UPDATE audit | — |
| `backend/scripts/migrate_sqlite_to_postgres.py` | **DOC_ONLY** + CLI | POSTGRES_MIGRATION.md | **Low** | **Keep** | — |

---

## 3. Scan flow vs scoring (production impact)

| Step | Module | Scoring source | Classification |
|------|--------|----------------|----------------|
| UI Scan | `BucketPage` → `POST /scan/{bucket}` | — | ACTIVE_RUNTIME |
| Stage A | `scan_manager` + universe filters | Hard filters only | ACTIVE_RUNTIME |
| Stage B (default) | `scan_scoring` → `screener.score()` | **Legacy** `screeners` + `scoring/*` | ACTIVE_RUNTIME |
| Stage B (flag) | `scan_scoring` → `ScoringEngine` | **v2 engine** | ACTIVE_RUNTIME when `USE_SCORING_ENGINE_IN_SCAN=true` |
| Insights tab | `Round2Panel` → `/api/v2/score` | **v2 full pipeline** | ACTIVE_RUNTIME |
| Quant tab | `AnalysisPanel` → `/analyze/{symbol}` | **Legacy analyze** | ACTIVE_RUNTIME + DUPLICATE vs v2 |

**Answer:** ScanManager does **not** import ScoringEngine directly; it uses `scan_scoring`, which can route to ScoringEngine. **Legacy screener scoring still determines default production scan rankings.**

---

## 4. Integration flags — real vs scaffolding

| Flag | Runtime behavior | Classification |
|------|------------------|----------------|
| `SCORE_ENGINE_V2_ENABLED` | Gates `/api/v2/score` | ACTIVE_RUNTIME |
| `USE_SCORING_ENGINE_IN_SCAN` | Switches Stage B engine | ACTIVE_RUNTIME (default off) |
| `RISK_ENGINE_V2` | Vol penalty + deductions | ACTIVE_RUNTIME |
| `VBT_ENABLED` | vectorbt backtest branch | ACTIVE_RUNTIME |
| `PYPFOPT_ENABLED` | PyPortfolioOpt vs fallback optimizer | ACTIVE_RUNTIME (branch) |
| `QLIB_ENABLED` | Metadata + proxy alpha path | STUB |
| `FINRL_ENABLED` | Changes allocation response notes | FLAG_ONLY / STUB |
| `LEAN_EXPORT_ENABLED` | Metadata on export payload | STUB (export still works) |
| `BT_ENABLED` | **Nothing** | FLAG_ONLY / DEAD |
| `OPENBB_ENABLED` | Real client when configured | ACTIVE_RUNTIME (optional) |
| `LLM_AGENTS_ENABLED` | Optional LLM enrichment on agents | ACTIVE_RUNTIME (branch, default off) |

---

## 5. Tests map (what validates suspicious code)

| Area | Test files | Gap |
|------|------------|-----|
| Scan scoring parity | `test_scan_scoring_engine_parity.py` | No full `scan_manager` job test |
| Backtest metrics | `test_backtest_metrics.py` | No ml backtest route test |
| quant_core | `test_quant_core_*.py` | `features`/`validation` prod-unused |
| Research | `test_walk_forward_*`, `test_pairs_*`, `test_factor_exposure.py` | API-only |
| Reports | `test_report_narrative.py` | No HTTP report route test |
| v2 phases | `test_quant_v2_phase1-7.py`, `test_round2_*.py` | No full `build_v2_score` integration |

---

## 6. Missing UI states (cleanup-related UX debt)

| Surface | Issue | Related dead/stub API |
|---------|-------|------------------------|
| Workspace load | Silent error on failure | — |
| Library | Swallowed fetch errors | — |
| Insights | No v2-unified-risk panel | `getV2UnifiedRisk` unused |
| Insights | No diagnostics block | `/analyze/.../diagnostics` no client |
| Portfolio | No factor exposure | `/portfolio/factor-exposure` |
| — | No research hub | `/research/walk-forward`, `/research/pairs` |

---

## 7. Proposed cleanup sequence (small safe commits)

Each commit should be independently revertible. **Do not batch destructive deletes.**

### Phase B — Trivial dead weight ✅ **Completed 2026-06-05**

| # | Item | Commit | Status |
|---|------|--------|--------|
| 3 | Remove `BT_ENABLED` from `config.py` + `.env.example` | `78771d9` | ✅ Done |
| 4 | Remove `backend/quant/contracts.py` + `quant/__init__.py` | `b69e613` | ✅ Done |
| 6 | Remove deprecated `BUCKET_META` export | `9daaf6f`, `ab4a80e` | ✅ Done |
| 7 | Remove unused `api.ts` exports (`getMediumBacktest`, `getTraderIntelProfile`, `updateTrade`) | `f809e56` | ✅ Done |
| 8 | Remove orphan i18n keys (en/zh) | `1fbd912` | ✅ Done |

**Verification:** Backend pytest 122 passed / 5 failed (pre-existing env: `exchange_calendars`, API form-data). Frontend `npm test` + `npm run build` pass.

**Deferred from Phase B (not in allowed list):**

| # | Item | Status |
|---|------|--------|
| 5 | Empty `__init__.py` markers (`services/`, `scoring/`, `agents/`) | Pending — not in this cleanup pass |

### Phase A — Zero-risk documentation (no code behavior change)

1. **`docs: add DEAD_CODE report cross-links`** — link from README doc index to this file.
2. **`docs: clarify ml vs engines/backtest boundaries`** — one paragraph in QUANT_STACK.md.

~~3. **`chore: remove unused BT_ENABLED from config and .env.example`** — ✅ done~~
~~4. **`chore: remove dead quant/contracts.py and quant/__init__.py`** — ✅ done~~
5. **`chore: remove empty __init__ re-exports`** — `services/__init__.py`, `scoring/__init__.py`, `services/agents/__init__.py` if truly empty.
~~6. **`frontend: remove deprecated BUCKET_META export`** — ✅ done~~
~~7. **`frontend: remove unused api.ts exports`** — ✅ done~~
~~8. **`frontend: remove unused i18n keys`** — ✅ done~~

### Phase B — Trivial dead weight (low risk) — **see completed table above**

~~3–8 completed. Remaining Phase B item: #5 empty `__init__.py` markers.~~

### Phase C — Consolidation without behavior change

9. **`refactor: extract lib/tone.ts for score/risk badge classes`** — replace duplicates in TradeJournal, StockTable, AnalysisPanel, trader-intel.
10. **`refactor: document scoring/data_quality split`** — comment in both files pointing to canonical vs v2 multiplier.

### Phase D — Legacy migration (medium risk; staging required)

11. **`feat: enable USE_SCORING_ENGINE_IN_SCAN in .env.example staging profile`** — monitor parity logs.
12. **`feat: watchlist report batch uses research_report_v2`** — removes last hard dependency on v1 report path for new runs.
13. **`feat: analyze Quant tab reads v2 score for display`** — keep v1 response fields for compatibility.

### Phase E — API/UI wiring (product commits)

14. **`feat: add getSymbolDiagnostics + Insights panel`** — consumes existing backend route.
15. **`feat: wire getV2UnifiedRisk in Round2Panel`** — consumes existing client stub.
16. **`feat: portfolio factor exposure panel`** — consumes `/portfolio/factor-exposure`.
17. **`feat: research hub page (optional)` — walk-forward + pairs read-only JSON.

### Phase F — Honest naming / stub cleanup (optional)

18. **`refactor: rename qlib_integration metadata to alpha_proxy`** — avoid implying Qlib SDK.
19. **`refactor: allocation_recommender finrl_allocator label → heuristic_allocator`** when `FINRL_ENABLED=false`.
20. **`later: delete research_report.py`** — only after v1 schema retired and watchlist migrated.

---

## 8. Quick reference — safe to delete vs must keep

| Safe to delete (after grep confirm) | Must keep |
|-----------------------------------|-----------|
| ~~`BT_ENABLED` config~~ ✅ removed | `scoring/data_quality.py` |
| ~~`quant/contracts.py`~~ ✅ removed | `engines/scoring/engine.py` |
| ~~`BUCKET_META`~~ ✅ removed | All `screeners/*.py` |
| ~~Unused `api.ts` exports (listed)~~ ✅ removed | `ml/backtest_*.py` (routes depend) |
| ~~Orphan i18n keys~~ ✅ removed | `research_report_v2.py` |
| Empty `__init__.py` markers | `research_report.py` until watchlist migrates |
| | `scan_scoring.py` |

| Do **not** delete (looks duplicate but is not) | Reason |
|-----------------------------------------------|--------|
| `scoring/` vs `engines/scoring/` | Legacy math vs v2 orchestration |
| `ml/backtest_*` vs `engines/backtest/institutional.py` | Symbol vs portfolio simulators |
| `engines/factor/` vs `engines/factors/` | Compute vs IC analytics |
| `quant_core/labels` vs `engines/labels/` | Pure functions vs DB jobs |
| Redirect pages under `app/` | Bookmarks + trader-intel links |

---

## 9. Summary

Phase B safe cleanup **completed 2026-06-05**: `BT_ENABLED`, `backend/quant/`, `BUCKET_META`, three unused `api.ts` exports, and seven orphan i18n key pairs removed across six commits.

The repo remains **well-connected**; remaining dead code is **narrow** (empty `__init__.py` markers, unused `api.ts` clients for API-only endpoints). The larger cleanup opportunity is **architectural duplication with intentional dual paths** (legacy scan/analyze vs quant v2, v1 vs v2 reports, ml vs institutional backtests). **Do not delete `scoring/` or screeners** without completing the ScoringEngine scan migration.

**Next safe cleanups:** empty `__init__.py` markers (#5), consolidate badge tone helpers, then migrate watchlist/report and scan flag in staging.

---

*Last updated: 2026-06-05 after Phase B cleanup commits.*
