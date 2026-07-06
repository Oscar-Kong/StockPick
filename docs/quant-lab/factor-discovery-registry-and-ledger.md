# Factor Discovery Registry and Immutable Ledger (Phase 5)

Phase 5 adds durable persistence for Factor Discovery research. A persisted validation pass is **research evidence only** — it does not authorize paper trading, production Scan use, or production lifecycle promotion.

## Database entities

| Table | Purpose |
|-------|---------|
| `factor_hypothesis_records` | Economic rationale and research intent (no performance claims) |
| `factor_definition_records` | Immutable versioned DSL definitions; unique `(factor_id, version)` |
| `factor_research_families` | Multiple-testing family scope |
| `factor_discovery_runs` | Every run (success or failure) |
| `factor_discovery_attempts` | Append-only attempt ledger |
| `factor_validation_artifact_records` | Immutable closed/opened validation JSON |
| `factor_research_data_snapshots` | Content-addressed panel metadata |
| `factor_sealed_test_receipts` | Atomic sealed-test reservations |
| `factor_status_events` | Authoritative lifecycle audit log |

ORM: `backend/engines/factor_discovery_models.py`. Repositories: `backend/services/factor_discovery/repositories.py`.

## Immutability rules

- Formula-bearing fields on `factor_definition_records` are write-once.
- Validation artifact payloads are never updated in place.
- Closed artifacts cannot contain sealed metrics.
- Opened artifacts link to closed artifacts via `closed_artifact_id`.
- Normal services expose no delete APIs.

## Attempt-count policy

Policy version: `distinct_formula_evaluations_v1` (`backend/services/factor_discovery/multiple_testing_service.py`).

Counts distinct `formula_hash` values within a research family that reached cross-sectional metric evaluation (`metric_evaluation_started` or outcomes `validation_completed` / `sealed_open_completed`) at the same `primary_horizon_sessions`. Parse/compile failures remain in the ledger but do not increment the family size. Technical retries of the same formula do not double-count.

Family size at evaluation time is stored on each artifact (`family_size_at_evaluation`). Later family growth marks prior artifacts as stale for corrected significance; artifacts are not rewritten.

## Lifecycle evidence

Transitions are enforced by `FactorLifecycleService` (`backend/services/factor_discovery/lifecycle_service.py`):

- `DRAFT → COMPILED`: compile evidence + matching formula hash
- `COMPILED → RESEARCHING`: durable run created
- `RESEARCHING → PROMISING`: explicit actor only (validation may recommend)
- `PROMISING → VALIDATED`: human approval + sealed receipt + matching hashes
- `PAPER → PRODUCTION`: blocked in Phase 5

Status events and cached `lifecycle_status` update in one transaction with row locking.

## Feature flag

`FACTOR_DISCOVERY_ENABLED` defaults to `false`. When disabled, experiment launch fails fast and Factor Discovery API routes return 503.
