# Factor Discovery — snapshot reproducibility

Format: `factor_snapshot_csv_bundle_v1`

## Identity

Snapshot request hash includes provider, policy, date range, universe source, required fields, and provider data version.

## Verification

1. Materialize snapshot A
2. Repeat identical request → reuse or match hashes
3. Reload from disk → recompute panel and session hashes
4. Tampering → `ARTIFACT_INTEGRITY_FAILURE`

Changing provider version, universe version, calendar, symbol mapping, or source data must change identity.

## CLI

```bash
python -m scripts.factor_discovery_materialize_snapshot --json
```
