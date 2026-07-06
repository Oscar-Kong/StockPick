# API Reference (Quant Lab Research)

Base path: `/api/v2/research`  
Feature flag: `QUANT_LAB_RESEARCH_API_ENABLED` (503 when false)

Research APIs do **not** auto-update live scan rankings, weights, or orders. Change proposals require explicit review.

## Overview

| Method | Path | Description |
|--------|------|-------------|
| GET | `/overview?sleeve=` | Research home rollup: confidence, freshness, versions, regime, predictions, brief findings, recommended ideas, activity, maintenance actions |

Bounded read-only aggregation — does not enqueue heavy research jobs.

## Ideas

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ideas` | Create research idea |
| GET | `/ideas` | List ideas (`status`, `sleeve`, `offset`, `limit`) |
| GET | `/ideas/{id}` | Get idea |
| PATCH | `/ideas/{id}` | Update idea |
| DELETE | `/ideas/{id}` | Delete idea |
| POST | `/ideas/generate` | Generate ideas from deterministic brief findings (`sleeve`, `limit`, `from_findings_only`) |
| POST | `/ideas/{id}/duplicate` | Duplicate idea (new id, archived source unchanged) |

## Experiment Studio

| Method | Path | Description |
|--------|------|-------------|
| GET | `/experiments/templates` | Six experiment template definitions |
| GET | `/experiments/presets` | Quick Check / Standard / Robust preset parameters |
| POST | `/experiments/validate` | Pre-run validation (hypothesis, universe, dependencies) |
| POST | `/experiments/{id}/launch` | Launch experiment job (duplicate-safe) |
| GET | `/experiments/jobs/{job_id}` | Job status with discrete stages |

Job stages: `validating` → `resolving_universe` → `loading_prices` → `calculating_features` → `running_analysis` → `calculating_outcomes` → `evaluating_reliability` → `persisting_result` → `complete` / `failed`.

**Statuses:** `new`, `saved`, `ready_to_test`, `running`, `supported`, `rejected`, `inconclusive`, `archived`

**Source types:** `factor_deterioration`, `factor_improvement`, `prediction_drift`, `recommendation_calibration`, `market_regime`, `scan_dispersion`, `portfolio_concentration`, `pair_relationship`, `data_quality`, `failed_experiment`, `user_created`

## Experiments

| Method | Path | Description |
|--------|------|-------------|
| POST | `/experiments` | Create experiment definition (not a run) |
| GET | `/experiments` | List (`idea_id`, `experiment_type`, `sleeve`) |
| GET | `/experiments/{id}` | Get experiment |
| PATCH | `/experiments/{id}` | Update experiment |
| DELETE | `/experiments/{id}` | Delete experiment |

**Experiment types:** `factor_validation`, `walk_forward`, `prediction_calibration`, `pairs_discovery`, `similar_signal`, `portfolio_policy`

## Unified runs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/runs` | Paginated run index (`run_type`, `sleeve`, `status`, `verdict`, `evidence_impact`, `search`, `date_from`, `date_to`, `archived`, `include_archived`, `experiment_id`, `idea_id`, `backfill`) |
| GET | `/runs/{run_id}` | Run summary (`ResearchRunSummary`) |
| GET | `/runs/{run_id}/detail` | Full result detail: interpretation, charts, metrics, evidence memory (`ResearchRunDetailResponse`) |
| GET | `/runs/{run_id}/export?format=json\|csv` | Export metadata + results (no secrets) |
| GET | `/runs/compare?run_ids=a,b` | Comparison metadata |
| GET | `/runs/compare/detail?run_ids=a,b,c` | Compatibility checks, metric diffs, charts (2–4 runs) |
| POST | `/runs/backfill?limit=` | Index existing persisted stores |
| POST | `/runs/{run_id}/index` | Index single run from store |
| POST | `/runs/{run_id}/refresh` | Re-index from source store + refresh interpretation |
| PATCH | `/runs/{run_id}/link` | Link run to experiment/idea |
| PATCH | `/runs/{run_id}/notes` | Save research notes on index row |
| PATCH | `/runs/{run_id}/archive` | Archive / unarchive run |
| POST | `/runs/{run_id}/duplicate-experiment` | Clone experiment definition from run |
| POST | `/runs/{run_id}/follow-up-idea` | Create linked follow-up idea |
| POST | `/runs/{run_id}/sync-evidence` | Sync symbol findings to evidence memory |
| GET | `/model-monitor?sleeve=` | Factor, prediction, data health, jobs, model config |
| GET | `/evidence-review` | Findings requiring impact review |
| POST | `/evidence-review/{finding_id}/action` | Review action (no direct weight updates) |
| POST | `/jobs/{job_id}/retry` | Retry research job with duplicate guard |

Run payloads remain in source tables (`backtest_runs`, `pairs_research_runs`, `factor_ic_history`, etc.). Index rows hold `result_reference` pointers, deterministic `interpretation_json`, `research_notes`, and `archived`.

**Deterministic verdicts:** `supports_hypothesis`, `rejects_hypothesis`, `inconclusive`, `insufficient_data`, `invalid` — computed server-side; optional LLM may rewrite prose only.

**Evidence impact levels:** `informational`, `supporting`, `contradicting`, `major_positive`, `major_negative`, `integrity_blocker`

## Evidence memory

| Method | Path | Description |
|--------|------|-------------|
| POST | `/evidence-memory` | Create stock-specific evidence record |
| GET | `/evidence-memory` | List (`symbol`, `run_id`, `experiment_id`, `evidence_impact`) |
| GET | `/evidence-memory/{id}` | Get record |
| PATCH | `/evidence-memory/{id}` | Update record |
| DELETE | `/evidence-memory/{id}` | Delete record |

Does not store full price history — references signals, factor snapshots, runs, and forward outcomes.

## Factor lineage

| Method | Path | Description |
|--------|------|-------------|
| GET | `/factor-lineage/{factor_id}` | Lineage rows for factor |
| POST | `/factor-lineage/sync?sleeve=&as_of_date=` | Sync from IC panel date |

## Impact policy & gate (deterministic)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/impact/evaluate` | Evaluate impact level + capped modifier |
| POST | `/gate/evaluate?run_id=` | Major evidence gate for a run |

Configured via `RESEARCH_MAX_ORDINARY_MODIFIER` (default `0` = display-only).

## Model Monitor & evidence review (Phase 6)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/model-monitor?sleeve=` | Factor, prediction, data health, research jobs, read-only model config |
| GET | `/evidence-review` | Findings classified for impact review |
| POST | `/evidence-review/{finding_id}/action` | Review action (informational, proposal, reject — no live weight change) |
| POST | `/jobs/{job_id}/retry` | Retry failed job with duplicate guard |

`GET /api/v2/audit` supports filters: `sleeve`, `since`, `until`, `run_id`, `experiment_id`, `proposal_id`, `strategy_version`.

## Factor Discovery — mining loop (Phase 7 / 8B UI)

Base path: `/api/v2/research/factor-discovery/mining`  
Flags: `FACTOR_DISCOVERY_LOOP_ENABLED`, `FACTOR_DISCOVERY_LOOP_MODE` (503 when disabled)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/readiness` | Consolidated UI readiness (flags, providers, bounded-auto, restrictions) |
| POST | `/sessions` | Create mining session (`AWAITING_AUTHORIZATION`) |
| POST | `/sessions/{id}/authorize` | Authorize immutable config (`expected_state_version`, `reason`) |
| POST | `/sessions/{id}/start` | Begin hypothesis generation |
| POST | `/sessions/{id}/advance` | Bounded workflow step(s) (`expected_state_version`, `maximum_steps` ≤ 10) |
| POST | `/sessions/{id}/pause` | Pause session |
| POST | `/sessions/{id}/resume` | Resume to prior workflow state |
| POST | `/sessions/{id}/cancel` | Terminal cancel |
| POST | `/sessions/{id}/hypotheses/{candidate_id}/approve` | Human hypothesis approval |
| POST | `/sessions/{id}/hypotheses/{candidate_id}/reject` | Human hypothesis rejection |
| POST | `/sessions/{id}/formulas/{candidate_id}/approve` | Human formula approval |
| POST | `/sessions/{id}/formulas/{candidate_id}/reject` | Human formula rejection |
| POST | `/sessions/{id}/revisions/{candidate_id}/approve` | Human revision approval |
| POST | `/sessions/{id}/revisions/{candidate_id}/reject` | Human revision rejection |
| GET | `/sessions` | List sessions (filters: `status`, `session_mode`, `search`, `awaiting_review`, …) |
| GET | `/sessions/{id}` | Session detail + `allowed_actions` + `action_disabled_reasons` |
| GET | `/sessions/{id}/events` | Append-only event log |
| GET | `/sessions/{id}/summary` | Deterministic session summary |

**Mutations:** require `expected_state_version` (422 if missing, 409 if stale). Success returns mutation envelope: `state_version`, `pending_reviews`, `allowed_actions`, `budget_summary`, …

**Families:** `GET /api/v2/research/factor-discovery/families` — list research families for session creation.

## Factor Discovery — review & evidence (Phase 9A)

Base path: `/api/v2/research/factor-discovery`  
Flag: `FACTOR_DISCOVERY_ENABLED` (503 when false). Review queue also requires mining loop enabled.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/candidates/hypotheses/{candidate_id}` | UI-ready hypothesis candidate detail + server-derived `allowed_actions` |
| GET | `/candidates/formulas/{candidate_id}` | UI-ready formula candidate detail (canonical DSL, AST, compiler warnings) |
| GET | `/candidates/revisions/{candidate_id}` | UI-ready revision candidate detail (semantic diff, policy rules) |
| GET | `/llm/interactions/{interaction_id}` | UI-safe LLM interaction metadata (no raw secrets) |
| GET | `/mining/review-queue` | Aggregated pending hypothesis/formula/revision/promising queue (paginated) |
| GET | `/mining/sessions/{id}/integrity` | Session integrity verification |
| GET | `/factors` | Persisted factor-definition registry (filters: search, lifecycle, direction, promising, has_validation) |
| GET | `/factors/{factor_id}` | Factor detail with version lineage and linked artifacts |
| GET | `/factors/{factor_id}/versions/{version}` | Immutable factor version detail |
| GET | `/artifacts/{artifact_id}/validation-result` | Closed validation artifact with integrity + promising policy (no sealed metrics) |
| GET | `/runs/{run_id}/validation-result` | Validation result by experiment run |

**Review mutations** (under `/mining/sessions/{id}/…`): require `expected_state_version`, `actor`, and `reason`. HTTP 409 on stale state; no automatic retry.

No sealed-test opening, lifecycle promotion, or Scan integration routes.

## Factor Discovery — staging validation (Phase 9B)

Read-only operational visibility. Data mutation via CLI only.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/factor-discovery/staging/preflight` | Staging preflight report (price, universe, snapshot readiness) |
| GET | `/factor-discovery/staging/extended-latest` | Latest Phase 9B.2 extended staging matrix report |
| GET | `/factor-discovery/staging/latest-audit` | Latest persisted staging audit artifact |

CLI: `python -m scripts.factor_discovery_staging_preflight`, `factor_discovery_audit`, `factor_discovery_materialize_snapshot`.

## Factor Discovery — promotion governance (Phase 10)

Requires `FACTOR_PROMOTION_GOVERNANCE_ENABLED=true`. Shadow evaluations additionally require `FACTOR_SHADOW_SCORING_ENABLED=true`. **Advisory only** — no live scan mutation.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/factor-discovery/promotion/readiness` | Governance/shadow flags and live-config safety |
| GET | `/factor-discovery/promotion-candidates` | List candidates (`sleeve`, `status`) |
| POST | `/factor-discovery/promotion-candidates` | Create from validated staging + factor definition |
| GET | `/factor-discovery/promotion-candidates/{id}` | Candidate detail with gate evaluation |
| POST | `/factor-discovery/promotion-candidates/{id}/transitions` | Governed status transition (audited) |
| GET | `/factor-discovery/promotion-candidates/{id}/evidence` | Immutable evidence bundle |
| GET | `/factor-discovery/promotion-candidates/{id}/audit` | Status transition audit history |
| POST | `/factor-discovery/promotion-candidates/{id}/explain` | Structured evidence summary (no gate override) |
| POST | `/factor-discovery/promotion-candidates/{id}/shadow-evaluations` | Request shadow scoring run |
| GET | `/factor-discovery/promotion-candidates/{id}/shadow-evaluations` | List shadow evaluation runs |

**Promotion statuses:** `experimental`, `staged`, `promotion_candidate`, `shadow`, `approved_for_manual_integration`, `rejected`, `archived`

## Change proposals

| Method | Path | Description |
|--------|------|-------------|
| POST | `/change-proposals` | Create proposal (draft) |
| GET | `/change-proposals` | List (`status`, `affected_sleeve`) |
| GET | `/change-proposals/{id}` | Get proposal |
| PATCH | `/change-proposals/{id}` | Update status/fields |
| DELETE | `/change-proposals/{id}` | Delete proposal |

**Statuses:** `draft`, `needs_validation`, `ready_for_review`, `rejected`, `approved_for_staging`, `archived`

No proposal auto-applies to production configuration.

## Settings — mailing list

Manage morning scan email recipients in-app (persisted to `backend/data_store/mailing_list.json`). When the mailing list has at least one **active** subscriber, it overrides `SCAN_EMAIL_TO` from `.env`. When the list is empty, recipients fall back to `SCAN_EMAIL_TO`.

Mutating routes require non-demo mode.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/settings/mailing-list` | List subscribers, active count, and effective recipient source (`settings` \| `env` \| `none`) |
| `POST` | `/settings/mailing-list` | Add subscriber. Body: `{ "email": "a@b.com", "label": "optional" }` |
| `PATCH` | `/settings/mailing-list/{id}` | Update `enabled` and/or `label` |
| `DELETE` | `/settings/mailing-list/{id}` | Remove subscriber |
| `POST` | `/settings/mailing-list/import-env` | Copy addresses from `SCAN_EMAIL_TO` into the managed list (skips duplicates) |

UI: Settings → **Ops** → **Mailing list**. StockPick sends via SMTP (Gmail); no Mailchimp/ConvertKit integration.

## Ops — Morning scan email

Protected ops routes for the daily scan digest. `POST /send` requires non-demo mode (`require_non_demo_mode`).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ops/notifications/morning-scan/send` | Send or dry-run email. Body: `{ "force": false, "dry_run": false }` |
| `GET` | `/ops/notifications/morning-scan/status` | Enabled flag, masked recipient, recipient source/count, schedule, last delivery, scan freshness |
| `GET` | `/ops/notifications/morning-scan/history?limit=20` | Recent delivery attempts (no secrets) |

## Related legacy Quant Lab endpoints

See [QUANT_LAB.md](./QUANT_LAB.md) for `/api/v2/quant-lab/evidence`, `/research/walk-forward`, `/research/pairs`, factor performance, and model admin routes.

## Home — daily dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/home/daily-dashboard` | Portfolio Today payload: holdings, `decision`, `top_penny_opportunities`, `freshness`, and nested `daily_trading_plan` |
| POST | `/home/refresh` | Background refresh (holdings, prices, decision, scans) |
| GET | `/home/refresh-status/{job_id}` | Poll refresh job |

**`daily_trading_plan`** (nested on `DailyDashboardResponse`): deterministic short-term plan from policy engine — `decision` (`buy` \| `manage` \| `reduce` \| `exit` \| `watch` \| `stay_in_cash`), exposure meters, `focus_list` (3–5 symbols), `primary_candidate` (entry/stop/target sizing), `rule_checklist`, `holiday_risk`, `data_freshness`. Reuses latest cached penny scan (no new scan on page load).

## Portfolio — daily trading plan review

| Method | Path | Description |
|--------|------|-------------|
| GET | `/portfolio/daily-trading-plan/review?trading_date=` | Load end-of-day review for a trading date |
| POST | `/portfolio/daily-trading-plan/review` | Upsert review (`plan_followed`, `actual_action`, `overridden_rules`, `user_notes`, `end_of_day_outcome`) |

Decision support only — no order execution.

## Portfolio — performance & summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/portfolio/performance` | P/L summary and mark-to-market equity curves for current holdings |
| GET | `/portfolio/summary` | Canonical portfolio summary (value, cash, freshness) from the same ledger as Home |

**`PortfolioPerformanceResponse`:** `total_value`, `today_pl`, `today_pl_pct`, `unrealized_pl`, `unrealized_pl_pct`, `realized_pl`, optional `realized_pl_equity`, `realized_pl_events`, `realized_pl_source` (`robinhood_mcp` \| `ledger`), `curves`, `period_change_pct`, `disclaimer`. When Robinhood MCP is authenticated, **realized P/L (YTD)** comes from `get_pnl_trade_history` (includes partial equity sells and prediction/event contracts with empty symbol). Otherwise falls back to YTD closed lots in the ledger. Unrealized = open-position cost basis. Response cached **120s** (`PORTFOLIO_PERFORMANCE_CACHE_TTL`); chart builds one 1y price series and slices ranges (avoids 5× redundant fetches).

## Brokerage — portfolio ledger & CSV import

Base path: `/api/brokerage` (mutating routes require non-demo mode)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ledger` | List all ledger rows + computed open holdings |
| POST | `/ledger` | Create manual ledger row (`LedgerEntryInput`) |
| PATCH | `/ledger/{id}` | Update draft row; pass `"lock": true` on Save to lock permanently |
| DELETE | `/ledger/{id}` | Delete row |
| POST | `/ledger/rebuild` | Recompute holdings from ledger |
| POST | `/preview/robinhood-csv` | Parse CSV; return editable preview rows + current/projected holdings (Form: `file`, optional `replace=true`) |
| POST | `/import/robinhood-csv/approve` | Apply reviewed rows from preview (`CsvApproveRequest`: `filename`, `replace`, `rows[]` with `included`, editable fields) |
| POST | `/import/robinhood-csv` | Legacy direct import (no review step) |
| GET | `/robinhood-mcp/status` | Robinhood MCP OAuth configured? |
| POST | `/sync/robinhood-mcp` | Start background Robinhood MCP sync → `{ job_id, status: "running" }` |
| GET | `/sync/robinhood-mcp/{job_id}` | Poll sync job until `completed` or `failed` |
| POST | `/buying-power` | Save explicit cash / IPO reserved amounts |

**CSV flow:** UI calls preview → user edits/unchecks rows → approve sends the edited payload (not the raw file). Semantic dedupe on append includes activity date, symbol, side, quantity, and price.
