# Quant Integration Plan

How external quant tools fit Stock Picker, and what is done vs still API-only.

## Status (2026)

| Phase | Capability | API | UI |
|-------|------------|-----|-----|
| 0 | Feature flags, `backend/quant/contracts` | Config | — |
| 1 | vectorbt backtests + sweep | `/backtest/...`, `engine=vectorbt` | Workspace → Analyze → **Backtest** |
| 2 | Portfolio optimize | `POST /portfolio/optimize` | **`/portfolio`** → Optimize weights |
| 3 | Qlib alpha | `POST /ml/alpha/ingest`, screener hook | CLI ingest only |
| 4 | Policy backtest | `POST /portfolio/policy-backtest` | **`/portfolio`** → Policy backtest |
| 5 | FinRL allocation | `GET /allocation/recommendation/{bucket}` | Not yet |
| 6 | LEAN handoff | `/lean/export`, `/lean/import-summary` | Not yet |

Product map: [PROJECT_INVENTORY.md](PROJECT_INVENTORY.md). Ops: [RUNBOOK.md](RUNBOOK.md). Runtime split: [QUANT_STACK.md](QUANT_STACK.md).

---

## Goal

Layer quant tools on top of the existing **penny / medium / compounder** screener without breaking:

- Watchlist, scan, and analyze flows
- Fast local dev (flags off by default)
- Optional OpenBB enrichment

---

## Tool roles (no overlap)

| Tool | Role |
|------|------|
| **Qlib** | Offline alpha → ingest → optional signal in medium/compounder |
| **vectorbt** | Fast backtests and parameter sweeps |
| **PyPortfolioOpt** | Basket weight optimization (`PYPFOPT_ENABLED`) |
| **Policy sim** | Equal-weight / inverse-vol / top-N rebalance backtests |
| **FinRL-X** | Allocation recommendations (scaffold) |
| **LEAN** | External execution; export/import summaries only |

---

## Environment strategy

| Env | Use |
|-----|-----|
| `backend/.venv` | FastAPI app, screeners, API routes |
| `quant/.venv` (optional) | Heavy offline training (Qlib, FinRL research) |

Do not run long training inside HTTP handlers.

---

## Integration pattern (repeat for new tools)

1. Adapter or client module  
2. Service layer (`backend/services/…`)  
3. Optional hook in screener or analyze  
4. API route + Pydantic schema  
5. Frontend types + `api.ts` + page/tab  

Same pattern as OpenBB: [OPENBB.md](OPENBB.md).

---

## Guardrails

- Feature flags to disable any module instantly  
- Timeouts and fallbacks on optional quant routes  
- Never block scans on model training  
- Validate weights (sum ≈ 1, bounds, no NaN scores)  
- Reject stale predictions by date when ingesting alpha  

---

## Remaining work (optional)

1. **Allocation UI** — thin page calling `GET /allocation/recommendation/{bucket}`  
2. **LEAN UI** — export form + display import summary  
3. **Alpha ingest UI** — upload JSON for `/ml/alpha/ingest` (today: curl or script)  
4. Offline `qlib_train.py` / `qlib_infer.py` scripts if not already in repo  

---

## Completed checklist

- [x] Phase 0 — flags and contracts  
- [x] Phase 1 — vectorbt + sweep in Backtest tab  
- [x] Phase 2 — optimize endpoint + Portfolio page  
- [x] Phase 3 — alpha ingest + screener fallback  
- [x] Phase 4 — policy backtest + Portfolio page  
- [x] Phase 5 — allocation API (scaffold)  
- [x] Phase 6 — LEAN export/import API (scaffold)  
- [x] Docs: API reference, runbook, project inventory  
