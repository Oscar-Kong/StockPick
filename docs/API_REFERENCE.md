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
| GET | `/runs` | Paginated run index (`run_type`, `sleeve`, `status`, `experiment_id`, `idea_id`, `backfill`) |
| GET | `/runs/{run_id}` | Run summary (`ResearchRunSummary`) |
| GET | `/runs/compare?run_ids=a,b` | Comparison metadata |
| POST | `/runs/backfill?limit=` | Index existing persisted stores |
| POST | `/runs/{run_id}/index` | Index single run from store |
| PATCH | `/runs/{run_id}/link` | Link run to experiment/idea |

Run payloads remain in source tables (`backtest_runs`, `pairs_research_runs`, `factor_ic_history`, etc.). Index rows hold `result_reference` pointers only.

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

## Related legacy Quant Lab endpoints

See [QUANT_LAB.md](./QUANT_LAB.md) for `/api/v2/quant-lab/evidence`, `/research/walk-forward`, `/research/pairs`, factor performance, and model admin routes.
