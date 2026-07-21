# Architecture

StockPick is organized around product domains. Shared infrastructure lives under `backend/core/`; feature logic remains under `backend/services/` during incremental migration toward `backend/domains/`.

## Product sleeves

Active sleeves: **penny**, **compounder**. Legacy API/database values may still contain `medium`; `core.sleeve.normalize_sleeve()` maps `medium` → `penny` at boundaries.

## Backend layout

| Area | Location | Notes |
|------|----------|--------|
| Infrastructure | `backend/core/` | `database.py`, `errors.py`, `sleeve.py` |
| HTTP routes | `backend/api/` | FastAPI routers registered in `main.py` |
| Domain services | `backend/services/` | Scan, portfolio ledger & decisions, research, quant (migrating to `domains/`) |
| Scan pipeline | `backend/services/scan_pipeline.py` | Deep module: Stage A → Stage B → rank → persist (`run_scan_pipeline`) |
| Scan public API | `backend/services/scan_service.py` | `start_async`, `get_latest`, `get_status`; `scan_manager` is a backwards-compat alias |
| Scan job shim | `backend/services/scan_manager.py` | Re-exports `scan_service` / `ScanService` |
| Portfolio refresh | `backend/services/refresh_orchestrator.py` | `PortfolioRefresh` deep module: holdings → prices → decision (+ penny scan on home); re-prices when holdings change so TTL cannot skip new symbols |
| Robinhood MCP sync | `backend/services/portfolio_snapshot_service.py` | Live positions SoT; always force-refreshes marks; UI passes `run_decision=true` so Today matches when holdings exist (cash-only skips decision); MCP status card is diagnostics-only (collapsed unless auth issue / Troubleshoot) |
| Candidate gate | `backend/data/candidate_gate.py` | Unified Stage B DQ + filter seam |
| PIT history | `backend/data/pit_history.py` | Shared `truncate_history` for walk-forward and scan-eval |
| Research runs | `backend/services/research_run_repository.py` | Read facade; `routes_research_lab` GET `/runs*` delegates here |
| Portfolio cockpit | `backend/services/portfolio_cockpit_service.py` | Unified Today view; `routes_home` daily-dashboard uses `get_today_view` |
| Frontend portfolio | `frontend/src/components/portfolio/PortfolioWorkspace.tsx` | Single `/` route: **Today** (holdings & action queue), **Daily Plan** (`?tab=plan`), **Research** (optimize/backtest/exposure/allocation), **Activity** (CSV, journal) |
| Data layer | `backend/data/` | SQLite/Postgres stores, cache, universe |
| Quant engines | `backend/engines/` | Scoring, factors, risk; Stage B legs in `engines/factor/sleeve_signals.py` |
| Screeners | `backend/screeners/` | Penny/compounder hard filters + display metrics; composite legs from `sleeve_signals` |
| Scoring facade | `backend/services/scoring_facade.py` | Canonical Stage B entry for Scan, Watchlist, Analyze |

## Frontend layout

| Area | Location | Notes |
|------|----------|--------|
| Routes | `frontend/src/app/` | Next.js app router |
| Feature UI | `frontend/src/components/` | Moving toward `features/` |
| API client | `frontend/src/lib/api.ts`, `frontend/src/lib/api/` | Transport in `client.ts`; domain modules `scan.ts`, `portfolio.ts`, `research/runs.ts` |
| Portfolio hook | `frontend/src/hooks/useDailyDashboard.ts` | Shared Today dashboard load/poll/refresh (`PortfolioWorkspace`) |
| Research runs hook | `frontend/src/hooks/useResearchRuns.ts` | Results tab list/detail/compare read path |

Legacy URL aliases (`/penny`, `/medium`, `/watchlist`, etc.) redirect via `frontend/next.config.ts`.

## Research reports

Single pipeline: `services/research_report.py` (quant score + narrative). No separate v1/v2 generators.

## Related docs

- [DEPLOYMENT.md](DEPLOYMENT.md) — public demo
- [USER_GUIDE.md](USER_GUIDE.md) — product usage
- [RUNBOOK.md](RUNBOOK.md) — local ops
