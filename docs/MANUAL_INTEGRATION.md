# Round 2 — Manual Integration Checklist

This guide lists what **you** must configure or run locally so Round 2 features work end-to-end. Code is in place; several paths depend on API keys, scheduled jobs, or optional packages.

---

## 1. Environment (`.env`)

Copy from `.env.example` and set at minimum:

| Variable | Purpose |
|----------|---------|
| `SCORE_ENGINE_V2_ENABLED=true` | Enables all `/api/v2/*` endpoints |
| `PREDICTION_SNAPSHOTS_ENABLED=true` | Records recommendations for learning loop |
| `FMP_API_KEY` | Peers, earnings estimates, PIT income statements |
| `FINNHUB_API_KEY` | Price/fundamentals fallback |
| `FACTOR_MODEL_VERSION=quant-v2-round2` | Version tag on snapshots |

Round 2 flags (defaults on in `.env.example`):

```bash
FORWARD_LABELS_ENABLED=true
OUTCOME_WEIGHT_FEEDBACK_ENABLED=true
LEGACY_BACKTEST_COSTS_ENABLED=true
PIT_FUNDAMENTALS_ENABLED=true
VALUATION_ENGINE_ENABLED=true
MULTI_AGENT_PIPELINE_ENABLED=true
LLM_AGENTS_ENABLED=false   # set true only when LLM proxy is configured
```

**LLM (optional):** Set `LLM_AGENTS_ENABLED=true` only after:

```bash
GPT_PROXY_API_KEY=...
GPT_PROXY_BASE_URL=...
GPT_PROXY_MODEL=...
LLM_ENABLED=true
```

---

## 2. Start the stack

```bash
./scripts/dev-up.sh
# or manually: backend on :18731, frontend on :18730
```

Verify:

```bash
curl -s http://127.0.0.1:18731/health
curl -s http://127.0.0.1:18731/api/v2/admin/round2-stats | jq
curl -s "http://127.0.0.1:18731/api/v2/score/AAPL?sleeve=medium" | jq '.recommendation,.valuation.sensitivity_grid'
```

Open **Analyze → AAPL** — sidebar should show Round 2 quant block (recommendation, valuation grid, earnings, similar-signal).

---

## 3. Seed data (first-time / empty DB)

Round 2 quality improves after jobs populate history:

```bash
# IC panel + deciles + sector breakdown cache
curl -X POST http://127.0.0.1:18731/api/v2/jobs/ic-panel

# Forward return labels (needs price history)
curl -X POST http://127.0.0.1:18731/api/v2/jobs/forward-labels

# PIT fundamentals from FMP income statements (needs FMP_API_KEY)
curl -X POST http://127.0.0.1:18731/api/v2/jobs/pit-fundamentals

# Resolve prediction outcomes (after snapshots exist)
curl -X POST http://127.0.0.1:18731/api/v2/jobs/resolve-outcomes

# Outcome-driven weight nudge (after outcomes exist)
curl -X POST http://127.0.0.1:18731/api/v2/jobs/outcome-weights
```

**Daily automation:** Enable scheduler in `.env`:

```bash
SCHEDULER_ENABLED=true
QUANT_JOBS_ENABLED=true
QUANT_IC_CRON=45 20 * * 1-5
```

This runs regime, IC panel, forward labels, outcomes, and PIT ingest on schedule.

**Generate snapshots:** Run Analyze or scans on symbols — each v2 score can persist a `prediction_snapshot`.

---

## 4. External research (optional)

### Factor export + Alphalens

```bash
cd backend
source .venv/bin/activate
python scripts/factor_research_export.py --factor medium_rs_vs_spy
```

Outputs: `backend/data_store/research/factor_panel.parquet`, `forward_labels.parquet`, `alphalens_*.html`.

For full Alphalens tear sheets:

```bash
pip install alphalens-reloaded matplotlib
python scripts/factor_research_export.py
```

### VectorBT

Set `VBT_ENABLED=true` and install quant extras (`pip install -r requirements-quant.txt`). Use Analyze → Backtest tab → engine **vectorbt**.

---

## 5. What still needs manual / paid data work

| Gap | What you do |
|-----|-------------|
| **EDGAR PIT** | FMP ingest covers quarterly filings; true SEC EDGAR `companyfacts` ingest is not wired — use FMP paid tier or build `data/edgar_pit.py` |
| **Universe depth** | IC / similar-signal need factor snapshots — run scans or analyze on watchlist regularly |
| **LLM multi-agent** | Enable `LLM_AGENTS_ENABLED`; review cost per symbol; agents never override quant score |
| **Production Postgres** | Set `DATABASE_URL` + run migration notes in [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md) |
| **Alerts** | No paging yet — poll `GET /api/v2/admin/round2-stats` or wire to your monitor |

---

## 6. UI verification checklist

- [ ] Analyze sidebar: recommendation label + pillars + data confidence
- [ ] Valuation: DCF / peer / **WACC×growth sensitivity table**
- [ ] Earnings: revisions, analyst up/down, 5d/20d drift
- [ ] Similar-signal: sample_n, win_rate, top analogs
- [ ] Backtest tab: **Net** vs **Gross** return when costs enabled
- [ ] Research report tab: v2 sections at top
- [ ] Trade journal open → links to same-day snapshot (check `snapshot_id` on trade)

---

## 7. Tests

```bash
cd backend
.venv/bin/python tests/test_round2_optimizations.py
.venv/bin/python tests/test_round2_api.py
.venv/bin/python tests/test_openalpha_factors.py
```

---

## 8. OpenAlpha-inspired factor research (optional)

See [OPENALPHA_INTEGRATION.md](OPENALPHA_INTEGRATION.md).

```bash
cd backend
.venv/bin/python scripts/alpha_batch_eval.py --list
.venv/bin/python scripts/alpha_batch_eval.py --universe sp500 --export
.venv/bin/python scripts/alpha_combo_optimizer.py --sleeve medium --export
```

Enable live legs only after IC review: `OPENALPHA_FACTORS_ENABLED=true` in `.env`.

---

## 9. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `/api/v2/score` 503 | `SCORE_ENGINE_V2_ENABLED=true`, restart backend |
| Empty similar-signal | Run scans; need `factor_snapshots` rows |
| Empty `by_sector` in factor performance | Run `POST /jobs/ic-panel` once |
| PIT job writes 0 rows | Set `FMP_API_KEY`, `FMP_ENABLED=true` |
| LLM enrichment silent | Check `LLM_ENABLED`, proxy keys, set `LLM_AGENTS_ENABLED=true` |
| Valuation grid all `—` | WACC ≤ terminal growth for some cells (expected) |

See also [ROUND2_REMAINING_WORK.md](ROUND2_REMAINING_WORK.md) for architecture gaps and [RUNBOOK.md](RUNBOOK.md) for ops.
