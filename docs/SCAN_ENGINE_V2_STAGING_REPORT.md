# ScoringEngine v2 scan path — staging rollout report

**Generated:** 2026-06-08  
**Production default unchanged:** `USE_SCORING_ENGINE_IN_SCAN=false` in `.env` / `.env.example`  
**Legacy screener:** retained for parity and fallback

Related: [SCAN_SCORING_ENGINE_MIGRATION.md](./SCAN_SCORING_ENGINE_MIGRATION.md), [POST_D9EA94C_FIX_VERIFICATION.md](./POST_D9EA94C_FIX_VERIFICATION.md)

---

## Staging profile (no `.env` edit required)

Use the dedicated env file and wrapper script — flags apply **only to that process**:

```bash
# From project root
set -a && source scripts/staging-scan-engine.env && set +a

# Cached parity (historical_store, no live API — recommended for CI/local)
./scripts/run-staging-scan-parity.sh --cached

# Full ScanManager path (live providers; slower; may hit fallback on API errors)
./scripts/run-staging-scan-parity.sh --full
```

**`scripts/staging-scan-engine.env`:**

| Variable | Staging value |
|----------|----------------|
| `APP_ENV` | `staging` |
| `USE_SCORING_ENGINE_IN_SCAN` | `true` |
| `SCORE_ENGINE_V2_ENABLED` | `true` |
| `PERSIST_SCORE_ATTRIBUTION` | `true` |
| `OPENBB_ON_SCAN` | `false` |

Optional tuning:

```bash
UNIVERSE_SCAN_BATCH_SIZE=40          # cap Stage A universe
STAGING_CACHED_MAX_SYMBOLS=12        # per-bucket Stage B cap (cached mode)
STAGING_SCAN_MAX_RESULTS=25          # full mode max ranked results
```

**UI validation:** restart backend with staging env, run scan from `/scan`, confirm `ScanScoreMeta` shows **ScoringEngine v2** badge and parity chip when `parity_summary` is present (`BucketPage` / `ScanScoreMeta.tsx`).

**Rollback:** unset env or `USE_SCORING_ENGINE_IN_SCAN=false`; restart backend. No migration.

---

## Runs executed

### A. Full ScanManager (`--full`, 2026-06-08)

Command: `UNIVERSE_SCAN_BATCH_SIZE=40 ./scripts/run-staging-scan-parity.sh --full`

| Bucket | Scan completed | Stage B parity | Results | Notes |
|--------|----------------|----------------|---------|-------|
| penny | Yes | **No** | 8 | 100% `provider_limited_partial_data` fallback |
| medium | Yes | **No** | 10 | Same — strict path never reached Stage B engine |
| compounder | Yes | **No** | 8 | Same |

**Root cause:** AkShare connection resets + FMP 403 on this machine during the run. With no symbols passing hard filters + Stage B, scan_manager emitted **partial-data fallback** candidates only. Fallback rows bypass `score_stage_b_candidate` → **no `parity_summary`**, no engine metadata in cache.

**UI (full run):** `scoring_engine_used` / `parity_summary` absent on cached latest scans → **no ScoringEngine v2 badge**, no parity chip.

### B. Cached Stage B parity (`--cached`, 2026-06-08)

Command: `STAGING_CACHED_MAX_SYMBOLS=12 ./scripts/run-staging-scan-parity.sh --cached`

Uses `historical_store` OHLC + real `score_stage_b_candidate` with `USE_SCORING_ENGINE_IN_SCAN=true`. Raw JSON: `storage/staging/scan_engine_parity_report.json`.

| Bucket | Status | Stage B candidates | Avg Δ | Max Δ | Rec bucket diffs | UI badge (expected) | Parity chip |
|--------|--------|-------------------|-------|-------|------------------|---------------------|-------------|
| **penny** | completed | **12** | **0.02** | **0.05** | **0** | Yes | Yes |
| **medium** | no_parity_data | **0** | — | — | — | No | No |
| **compounder** | completed | **7** | **0.02** | **0.04** | **0** | Yes | Yes |

**Medium bucket:** zero symbols passed `MediumScreener.hard_filter` on cached history (trend ≥ 55 or breakout ≥ 70 gate). Quality filters passed for names like AAPL/CSCO, but hard filter rejected all. Re-run medium with `--full` when providers are healthy, or temporarily lower scan filters in UI for staging only.

---

## Top 5 parity deltas (cached run)

### Penny (max Δ = 0.05)

| Symbol | Legacy | Engine | Δ | Legacy tier | Engine tier |
|--------|--------|--------|---|-------------|-------------|
| OPEN | 49.0 | 49.0 | 0.05 | hold | hold |
| PACB | 67.8 | 67.8 | 0.05 | buy | buy |
| BLNK | 55.3 | 55.3 | 0.04 | watch | watch |
| CGC | 66.3 | 66.3 | 0.03 | buy | buy |
| EVGO | 66.8 | 66.8 | 0.03 | buy | buy |

**Dominant factors (penny):** `penny_momentum_5d`, `penny_volatility_fit`, `penny_rsi_fit`, `penny_social_buzz`.

### Compounder (max Δ = 0.04)

| Symbol | Legacy | Engine | Δ | Legacy tier | Engine tier |
|--------|--------|--------|---|-------------|-------------|
| AAPL | 65.8 | 65.8 | 0.04 | buy | buy |
| GOOGL | 65.8 | 65.8 | 0.04 | buy | buy |
| ADP | 45.2 | 45.2 | 0.03 | hold | hold |
| AMGN | 61.9 | 61.9 | 0.01 | watch | watch |
| COST | 49.2 | 49.2 | 0.01 | hold | hold |

**Dominant factors (compounder):** `compounder_smooth_growth`, `compounder_rev_eps`, `compounder_roic_margins`, `compounder_moat`.

---

## Factor / delta interpretation

| Finding | Implication |
|---------|-------------|
| Average Δ **0.02**, max Δ **≤ 0.05** on penny & compounder | Engine path is **closely aligned** with legacy screener for scored symbols (well below alert threshold 10). |
| **0** recommendation bucket diffs | No symbol changed tier (`strong_buy` / `buy` / `watch` / `hold` / `avoid`). |
| **0** symbols with Δ > 10 | No high-divergence outliers in this sample. |
| Top factors match sleeve factor IDs in v3 | Deltas are rounding/post-pipeline noise, not conflicting factor logic. |

**When deltas are large (future runs):** inspect per-symbol `top_factor_contributions` in `parity_summary.records[]`, plus `metrics.scoring_engine_attribution` (regime, DQ, OpenBB) in logs. Momentum and social factors on penny, growth/ROIC on compounder, are the usual drivers of rank changes.

---

## Bugfix during staging (supporting)

`backend/data/quality_filters.py` was missing `OTC_SUFFIXES`, `OTC_EXCHANGE_KEYWORDS`, and `Bucket` import — caused `NameError` during Stage B on medium/compounder. **Fixed** (production default unchanged; legacy path unaffected).

---

## Verification commands (pre-rollout gate)

| Command | Result (2026-06-08) |
|---------|---------------------|
| `python -m pytest tests/test_scan_manager_integration.py tests/test_scan_parity.py tests/test_scan_scoring_engine_parity.py -q` | **PASS** — 12 tests |
| `npm test` | **PASS** — 10/10 |
| `npm run build` | **PASS** |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS** — 0 errors, 4 warnings |

---

## Rollout recommendation

| Step | Action |
|------|--------|
| 1 | Keep **`USE_SCORING_ENGINE_IN_SCAN=false`** in committed `.env` / production |
| 2 | On a machine with **healthy AkShare/FMP**, run `./scripts/run-staging-scan-parity.sh --full` for all three buckets |
| 3 | Confirm UI: **ScoringEngine v2** badge + parity chip on `/scan` after full engine scan |
| 4 | If full-run avg Δ stays **< 5** and bucket diffs are low → candidate for production flip |
| 5 | If medium still empty → review medium hard_filter strictness or provider-enriched trend/breakout inputs |

**Current verdict:** Cached parity shows **safe alignment** for penny and compounder. **Full end-to-end scan parity is blocked on this environment by data providers**; medium Stage B not exercised in cached sample due to hard_filter. Staging infrastructure (env profile, script, UI surfacing, tests) is **ready**; repeat `--full` when APIs are stable before production enable.

---

## Artifacts

| Path | Description |
|------|-------------|
| `scripts/staging-scan-engine.env` | Staging env profile |
| `scripts/run-staging-scan-parity.sh` | Wrapper (`--cached` / `--full`) |
| `backend/scripts/run_staging_scan_parity.py` | Parity report generator |
| `storage/staging/scan_engine_parity_report.json` | Latest cached parity JSON |
| `storage/staging/scan_engine_parity_run.log` | Full-mode attempt log (provider errors) |
