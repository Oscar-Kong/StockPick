# Quant Lab

**Route:** `/quant-lab`

Research and validation console. Shows **latest persisted evidence** before asking you to run new jobs. Does **not** auto-update live scan rankings or primary recommendations.

## Product roles

| Surface | Role | Changes live scan rankings? |
|---------|------|----------------------------|
| **Scan** | Finds ranked stock candidates | Yes — when you run a new scan |
| **Workspace** | Explains one candidate | No |
| **Portfolio** | Basket risk, sizing, policy backtest | No (portfolio context only) |
| **Quant Lab** | Validates and monitors the quant system | **No** — validation only |

Quant Lab shows **latest evidence** on load, then lets you run heavy research on demand. It does not directly re-rank today's scan.

See also: [Product flow in UI](../frontend/src/components/product/ProductFlowDiagram.tsx) — rendered on `/quant-lab`.

## Evidence overview (page load)

On open, Quant Lab loads read-only summaries via `GET /api/v2/quant-lab/evidence?sleeve=medium`:

| Card | Source | Persisted? |
|------|--------|------------|
| Latest factor IC | `factor_ic_history` | Yes |
| Latest walk-forward | `backtest_runs` (`run_type=walk_forward_research`) | Yes |
| Latest prediction outcomes | `prediction_snapshots` / outcomes | Yes |
| Latest pairs research | `pairs_research_runs` | **Yes** (bounded retention) |
| Latest quant jobs | `job_logs` + `job_queue` | Yes |

Trust badges: **Fresh · Stale · Insufficient sample · Feature disabled · No saved run · Research only · Needs attention**

Heavy jobs (`POST /research/walk-forward`, `POST /research/pairs`, IC panel, scheduler mutations) run **only on user click**.

## Research foundation API (Phase 2)

Backend foundation at `/api/v2/research` (see [API_REFERENCE.md](./API_REFERENCE.md)):

- **Ideas** — hypotheses with source types and statuses
- **Experiments** — lightweight definitions separate from runs
- **Unified run index** — thin summaries over `backtest_runs`, `pairs_research_runs`, `factor_ic_history`, predictions, jobs
- **Evidence memory** — per-symbol deterministic findings linked to runs
- **Factor lineage** — calculation metadata per factor/date
- **Impact policy & major evidence gate** — centralized, deterministic (no LLM)
- **Change proposals** — reviewable drafts; never auto-applied

Env: `QUANT_LAB_RESEARCH_API_ENABLED`, `RESEARCH_MAX_ORDINARY_MODIFIER` (default `0` = display-only).

## Research home (Phase 3)

**Default view:** Overview (`/quant-lab` or `/quant-lab?section=overview`).

| Section | Query | Loads on open |
|---------|-------|----------------|
| Overview | `section=overview` (default) | `GET /api/v2/research/overview?sleeve=` only |
| Ideas | `section=ideas` | `GET /api/v2/research/ideas` |
| Models | `section=models` | Static model library (GBM, HMM, Markowitz, cointegration, GARCH) — no API |
| Model Monitor | `section=model-monitor` | `GET /api/v2/research/model-monitor` — factor/prediction/data health, jobs, audit, evidence review |
| Legacy tools | `section=legacy&tab=` | Factor performance, walk-forward, predictions, pairs |

Overview includes deterministic **research brief** findings, recommended ideas, recent activity, and collapsible **evidence maintenance** actions (IC panel, forward labels, resolve outcomes, quant daily jobs, evidence backfill).

Ideas board supports manual create, generate-from-brief, edit/notes/priority, archive, duplicate, and **Configure experiment** (creates experiment record + opens Experiment Studio).

## Model library (`section=models`)

Read-only reference for five core quant models with KaTeX-rendered equations and **In this project** mapping:

| Model | Status | Where used in this repo |
|-------|--------|-------------------------|
| Geometric Brownian Motion | Reference | Conceptual baseline; walk-forward and optimizer use empirical returns |
| Hidden Markov Model | Partial | Target for regime labels; today rule-based SPY vol in `scoring/regime.py` |
| Markowitz Mean–Variance | Live | `portfolio_optimizer.py` / PyPortfolioOpt — Portfolio → Research |
| Cointegration & stat arb | Live | `engines/pairs/` — Legacy Pairs tab & Experiment Studio |
| GARCH | Partial | ATR-based vol regime proxy; full GARCH fit not wired yet |

Route: `/quant-lab?section=models`. No backend API — static catalog in `frontend/src/lib/quantLabModels.ts`.

## Experiment Studio (Phase 4)

**Route:** `/quant-lab?section=experiments` with optional `step`, `template`, `experiment`, `job`, `idea` query params.

Six templates share a wizard: **Choose → Configure → Review → Run → Status → Result**.

| Template | Engine (unchanged) |
|----------|-------------------|
| Factor Validation | IC panel + `get_factor_performance` |
| Walk-Forward | `run_walk_forward_research` |
| Prediction Calibration | forward labels + resolve outcomes |
| Pairs Discovery | `run_pairs_research` |
| Similar-Signal Replay | `run_similar_signal_backtest` |
| Portfolio Policy | `run_portfolio_backtest` (institutional persist) |

Presets (**Quick Check**, **Standard Research**, **Robust Validation**) expose all parameter overrides in the UI. Pre-run validation via `POST /api/v2/research/experiments/validate`. Launch via `POST /api/v2/research/experiments/{id}/launch` with discrete job stages (no fake % progress).

Legacy per-tab forms remain under **Legacy tools**.

## API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v2/quant-lab/evidence?sleeve=` | All last-run cards (read-only) |
| `GET /research/walk-forward/latest?sleeve=` | Latest walk-forward summary |
| `GET /research/pairs/latest` | Latest persisted pairs summary |
| `GET /research/pairs/{run_id}` | Full persisted pairs run (bounded pair rows) |
| `GET /research/walk-forward/{run_id}` | Full persisted run detail |

## Tabs (implemented)

| Tab | API | UX |
|-----|-----|-----|
| Factor Performance | `GET /api/v2/factors/performance` | Sleeve filter; stale IC warning; empty state when no IC rows |
| Walk-Forward | `POST /research/walk-forward` | **Run** only; research warning; date/horizon validation; last-run hint |
| Prediction Outcomes | `GET /api/v2/predictions`, `/feedback/summary` | Independent partial failure; stale outcome badge |
| Pairs Trading | `POST /research/pairs`, `GET /research/pairs/latest` | **Run** + hydrates last persisted run on tab open |
| Data Quality | `getQuantHealthSummary`, `/data/scheduler/status` | Non-fatal health/scheduler failures |
| Model Admin | `/api/v2/version`, `/weights`, `/audit`, `/factors/admin` | `Promise.allSettled`; per-panel errors |

## Frontend structure

```
frontend/src/components/QuantLabPage.tsx     → section shell (?section=)
frontend/src/components/quant-lab/
  OverviewTab.tsx           → research home (default)
  IdeasBoardTab.tsx         → ideas CRUD + generate
  ExperimentStudio.tsx      → unified experiment wizard
  ResultsTab.tsx            → paginated runs + detail + compare
  ModelsTab.tsx             → model library (equations + project mapping)
  ModelMonitorTab.tsx       → health, jobs, audit, evidence review
  LegacyQuantLabTabs.tsx    → factor, WF, predictions, pairs
  QuantLabTabShell.tsx      → shared UI helpers
  ResearchReliabilityCard.tsx
  QuantLabEvidencePanel.tsx → collapsible on Overview only
  DataQualityTab.tsx        → embedded in Model Monitor
  FactorPerformanceTab.tsx, WalkForwardTab.tsx, …
frontend/src/lib/
  quantLabNavigation.ts     → ?section= routing
  experimentStudio.ts       → studio URL helpers
  researchReliability.ts
  researchOverviewNormalizers.ts
```

## Research Reliability

Every tab shows a **Research Reliability** card first (badge, 0–100 score, reasons, warnings, blockers, suggested next action). See [RESEARCH_RELIABILITY.md](./RESEARCH_RELIABILITY.md).

| Tab | Reliability inputs |
|-----|-------------------|
| Factor Performance | IC freshness, factor count, sample size, mean IC + **Promote/Keep/Watch/Retire** per factor |
| Walk-Forward | Periods, windows, horizons, rank IC — plus **overfitting warnings** (no PBO/CPCV yet) |
| Prediction Outcomes | Resolved/unresolved counts, forecast error, stale outcomes |
| Pairs | Universe size, cointegration, statsmodels, sample length |
| Data Quality | Quant Health, scheduler, failed jobs |
| Model Admin | v2 version, catalog, dynamic weights, audit |

**Evidence → action:** `EvidenceToActionBoundary` on the page states that Quant Lab does not change live scan rankings. Weight or model changes require explicit manual review (`ApplyChangesNotice`).

## Ops

Run IC panel (populates Factor Performance):

```bash
curl -X POST http://127.0.0.1:18731/api/v2/jobs/ic-panel
```

## Related

- [Quant Lab Redesign Final Report](./QUANT_LAB_REDESIGN_FINAL_REPORT.md)
- [Quant Lab Redesign Progress](./QUANT_LAB_REDESIGN_PROGRESS.md)
- [Manual test checklist](./QUANT_LAB_MANUAL_TEST_CHECKLIST.md)
- [Research Reliability](./RESEARCH_RELIABILITY.md)
