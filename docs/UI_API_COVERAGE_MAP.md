# UI ↔ API coverage map

Quick reference: backend route → `frontend/src/lib/api.ts` → UI consumer.  
Status legend: **Full** | **Partial** | **Client only** | **None** | **Admin**

Last audited: 2026-06-08 (pre–UI integration pass; no code changes in this step).

---

## Core & health

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET /health` | `getHealth()` | `ApiStatus` (footer pills) | Partial — not a dashboard card |
| *(none)* `/api/v2/health/quant` | — | — | **Not implemented** — compose or add backend aggregator for Quant Health |

---

## Scan (`/scan`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `POST /scan/{bucket}` | `startScan()` | `BucketPage` | Full |
| `GET /scan/{job_id}` | `getScanStatus()` | `BucketPage` poll | Full |
| `GET /scan/latest/{bucket}` | `getLatestScan()` | `BucketPage` | Partial — no stale-age warning |
| `POST /scan/{bucket}/{symbol}/pick-summary` | `getScanPickSummary()` | `ScanPickSummaryCell` | Full (lazy) |
| Response: `scoring_engine_used`, `parity_summary` | types in `types.ts` | `ScanScoreMeta` | Partial — toolbar only, not per-row |

---

## Analyze (`/analyze`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET /analyze/watchlist` | `getAnalyzeWatchlist()` | `WatchlistRail`, `WorkspacePage` | Full |
| `GET /analyze/compare` | `getAnalyzeCompare()` | `ComparePanel` | Full |
| `GET /analyze/{symbol}` | `getAnalyzeSymbol()` | `AnalysisPanel` | Full (legacy context) |
| `GET /analyze/{symbol}/bucket-fit` | `getAnalyzeBucketFit()` | `AnalysisPanel` | Full (lazy) |
| `GET /analyze/{symbol}/diagnostics` | `getSymbolDiagnostics()` | `DiagnosticsPanel` (Insights tab) | Partial — should move to dedicated tab |
| `GET /analyze/{symbol}/report` | `getResearchReport()` | `AnalysisPanel` report tab | Full |
| `POST /explain` | `explainStock()` | `AnalysisPanel` overview | Full |

---

## Quant v2 (`/api/v2`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET /api/v2/score/{symbol}` | `getV2Score()` | `AnalysisPanel`, `Round2Panel`, toolbar | **Full** — primary score |
| `GET /api/v2/risk/{symbol}` | `getV2UnifiedRisk()` | `UnifiedRiskPanel` (Insights) | Partial — buried in Insights `<details>` |
| `GET /api/v2/sizing/{symbol}` | `getV2PositionSizing()` | `AnalysisPanel`, `Round2Panel` | Full |
| `GET /api/v2/regime` | — | — | **None** → Home / Quant Lab |
| `GET /api/v2/weights/{sleeve}` | — | — | **None** → Quant Lab |
| `GET /api/v2/factors/performance` | — | — | **None** → Quant Lab |
| `GET /api/v2/factors/ic` | — | — | **None** → Quant Lab |
| `GET /api/v2/predictions` | — | — | **None** → Quant Lab |
| `GET /api/v2/feedback/summary` | — | — | **None** → Quant Lab |
| `GET /api/v2/feedback/trades/{id}` | — | — | **None** |
| `GET /api/v2/valuation/{symbol}` | — | — | Partial — via v2 score object only |
| `GET /api/v2/similar-signal/{symbol}` | — | — | Partial — via v2 score → `SimilarSignalBlock` |
| `GET /api/v2/agents/{symbol}` | — | — | **None** |
| `GET /api/v2/report/{symbol}` | — | — | Duplicate of `/analyze/.../report` path |
| `POST /api/v2/backtest/portfolio` | `runV2PortfolioBacktest()` | `PortfolioPage` (institutional toggle) | Full |
| `GET /api/v2/hard-filters/{sleeve}` | — | — | **None** → Quant Lab admin |
| `GET /api/v2/version` | — | — | **None** → Quant Lab / Settings |
| `GET /api/v2/audit` | — | — | **None** → Quant Lab admin |
| `GET /api/v2/admin/round2-stats` | — | — | **None** → Quant Lab |
| `GET /api/v2/factors/admin` | — | — | **None** → Quant Lab admin |
| `GET /api/v2/jobs/queue` | — | — | **None** → Quant Lab / Settings |
| `POST /api/v2/jobs/*` (ic-panel, rebalance, forward-labels, …) | — | — | **Admin** — Quant Lab run buttons only |

---

## Portfolio (`/portfolio`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `POST /portfolio/optimize` | `optimizePortfolio()` | `PortfolioPage` | Full |
| `POST /portfolio/policy-backtest` | `runPortfolioPolicyBacktest()` | `PortfolioPage` | Full |
| `POST /portfolio/factor-exposure` | `getPortfolioFactorExposure()` | `PortfolioFactorExposurePanel` | Full |

---

## Research (`/research`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `POST /research/walk-forward` | — | — | **None** → Quant Lab |
| `GET /research/walk-forward/{run_id}` | — | — | **None** → Quant Lab / Library |
| `POST /research/pairs` | — | — | **None** → Quant Lab |

---

## Allocation / ML / LEAN

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET /allocation/recommendation/{bucket}` | `getAllocationRecommendation()` | — | **Client only** → Portfolio |
| `GET /ml/alpha/latest` | `getLatestAlpha()` | — | **Client only** |
| `POST /ml/alpha/ingest` | `ingestAlphaPredictions()` | — | **Client only** → Quant Lab admin |
| `POST /lean/export` | `exportToLean()` | — | **Client only** → Portfolio / Library |
| `GET /lean/export/{id}` | `getLeanExport()` | — | **Client only** |
| `POST /lean/import-summary` | `importLeanSummary()` | — | **Client only** |

---

## Backtest (`/backtest`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET /backtest/{bucket}/{symbol}` | `getBacktest()` | `BacktestPanel`, `StockDetailDrawer` | Full |
| `POST /backtest/{bucket}/{symbol}/sweep` | `runBacktestSweep()` | `BacktestPanel` | Full |
| `GET /backtest/entry-variants/{bucket}` | `listEntryVariants()` | `BacktestPanel` | Full |
| `GET /backtest/strategy-version/{bucket}` | — | — | **None** (strategy badge uses scan/saved metadata) |

---

## Stock (`/stock`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET /stock/{symbol}` | `getStock()` | `BucketPage` drawer, `StockDetailDrawer` | Partial — no multi-tab drawer |

---

## Saved (`/saved`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET/POST/DELETE /saved/scans` | `listSavedScans`, `saveScanSnapshot`, `deleteSavedScan` | `LibraryPage`, `BucketPage` | Partial — no score source on saved rows |
| `GET/POST/PATCH/DELETE /saved/reports` | report CRUD | `LibraryPage`, `AnalysisPanel` | Full |
| `GET /saved/analyze` | `listSavedAnalyze()` | — | **Client only** → Library |
| `GET /saved/analyze/latest/{symbol}` | `getLatestSavedAnalyze()` | — | **Client only** |
| `GET /saved/progress-summary` | `getSavedProgressSummary()` | `HomeDashboard` | Partial — counts only |

---

## Watchlist / trades

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| Watchlist CRUD + import/refresh | watchlist exports | `WorkspacePage`, `WatchlistRail`, `WatchlistImport` | Full |
| `POST /watchlist/reports` | — | — | **None** |
| Trades CRUD + stats | trade exports | `TradeJournal` | Partial — no PATCH UI, no screenshot |
| `GET /trades/{id}/screenshot` | — | — | **None** |

---

## Data / scheduler (`/data`)

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET /data/quality/{symbol}` | `getDataQuality()` | `AnalysisPanel` data tab | Full |
| `GET /data/reconcile/{symbol}` | — | — | Partial — merged via quality in analyze |
| `GET /data/openbb/risk/{symbol}` | — | — | **None** (indirect via metrics) |
| `GET /data/strategy` | — | — | **None** |
| `GET /data/scheduler/status` | — | — | **None** → Settings / Quant Lab |
| `POST /data/scheduler/run` | — | — | **Admin** |
| `POST /data/scheduler/refresh-*` | — | — | **Admin** |

---

## Settings / trader intel

| Endpoint | API client | UI consumer | Status |
|----------|------------|-------------|--------|
| `GET/PATCH/POST /settings/apis` | api settings exports | `ApiSettingsPanel` | Partial — no feature flags |
| Trader intel routes | trader intel exports | `/trader-intel` page | Full but **hidden from main nav** |

---

## Coverage summary

| Category | Endpoints (approx.) | With client | With UI | Fully integrated |
|----------|---------------------|-------------|---------|------------------|
| Decision support (scan/workspace/portfolio) | ~25 | ~22 | ~18 | ~12 |
| Quant v2 advanced | ~25 | 4 | 4 | 2 |
| Research / admin | ~15 | 0 | 0 | 0 |
| Ops (scheduler, jobs, lean, ml) | ~12 | 6 | 1 | 0 |

**Client functions without UI consumer (remove or wire):**  
`getAllocationRecommendation`, `exportToLean`, `getLeanExport`, `importLeanSummary`, `getLatestAlpha`, `ingestAlphaPredictions`, `listSavedAnalyze`, `getLatestSavedAnalyze`.

**High-value endpoints without client:**  
~~All `/research/*`, most `/api/v2/factors/*`, `/api/v2/predictions`, `/api/v2/feedback/*`, `/data/scheduler/*`, `/api/v2/regime`, `/api/v2/weights/{sleeve}`.~~  
**Updated 2026-06-08:** Step 2 added typed clients in `frontend/src/lib/api.ts` for v2 research/ops, walk-forward, pairs, scheduler, and `getQuantHealthSummary()` compose helper. UI wiring remains Steps 3–10.
