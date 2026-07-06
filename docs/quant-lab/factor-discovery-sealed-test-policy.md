# Factor Discovery Sealed-Test Policy (Phase 5)

Sealed-test opening is a **separate operation** from normal Factor Discovery validation. Normal experiment launch never computes sealed metrics.

## Flow

1. Closed run and closed artifact must exist.
2. `SealedTestAccess` submitted with `approval_reference` and hash locks.
3. Receipt **reserved atomically** in `factor_sealed_test_receipts` (unique identity constraint).
4. Exact persisted research identity reloaded and verified.
5. Sealed metrics computed.
6. Opened artifact persisted; receipt marked `COMPLETED`.

If reservation fails: `SEALED_TEST_ALREADY_RESERVED` or `SEALED_TEST_ALREADY_OPENED` — no recomputation.

If computation fails after reservation: receipt preserved as `FAILED` with `failure_code`.

## Identity lock

Reservation uniqueness covers: factor version, formula hash, plan hash, panel snapshot, period hash, validation config hash, access policy version.

Implementation: `backend/services/factor_discovery/sealed_test_service.py`.

## API

`POST /api/v2/research/factor-discovery/sealed-test/open` (requires `FACTOR_DISCOVERY_ENABLED=true`).

A persisted validation pass is research evidence only. It does not authorize paper trading, production Scan use, or production lifecycle promotion.
