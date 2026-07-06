# Factor Discovery concurrency and idempotency (Phase 6A)

## Database backends

Local tests use SQLite. PostgreSQL is supported for production-style deployments.

| Guarantee | SQLite | PostgreSQL |
|-----------|--------|------------|
| Factor version uniqueness | `UNIQUE (factor_id, version)` | Same |
| Sealed receipt identity | `uq_factor_sealed_test_identity` | Same |
| Validation artifact hash | `uq_factor_validation_artifact_hash` | Same |
| Lifecycle row lock | `SELECT … FOR UPDATE` ignored | Row lock honored |
| Launch idempotency | `idempotency_key` + `launch_payload_hash` | Same |

On SQLite, rely on unique constraints for races; do not assume row-level lifecycle locking.

## Idempotency

Launch idempotency key + canonical `launch_payload_hash` (see `services/factor_discovery/idempotency.py`):

- Same key + same payload → same run
- Same key + different payload → `IDEMPOTENCY_PAYLOAD_MISMATCH`

Snapshot idempotency uses `snapshot_identity_hash` from provider, policy, range, fields, and source version.

## Sealed receipt races

Reservation occurs before metric computation. Duplicate identity → `SEALED_TEST_ALREADY_RESERVED` or `SEALED_TEST_ALREADY_OPENED`. Failed receipts → `SEALED_RECEIPT_FAILED` (manual recovery only).

## Lifecycle atomicity

`FactorLifecycleService.transition()` updates cached status and appends `factor_status_events` in one transaction with `lifecycle_version` increment.

## Retry semantics

| Kind | Counted as statistical attempt? |
|------|--------------------------------|
| Transport retry | No |
| Technical run retry | Preserved in attempt ledger |
| Revalidation | New artifact via `revalidation_service` |
| Sealed opening | Separate receipt flow |
