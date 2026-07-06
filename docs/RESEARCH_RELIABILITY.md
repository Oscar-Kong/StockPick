# Research Reliability Audit

Phase 11 statistical and methodological controls for Quant Lab factor research.

## Controls in place

| Control | Implementation |
|---------|------------------|
| Point-in-time universe | `universe_pit`, membership audits, preflight |
| Forward labels separated | Validation engine; leakage audit + negative controls |
| Sealed test reservations | `sealed_test_service.py` — metrics hidden until opened |
| Acceptance gate per run | `engines/factor/discovery/acceptance.py` |
| Staging negative controls | `negative_controls.py` — shuffle, future mutation, empty universe |
| Reproducibility hashing | `result_hashing.py`, `reproduce.py`, extended staging repro checks |
| Multiple-testing awareness | `multiple_testing_service.py` (research context) |
| Attempt ledger | `FactorDiscoveryAttempt`, mining evaluations |
| Promotion gates (17) | `gate_policy_v1.json` — blocking failures visible |
| Evidence bundles | Immutable `fpev_*.json` with hash verification |

## Risks and mitigations

| Risk | Mitigation | Residual |
|------|------------|----------|
| False discovery | Acceptance thresholds; weak factors flagged not promoted | Small staging universe inflates significance |
| Selection bias | Walk-forward slices; extended staging matrix | Regime slices may be omitted |
| Repeated tuning | Sealed test + separate validation periods | Same panel reused across matrix cells |
| Regime dependence | SPY vol/stress slices when data allows | Often N/A on current import |
| Factor correlation | Redundancy in validation artifacts | No auto portfolio dedup |
| Cost / turnover | Reported when artifact includes metrics | Often N/A in staging panel |
| Concentration | Robustness fields when sector/mcap available | N/A on price-only panel |

## Review labels

Use distinct meanings in UI and reports:

1. **Statistically interesting** — metric present; may fail acceptance
2. **Economically meaningful** — spread/cost analysis when available
3. **Robust enough for shadow** — blocking gates pass; human promoted to shadow
4. **Approved for manual integration** — governance terminal state; integration is external

## Audit commands

```bash
python backend/scripts/factor_discovery_staging_preflight.py --allow-test
python backend/scripts/run_factor_mining_extended_staging.py --dry-run
python backend/scripts/run_factor_research_acceptance.py --mode fixture
```

See [FACTOR_RESEARCH_LIMITATIONS.md](./FACTOR_RESEARCH_LIMITATIONS.md).
