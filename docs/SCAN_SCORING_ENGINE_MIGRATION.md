# Scan ScoringEngine migration

Guide for enabling `USE_SCORING_ENGINE_IN_SCAN=true` in local/staging without removing legacy screener scoring.

## Background

Scan Stage B scores candidates after universe filtering. Two paths exist:

| Flag | Stage B scorer | Rankings use |
|------|----------------|--------------|
| `USE_SCORING_ENGINE_IN_SCAN=false` (default) | Legacy `screeners/*.py` → `screener.score()` | Legacy path |
| `USE_SCORING_ENGINE_IN_SCAN=true` | `ScoringEngine` (same pipeline as `/api/v2/score`) | Engine path |

When the engine path is active, **both** legacy and engine scores are computed for every symbol. Legacy scoring is **not deleted** — it is used for parity comparison only.

## Enable in local / staging

1. Copy env template if needed: `cp .env.example .env`
2. **Recommended (does not edit `.env`):**

```bash
source scripts/staging-scan-engine.env
./scripts/run-staging-scan-parity.sh --cached   # historical_store parity
./scripts/run-staging-scan-parity.sh --full     # live ScanManager
```

3. Or set in `.env` manually:

```bash
APP_ENV=staging
USE_SCORING_ENGINE_IN_SCAN=true
PERSIST_SCORE_ATTRIBUTION=true
SCORE_ENGINE_V2_ENABLED=true
```

4. Restart backend.
5. Run a scan from the UI (`/scan?bucket=medium`) or API:

```bash
curl -X POST http://localhost:8000/scan/medium
# → { "job_id": "..." }

curl http://localhost:8000/scan/{job_id}
# → results + parity_summary when completed
```

Production deployments should keep `USE_SCORING_ENGINE_IN_SCAN=false` until parity is acceptable.

## Parity output

### Per symbol (Stage B)

Each scored symbol emits a structured record when the engine path is active:

| Field | Description |
|-------|-------------|
| `symbol` | Ticker |
| `sleeve` | `penny`, `medium`, or `compounder` |
| `legacy_score` | Legacy screener score after DQ + OpenBB adjustments |
| `engine_score` | `ScoringEngine.final_score` |
| `parity_delta` | `abs(legacy_score - engine_score)` |
| `scoring_engine_used` | Always `true` on engine path |
| `top_factor_contributions` | Top 5 engine factors by \|contribution\| |
| `legacy_recommendation_bucket` | Score tier: `strong_buy`, `buy`, `watch`, `hold`, `avoid` |
| `engine_recommendation_bucket` | Same tiers for engine score |
| `recommendation_bucket_differs` | Whether tiers differ |

**Where to find it:**

- Backend logs: `Scan score parity SYMBOL/sleeve legacy=… engine=… delta=…`
- Per-result metrics: `StockResult.metrics.parity` (full record)
- Scan summary records list: `parity_summary.records[]`

### Scan-level summary

After Stage B completes:

| Field | Description |
|-------|-------------|
| `average_delta` | Mean parity delta across scored symbols |
| `max_delta` | Largest parity delta |
| `symbols_delta_gt_10` | Count with delta > 10 |
| `recommendation_bucket_diffs` | Count where legacy vs engine tier differs |
| `symbol_count` | Symbols with parity records |

**Where to find it:**

- Backend logs: `Scan parity summary bucket=… avg_delta=… max_delta=… delta_gt_10=… recommendation_bucket_diffs=…`
- `GET /scan/{job_id}` → `parity_summary`
- `GET /scan/latest/{bucket}` → `parity_summary` (cached with latest scan)
- Scan job `message`: `Found N candidates (ScoringEngine; avg parity delta X.X)`

## Interpreting parity

- **Small average delta (< 5)** — engine path is close to legacy; safe to consider production flip.
- **Large deltas on specific symbols** — inspect `top_factor_contributions` and regime/DQ/OpenBB attribution in `metrics.scoring_engine_attribution`.
- **Bucket diffs** — symbols crossing score tiers (e.g. `buy` → `watch`) may change scan ranking order even when average delta is modest.

Recommendation tiers use the same thresholds as the v2 recommendation engine (`>=80 strong_buy`, `>=65 buy`, `>=50 watch`, `>=35 hold`, else `avoid`).

## Code map

| Module | Role |
|--------|------|
| `services/scan_scoring.py` | Routes Stage B; builds parity when flag on |
| `services/scan_parity.py` | Structured records + scan summary aggregation |
| `services/scan_manager.py` | Collects records; logs + saves metadata |
| `engines/scoring/engine.py` | ScoringEngine pipeline |
| `screeners/*.py` | Legacy scoring (still required) |

## Tests

```bash
cd backend
pytest tests/test_scan_parity.py tests/test_scan_scoring_engine_parity.py -v
```

Tests cover penny, medium, and compounder buckets for legacy shape preservation, engine path output, and summary aggregation.

## Rollback

Set `USE_SCORING_ENGINE_IN_SCAN=false` and restart. No data migration required; cached scans retain `parity_summary` only when they were run with the engine path.
