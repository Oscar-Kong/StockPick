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

## UI layout (2026 makeover)

- **Header:** page title, sleeve selector (when the section uses a sleeve), **Guide** drawer button, and research-only badge.
- **Sticky section nav:** workflow tabs (Overview → Model Monitor); Legacy in **More** menu below 900px.
- **Section workspace:** single `DataPanel` per section; no forced min-height padding.
- **Guide drawer:** Evidence, Scan relationship, and Action boundary panels (formerly stacked above content).
- **Overview:** four `MetricTile` KPIs + two-column findings grid.
- **Experiments:** configure/review use a desktop split pane (form + run summary aside).

See `design-system/pages/quant-lab.md` for the full spec.

See also: [Product flow in UI](../frontend/src/components/product/ProductFlowDiagram.tsx) — rendered on `/quant-lab`.

## Evidence overview (page load)

On open, Quant Lab loads read-only summaries via `GET /api/v2/quant-lab/evidence?sleeve=penny`:

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
| Model Monitor | `section=model-monitor` | `GET /api/v2/research/model-monitor` — factor/prediction/data health, jobs, audit, evidence review |
| Legacy tools | `section=legacy&tab=` | Factor performance, walk-forward, predictions, pairs |

Overview includes deterministic **research brief** findings, recommended ideas, recent activity, and collapsible **evidence maintenance** actions (IC panel, forward labels, resolve outcomes, quant daily jobs, evidence backfill).

Ideas board supports manual create, generate-from-brief, edit/notes/priority, archive, duplicate, and **Configure experiment** (creates experiment record + opens Experiment Studio).

> **Retired:** `section=models` (static equation library) redirects to `section=model-monitor`. Use Portfolio → Research for Markowitz optimization and Legacy → Pairs for cointegration research.

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

## Factor discovery (Phase 6B LLM layer complete)

Phase 0–6B backend persistence, gated experiment integration, and schema-constrained LLM research layer are **complete**. Both runtime flags remain **disabled by default** (`FACTOR_DISCOVERY_ENABLED=false`, `FACTOR_DISCOVERY_LLM_ENABLED=false`).

- Contracts: `backend/models/schemas_factor_discovery.py`
- DSL & compiler: `backend/engines/factor/discovery/`
- Execution engine: `compute_factor_panel()` — see [execution engine](./quant-lab/factor-discovery-execution-engine.md)
- Validation engine: `validate_factor_execution()` — see [validation engine](./quant-lab/factor-discovery-validation-engine.md)
- Phase 5 persistence: [registry & ledger](./quant-lab/factor-discovery-registry-and-ledger.md) · [sealed-test policy](./quant-lab/factor-discovery-sealed-test-policy.md) · [experiment runner](./quant-lab/factor-discovery-experiment-runner.md)
- Phase 6A hardening: [data provider](./quant-lab/factor-discovery-data-provider.md) · [concurrency & idempotency](./quant-lab/factor-discovery-concurrency-and-idempotency.md) · [operations](./quant-lab/factor-discovery-operations.md)
- Phase 6B LLM: [LLM architecture](./quant-lab/factor-discovery-llm-architecture.md) · [prompts](./quant-lab/factor-discovery-llm-prompts.md) · [security](./quant-lab/factor-discovery-llm-security.md) · [human review policy](./quant-lab/factor-discovery-human-review-policy.md)
- Env: `FACTOR_DISCOVERY_ENABLED`, `FACTOR_DISCOVERY_LLM_ENABLED`, `FACTOR_DISCOVERY_LLM_PROVIDER` (all default off/disabled)
- Docs: [audit](./quant-lab/factor-discovery-audit.md) · [architecture](./quant-lab/factor-discovery-architecture.md) · [DSL](./quant-lab/factor-discovery-dsl.md) · [data inventory](./quant-lab/factor-discovery-data-inventory.md) · [risk register](./quant-lab/factor-discovery-risk-register.md) · [implementation plan](./quant-lab/factor-discovery-implementation-plan.md)

> A persisted validation pass is research evidence only. It does not authorize paper trading, production Scan use, or production lifecycle promotion.

## Factor Discovery mining loop (Phase 7) & workspace (Phase 8B / 9A)

Backend bounded workflow: hypothesis generation → human review → formula translation → closed experiment → critique with validation-exposure limits. Disabled by default (`FACTOR_DISCOVERY_LOOP_ENABLED=false`).

**Quant Lab UI:** `/quant-lab?section=factor-discovery` — supervised session dashboard, new research flow, **server-backed review queue**, **candidate review cards**, **validation evidence panel**, **factor registry**, readiness. See [factor-discovery-workspace.md](./quant-lab/factor-discovery-workspace.md).

**Phase 9A** completes research review and evidence presentation. It does **not** validate factors for investment use, reveal sealed-test performance, promote lifecycle status, or connect factors to production Scan. Real-data staging validation is **Phase 9B**.

**Phase 9B** adds real-data staging validation: preflight audits, immutable snapshot reproducibility, and staging audit artifacts. See [factor-discovery-staging-validation.md](./quant-lab/factor-discovery-staging-validation.md).

**Phase 9B.2** runs an extended staging matrix across Penny and Compounder sleeves with regime slices, negative controls, and a promotion-readiness gate (`READY_FOR_PROMOTION_REVIEW` / `NOT_READY_FOR_PROMOTION_REVIEW`). See [FACTOR_MINING_EXTENDED_STAGING.md](./FACTOR_MINING_EXTENDED_STAGING.md).

**Phase 10** adds controlled promotion governance: lifecycle states from `experimental` through `approved_for_manual_integration`, versioned promotion gates, immutable evidence bundles, shadow scoring (research-only), and the **Promotion Review** tab in Factor Discovery. Does **not** activate live scan scoring. See [FACTOR_PROMOTION_GOVERNANCE.md](./FACTOR_PROMOTION_GOVERNANCE.md) and [FACTOR_SHADOW_SCORING.md](./FACTOR_SHADOW_SCORING.md).

**Phase 11** (final) adds the acceptance runner, isolation audit, traceability matrix, and release documentation. Status: **`PHASE_11_COMPLETE`**. See [FACTOR_RESEARCH_FINAL_ACCEPTANCE.md](./FACTOR_RESEARCH_FINAL_ACCEPTANCE.md), [PHASE_0_TO_11_TRACEABILITY.md](./PHASE_0_TO_11_TRACEABILITY.md), [RESEARCH_RELIABILITY.md](./RESEARCH_RELIABILITY.md).

```bash
python backend/scripts/run_factor_research_acceptance.py --mode fixture   # CI
python backend/scripts/run_factor_research_acceptance.py --mode real      # local DB
```

- Architecture: [quant-lab/factor-discovery-mining-loop.md](./quant-lab/factor-discovery-mining-loop.md)
- Review UI: [factor-discovery-candidate-review-ui.md](./quant-lab/factor-discovery-candidate-review-ui.md) · [promising review](./quant-lab/factor-discovery-promising-review-ui.md) · [artifact integrity UI](./quant-lab/factor-discovery-artifact-integrity-ui.md) · [factor registry](./quant-lab/factor-discovery-factor-registry.md)
- API: `GET/POST /api/v2/research/factor-discovery/...` (503 when disabled)
- Does **not** affect live Scan rankings or open sealed tests

## Scan Selection Evaluation (Experiment Studio)

`experiment_type: scan_evaluation` is wired through Experiment Studio (UI: `ScanEvaluationConfigFields` on configure, `ScanEvaluationResultPanel` on result + Results detail):

| Step | Module |
|------|--------|
| Template | `experiment_presets_service.TEMPLATE_META` + Experiment Studio choose step |
| Configure | `ScanEvaluationConfigFields.tsx` (algorithms, horizons, friction) |
| Validate | `experiment_validation_service` + `validate_scan_evaluation_params` |
| Launch | `experiment_launch_service._run_scan_evaluation` |
| Runner | `scan_evaluation_experiment_runner.ScanEvaluationExperimentRunner` |
| Persist | `backtest_runs` (`run_type=scan_evaluation`) |
| Index | `research_run_service.adapter_scan_evaluation` |
| Results UI | `ScanEvaluationResultPanel.tsx` (comparison table + caveats) |
| Charts | `scan_evaluation_charts.charts_from_artifact` via `research_run_detail_service.build_charts` |

Preset: `scan_eval_smoke`. Does **not** modify production scan rankings.

## Related

- [Quant Lab Redesign Final Report](./QUANT_LAB_REDESIGN_FINAL_REPORT.md)
- [Quant Lab Redesign Progress](./QUANT_LAB_REDESIGN_PROGRESS.md)
- [Manual test checklist](./QUANT_LAB_MANUAL_TEST_CHECKLIST.md)
- [Research Reliability](./RESEARCH_RELIABILITY.md)
