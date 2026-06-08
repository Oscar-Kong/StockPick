# Project Inventory & Cleanup Notes

Last reviewed against the repo layout, UI routes, and API surface. Use this with the [documentation index](../README.md#documentation-index).

---

## Product map (what users actually open)

| Route | What it is |
|-------|------------|
| `/` | Home hub — ticker jump, links to Scan / Workspace / Library, saved counts, resume links |
| `/scan` | Scan hub — penny, medium, compounder tabs |
| `/workspace` | Watchlist rail + **Research** (analyze), **Compare**, **Trade journal** |
| `/library` | Saved scans, reports, analyze snapshots |
| `/portfolio` | Basket weight optimize + rebalance policy backtest |
| `/trader-intel` | Trader style profiles and presets |

**Redirects (bookmarks still work):**

| Old route | Goes to |
|-----------|---------|
| `/penny`, `/medium`, `/compounder` | `/scan?bucket=…` |
| `/watchlist`, `/analyze` | `/workspace` (analyze keeps `?symbol=`) |
| `/trades` | `/workspace?tab=journal` |
| `/reports` | `/library?tab=reports` |
| `/scans` | `/library?tab=scans` |

---

## Features with API but no dedicated UI

These work via API / scripts / future UI; documented so nothing is “missing” silently.

| Capability | API / script | UI today |
|------------|--------------|----------|
| Portfolio optimize | `POST /portfolio/optimize` | `/portfolio` |
| Portfolio policy backtest | `POST /portfolio/policy-backtest` | `/portfolio` |
| Allocation recommendation | `GET /allocation/recommendation/{bucket}` | None |
| LEAN export / import summary | `/lean/export`, `/lean/import-summary` | None |
| Alpha ingest | `POST /ml/alpha/ingest` | None (feeds screeners when `QLIB_ENABLED`) |
| Factor validation | `backend/scripts/factor_validation.py` | CLI only |
| Scheduler | `/data/scheduler/*` | None (background when `SCHEDULER_ENABLED`) |
| OpenBB risk snapshot | `GET /data/openbb/risk/{symbol}` | Indirect via analyze alerts/metrics |

---

## Removed or unused in repo (cleanup)

| Item | Status | Action taken / recommendation |
|------|--------|------------------------------|
| `WatchlistMatrix.tsx` | **Unused** — replaced by `WatchlistRail` | **Deleted** |
| `@tanstack/react-query` | Was unused — no imports in app | **Removed** from `frontend/package.json` |
| `frontend/README.md` | Default create-next-app boilerplate | Replaced with pointer to root README |
| `docs/ANALYZE_PANEL.md` | Was missing from `docs/` | **Restored** (business guide) |

---

## Intentionally kept (not useless)

| Item | Why keep |
|------|----------|
| Redirect pages (`/penny`, `/analyze`, …) | Old links and docs still work |
| `GET /analyze/watchlist` | Powers Workspace watchlist rail + alerts |
| Quant flags default `false` | Safe local dev; enable per [RUNBOOK](RUNBOOK.md) |
| `backend/scripts/*` | Ops / validation, not UI |

---

## Data sources (align expectations)

Configured in `.env` (see `.env.example`):

- **Primary price / fundamentals:** `akshare` by default (not only FMP/Finnhub)
- **News:** Finnhub (+ optional NewsAPI)
- **Macro:** FRED (+ optional OpenBB)
- **Reconcile:** multi-vendor including FMP, AV, Finnhub, akshare, optional OpenBB

README and ARCHITECTURE mention all of the above.

---

## Editor indexing

`.cursorignore` at repo root excludes `.venv`, `.next`, `node_modules`, and dev logs.

## Suggested next cleanups (optional)

1. **Allocation** and **LEAN** UI pages (APIs exist).
2. **Alpha ingest** upload UI (today: `POST /ml/alpha/ingest` via curl).
