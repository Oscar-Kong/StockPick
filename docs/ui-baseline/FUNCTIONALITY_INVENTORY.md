# Phase 0 Functionality Inventory

**Recorded:** June 30, 2026  
**Rule:** All items below must be preserved through Phases 1–6 unless explicitly approved.

Source components verified in `frontend/src/`.

---

## Portfolio (`/` — `PortfolioWorkspace`)

### Summary metrics

| Metric / display | Source |
|------------------|--------|
| Portfolio value | `PortfolioToday` / `PortfolioSummaryStrip` |
| Cockpit status pill | `CockpitStatusPill` |
| Data source label | `data.data_source_label` |
| Last updated / decision run time | Freshness from `DailyDashboardResponse` |
| Cash / buying power | Activity tab + import footer |
| Demo data indicator | `DemoDataBanner`, `data.is_demo_data` |

### Tabs (URL: `?tab=today\|research\|activity`, default today)

| Tab | Content |
|-----|---------|
| **Today** | Holdings decision table, action queue, risk alerts, penny opportunities |
| **Research** | Sub-panels via `?panel=optimize\|backtest\|exposure\|allocation` |
| **Activity** | CSV import, ledger, closed positions, buying power |

Legacy URL support: `?journal=1` → activity; `?tools=` / `#portfolio-tools` → research.

### Holdings columns (`ActiveHoldingsDecisionTable`)

| Column | Data |
|--------|------|
| Symbol / position | Shares, market value, avg cost → price, bucket chip |
| P/L % | `pl_pct` |
| Weight | Current % + target % |
| Decision mix | Buy / Hold / Sell bar (`DecisionMixBar`) |
| Decision | Badge + action summary |

### Row actions

* Expand row → `HoldingWhyDrawer` (why / evidence)
* Link symbol → `/workspace?symbol=`
* Chevron toggle with `aria-expanded`

### Expandable details

* Per-holding why drawer with recommendation context
* Risk alerts panel
* Penny opportunities panel

### Allocation / risk / recommendation

* `PortfolioAllocationPanel`, `PortfolioFactorExposurePanel`, `UnifiedRiskPanel` (research tab)
* Buy/Hold/Sell percentages on every holding row
* `DecisionBadge`, confidence via decision items
* `RiskAlertsPanel` on Today tab

### Refresh / sync

| Action | API |
|--------|-----|
| Refresh data | `refreshHomeData` → job poll `getHomeRefreshStatus` (5s interval) |
| Run decision now | `runDailyDecisionNow` |
| CSV import | `previewRobinhoodCsv` → review → import |
| Set buying power | `setBuyingPower` |

### Loading / error / stale

* Initial: `LoadingSkeleton variant="home"`
* Error: `ErrorState` with message
* Refresh in progress: `refreshing` disables actions; `DataFreshnessBanner`
* Stale: freshness fields on dashboard response

### Mobile

* Responsive holdings table (desktop rows + mobile layout in same component file)
* Toolbar wraps; tab bar in page header

---

## Scan (`/scan` — `ScanHub` + `BucketPage`)

### Buckets (URL: `?bucket=`)

Active order from `ACTIVE_BUCKET_ORDER` (penny, compounder; medium if enabled in buckets config).

### Filters / options (`ScanCommandBar`)

| Control | Field |
|---------|-------|
| Max results | `max_results` (5–50) |
| Mode | fast / full (scan options) |
| Advanced tray | `min_price`, `max_price`, `min_volume` |
| Reset | restores defaults |

### Sorting / ranking

* Results ordered by backend scan score (rank column in table)
* Strategy version + scoring engine metadata displayed

### Table columns (`StockTable`)

Default: rank, symbol, recommendation, score, price, change, factor, warning, thesis, watchlist.  
Optional: source (column customization via `DenseTableToolbar`).

### Recommendation / confidence / freshness

* `RecommendationBadge`, score breakdown popover
* `StaleDataBadge` when scan >24h
* Last scan timestamp in header
* Parity / scoring engine indicators

### Partial results / loading

* `ScanProgress`, `ScanInlineStatus`, progress bar
* Poll via `startScanPoll` until complete
* Load last scan / saved scans menu

### Row actions

* Row click → workspace or detail
* Add to watchlist (per-row, pending state)
* Held position indicator from portfolio

### Detail interactions

* `ScanScoreBreakdown`, `StockDetailDrawer` (where wired)
* Save scan snapshot → Library

---

## Analyze / Workspace (`/workspace` — `WorkspacePage`)

### Symbol selection

* URL param `?symbol=`
* Watchlist rail (`AnalysisSidebar` / watchlist rail)
* Search in workspace toolbar
* Prev/next symbol navigation

### Tabs (`AnalysisTabNav` — in-panel state)

| Tab ID | Purpose |
|--------|---------|
| overview | Summary + recommendation block |
| score | Score breakdown |
| risk | Unified risk |
| diagnostics | Data quality / alerts |
| valuation | Valuation badges |
| backtest | Backtest panel |
| similar | Similar stocks |
| report | Research report (save) |
| notes | User notes |

### Charts / indicators

* `PriceChart` with range selectors
* Technical overlays per chart config
* V2 quant panel, factor attribution table

### Recommendation / confidence / evidence

* `RecommendationBlock`, Buy/Hold/Sell percentages
* `ConfidenceBadge`, `ScoreBadge`
* Evidence sections, catalysts, risks in overview

### Data date

* Latest price / analyze timestamp in toolbar (component-level)

### Loading / error

* `LoadingSkeleton`, workspace-specific load errors (`workspaceLoadError.ts`)
* V2 fallback banner when degraded

---

## Quant Lab (`/quant-lab` — `QuantLabPage`)

### Sections (URL: `?section=`)

| Section | Component |
|---------|-----------|
| overview | `OverviewTab` |
| ideas | `IdeasBoardTab` |
| experiments | `ExperimentStudio` |
| results | `ResultsTab` |
| model-monitor | `ModelMonitorTab` |
| legacy | `LegacyQuantLabTabs` (`?tab=factor-performance\|walk-forward\|predictions\|pairs`) |

> Retired: `section=models` redirects to `model-monitor`.

### Setup / execution

* Sleeve selector (penny / compounder bucket)
* Experiment presets in `ExperimentStudio`
* Scan evaluation config fields
* Run / cancel / status polling

### Results / metrics / charts

* `ResultsTab`, `ResultChart`, scan evaluation result panels
* Recall@K metrics, comparison cards
* Factor performance, walk-forward, pairs (legacy tabs)

### Evidence / interpretation

* `QuantLabEvidencePanel` (collapsible on overview)
* `QuantLabScanRelationshipPanel`
* Limitations / caveats sections

### Export / save

* Experiment run history (localStorage helpers in `quantLabLastRun.ts`)
* Links back to Scan bucket context

### States

* Loading skeletons per tab
* Empty experiment states
* Research-only badge + warnings

---

## Library (`/library` — `LibraryPage`)

### Tabs (URL: `?tab=scans\|reports\|snapshots`)

| Tab | Behavior |
|-----|----------|
| scans | List saved scans → detail table (symbol, score, open in workspace) |
| reports | List saved reports → edit title/notes, render `ResearchReport`, delete |
| snapshots | Table of saved analyze snapshots |

### Filters

* Tab-level only (no full-text search)

### Row actions

* Select scan/report from sidebar list
* Delete scan/report
* Open symbol in workspace
* Save title/notes on reports

### Loading / empty / error

* Loading: plain text `t.library.loading`
* Empty: dashed card with link to scan/workspace
* **Error: swallowed** — failed fetch shows as empty (preserve fix in Phase 1)

### Mobile

* Grid stacks to single column below `lg`
* Horizontal scroll on snapshot table

---

## Settings (`/settings`)

### Sections (URL: `?section=language\|quant-health\|api\|ops`)

| Section | Panel |
|---------|-------|
| language | `LanguageSettingsPanel` |
| quant-health | `QuantHealthCard` |
| api | `ApiSettingsPanel` |
| ops | `MorningScanEmailPanel` |

### Navigation

* Desktop: sidebar section links
* Mobile: native `<select>` (`settings-mobile-select`)
* Close button → history.back or `/`
* Escape key closes

### Theme / language

* Language: persisted via settings API / local storage (panel-specific)
* **Theme toggle: not implemented** (Phase 5)

### Persistence

* Section in URL via `router.replace`
* API keys and ops settings via backend panels

---

## Application shell (all pages)

| Feature | Component |
|---------|-----------|
| Sticky nav | `Nav.tsx` — 6 primary links + SettingsMenu + CommandPalette |
| Demo banner | `PublicDemoBanner` |
| Footer API status | `ApiStatus` in layout |
| Command palette | ⌘K navigation, search |
| i18n | Full string tables |

---

## API boundaries (do not change in UI phases)

* `frontend/src/lib/api.ts` — primary HTTP client
* Portfolio: `getDailyDashboard`, `refreshHomeData`, `runDailyDecisionNow`, …
* Scan: `startScan`, `getLatestScan`, poll status endpoints
* Analyze: `/analyze/{symbol}` wrappers
* Quant Lab: experiment + quant endpoints
* Library: `listSavedScans`, `listSavedReports`, `listSavedAnalyze`

---

## URL persistence summary

| Page | Parameters |
|------|------------|
| Portfolio | `tab`, `panel`, legacy `tools`, `journal` |
| Scan | `bucket`, scan options in component state (not all in URL) |
| Workspace | `symbol` |
| Quant Lab | `section`, `tab` (legacy) |
| Library | `tab` |
| Settings | `section` |
