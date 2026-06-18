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
3. **Runtime eligibility** — price, liquidity, and bucket rules in the scanner (`filter_universe_by_price`, screener modules).

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
| `SCAN_STAGE_B_TIME_BUDGET_SECONDS`| `0` (unlimited)                  | Stop Stage B after this many seconds; `0` = score all candidates. Partial results if capped. |
| `SCAN_RESULT_TTL_PENNY`           | inherits `SCAN_RESULT_TTL` (900) | TTL for `scan:latest:penny`.                                                           |
| `SCAN_RESULT_TTL_COMPOUNDER`      | `86400`                          | TTL for `scan:latest:compounder`; compounder data changes slowly.                      |

### Scan response shape additions

`GET /scan/{job_id}` and `GET /scan/latest/{bucket}` now return optional fields used by the UI:

- `timings`: `{stage_a_ms, stage_b_ms, total_ms, stage_b_candidates, stage_b_mode}`
- `cache_age_seconds` (latest only): seconds since the result was written to the cache table.
- `last_attempt_failed_at` / `last_attempt_error` (latest only): set when the most recent scan attempt failed. The previously cached successful results are **not** clobbered — they remain visible alongside the failure marker so the UI can render "showing prior results; last attempt failed at …".

All new fields are nullable and backward-compatible — clients that ignore them keep working.

### Canonical scoring entry point

Every code path that needs a final score for a symbol should route through
`services.scoring_facade.score_symbol_canonical(...)`. Scan Stage B, Watchlist,
and Analyze all use it, so the same `CandidateContext` produces the same
numeric score regardless of entry point. When `USE_SCORING_ENGINE_IN_SCAN`
flips, both Scan and Watchlist switch to the ScoringEngine in lockstep — no
more "same symbol, two scores" drift.

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
