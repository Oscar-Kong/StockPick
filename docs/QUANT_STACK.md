# Quant Stack Architecture

This document describes the runtime split for planned quant integrations.

## Runtime Planes

- **App runtime (`backend/.venv`)**
  - FastAPI routes
  - screeners/scoring
  - caching and watchlist
  - optional OpenBB enrichment
- **Quant runtime (`quant/.venv`)**
  - Qlib training/inference jobs
  - FinRL-X training/allocation jobs
  - optional heavy backtest research workflows

## Integration Boundaries

- API request handlers only read precomputed outputs.
- Training and parameter sweeps run offline/scheduled.
- Backtest engine selection is runtime-gated:
  - `engine=default` uses in-repo simulation
  - `engine=vectorbt` uses optional adapter when `VBT_ENABLED=true`

## Output Contracts

Quant artifacts should include model metadata:

- `model_name`
- `model_version`
- `trained_at`
- `data_window`

Use `backend/quant/contracts.py` as the shared contract seed.

## UI coverage

Backtest and sweep: **Workspace → Analyze → Backtest**.

Portfolio optimize and policy backtest: **Portfolio** → `/?tab=research` (legacy `/portfolio` redirects).

Still API-only: allocation recommendation, LEAN export, alpha ingest UI. See [PROJECT_INVENTORY.md](PROJECT_INVENTORY.md).

## Round 2 research export

Offline factor validation (Alphalens-style):

```bash
cd backend
.venv/bin/python scripts/factor_research_export.py [--factor medium_rs_vs_spy]
```

Artifacts: `backend/data_store/research/` (`factor_panel.parquet`, `forward_labels.parquet`, optional HTML).

Requires factor snapshot history (from scans/analyze) and forward label job for meaningful panels.

Optional: `pip install alphalens-reloaded matplotlib` for PNG tear sheets.

Integration checklist: [MANUAL_INTEGRATION.md](MANUAL_INTEGRATION.md).

