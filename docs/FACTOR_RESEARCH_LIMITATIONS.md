# Factor Research — Known Limitations

PickerQuant factor discovery is **research-grade**, not institutional production data. Do not claim hedge-fund-grade coverage without evidence.

## Data

| Limitation | Impact |
|------------|--------|
| Staging universe ~5–9 symbol overlap (2026 local DB) | IC/spread metrics noisy; not representative of full US market |
| Price-only staging panel (adjusted_close, volume) | Sector/mcap concentration gates often N/A |
| SPY regime slices omitted when overlap &lt; 20 sessions | Stress/vol regimes may be untested on current import |
| Legacy `medium` PIT rows outside staging bucket | Resolved by preferring `staging:%` bucket in date resolution |
| Fundamentals PIT not in staging provider | Compounder research limited to available fields |
| Survivorship controls audit-only | Delisted symbols depend on import quality |

## Statistical

| Limitation | Impact |
|------------|--------|
| Weak staging candidates (acceptance FAIL) | Expected for infrastructure validation runs |
| Multiple-testing service present but not auto-applied in staging matrix | Manual review required |
| Shuffled-label control non-blocking on some panels | Listed as expected control limitation |
| No automated redundancy matrix in staging | Pairwise IC dedup deferred |

## Governance

| Limitation | Impact |
|------------|--------|
| `approved_for_manual_integration` ≠ live activation | Separate ChangeProposal + integration step required |
| No `scan_adapter.py` | Discovery factors cannot enter live scoring via Quant Lab |
| Shadow v1 proxy signal | Full DSL shadow on scan universe not yet wired |
| Sleeve separation at metadata level | Same PIT universe for penny/compounder until sleeve-filtered PIT exists |

## Operational

| Limitation | Impact |
|------------|--------|
| Real acceptance warns when `FACTOR_DISCOVERY_STAGING_ENABLED=false` | Fresh preflight requires env flags |
| Frontend ESLint: 8 pre-existing errors (ResultsTab hooks) | Non-blocking; deferred cleanup |
| No factor drift monitor | Post-release IC decay tracking manual |

## Label semantics (not synonyms)

| Label | Meaning |
|-------|---------|
| Statistically interesting | Non-zero IC in sample; may fail acceptance |
| Economically meaningful | Spread survives cost assumptions (when reported) |
| Robust enough for shadow | Passes blocking promotion gates + human review |
| Approved for manual integration | Governance approval only; not live |
