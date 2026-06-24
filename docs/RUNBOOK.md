# Runbook

Operational guide for local development and common issues.

## 1) Start services

### One command (recommended)

From project root:

```bash
./scripts/dev-up.sh
```

Stop:

```bash
./scripts/dev-down.sh
```

Logs: `storage/dev/backend.log`, `storage/dev/frontend.log`

### Manual

**Backend**

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 18731
```

Optional quant extras:

```bash
pip install -r requirements-quant.txt
```

**Production job worker** (when `JOB_QUEUE_BACKEND=db` or `redis`):

```bash
cd backend
python scripts/run_job_worker.py
```

PostgreSQL: see [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md).

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open: `http://127.0.0.1:18730`

---

## 2) Sanity checks

| Check     | How                                             |
| --------- | ----------------------------------------------- |
| API up    | `GET http://127.0.0.1:18731/health`             |
| Scan      | `/scan` → run one bucket                        |
| Workspace | Add ticker to watchlist → open Research         |
| Analyze   | Quant tab shows signal bars; Refresh works      |
| Portfolio | `/` — Today (decisions), Research (optimize/backtest/exposure/allocation), Activity (CSV, journal) |
| Library   | Save a scan or report, visible under `/library` |
| Journal   | Home → Journal panel (`/?journal=1#home-journal`) |

Investor guide for Analyze: [ANALYZE_PANEL.md](ANALYZE_PANEL.md)

Round 2 quant (recommendation loop, valuation, jobs): [MANUAL_INTEGRATION.md](MANUAL_INTEGRATION.md)

---

## 3.5 Round 2 quant jobs

After `SCORE_ENGINE_V2_ENABLED=true`, trigger or schedule:

| Job                      | Endpoint                                         |
| ------------------------ | ------------------------------------------------ |
| IC panel + deciles       | `POST /api/v2/jobs/ic-panel`                     |
| Forward labels           | `POST /api/v2/jobs/forward-labels`               |
| PIT fundamentals (FMP)   | `POST /api/v2/jobs/pit-fundamentals`             |
| Resolve outcomes         | `POST /api/v2/jobs/resolve-outcomes`             |
| Outcome weight feedback  | `POST /api/v2/jobs/outcome-weights`              |
| Daily bundle (scheduler) | `quant_daily_jobs` when `SCHEDULER_ENABLED=true` |

Ops metrics: `GET /api/v2/admin/round2-stats`

Factor research export:

```bash
cd backend && .venv/bin/python scripts/factor_research_export.py
```

---

## 3) Environment

Copy `.env.example` → `.env`.

Important for local dev:

| Variable            | Suggested local                   |
| ------------------- | --------------------------------- |
| `SCHEDULER_ENABLED` | `false` — less background load    |
| `OPENBB_ON_SCAN`    | `false` — faster bulk scans       |
| `OPENBB_ENABLED`    | `true` only when OpenBB installed |
| Quant flags         | keep `false` until deps installed |

Primary data roles default to **finnhub** for quotes and **FMP** for fundamentals (`PRIMARY_PRICE_SOURCE`, `PRIMARY_FUNDAMENTALS_SOURCE`). Set API keys for Finnhub, FMP, AV as needed.

**FMP 403 / blocked history:** if FMP returns HTTP 403 (common on free-tier keys), the backend trips a process-wide circuit breaker and falls back to **yfinance** for OHLC during scans and analyze. Install `yfinance` (`pip install yfinance`) — it is listed in `backend/requirements.txt`. Logs will show `FMP access denied (403) — disabling FMP for this process`. Restart the backend to retry FMP after fixing the key or tier.

**Analyze OHLC freshness:** `PriceService.get_history()` now checks the **last bar date**, not only row count. Stale SQLite history triggers a provider fetch, merge, and persist. `GET /analyze/{symbol}?refresh=true` bypasses the analysis cache **and** forces a price-history refresh. The response includes `price_history_last_date`, `price_history_is_stale`, `price_history_refreshed_at`, and `price_history_bar_count`.

**Scan default in UI:** bucket scans now default to `mode=fast` (15 deep-scored candidates). Use deep mode from the API (`POST /scan/{bucket}` with `"mode":"deep"`) when you want the full Stage B cap (`SCAN_STAGE_B_TOP_N`, default 50).

### Scan performance knobs

Ticker universes are built in three layers (`backend/data/universe.py`, `backend/data/listing_master.py`):

1. **Official listing master** — Nasdaq Trader `nasdaqlisted.txt` + `otherlisted.txt`, cached under `universe:listing_master` with revision `universe:listing_master_revision`.
2. **Curated discovery seeds** — thematic lists such as `PENNY_DISCOVERY_SEEDS` and `LARGE_CAP_SEEDS` (not proof of current listing or sub-$5 status).
3. **Runtime eligibility** — price, liquidity, and bucket rules (`check_bucket_eligibility`, screener modules).
4. **Stage A ranking** — inexpensive cross-sectional `pre_score` from bulk OHLC (+ cached fundamental quality for compounders). Top `SCAN_STAGE_B_TOP_N` advance to Stage B.

**Refresh:** listing master refreshes once daily via the scheduler daily pipeline and asynchronously on startup. Manual refresh: `POST /data/scheduler/refresh-listing-master` (optional `?force=true`). Inspect cache metadata: `GET /data/universe/listing-master`.

**Fallback:** if listing validation is unavailable, `get_universe()` returns normalized curated seeds minus `STALE_OR_DELISTED` and sector ETFs. If refresh fails but a prior snapshot exists, the last-known-good listing master is kept (long TTL).

**Aliases:** centralized in `TICKER_ALIASES` (e.g. `SQ` → `XYZ`). Class shares use dash form (`BRK-B`).

**In-process cache:** `get_universe()` uses an LRU keyed by listing revision — refreshing the listing master invalidates cached universes without restarting Python.

**Adding a thematic seed:** append symbols to the appropriate `_PENNY_*` group in `universe.py`; they are validated against the listing master at runtime. Multi-theme membership is tracked in `SYMBOL_THEMES`.

Set `UNIVERSE_SCAN_BATCH_SIZE=0` in `.env` to scan the full list instead of the first N alphabetically.

**Bulk scan fast path:** universe scans set `services.scan_context.set_bulk_scan(True)` for the job thread. While active, Stage B skips per-symbol reconcile, StockTwits/Finnhub sentiment, and OpenBB governance fetches. Single-symbol **Workspace → Analyze** keeps full depth. Set `OPENBB_ON_SCAN=false` as well for fastest scans.

**UI poll window:** the scan page polls until the backend job completes or fails — no client-side wall-clock cap. Transient status-fetch errors retry; after 20 consecutive failures the UI shows the error message. Use **Load last scan** if you navigated away mid-run.

**Trade hint column:** each scan row includes `metrics.recommendation`, `buy_pct`, and `wait_pct` — a research-only buy vs wait mix derived from score, sleeve, risk, data quality, and earnings flags. Hover the cell for a one-line reason. Cached scans without these fields are approximated client-side until re-scanned.

These were previously hard-coded inside `backend/services/scan_manager.py`. They are now configurable:

| Variable                          | Default                          | Effect                                                                                 |
| --------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------- |
| `UNIVERSE_SCAN_BATCH_SIZE`        | `100`                            | Cap Stage A symbols (`0` = full curated universe; recommended after expanding penny list). |
| `MAX_CANDIDATES_PER_BUCKET`       | `25`                             | Hard cap on rows returned per scan (UI `max_results` cannot exceed this).              |
| `SCAN_STAGE_B_TOP_N`              | `50`                             | Max candidates deep-scored per scan (`mode=deep`).                                     |
| `SCAN_STAGE_B_TOP_N_FAST`         | `15`                             | Candidate cap when `ScanOptions.mode="fast"` — used for low-latency exploratory scans. |
| `SCAN_PRICE_DOWNLOAD_MAX_SECONDS` | `45`                             | Hard cap (seconds) on the Stage A bulk OHLC provider fetch.                            |
| `SCAN_PENNY_STAGE_A_PERIOD`         | `6mo`                            | Penny Stage A bulk OHLC horizon.                                                       |
| `SCAN_PENNY_STAGE_B_PERIOD`         | `6mo`                            | Penny Stage B candidate build horizon.                                                   |
| `SCAN_COMPOUNDER_STAGE_A_PERIOD`    | `1y`                             | Compounder Stage A cheap universe filter horizon.                                      |
| `SCAN_COMPOUNDER_STAGE_B_PERIOD`    | `5y`                             | Compounder Stage B deep scoring horizon (feeds 5Y smooth growth).                      |
| `FUNDAMENTAL_SNAPSHOT_MAX_AGE_DAYS` | `1`                              | Reuse DB fundamental snapshots younger than this; stale triggers one reconcile refresh. |
| `SCAN_STAGE_B_TIME_BUDGET_SECONDS`| `0` (unlimited)                  | Stop Stage B after this many seconds; `0` = score all candidates. Partial results if capped. |
| `SCAN_RESULT_TTL_PENNY`           | inherits `SCAN_RESULT_TTL` (900) | TTL for `scan:latest:penny`.                                                           |
| `SCAN_RESULT_TTL_COMPOUNDER`      | `86400`                          | TTL for `scan:latest:compounder`; compounder data changes slowly.                      |

### Scan response shape additions

`GET /scan/{job_id}` and `GET /scan/latest/{bucket}` now return optional fields used by the UI:

- `timings`: `{stage_a_ms, stage_a_bulk_download_ms, stage_a_rank_ms, stage_a_bulk_symbols, stage_b_ms, stage_b_candidate_build_ms, stage_b_bulk_cache_hits, stage_b_provider_fallbacks, stage_b_history_reloads, stage_b_candidate_build_calls, stage_b_candidates, stage_b_mode, stage_a_eligible, stage_a_excluded}`
- `history_horizons`: `{stage_a_period, stage_b_period, bucket}` — OHLC windows used for the scan.
- `data_flow` (cached scan metadata): `{bulk_download_ms, bulk_symbols_returned, stage_a_rank_ms, stage_b_build_ms, bulk_cache_hits, provider_fallbacks, history_reload_count, fundamental_cache_hits, fundamental_refreshes, candidate_build_calls, per_symbol_sources[], per_symbol_diagnostics[]}`.
- `data_flow.per_symbol_diagnostics[]`: per-symbol `{price_history_period, price_history_bars, fundamental_snapshot_date, fundamental_source, reconciliation_quality, missing_fundamental_fields, confidence_penalty, ...}`.
- `stage_a_diagnostics` (cached scan metadata): `{eligible_count, excluded_count, advanced_count, candidates[], excluded[]}` where each candidate includes `pre_score`, percentile `features`, `rank`, `warnings`, and optional `data_quality`.
- `skipped_candidates` / `skipped_count` (cached scan metadata): structured Stage B skip records `{symbol, reason, detail?}` where `reason` is one of `missing_history`, `stale_history`, `provider_failure`, `invalid_price`, `missing_required_fundamentals`, `candidate_build_exception`, or `strict_filter_rejection`.
- `cache_age_seconds` (latest only): seconds since the result was written to the cache table.
- `last_attempt_failed_at` / `last_attempt_error` (latest only): set when the most recent scan attempt failed. The previously cached successful results are **not** clobbered — they remain visible alongside the failure marker so the UI can render "showing prior results; last attempt failed at …".

All new fields are nullable and backward-compatible — clients that ignore them keep working.

**Penny scan metrics (Stage B):** candidate `metrics` now separates raw liquidity from normalized scores:

| Field | Meaning |
|-------|---------|
| `relative_volume_ratio` / `volume_ratio` | Today vs prior 20 completed bars (current bar excluded from baseline), e.g. `3.2` → display as **3.2x** |
| `relative_volume_score` / `volume_signal_score` | Normalized 0–100 volume factor (3× baseline → 100) |
| `average_dollar_volume_20d` | Mean daily `$` volume over prior 20 bars (excludes today) |
| `atr_percent`, `gap_percent`, `spread_estimate_pct` | Raw volatility / gap / intraday spread proxies |
| `liquidity_warnings` | Non-fatal risk flags (unconfirmed volume spike, extreme gap, wide spread, etc.) |

Penny **hard filters** reject on price bounds, minimum share/dollar volume, min history, stale data quality, OTC/PINK, and **extreme** spread (`PENNY_MAX_SPREAD_PCT`, default 15%) — not on moderate spread or missing momentum signals.

| Env | Default | Role |
|-----|---------|------|
| `PENNY_MAX_SPREAD_PCT` | `15.0` | Hard filter — reject when `(high−low)/close` on latest bar exceeds this percent |

### Canonical scoring entry point

Every code path that needs a final score for a symbol should route through
`services.scoring_facade.score_symbol_canonical(...)`. Scan Stage B, Watchlist,
and Analyze all use it, so the same `CandidateContext` produces the same
numeric score regardless of entry point.

**Stage B scoring modes** (`SCAN_SCORING_MODE`):

| Mode | Production scorer | Legacy scorer | Use case |
|------|-------------------|---------------|----------|
| `legacy` | Legacy screener | Always | Rollback / baseline |
| `engine` | ScoringEngine | Never | Production rollout (recommended) |
| `parity_sample` | ScoringEngine | Deterministic sample | Staging comparison |

When `SCAN_SCORING_MODE` is unset, `USE_SCORING_ENGINE_IN_SCAN=true` maps to `engine`; otherwise `legacy`.

| Env | Default | Role |
|-----|---------|------|
| `SCAN_SCORING_MODE` | *(unset)* | `legacy` \| `engine` \| `parity_sample` |
| `SCAN_PARITY_SAMPLE_RATE` | `0.10` | Legacy comparison fraction in parity mode (hash of `scan_id:symbol`) |

Parity diagnostics include `scan_id`, `timestamp`, `scoring_version`, `factor_differences`, and score deltas. Scan timings add `stage_b_scoring_*_ms` and call counts — in `engine` mode legacy screener work is skipped (~50% less Stage B scoring vs the old always-run-both path).

**Final scan ranking** (Stage B output, after factor scoring):

Each candidate exposes three independent 0–100 pillars plus a weighted composite:

| Field | Meaning |
|-------|---------|
| `alpha_score` | Setup attractiveness from bucket factors |
| `confidence_score` | Data completeness, freshness, provider agreement, history, reconciliation |
| `tradability_score` | Liquidity, volume, volatility, spread proxy, gap risk |
| `ranking_score` | Weighted composite used for sort order (see env weights below) |

The scan results table shows **only `ranking_score`** when `confidence_score` and `tradability_score` are at the neutral placeholder (~50, meaning insufficient data to differentiate). Pillar chips appear only when a sub-score materially differs from 50.

`StockResult.score` mirrors final `ranking_score` after diversification and persistence. Scan metadata includes `ranking_diagnostics` with exclusion reasons (`excluded_by_sector_limit`, `excluded_by_correlation_limit`, `excluded_by_share_class`, `replaced_by_higher_confidence_candidate`, `retained_by_persistence_rule`, etc.).

| Env | Default | Role |
|-----|---------|------|
| `SCAN_RANK_ALPHA_WEIGHT_PENNY` | `0.65` | Alpha weight (penny bucket; medium/compounder have `_MEDIUM` / `_COMPOUNDER` variants) |
| `SCAN_RANK_CONFIDENCE_WEIGHT_PENNY` | `0.20` | Confidence weight |
| `SCAN_RANK_TRADABILITY_WEIGHT_PENNY` | `0.15` | Tradability weight |
| `SCAN_MAX_PER_SECTOR` | `3` | Max final results from one sector |
| `SCAN_MAX_PER_CORRELATION_CLUSTER` | `2` | Max final results from one return-correlation cluster |
| `SCAN_CORRELATION_CLUSTER_THRESHOLD` | `0.75` | Pairwise return correlation to merge clusters |
| `SCAN_PERSISTENCE_DELTA` | `3.0` | Minimum score gap before a newcomer displaces a prior-scan incumbent |
| `SCAN_MIN_RESULTS_AFTER_DIVERSIFICATION` | `3` | Target minimum breadth (sector cap may relax; share-class and correlation caps do not) |
| `SCAN_PENNY_LOW_CONFIDENCE_MAX` | `2` | Max low-confidence penny names in final list |
| `SCAN_PENNY_LOW_CONFIDENCE_THRESHOLD` | `45.0` | Confidence below this counts toward penny cap |

**Offline scan evaluation** (historical replay — does not change production rankings):

```bash
cd backend && python scripts/run_scan_evaluation.py \
  --bucket penny --start-date 2024-03-01 --end-date 2024-06-01 \
  --algorithm-version stage_a_v2 --max-universe 30 --output-dir data/scan_eval
```

See [SCAN_EVALUATION.md](SCAN_EVALUATION.md) for MacBook quick start, algorithm version labels, and output files.

### Auto-refresh slot reservation

`services.refresh_orchestrator.try_begin_auto_refresh()` is the only correct
way to start a stale-while-revalidate background refresh from a dashboard GET.
It atomically (under a single lock acquire) checks running-status, checks the
cooldown, reserves the slot, and stamps the cooldown — so concurrent dashboard
loads cannot double-fire the refresh. Manual refresh (`POST /home/refresh`)
still uses `start_home_refresh_async` and bypasses the cooldown when `force=true`.

---

## 4) Quant workflows (API / scripts)

See [PROJECT_INVENTORY.md](PROJECT_INVENTORY.md) for UI gaps.

1. **Offline alpha** → `POST /ml/alpha/ingest` → scan medium/compounder
2. **Portfolio optimize** → `POST /portfolio/optimize` with symbol list
3. **Portfolio policy backtest** → `POST /portfolio/policy-backtest` (`institutional: false` for fast sim; `true` or `POST /api/v2/backtest/portfolio` for costs/slippage)
4. **Portfolio factor exposure** → `POST /portfolio/factor-exposure`
5. **Allocation** → `GET /allocation/recommendation/{bucket}?symbols=AAPL,MSFT`
6. **LEAN** → `POST /lean/export` → external LEAN → `POST /lean/import-summary`
7. **Factor check** → `cd backend && python scripts/factor_validation.py --symbols AAPL,MSFT --factor momentum_20d`

Enable flags one at a time per [QUANT_STACK.md](QUANT_STACK.md).

---

## 5) Troubleshooting

### Backend won’t start

Recreate venv if the project path moved:

```bash
cd backend && rm -rf .venv && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Frontend dev loop / high CPU

```bash
./scripts/dev-down.sh
rm -rf frontend/.next
cd frontend && npm run dev
```

Or production mode: `npm run build && npm run start`

### Analyze slow or 504

- Bucket-fit loads three screeners — wait for sidebar tiles
- Use **Refresh** sparingly on large names
- Check `ANALYZE_ROUTE_TIMEOUT_SECONDS` in config

### “Analysis unavailable” while `/health` works

The workspace shows this when the **browser** reports a network failure (`Failed to fetch`) — not only when the API process is down.

1. Open DevTools → **Network** → find the failed `/analyze/{symbol}` request.
2. **(failed)** with no status, or a CORS console error → your UI origin is not in `ALLOWED_ORIGINS`. Dev defaults allow `http://localhost:18730` and `http://127.0.0.1:18730`; custom `.env` overrides replace those defaults.
3. **(canceled)** → request aborted on refresh/navigation; retry or wait for the watchlist to finish loading first.
4. **504 / pending then failed** → analyze timed out or the connection dropped mid-request; retry or raise `ANALYZE_ROUTE_TIMEOUT_SECONDS`.
5. **500 on `/analyze/...?refresh=1`** → backend bug during fresh analyze (e.g. numpy scalars in the JSON snapshot). Check the API response `message` field or backend logs; cached requests without `refresh=1` may still return 200.

Quick check from the same machine:

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18731/health
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18731/analyze/CLOV
```

Both should return `200`. If curl succeeds but the browser fails, suspect CORS or a non-default UI URL (LAN IP, forwarded port, `localhost` vs `127.0.0.1` mismatch in `ALLOWED_ORIGINS`).

### Walk-forward times out in Quant Lab

Walk-forward scores many symbols across each rebalance date — it is intentionally slow.

- UI client timeout: **10 minutes** (`WALK_FORWARD_REQUEST_TIMEOUT_MS`)
- Backend route timeout: **10 minutes** (`WALK_FORWARD_ROUTE_TIMEOUT_SECONDS`, default `600`)
- UI runs use `persist_snapshots: false` (summary still saved to `backtest_runs`)
- If it still times out: shorten the date range, select one horizon (20d only), or set `WALK_FORWARD_ROUTE_TIMEOUT_SECONDS=900` in `.env`

### Quant Lab research API (Phase 2)

Requires `QUANT_LAB_RESEARCH_API_ENABLED=true` (default). Returns **503** when disabled.

```bash
# List indexed runs (backfills from existing stores on first call)
curl -s "http://127.0.0.1:18731/api/v2/research/runs?limit=10" | jq .

# Create idea
curl -s -X POST http://127.0.0.1:18731/api/v2/research/ideas \
  -H 'Content-Type: application/json' \
  -d '{"title":"Test IC drift","hypothesis":"Momentum IC fading","source_type":"factor_deterioration","sleeve":"penny"}' | jq .

# Evaluate major evidence gate for a persisted walk-forward run
curl -s -X POST "http://127.0.0.1:18731/api/v2/research/gate/evaluate?run_id=YOUR_RUN_ID" | jq .
```

`RESEARCH_MAX_ORDINARY_MODIFIER=0` (default) keeps supporting/contradicting evidence **display-only** — no score mutation.


Seed deterministic evidence (IC, walk-forward, predictions, pairs, jobs):

```bash
cd backend
python scripts/seed_quant_lab_demo.py --sleeve medium
DATABASE_URL=sqlite:///$(pwd)/../storage/dev/quant_lab_demo.db \
  python -m uvicorn main:app --port 18731
```

Automated tests:

```bash
cd backend && pytest -q tests/test_quant_lab_contracts.py tests/test_quant_lab_integration.py
cd frontend && npm test -- --run src/components/quant-lab
cd frontend && npx playwright install chromium && npm run test:e2e
```

See [QUANT_LAB_FUNCTIONAL_TEST_REPORT.md](QUANT_LAB_FUNCTIONAL_TEST_REPORT.md) and [QUANT_LAB_MANUAL_TEST_CHECKLIST.md](QUANT_LAB_MANUAL_TEST_CHECKLIST.md).

### `engine=vectorbt` fails

- `VBT_ENABLED=true`
- `pip install -r requirements-quant.txt`

### Optimizer fallback

With `PYPFOPT_ENABLED=false` or package missing, a fallback optimizer runs by design.

### OpenBB

- Install: `pip install -r requirements-openbb.txt`
- Verify: `python backend/scripts/verify_openbb.py`
- See [OPENBB.md](OPENBB.md)

---

## 8) Public demo deployment (Vercel + Render)

Full steps: **[DEPLOYMENT.md](DEPLOYMENT.md)**.

Key flags on Render:

| Variable | Demo value |
|----------|------------|
| `DEMO_MODE` | `true` |
| `DEMO_SEED_DATA` | `true` |
| `ALLOWED_ORIGINS` | Your Vercel URL (exact) |
| `DATABASE_URL` | `sqlite:///./data/stockpick_demo.db` |

Health check: `GET /health` (no external API calls). Render health path: `/health`.

Vercel: `NEXT_PUBLIC_API_URL=<Render URL>`.

---

## 9) Data locations

- SQLite / cache: `backend/data_store/`
- LEAN artifacts: `backend/data_store/lean_exports/`

---

## 10) Safe upgrade sequence (quant)

1. Flags off
2. Install `requirements-quant.txt`
3. Smoke test health + one backtest
4. Enable one flag at a time
5. Validate API + UI paths that use the feature
