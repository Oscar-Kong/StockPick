# UI Feature Integration Audit

**Date:** 2026-06-08  
**Scope:** Map every meaningful backend endpoint to frontend API client, UI consumer, integration status, recommended placement, and required UX states.  
**Prerequisite for:** UI integration Steps 2–10 (see project brief).  
**Companion:** [UI_API_COVERAGE_MAP.md](UI_API_COVERAGE_MAP.md)

---

## Executive summary

StockPick has a **mature backend** (~80 HTTP routes across 17 routers) and a **decision-support frontend** that covers scan, workspace analysis, portfolio optimization, and library — but **advanced quant research and ops surfaces are largely API-only**.

| Integration tier | Count (approx.) | Examples |
|------------------|-----------------|----------|
| Fully integrated | 18 | Scan run/poll, v2 primary score, portfolio optimize/policy/exposure, AI report |
| Partially integrated | 22 | Unified risk (buried in Insights), diagnostics, scan parity (toolbar only), `/health` (footer only) |
| API-only, valuable | 20 | Walk-forward, pairs, factor IC, predictions, allocation, LEAN export, scheduler |
| API-only, admin | 12 | v2 jobs queue, factor admin, alpha ingest, scheduler run |
| Duplicate / confusing | 5 | Research vs Compare vs Journal nav; Insights vs dedicated tabs; v2 report vs analyze report |
| Should stay hidden | 3 | FinRL flag theater, Qlib stub metadata, screenshot trade endpoint |

**Critical gap:** There is **no** `GET /api/v2/health/quant` (or `docs/QUANT_HEALTH.md`). Quant Health UI must **compose** from `/health`, latest scans, saved progress, and optional v2 admin endpoints — or add a backend aggregator in a follow-up.

**Navigation today vs target:**

| Today (`Nav.tsx`) | Target IA |
|-------------------|-----------|
| Home, Research, Compare, Journal, Screen, Portfolio, Library | Home, Scan, Workspace, Portfolio, **Quant Lab**, Library, Settings |
| Settings via gear only | Settings in top nav |
| Trader Intel: route exists, not in nav | Secondary link or Home card |
| No Quant Lab | `/quant-lab` new route |

---

## Classification legend

| Status | Meaning |
|--------|---------|
| **Fully integrated** | Typed client + UI with loading/error/empty; discoverable in intended IA |
| **Partially integrated** | Client and/or UI exist but incomplete, buried, or missing states |
| **API-only but valuable** | Backend ready; should surface in UI (Quant Lab / Portfolio / Home) |
| **API-only and admin-only** | Ops/job triggers; Settings or Quant Lab with explicit Run + warning |
| **Duplicate / confusing** | Overlaps another surface; consolidate in integration pass |
| **Should stay hidden** | Stub, legacy compat, or internal-only |

---

## 1. Core & system health

### `GET /health`

| Field | Value |
|-------|-------|
| API client | `getHealth()` |
| UI consumer | `ApiStatus.tsx` (layout footer) |
| Status | **Partially integrated** |
| Recommended UI | **Home** → `QuantHealthCard`; **Settings** → provider detail panel |
| Component changes | New `QuantHealthCard`, `HealthStatusBadge`; extend `HomeDashboard` |
| States | Loading skeleton; error + `RetryButton`; empty N/A; stale if fetch >5min old |

**Surfaces to show:** provider configured flags, `scheduler_enabled`, `strategy_version`, `factor_model_version`, `redis_connected`, `database_dialect`, `app_env`.

### Quant Health (aggregated — not a single endpoint today)

| Field | Value |
|-------|-------|
| Backend | **Missing** dedicated route; compose from `/health` + `GET /scan/latest/*` + `GET /saved/progress-summary` + future `GET /api/v2/factors/ic` freshness |
| API client | New `getQuantHealthSummary()` (client-side compose initially) |
| Status | **API-only but valuable** (compose) |
| Recommended UI | **Home** card; **Settings** expandable; **Quant Lab → Data Quality** tab |
| Component changes | `QuantHealthCard` with sections: overall, scoring engine flag (from env hint or scan metadata), scan freshness, factor IC (when wired), prediction outcomes (when wired), scheduler warnings |
| States | Partial data OK with per-section stale badges; global error if `/health` fails |

---

## 2. Scan (`routes_scan.py`)

### `POST /scan/{bucket}`, `GET /scan/{job_id}`, `GET /scan/latest/{bucket}`

| Field | Value |
|-------|-------|
| API client | `startScan`, `getScanStatus`, `getLatestScan` |
| UI consumer | `BucketPage`, `ScanHub`, `ScanControls`, `ScanProgress` |
| Status | **Fully integrated** (run flow); **partial** (metadata UX) |
| Recommended UI | **Scan** page (three bucket tabs) |
| Component changes | `StaleDataBadge` when `completed_at` > threshold; per-row `ScoreSourceBadge`; enrich `StockTable` columns |
| States | Scan running progress; empty bucket; error on failed job; stale cached scan warning |

### Scan metadata: `scoring_engine_used`, `parity_summary`

| Field | Value |
|-------|-------|
| Types | `ScanParitySummary`, `ScanStatusResponse` in `types.ts` |
| UI consumer | `ScanScoreMeta` on `BucketPage` toolbar |
| Status | **Partially integrated** |
| Recommended UI | Scan toolbar + **detail drawer Summary** tab |
| Component changes | Extend `ScanScoreMeta` for per-row badge; parity chip in drawer |
| States | Hide parity section when `parity_summary` null (legacy-only scan); tooltip for avg/max delta |

### `POST /scan/{bucket}/{symbol}/pick-summary`

| Field | Value |
|-------|-------|
| API client | `getScanPickSummary` |
| UI consumer | `ScanPickSummaryCell` (lazy on expand) |
| Status | **Fully integrated** |
| Recommended UI | Scan table cell + drawer |
| States | Loading inline; error retry; empty if LLM disabled |

### Saved scan from scan page

| Field | Value |
|-------|-------|
| API client | `saveScanSnapshot` |
| UI consumer | `BucketPage` save action |
| Status | **Fully integrated** |

---

## 3. Stock detail (`routes_stock.py`)

### `GET /stock/{symbol}`

| Field | Value |
|-------|-------|
| API client | `getStock` |
| UI consumer | `BucketPage` → `StockDetailDrawer` |
| Status | **Partially integrated** |
| Recommended UI | Scan **DetailDrawer** with tabs: Summary, Factor Attribution, Risk, Diagnostics, Similar Signals, Backtest, Report, Notes |
| Component changes | Replace flat `StockDetailDrawer` with tabbed `DetailDrawer`; lazy-fetch per tab |
| States | Drawer skeleton; tab-level error/retry; insufficient data for diagnostics |

**Lazy-load map (drawer):**

| Tab | Endpoint | When |
|-----|----------|------|
| Summary | stock + scan row | Open drawer |
| Factor Attribution | v2 score or signals | Tab select |
| Risk | `/api/v2/risk/{symbol}` | Tab select |
| Diagnostics | `/analyze/{symbol}/diagnostics` | Tab select |
| Similar Signals | v2 score `similar_signal` or dedicated endpoint | Tab select |
| Backtest | `/backtest/{bucket}/{symbol}` | Tab select |
| Report | `/analyze/{symbol}/report` | Tab select |
| Notes | watchlist notes / saved analyze | Tab select |

---

## 4. Analyze & workspace (`routes_analyze.py`)

### `GET /analyze/{symbol}`

| Field | Value |
|-------|-------|
| API client | `getAnalyzeSymbol` |
| UI consumer | `AnalysisPanel`, `WorkspacePage` |
| Status | **Fully integrated** (legacy bundle) |
| Recommended UI | **Workspace** — context for Overview tab only; do not duplicate v2 recommendation |
| States | Symbol loading; 404 symbol; bucket assignment warning |

### `GET /api/v2/score/{symbol}` (primary recommendation)

| Field | Value |
|-------|-------|
| API client | `getV2Score` |
| UI consumer | `AnalysisPanel`, `Round2Panel`, `ScoreSourceBadge`, `resolveAnalysisDisplay` |
| Status | **Fully integrated** — one primary recommendation rule satisfied |
| Recommended UI | Workspace **Overview** + **Score Breakdown** tabs |
| Component changes | Split `Round2Panel` / `V2QuantPanel` into tab-aligned panels; `RecommendationBadge` |
| States | v2 disabled → `V2FallbackBanner`; insufficient data message |

### `GET /analyze/{symbol}/diagnostics`

| Field | Value |
|-------|-------|
| API client | `getSymbolDiagnostics` |
| UI consumer | `DiagnosticsPanel` inside Insights tab |
| Status | **Partially integrated** |
| Recommended UI | Workspace **Diagnostics** dedicated tab |
| Component changes | Move out of `<details>`; use `AsyncSection` |
| States | **Already has:** loading, error, retry, insufficient data |

### `GET /api/v2/risk/{symbol}`

| Field | Value |
|-------|-------|
| API client | `getV2UnifiedRisk` |
| UI consumer | `UnifiedRiskPanel` in Insights |
| Status | **Partially integrated** |
| Recommended UI | Workspace **Risk & Volatility** tab |
| Component changes | Promote `UnifiedRiskPanel`; add tooltips (VaR, ES, PCA) |
| States | v2 risk disabled panel; retry; empty metrics |

### `GET /api/v2/sizing/{symbol}`

| Field | Value |
|-------|-------|
| API client | `getV2PositionSizing` |
| UI consumer | `AnalysisPanel` overview, `PositionSizingBlock` |
| Status | **Fully integrated** |
| Recommended UI | Workspace Overview |

### `GET /analyze/{symbol}/report`, `GET /api/v2/report/{symbol}`

| Field | Value |
|-------|-------|
| API client | `getResearchReport` → `/analyze/.../report` only |
| UI consumer | `AnalysisPanel` report tab, `ResearchReport` |
| Status | **Fully integrated**; v2 report path **duplicate** |
| Recommended UI | Workspace **AI Report** tab |
| Component changes | `NotFinancialAdviceFooter`; banner “LLM explains quant; does not override score” |
| States | Report generating; LLM off empty state |

### `POST /explain`

| Field | Value |
|-------|-------|
| API client | `explainStock` |
| UI consumer | `AnalysisPanel` overview |
| Status | **Fully integrated** |
| Note | Keep as lightweight overview blurb; full report in AI Report tab |

### `GET /analyze/compare`, watchlist routes

| Field | Value |
|-------|-------|
| UI consumer | `ComparePanel`, `WatchlistRail` |
| Status | **Fully integrated** but **Duplicate / confusing** as top-level “Research / Compare / Journal” |
| Recommended UI | Merge into **Workspace** (compare as sub-view or command palette); Journal → Workspace Notes tab |
| Component changes | Nav consolidation; keep `/compare`, `/journal` redirects |

### Valuation (`GET /api/v2/valuation/{symbol}` — backend exists, no dedicated client)

| Field | Value |
|-------|-------|
| API client | **Missing** — partial data via v2 score |
| UI consumer | `ValuationBlock`, `ValuationBadges` (analyze payload) |
| Status | **Partially integrated** |
| Recommended UI | Workspace **Valuation** tab |
| Component changes | Add `getV2Valuation()`; dedicated tab with sensitivity if present |
| States | Unavailable warning; low confidence badge |

### Similar signal (`GET /api/v2/similar-signal/{symbol}`)

| Field | Value |
|-------|-------|
| API client | **Missing** (embedded in v2 score response) |
| UI consumer | `SimilarSignalBlock` |
| Status | **Partially integrated** |
| Recommended UI | Workspace **Similar Signals** tab + Scan drawer tab |
| Component changes | `ResearchWarning` disclaimer |
| States | Small sample warning |

---

## 5. Portfolio (`routes_portfolio.py`)

### Optimize, policy backtest, factor exposure

| Field | Value |
|-------|-------|
| API clients | `optimizePortfolio`, `runPortfolioPolicyBacktest`, `getPortfolioFactorExposure`, `runV2PortfolioBacktest` |
| UI consumer | `PortfolioPage`, `PortfolioFactorExposurePanel` |
| Status | **Fully integrated** (optimize + policy + exposure); **partial** (concentration, allocation, LEAN) |
| Recommended UI | **Portfolio** page tabs/sections |
| Component changes | Add allocation panel, LEAN export button, concentration metrics from optimize result |
| States | `<2` symbols for PCA → existing insufficient message; optimizer infeasible error |

### Risk concentration (derived from optimize response)

| Status | **Partially integrated** — data in API response, not labeled in UI |
| Recommended UI | Portfolio section below optimize results |
| States | Empty until optimize run |

---

## 6. Allocation & LEAN (`routes_allocation.py`, `routes_lean.py`)

### `GET /allocation/recommendation/{bucket}`

| Field | Value |
|-------|-------|
| API client | `getAllocationRecommendation` (**unused**) |
| Status | **API-only but valuable** |
| Recommended UI | **Portfolio** → Allocation section |
| Component changes | Heuristic label when FinRL stub; `ResearchWarning` |
| States | Loading on bucket select; empty bucket |

### LEAN export/import

| Field | Value |
|-------|-------|
| API client | `exportToLean`, `getLeanExport`, `importLeanSummary` (**all unused**) |
| Status | **API-only but valuable** |
| Recommended UI | **Portfolio** export button; **Library** tab for past exports |
| States | Export in progress; download link; `LEAN_EXPORT_ENABLED` off → hidden with tooltip |

---

## 7. ML / alpha (`routes_ml.py`)

### `GET /ml/alpha/latest`, `POST /ml/alpha/ingest`

| Field | Value |
|-------|-------|
| API client | Both exist, **unused** |
| Status | **API-only** — ingest **admin-only**; latest **valuable** for Quant Lab |
| Recommended UI | Quant Lab → Prediction Outcomes or Model Admin |
| States | Qlib stub disclaimer |

---

## 8. Research (`routes_research.py`)

### Walk-forward

| Endpoint | `POST /research/walk-forward`, `GET /research/walk-forward/{run_id}` |
| API client | **None** |
| Status | **API-only but valuable** |
| Recommended UI | **Quant Lab → Walk-Forward Validation** (user clicks Run) |
| Component changes | New clients + run status polling; save run to Library |
| States | Running spinner; failed run error; empty until first run; **ResearchWarning**: offline research |

### Pairs trading

| Endpoint | `POST /research/pairs` |
| API client | **None** |
| Status | **API-only but valuable** |
| Recommended UI | **Quant Lab → Pairs Trading** |
| Component changes | Pair search form; results table with cointegration tooltip |
| States | No pairs found; insufficient history |

---

## 9. Quant v2 admin & factors (`routes_v2.py`)

| Endpoint group | Client | UI | Status | Recommended UI |
|----------------|--------|-----|--------|----------------|
| `GET /api/v2/regime` | None | None | Valuable | Home market/regime card |
| `GET /api/v2/factors/ic`, `/factors/performance` | None | None | Valuable | Quant Lab → Factor Performance |
| `GET /api/v2/predictions`, `/feedback/*` | None | None | Valuable | Quant Lab → Prediction Outcomes |
| `GET /api/v2/weights/{sleeve}`, `/hard-filters/{sleeve}` | None | None | Valuable | Quant Lab → Model Admin |
| `GET /api/v2/version`, `/audit`, `/admin/*` | None | None | Admin | Quant Lab → Model Admin |
| `POST /api/v2/jobs/*` | None | None | Admin | Quant Lab / Settings (explicit Run) |
| `GET /api/v2/agents/{symbol}` | None | None | Low priority | Workspace advanced collapsible |

**Required states for all Quant Lab tabs:** loading, error, retry, empty, insufficient data, stale IC/factor warning, research-only footer.

---

## 10. Backtest (`routes_backtest.py`)

| Endpoint | Client | UI | Status |
|----------|--------|-----|--------|
| Symbol backtest | `getBacktest` | `BacktestPanel`, drawer | **Full** |
| Sweep | `runBacktestSweep` | `BacktestPanel` | **Full** |
| Entry variants | `listEntryVariants` | `BacktestPanel` | **Full** |
| Strategy version | None | None | **Hidden** (optional badge in Quant Lab) |

Workspace **Backtest** tab: reuse `BacktestPanel`; show small-sample warning.

---

## 11. Saved library (`routes_saved.py`)

| Feature | Client | UI | Status | Gap |
|---------|--------|-----|--------|-----|
| Saved scans | Yes | `LibraryPage` | Partial | No score source / as-of on list rows |
| Saved reports | Yes | `LibraryPage` | Full | — |
| Saved analyze snapshots | Yes | **None** | **API-only valuable** | Add Library tab |
| Progress summary | Yes | `HomeDashboard` | Partial | Expand to activity cards |
| Research runs | None | None | Future | After walk-forward UI |

---

## 12. Watchlist & trades

| Feature | Status | Recommended UI |
|---------|--------|----------------|
| Watchlist CRUD | **Full** — Workspace rail | Keep |
| Watchlist notes | **Full** — partial in workspace | Workspace Notes tab |
| `POST /watchlist/reports` | **None** | Low priority batch report |
| Trade journal | **Partial** — `/journal` nav duplicate | Workspace Notes or secondary Journal link |
| Trade screenshot | **Hidden** | Skip unless journal enhanced |

---

## 13. Data & scheduler (`routes_data.py`)

| Endpoint | Client | UI | Status | Recommended UI |
|----------|--------|-----|--------|----------------|
| `GET /data/quality/{symbol}` | `getDataQuality` | Analysis data tab | **Full** | Keep in Workspace Data or merge Score Breakdown |
| `GET /data/reconcile/{symbol}` | None | Indirect | Partial | Quant Lab Data Quality |
| `GET /data/scheduler/status` | None | None | Admin | Settings + Quant Lab Data Quality |
| Scheduler run/refresh POSTs | None | None | Admin | Settings with confirm dialog |

---

## 14. Settings (`routes_settings.py` + config)

| Feature | Today | Target |
|---------|-------|--------|
| API provider toggles | `ApiSettingsPanel` | Keep + link to `/health` detail |
| Feature flags | Env-only | Settings read-only display + docs link |
| Scheduler controls | None | Settings section (status + manual refresh) |
| Risk / LLM profile | Partial (API keys) | Settings sections |
| Language | `LanguageSettingsPanel` | Keep |
| Cache management | None | Settings “Data & cache” with scheduler triggers |
| Quant Health detail | None | Expandable from Home card |

---

## 15. Trader Intel (`routes_trader_intel.py`)

| Field | Value |
|-------|-------|
| API client | Full set in `api.ts` |
| UI consumer | `app/trader-intel/page.tsx` |
| Status | **Fully integrated** but **hidden from main nav** |
| Recommended UI | Secondary nav link **or** Home quick-action card |
| Label | “Trader Intel” — mark experimental if presets stale |

---

## 16. Reusable components — inventory vs needed

| Component | Exists? | Action |
|-----------|---------|--------|
| `ScoreSourceBadge` | Yes | Reuse scan + workspace |
| `DataQualityBadge` | Yes | Reuse |
| `ScanScoreMeta` | Yes | Extend per-row |
| `DiagnosticsPanel` | Yes | Promote to tab |
| `UnifiedRiskPanel` | Yes | Promote to tab |
| `PortfolioFactorExposurePanel` | Yes | Keep |
| `AsyncSection` | Yes | Standardize all lazy panels |
| `ScoreBadge` | No | Create |
| `RiskBadge` | No | Create |
| `ConfidenceBadge` | No | Create |
| `RecommendationBadge` | No | Create |
| `HealthStatusBadge` | No | Create |
| `StaleDataBadge` | No | Create |
| `MetricCard` / `MetricGrid` | No | Create for Home + Quant Lab |
| `FactorAttributionTable` | Partial (`ScoreBreakdown`) | Extract/enhance |
| `RiskBreakdownPanel` | Partial (`UnifiedRiskPanel`) | Rename/consolidate |
| `QuantHealthCard` | No | Create |
| `EmptyState` / `ErrorState` / `LoadingSkeleton` | Partial (`AsyncSection`) | Consolidate |
| `RetryButton` | Inline in AsyncSection | Export |
| `TooltipLabel` | No | Create for IC, VaR, PCA, etc. |
| `SectionHeader` / `CollapsibleSection` | No | Create |
| `DetailDrawer` | Partial (`StockDetailDrawer`) | Tabbed upgrade |
| `ResearchWarning` | No | Create |
| `NotFinancialAdviceFooter` | Partial in report | Extract |

---

## 17. Page-by-page integration checklist

### Home dashboard

| Block | Endpoints | Status | Priority |
|-------|-----------|--------|----------|
| Quant Health card | `/health` + compose | Missing | P0 |
| Latest scan summary | `/scan/latest/{bucket}` ×3 | Missing | P0 |
| Market / regime | `/api/v2/regime` | Missing | P1 |
| Prediction/outcome summary | `/api/v2/predictions`, `/feedback/summary` | Missing | P1 |
| Quick actions | routes only | Partial | P0 |

### Scan page

| Block | Status | Priority |
|-------|--------|----------|
| Score source + parity toolbar | Partial | P0 |
| Rich table columns | Missing | P0 |
| Tabbed detail drawer + lazy load | Missing | P0 |
| Stale scan warning | Missing | P1 |

### Workspace

| Tab (target) | Current | Gap |
|--------------|---------|-----|
| Overview | overview tab | Rename/group; primary rec OK |
| Score Breakdown | quant tab | Split attribution vs round2 |
| Risk & Volatility | insights sub-panel | Promote |
| Diagnostics | insights sub-panel | Promote |
| Valuation | data/overview bits | Dedicated tab + client |
| Backtest | backtest tab | OK |
| Similar Signals | quant/similar block | Dedicated tab |
| AI Report | report tab | Add disclaimer |
| Notes | journal separate | Merge tab |

### Portfolio

| Block | Status |
|-------|--------|
| Optimize + policy + exposure | Full |
| Concentration metrics | Missing |
| Allocation recommendation | Missing |
| LEAN export | Missing |

### Quant Lab (`/quant-lab` — **new**)

| Tab | Endpoints | Status |
|-----|-----------|--------|
| Factor Performance | factors/ic, factors/performance | Not started |
| Walk-Forward | research/walk-forward | Not started |
| Prediction Outcomes | predictions, feedback | Not started |
| Pairs Trading | research/pairs | Not started |
| Data Quality | health, data/quality, scheduler | Not started |
| Model Admin | version, audit, weights | Not started |

### Library

| Block | Status |
|-------|--------|
| Scans + reports | Full |
| Analyze snapshots | Missing |
| LEAN exports | Missing |
| Filters (bucket, date, type) | Missing |

### Settings

| Block | Status |
|-------|--------|
| API providers | Full |
| Scheduler / ops | Missing |
| Quant health detail | Missing |
| Feature flags display | Missing |

---

## 18. Frontend API client gaps (Step 2)

**Add clients (with abort signal where heavy):**

- `getV2Regime()`
- `getV2FactorIc()`, `getV2FactorPerformance()`
- `getV2Predictions()`, `getV2FeedbackSummary()`
- `getV2Weights(sleeve)`, `getV2HardFilters(sleeve)`
- `getV2Valuation(symbol)`, `getV2SimilarSignal(symbol)` (if not always on score)
- `getV2Version()`, `getV2Audit()`, `getV2JobsQueue()`
- `runWalkForwardResearch()`, `getWalkForwardRun(id)`
- `runPairsResearch()`
- `getSchedulerStatus()`, `runSchedulerJob(name)` (admin)
- `getQuantHealthSummary()` (compose helper)

**Wire existing unused clients:**

- `getAllocationRecommendation` → Portfolio
- `exportToLean`, `getLeanExport` → Portfolio + Library
- `listSavedAnalyze` → Library

**Mark deprecated / avoid duplicate:**

- Prefer `/analyze/{symbol}/report` over `/api/v2/report/{symbol}` unless parity needed

---

## 19. i18n gaps (Step 10)

Keys needed in `en.ts` / `zh.ts`:

- Nav: `quantLab`, consolidated `workspace`, `scan` (rename from screen)
- Quant Health sections and warnings
- Scan parity tooltips
- Workspace tab labels (9 tabs)
- Quant Lab tab labels + research disclaimers
- Tooltips: IC, VaR, ES, PCA, cointegration, walk-forward, parity delta, data confidence
- Stale / insufficient data / not financial advice

---

## 20. Testing plan (post-implementation)

| Test | File (proposed) |
|------|-----------------|
| `QuantHealthCard` healthy/warning/error | `QuantHealthCard.test.tsx` |
| `ScanScoreMeta` legacy/v2/parity | exists — extend |
| `DiagnosticsPanel` insufficient data | exists — keep |
| `UnifiedRiskPanel` v2 disabled | exists — keep |
| `PortfolioFactorExposurePanel` PCA edge cases | exists — keep |
| Quant Lab tabs smoke | `QuantLabPage.test.tsx` |

**Commands:** `npm test`, `npm run build`, `npm run typecheck`, `npm run lint`

---

## 21. Documentation updates (post-implementation)

| Doc | Action |
|-----|--------|
| `README.md` | Nav IA, Quant Lab, Quant Health compose |
| `docs/FRONTEND_INFORMATION_ARCHITECTURE.md` | Create — page map + progressive disclosure rules |
| `docs/QUANT_LAB.md` | Create — tab purposes + research warnings |
| `docs/UI_API_COVERAGE_MAP.md` | Refresh after Step 2–10 |
| `docs/QUANT_HEALTH.md` | Create when aggregator exists OR document compose strategy |

---

## 22. Implementation sequence (confirmed)

1. ✅ **This audit** + `UI_API_COVERAGE_MAP.md`
2. ✅ API clients + types *(2026-06-08: v2/research/scheduler clients + `QuantHealthSummary` types; UI not wired yet)*
3. Reusable components
4. Home Quant Health + scan cards
5. Scan parity + detail drawer
6. Workspace tab restructure
7. Portfolio allocation + LEAN
8. Quant Lab route
9. Library + Settings
10. i18n, tests, docs

**Do not break:** `/penny`, `/medium`, `/compounder`, `/watchlist`, `/analyze`, `/trades`, `/reports`, `/scans` redirects.

---

## 23. UX rules compliance (pre-integration scorecard)

| Rule | Current | Target |
|------|---------|--------|
| Progressive disclosure | Partial | Quant Lab absorbs research |
| One primary recommendation | ✅ v2 primary in workspace | Keep |
| LLM does not override quant | Partial disclaimer | AI Report tab banner |
| Lazy-load heavy endpoints | Partial (pick-summary) | Drawer + Quant Lab Run buttons |
| No render-loop API calls | ✅ refs in AnalysisPanel | Audit new pages |
| EN + ZH | Partial for new surfaces | Full in Step 10 |
| Mobile readable | OK on laptop-first | Maintain |

---

*End of audit. Proceed to Step 2: typed API clients and response types.*
