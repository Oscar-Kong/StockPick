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

## Ops — Morning scan email

Protected ops routes for the daily scan digest. `POST /send` requires non-demo mode (`require_non_demo_mode`).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ops/notifications/morning-scan/send` | Send or dry-run email. Body: `{ "force": false, "dry_run": false }` |
| `GET` | `/ops/notifications/morning-scan/status` | Enabled flag, masked recipient, schedule, last delivery, scan freshness |
| `GET` | `/ops/notifications/morning-scan/history?limit=20` | Recent delivery attempts (no secrets) |

## Related legacy Quant Lab endpoints

See [QUANT_LAB.md](./QUANT_LAB.md) for `/api/v2/quant-lab/evidence`, `/research/walk-forward`, `/research/pairs`, factor performance, and model admin routes.
