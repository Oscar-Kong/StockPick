# Project Inventory & Cleanup Notes

Last reviewed against the repo layout, UI routes, and API surface. Use this with the [documentation index](../README.md#documentation-index).

---

## Product map (what users actually open)

| Route | What it is |
|-------|------------|
| `/` | Home — daily decision cockpit (portfolio summary strip, action queue, holdings); compact header + collapsible CSV import |
| `/scan` | Scan hub — compact command bar, inline status, dense results table; **Held** badge when ticker is in Home portfolio |
| `/workspace` | Full-width research terminal — watchlist rail + grouped analyze tabs, symbol nav, mobile Insights sheet |
| `/library` | Saved scans, reports, analyze snapshots — split list/detail layout |
| `/portfolio` | Basket optimize + policy backtest — expanded ~1520px layout |
| `/quant-lab` | Factor research tabs first; evidence/scan relationship in collapsible panels below |
| `/settings` | Two-column settings — language, quant health, API integrations |
| `/trader-intel` | Trader style profiles and presets |

**Redirects (bookmarks still work):**

| Old route | Goes to |
|-----------|---------|
| `/penny`, `/medium`, `/compounder` | `/scan?bucket=…` |
| `/watchlist`, `/analyze` | `/workspace` (analyze keeps `?symbol=`) |
| `/trades` | `/?journal=1#home-journal` (compact journal on Home) |
| `/reports` | `/library?tab=reports` |
| `/scans` | `/library?tab=scans` |

---

## Robinhood CSV import (backend)

Simple three-step flow in `portfolio_snapshot_service.import_robinhood_csv`:

1. **Parse & store** — `csv_importer.parse_robinhood_csv` → upsert all rows into `trade_history` ledger
2. **Verify journal** — `journal_verifier.verify_journal_trades_against_ledger` checks manual Home journal trades against the new CSV (warnings on mismatch)
3. **Rebuild portfolio** — `portfolio_rebuilder.rebuild_portfolio` from full ledger → save holdings snapshot

**Row types:**

| Type | Examples | Affects |
|------|----------|---------|
| `buy` / `sell` | Stock trades | Open holdings, closed positions, cash |
| `event` | RTP, SLIP, DIV, unknown misc | Cash only — stored in snapshot `misc_events` (separate from position buckets) |

**Replace import** clears CSV-sourced ledger rows only (`clear_csv_sourced_ledger`); manual journal rows (`trans_code=MANUAL` or `[journal #]`) are kept.

Key files: `backend/integrations/robinhood/csv_importer.py`, `portfolio_rebuilder.py`, `journal_verifier.py`, `backend/services/portfolio_snapshot_service.py`, `POST /brokerage/import/robinhood-csv`.

---

## Frontend design system (Dense Research Workbench)

Shared layout and typography live in `frontend/src/app/globals.css` and `frontend/src/components/ui/`:

- **Page width:** `PageContainer` (~1520px max) for data-heavy modules; workspace uses full shell width
- **Typography:** 15px body, 13px+ persistent labels, tabular nums on financial values
- **Primitives:** `DataPanel`, `SummaryStrip`, `ModuleToolbar`, `DenseTable`, `StatTile`, `MetricCard`
- **Tables:** sticky headers, right-aligned numeric columns, 14px row text
- **Colors:** dark shell preserved; green/orange/keep semantic colors unchanged

---

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
