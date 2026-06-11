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
| Compare   | Workspace → Compare tab, 2+ symbols             |
| Portfolio | `/portfolio` — optimize weights on 2+ symbols   |
| Library   | Save a scan or report, visible under `/library` |
| Journal   | Workspace → Journal tab                         |

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

Primary data roles default to **akshare** for price/fundamentals; set API keys for Finnhub, FMP, AV as needed.

### Scan performance knobs

These were previously hard-coded inside `backend/services/scan_manager.py`. They are now configurable:

| Variable                          | Default                          | Effect                                                                                 |
| --------------------------------- | -------------------------------- | -------------------------------------------------------------------------------------- |
| `SCAN_STAGE_B_TOP_N`              | `50`                             | Max candidates deep-scored per scan (`mode=deep`).                                     |
| `SCAN_STAGE_B_TOP_N_FAST`         | `15`                             | Candidate cap when `ScanOptions.mode="fast"` — used for low-latency exploratory scans. |
| `SCAN_PRICE_DOWNLOAD_MAX_SECONDS` | `45`                             | Hard cap (seconds) on the Stage A bulk OHLC provider fetch.                            |
| `SCAN_RESULT_TTL_PENNY`           | inherits `SCAN_RESULT_TTL` (900) | TTL for `scan:latest:penny`.                                                           |
| `SCAN_RESULT_TTL_COMPOUNDER`      | `86400`                          | TTL for `scan:latest:compounder`; compounder data changes slowly.                      |

### Scan response shape additions

`GET /scan/{job_id}` and `GET /scan/latest/{bucket}` now return optional fields used by the UI:

- `timings`: `{stage_a_ms, stage_b_ms, total_ms, stage_b_candidates, stage_b_mode}`
- `cache_age_seconds` (latest only): seconds since the result was written to the cache table.
- `last_attempt_failed_at` / `last_attempt_error` (latest only): set when the most recent scan attempt failed. The previously cached successful results are **not** clobbered — they remain visible alongside the failure marker so the UI can render "showing prior results; last attempt failed at …".

All new fields are nullable and backward-compatible — clients that ignore them keep working.

---

## 4) Quant workflows (API / scripts)

See [PROJECT_INVENTORY.md](PROJECT_INVENTORY.md) for UI gaps.

1. **Offline alpha** → `POST /ml/alpha/ingest` → scan medium/compounder
2. **Portfolio optimize** → `POST /portfolio/optimize` with symbol list
3. **LEAN** → `POST /lean/export` → external LEAN → `POST /lean/import-summary`
4. **Factor check** → `cd backend && python scripts/factor_validation.py --symbols AAPL,MSFT --factor momentum_20d`

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

## 6) Data locations

- SQLite / cache: `backend/data_store/`
- LEAN artifacts: `backend/data_store/lean_exports/`

---

## 7) Safe upgrade sequence (quant)

1. Flags off
2. Install `requirements-quant.txt`
3. Smoke test health + one backtest
4. Enable one flag at a time
5. Validate API + UI paths that use the feature
