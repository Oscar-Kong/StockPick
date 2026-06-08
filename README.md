# Stock Picker

Stock Picker is a local-first US equities research dashboard with three strategy buckets:

- **Penny**: short-term momentum candidates (days to ~2 weeks)
- **Medium**: swing candidates (roughly 1-2 months)
- **Compounder**: long-term quality growers (multi-year)

It combines rule-based screening, data reconciliation, optional OpenBB governance/macro signals, backtesting, portfolio tooling, and quant integration scaffolding (vectorbt / PyPortfolioOpt / Qlib / FinRL / LEAN handoff).

## What This Project Does

From one UI, you can:

1. **Scan** a bucket and rank candidates (`/scan`)
2. **Workspace** — watchlist, single-symbol analyze, compare peers, trade journal (`/workspace`)
3. **Library** — saved scans, research reports, analyze snapshots (`/library`)
4. **Portfolio** — basket weight optimization and rebalance policy backtests (`/portfolio`)
5. **Trader Intel** — style presets and bucket tilts (`/trader-intel`)
6. Run backtests and parameter sweeps inside Analyze
7. Home hub with ticker jump and resume links (`/`)

**API-only today** (no dedicated UI yet): allocation recommendation, LEAN export, offline alpha ingest. See [Project Inventory](docs/PROJECT_INVENTORY.md).

## How It Works (End-to-End Flow)

1. **Scan request** (`POST /scan/{bucket}`)
2. **Stage A**: bulk OHLC pull + quick filter
3. **Stage B**: deep scoring for narrowed symbols
4. **Scoring**: technical/fundamental/sentiment/data-quality (+ optional OpenBB governance)
5. **Persistence**:
   - latest scan cache
   - historical/factor snapshots
6. **Frontend** shows ranked list, detail drawer, and analysis tabs
7. Optional quant services consume scan/watchlist symbols:
   - optimizer
   - policy backtests
   - alpha + allocation
   - LEAN export

## Tech Stack

- **Frontend**: Next.js + React + Tailwind + Recharts
- **Backend**: FastAPI + Pydantic + SQLAlchemy
- **Storage**: SQLite (local, DB-first cache + historical tables)
- **Data providers** (roles set in `.env`):
  - **akshare** — default primary price & fundamentals
  - **Finnhub** — quotes, earnings, news
  - **FMP / Alpha Vantage** — fundamentals reconcile
  - **FRED**, **NewsAPI**
  - optional **OpenBB** — governance, macro, extra reconcile source

## Repository Layout

```text
frontend/                # Next.js app
backend/
  api/                   # FastAPI route modules
  services/              # business logic / orchestration
  data/                  # cache, pricing, reconciliation, persistence helpers
  screeners/             # bucket-specific hard filters + score logic
  scoring/               # signal and score utilities
  ml/                    # backtest engines
  quant/                 # shared quant contracts
  data_store/            # local sqlite + export artifacts
docs/                    # architecture, runbook, API, integration docs
```

## Quick Start

## 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 18731
```

Optional quant dependencies:

```bash
pip install -r requirements-quant.txt
```

If the project folder path changed, recreate `.venv` to fix stale shebang paths.

## 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev uses **Webpack only** (Turbopack is not used).

If the dev server misbehaves or spikes CPU, stop it and clear the cache:

```bash
./scripts/dev-down.sh
rm -rf frontend/.next
npm run dev
```

For a low-CPU option, use production mode: `npm run build && npm run start`.

Open: [http://127.0.0.1:18730](http://127.0.0.1:18730)

**Language:** use the gear icon (top right) → **English** / **中文**. Preference is stored in `localStorage` (`picker-locale`). All pages and major UI chrome are translated (Home, Research, Screen, Portfolio, Library, Settings, Trader Intel). Scan pick summaries respect locale when LLM is enabled. API-sourced content (reports, alerts, provider labels) remains in the language returned by the backend.

### One-command local start

From project root:

```bash
./scripts/dev-up.sh
```

Stop both services:

```bash
./scripts/dev-down.sh
```

## Configuration

Copy `.env.example` to `.env` and set keys/flags. **Never commit `.env`** — see [GitHub setup](docs/GITHUB_SETUP.md).

```bash
cp .env.example .env
# edit .env with your keys
```

### Core provider keys

| Variable | Required | Purpose |
|----------|----------|---------|
| `FINNHUB_API_KEY` | Recommended | quotes/news/earnings |
| `FMP_API_KEY` | Recommended | rich fundamentals |
| `ALPHA_VANTAGE_API_KEY` | Recommended | additional fundamentals |
| `FRED_API_KEY` | Optional | macro regime |
| `NEWSAPI_KEY` | Optional | fallback sentiment |
| `GPT_PROXY_API_KEY` | Optional | WhaleCloud proxy key |
| `GPT_PROXY_BASE_URL` | Optional | WhaleCloud proxy base URL |
| `GPT_PROXY_MODEL` | Optional | model name from your proxy console |

Optional LLM profile tuning:
`INVEST_TIME_HORIZON`, `INVEST_RISK_TOLERANCE`, `INVEST_MAX_POSITION_SIZE`,
`INVEST_ALLOWED_STRATEGIES`, `INVEST_INTERESTED_SECTORS`, `INVEST_AVOID_LIST`

### Feature flags

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENBB_ENABLED` | `false` | OpenBB data/governance integration |
| `OPENBB_ON_SCAN` | `false` | allow slower OpenBB fetches during full scans |
| `VBT_ENABLED` | `false` | vectorbt engine in backtests |
| `PYPFOPT_ENABLED` | `false` | PyPortfolioOpt optimizer path |
| `QLIB_ENABLED` | `false` | Qlib alpha workflow flag |
| `FINRL_ENABLED` | `false` | FinRL allocation workflow flag |
| `LEAN_EXPORT_ENABLED` | `false` | LEAN handoff workflow flag |
| `PREDICTION_SNAPSHOTS_ENABLED` | `true` | Store every v2 score as a prediction snapshot |
| `VALUATION_ENGINE_ENABLED` | `true` | DCF + peer + reverse DCF on v2 score |
| `MULTI_AGENT_PIPELINE_ENABLED` | `true` | Specialist agent pipeline on v2 score |
| `DYNAMIC_WEIGHTS_ENABLED` | `true` | Regime-aware IC-weighted factors |
| `POSITION_SIZING_V2` | `true` | Portfolio-aware position sizing block |
| `BACKTEST_INSTITUTIONAL` | `true` | Costs/slippage in institutional backtests |
| `AI_REPORT_SCHEMA` | `v2` | Structured 10-section research report |

## Key Product Features

- Bucket scans with async progress polling
- **Quant v2 closed feedback loop** (Round 2):
  - Layered recommendation: alpha + valuation + catalyst − risk − data/liquidity penalties
  - `prediction_snapshots` + forward outcome tracking (20/60/90d vs SPY & sector)
  - Factor IC dashboard at `/api/v2/factors/performance`
  - DCF / peer / reverse DCF valuation engine
  - Similar-signal historical backtest
  - Data confidence gate (no Strong Buy below 80)
  - Multi-agent specialist pipeline (quant scores final decision, not LLM alone)
  - **Remaining work:** [docs/ROUND2_REMAINING_WORK.md](docs/ROUND2_REMAINING_WORK.md)
  - **Manual setup (API keys, jobs):** [docs/MANUAL_INTEGRATION.md](docs/MANUAL_INTEGRATION.md)
- Symbol analysis tabs:
  - overview
  - quant signal breakdown
  - data quality/reconciliation
  - chart
  - backtest + sweep
  - report
- Watchlist with refresh/import
- Strategy version and data quality visibility
- Optional quant layer endpoints (portfolio, ML, allocation, LEAN)

## API Overview

### Scan + Watchlist

- `POST /scan/{bucket}`
- `GET /scan/{job_id}`
- `GET /scan/latest/{bucket}`
- `GET /watchlist`
- `POST /watchlist`
- `DELETE /watchlist/{symbol}`
- `PATCH /watchlist/{symbol}/notes`
- `POST /watchlist/import`
- `POST /watchlist/refresh`

### Analyze + Stock

- `GET /stock/{symbol}`
- `GET /analyze/{symbol}` — optional `bucket`, `refresh`, `include_bucket_fit`
- `GET /analyze/{symbol}/bucket-fit`
- `GET /analyze/{symbol}/report`
- `GET /analyze/watchlist` — workspace matrix rows + alerts
- `GET /analyze/compare?symbols=...`
- `POST /explain` — LLM narrative (Overview tab)

### Saved + progress

- `GET/POST/DELETE /saved/scans`, `/saved/reports`
- `GET /saved/analyze`, `/saved/progress-summary`

### Trades (journal)

- `GET/POST/PATCH/DELETE /trades`, `/trades/manual`, `/trades/upload`, `/trades/stats/summary`

### Backtesting

- `GET /backtest/{bucket}/{symbol}?engine=default|vectorbt`
- `POST /backtest/{bucket}/{symbol}/sweep?engine=default|vectorbt`

### Portfolio + Quant

- `POST /portfolio/optimize`
- `POST /portfolio/policy-backtest`
- `GET /ml/alpha/latest`
- `POST /ml/alpha/ingest`
- `GET /allocation/recommendation/{bucket}`

### LEAN Handoff

- `POST /lean/export`
- `GET /lean/export/{export_id}`
- `POST /lean/import-summary`

See full details in [API Reference](docs/API_REFERENCE.md).

## Quant Integration Status

Implemented in runtime API:

- vectorbt adapter for backtests
- PyPortfolioOpt/fallback optimizer
- Qlib offline alpha ingest + lookup in screeners
- policy backtest engine
- allocation recommender scaffold
- LEAN export/import-summary scaffold

For production-grade models, offline training pipelines still need to be operated externally and fed back in via ingest/export endpoints.

## Documentation Index

| Doc | Audience |
|-----|----------|
| **[User Guide](docs/USER_GUIDE.md)** | **Everyone — start here; workflows & mental map** |
| [24/7 quant ops (API-safe)](docs/QUANT_247_OPS.md) | Running scheduled scans & live recommendations |
| [OpenAlpha integration](docs/OPENALPHA_INTEGRATION.md) | Quant — US-adapted factor research |
| [Architecture](docs/ARCHITECTURE.md) | Developers — modules and extension points |
| [API Reference](docs/API_REFERENCE.md) | Developers — HTTP endpoints |
| [Runbook](docs/RUNBOOK.md) | Ops — start, flags, troubleshooting |
| [GitHub setup (no secrets)](docs/GITHUB_SETUP.md) | Safe publish checklist & gitignore |
| [Analyze Panel (finance)](docs/ANALYZE_PANEL.md) | Investors — scores, factors, tabs |
| [Analyze Sector Report](docs/ANALYZE_SECTOR_REPORT.md) | Developers — analyze APIs, flow, v2 hooks |
| [Project Inventory](docs/PROJECT_INVENTORY.md) | Everyone — routes, gaps, cleanup |
| [OpenBB Integration](docs/OPENBB.md) | Optional governance/macro layer |
| [Quant Stack](docs/QUANT_STACK.md) | Quant runtime split |
| [Quant Integration Plan](docs/QUANT_INTEGRATION_PLAN.md) | Roadmap + implementation status |
| [Institutional Quant Architecture](docs/INSTITUTIONAL_QUANT_ARCHITECTURE.md) | Target v2 engines, formulas, schema, roadmap |

## Common Commands

```bash
# backend lint/smoke style checks (example)
python -m py_compile backend/main.py

# before git push — scan for leaked secrets
./scripts/check-secrets.sh

# frontend lint
cd frontend && npm run lint
```

## Disclaimer

This software is for research/education workflows and surfaces rule/model-based candidate ideas. It is **not financial advice**.
