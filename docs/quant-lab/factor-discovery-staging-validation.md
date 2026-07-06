# Factor Discovery — staging validation (Phase 9B)

Phase 9B validates reproducible price-only research on an audited staging dataset. It does **not** authorize production Scan, trading, sealed-test opening, or lifecycle promotion.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `FACTOR_DISCOVERY_STAGING_ENABLED` | `false` | Explicit staging operations gate |
| `FACTOR_RESEARCH_DATA_PROVIDER` | `disabled` | Set to `historical_store` for staging runs |
| `FACTOR_RESEARCH_SNAPSHOT_ROOT` | `backend/data/factor_discovery/snapshots` | Immutable snapshot storage |
| `FACTOR_RESEARCH_STAGING_INPUT_ROOT` | `backend/data/factor_discovery/staging_input` | Versioned CSV import root |
| `FACTOR_RESEARCH_STAGING_AUDIT_ROOT` | `backend/data/factor_discovery/staging_audits` | Staging audit JSON artifacts |
| `FACTOR_RESEARCH_EXTENDED_STAGING_ROOT` | `backend/data/factor_discovery/extended_staging` | Extended staging reports |
| `FACTOR_RESEARCH_ACCEPTANCE_ROOT` | `backend/data/factor_discovery/acceptance` | Phase 11 acceptance runner output |
| `FACTOR_RESEARCH_PROMOTION_EVIDENCE_ROOT` | `backend/data/factor_discovery/promotion_evidence` | Promotion evidence bundles |

## CLI

```bash
cd backend && source .venv/bin/activate

# Read-only preflight (local/staging DB)
python -m scripts.factor_discovery_staging_preflight --json

# Universe import (requires FACTOR_DISCOVERY_STAGING_ENABLED=true)
python -m scripts.factor_discovery_import_universe \
  --config data/factor_discovery/staging_input/universe/us_equity_research_v1_import.yaml \
  --dry-run --json
python -m scripts.factor_discovery_import_universe \
  --config data/factor_discovery/staging_input/universe/us_equity_research_v1_import.yaml --json

python -m scripts.factor_discovery_audit_universe --universe-id us_equity_research_v1 --json
python -m scripts.factor_discovery_audit --json --allow-test --actor local-audit

# Staging-only provider activation (never enable globally in production)
export FACTOR_DISCOVERY_STAGING_ENABLED=true
export FACTOR_RESEARCH_DATA_PROVIDER=historical_store
export FACTOR_DISCOVERY_ENABLED=true

python -m scripts.factor_discovery_materialize_snapshot \
  --start 2020-01-02 --end 2023-06-30 --json
python -m scripts.factor_discovery_run_suite \
  --snapshot-id <snapshot_id> --json
python -m scripts.factor_discovery_reproduce --run-id <run_id> --compare-run-id <run_id> --json
```

## Phase 9B.1 notes

### Price audit scalability

The original preflight hung because the price audit loaded the full `daily_quotes` table into Python (`session.query(DailyQuote).all()`). Phase 9B.1 uses **SQL aggregates** for counts/min/max/duplicates and **bounded sampling** for suspicious jumps, gaps, and invalid examples (`MAXIMUM_SAMPLE_SYMBOLS=50`, `MAXIMUM_FLAGGED_EXAMPLES_PER_CATEGORY=20`).

### Universe import

A large adjusted-price table is **not** sufficient for safe historical factor research. Date-specific, sourced, and versioned universe membership is required to prevent current-list and survivorship bias.

Staging source for Phase 9B.1:

| Field | Value |
|-------|-------|
| Source ID | `manual_staging_curated_v1` |
| Source version | `2026-07-02` |
| Format | interval CSV under `FACTOR_RESEARCH_STAGING_INPUT_ROOT` |
| Universe ID | `us_equity_research_v1` |

Import config: `backend/data/factor_discovery/staging_input/universe/us_equity_research_v1_import.yaml`

### Provider activation

`FACTOR_RESEARCH_DATA_PROVIDER=historical_store` is rejected unless `FACTOR_DISCOVERY_STAGING_ENABLED=true` (except `APP_ENV=test`). No fallback to fixture or live providers.

### Frozen staging factor

First non-fixture supervised run uses **`rank(return_126d)`** (`staging_return_126d_rank`) for reproducibility — not performance optimization.

## Workflow

1. Preflight (read-only) — price, universe, snapshot, capability audits
2. Import prices/universe via staging input CSV (versioned batch metadata)
3. Materialize immutable snapshot (`factor_snapshot_csv_bundle_v1`)
4. Verify reproducibility (identical request → identical hashes)
5. Run predetermined price-only factor set (systems validation, not optimization)
6. Persist staging audit artifact

## Readiness UI

Quant Lab → Factor Discovery → **Readiness** shows **Staging research readiness** (not trading readiness).

## Policies

- [Historical data policy](./factor-discovery-historical-data-policy.md)
- [Universe PIT policy](./factor-discovery-universe-pit-policy.md)
- [Snapshot reproducibility](./factor-discovery-snapshot-reproducibility.md)
- [Staging readiness policy](./factor-discovery-staging-readiness-policy.md)

> Passing Phase 9B means the research system is reproducible on the audited staging dataset. It does not prove profitability, reveal sealed evidence, or approve trading.
