# Factor Mining Extended Staging (Phase 9B.2)

Extended real-data staging validates that the supervised factor-mining pipeline remains reliable across sleeves, date slices, regimes, and failure conditions using the historical database.

Phase 9B.1 established single-factor reproducibility. Phase 9B.2 executes a **staging matrix** without mutating live scan rankings, production factor weights, or portfolio recommendations.

## Readiness outcomes

This phase returns exactly one of:

- `READY_FOR_PROMOTION_REVIEW`
- `NOT_READY_FOR_PROMOTION_REVIEW`

No factor promotion occurs in this phase.

## CLI

```bash
cd backend && source .venv/bin/activate

export FACTOR_DISCOVERY_STAGING_ENABLED=true
export FACTOR_RESEARCH_DATA_PROVIDER=historical_store
export FACTOR_DISCOVERY_ENABLED=true

# Inspect resolved matrix without executing runs
python scripts/run_factor_mining_extended_staging.py \
  --sleeves penny,compounder \
  --dry-run --json

# Full extended staging run
python scripts/run_factor_mining_extended_staging.py \
  --sleeves penny,compounder \
  --output-dir backend/data/factor_discovery/extended_staging \
  --json
```

Dates are resolved from database quote/universe overlap unless `--start-date` / `--end-date` are supplied.

## Staging manifest

Every extended run persists a versioned manifest containing:

- Git commit / code version
- Database fingerprint
- Provider ID and PIT universe version
- Active sleeves and date range
- Factor registry version, label definition, horizon, cost assumptions
- Random seed and configuration hash
- Environment flags and matrix specification

## Matrix dimensions

| Dimension | Values |
|-----------|--------|
| Sleeves | `penny`, `compounder` (legacy `medium` maps to `penny` at API boundaries only) |
| Period slices | Early / middle / recent walk-forward windows from supported overlap |
| Regimes | SPY volatility proxy slices when SPY quotes exist |
| Factors | Frozen canary `rank(return_126d)`, staging price-only set, momentum baseline |

## Negative controls

Executed once per run on the reference snapshot panel:

- Outcome fields absent
- Future price / universe mutation isolation
- Sealed-period isolation
- Shuffled-label sanity check
- Empty-universe rejection
- Configuration hash mismatch detection

Weak factors fail as research results; blocking controls fail the promotion gate.

## API

`GET /api/research/factor-discovery/staging/extended-latest` — latest extended staging report (read-only).

## Related docs

- [Phase 9B.1 staging validation](./quant-lab/factor-discovery-staging-validation.md)
- [Extended staging report](./FACTOR_MINING_EXTENDED_STAGING_REPORT.md)

> A large adjusted-price table is not sufficient for safe historical factor research. Date-specific, sourced, and versioned universe membership is required to prevent current-list and survivorship bias.
