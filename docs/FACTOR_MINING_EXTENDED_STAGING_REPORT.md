# Factor Mining Extended Staging Report

This file is populated after executing Phase 9B.2 against the local historical database.

Run:

```bash
cd backend && source .venv/bin/activate
export FACTOR_DISCOVERY_STAGING_ENABLED=true
export FACTOR_RESEARCH_DATA_PROVIDER=historical_store
export FACTOR_DISCOVERY_ENABLED=true
python scripts/run_factor_mining_extended_staging.py --sleeves penny,compounder --json
```

Latest artifact: `backend/data/factor_discovery/extended_staging/latest.json`

## Latest local run (Phase 9B.2)

| Metric | Value |
|--------|-------|
| Staging run ID | See `latest.json` |
| Final status | `READY_FOR_PROMOTION_REVIEW` |
| Matrix cells | 30 (2 sleeves × 3 walk-forward slices × 5 factors) |
| Cells succeeded | 30 / 30 |
| Preflight | ~3.4s, no blockers |
| Total runtime | ~93s |
| Snapshots reused | 27 |
| Reproducibility | 4/4 representative runs `EXACT_MATCH` |
| Weak factors (acceptance FAIL) | Expected for staging canary/candidates |
| Live config mutated | No |

Regime slices (SPY high/low vol, stress drawdown) were omitted when overlap with staging PIT universe was insufficient — only labeled regimes with ≥20 overlapping sessions are included.

| Section | Contents |
|---------|----------|
| `manifest` | Versioned staging baseline |
| `date_range` | Resolved supported overlap and regime slices |
| `matrix` | Sleeve × slice × factor cells |
| `negative_controls` | Leakage and sanity controls |
| `cell_results` | Per-cell diagnostics and acceptance |
| `reproducibility_results` | Representative repeat-run comparisons |
| `runtime` | Preflight, snapshot, and total durations |
| `promotion_readiness` | Final `READY_FOR_PROMOTION_REVIEW` or `NOT_READY_FOR_PROMOTION_REVIEW` |

## Result classification

- **Blockers** — promotion gate failures (preflight, leakage, reproducibility, sleeve coverage)
- **Warnings** — low symbol/date coverage on a slice
- **Weak factors** — acceptance `FAIL` on candidate factors (expected for negative controls and weak signals)
- **Infrastructure failures** — cell `status=failed`
- **Expected negative-control failures** — non-blocking controls that intentionally show no signal

See [FACTOR_MINING_EXTENDED_STAGING.md](./FACTOR_MINING_EXTENDED_STAGING.md) for workflow documentation.
