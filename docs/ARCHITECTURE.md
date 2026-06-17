# Architecture

StockPick is organized around product domains. Shared infrastructure lives under `backend/core/`; feature logic remains under `backend/services/` during incremental migration toward `backend/domains/`.

## Product sleeves

Active sleeves: **penny**, **compounder**. Legacy API/database values may still contain `medium`; `core.sleeve.normalize_sleeve()` maps `medium` → `penny` at boundaries.

## Backend layout

| Area | Location | Notes |
|------|----------|--------|
| Infrastructure | `backend/core/` | `database.py`, `errors.py`, `sleeve.py` |
| HTTP routes | `backend/api/` | FastAPI routers registered in `main.py` |
| Domain services | `backend/services/` | Scan, portfolio, research, quant (migrating to `domains/`) |
| Data layer | `backend/data/` | SQLite/Postgres stores, cache, universe |
| Quant engines | `backend/engines/` | Scoring, factors, risk |
| Screeners | `backend/screeners/` | Penny and compounder algorithms |

## Frontend layout

| Area | Location |
|------|----------|
| Routes | `frontend/src/app/` |
| Feature UI | `frontend/src/components/` (moving toward `features/`) |
| API client | `frontend/src/lib/api.ts`, `apiConfig.ts`, `apiError.ts` |

Legacy URL aliases (`/penny`, `/medium`, `/watchlist`, etc.) redirect via `frontend/next.config.ts`.

## Research reports

Single pipeline: `services/research_report.py` (quant score + narrative). No separate v1/v2 generators.

## Related docs

- [DEPLOYMENT.md](DEPLOYMENT.md) — public demo
- [USER_GUIDE.md](USER_GUIDE.md) — product usage
- [RUNBOOK.md](RUNBOOK.md) — local ops
