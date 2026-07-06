# OpenBB in Stock Picker

OpenBB is integrated as an **optional data and governance layer** — not a replacement for Finnhub (earnings/news) or your screening logic.

## Setup

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt -r requirements-openbb.txt
```

In `.env`:

```env
OPENBB_ENABLED=true
OPENBB_ON_SCAN=false
```

`OPENBB_ON_SCAN=false` (default) keeps **bulk scans fast** — SEC downloads are skipped during full-universe scans. Single-symbol **Analyze** still fetches/caches governance data.

Verify:

```bash
python scripts/verify_openbb.py
curl http://127.0.0.1:18731/data/openbb/risk/AAPL
```

Keys are read from your existing `.env` (`FMP`, `FRED`, `ALPHA_VANTAGE`, `NASDAQ_DATA_LINK`).

---

## Architecture (how it fits the product)

```
                    Stock Picker scan pipeline
                              │
    ┌─────────────────────────┼─────────────────────────┐
    ▼                         ▼                         ▼
PriceService            DataReconciler            FinnhubClient
(DB + provider)   + openbb 4th source          (earnings, news)
    │                         │
    ▼                         ▼
 Screeners              data_quality_score
 (penny/compounder/         + canonical PE, ROE…
  compounder)                    │
    │                            ▼
    ├─ Medium/Compounder:  "SEC / insider governance" signal (5%)
    │                       via OpenBB SEC + insider data
    ▼
 enrich_metrics → openbb_governance_score, warnings
    │
    ▼
 Score adjustments (governance + data quality)
    │
    ▼
 Research report §8 risks + Analyze alerts
```

### 1. Better fundamentals (all buckets)

`DataReconciler` adds an **openbb** source (FMP metrics via OpenBB). When sources disagree, you get a stronger `data_quality_score` and more reliable PE, ROE, and market cap for filters.

### 2. Macro regime (compounder bucket)

`FredClient.macro_regime_score()` uses OpenBB’s FRED provider when enabled, then falls back to direct FRED HTTP. Powers the **Macro regime** signal (10% weight) for long-term compounders.

### 3. Governance risk (compounder)

**New signal:** `SEC / insider governance` (5% weight, rescales other legs).

**New metrics on scan results:**

- `openbb_governance_score` (0–100)
- `openbb_risk_flags` — e.g. `insider_sell`, `sec_8k`, `sec_offering`
- `openbb_recent_filings`

**Score penalty** after enrichment (similar to data-quality adjustment).

### 4. Research & analyze

- Research report **§8 risks** includes SEC/insider warnings
- **Analyze** tab alerts: governance / offering / 8-K types
- API: `GET /data/openbb/risk/{symbol}`

### 5. Not replaced by OpenBB

| Feature | Still uses |
|---------|------------|
| Live quotes (primary) | Finnhub |
| News sentiment | Finnhub / NewsAPI |
| Price history DB | DB-first quotes (akshare / FMP / others per `.env`) |
| Penny momentum | Custom technical + volume rules |

---

## Code map

| File | Role |
|------|------|
| `backend/data/openbb_client.py` | OpenBB calls + `compute_risk_snapshot()` |
| `backend/services/openbb_integration.py` | Hooks for metrics, signals, reports |
| `backend/scoring/openbb_governance.py` | Score adjustment from governance |
| `backend/data/reconciler.py` | 4th reconcile source |
| `backend/data/fred_client.py` | Macro via OpenBB |
| `backend/screeners/compounder.py` | Governance signal |
| `backend/services/scan_manager.py` | Scan score finalize |
| `backend/api/routes_data.py` | `/data/openbb/risk/{symbol}` |

---

## Optional extras

```bash
pip install openbb-alpha-vantage openbb-technical
```

Or full install: `pip install "openbb[all]"` (large).

---

## Troubleshooting

- **Status bar “OpenBB: off”** — `OPENBB_ENABLED` false or package not installed
- **Governance score always 72** — SEC provider may be rate-limited; check logs
- **First import slow** — OpenBB builds assets on first `import openbb`

Docs: [OpenBB Python](https://docs.openbb.co/odp/python/installation)
