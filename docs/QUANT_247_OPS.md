# 24/7 Quant Ops — Live Recommendations Without Burning APIs

How to run Stock Picker continuously like a **local quant desk**: scheduled scans, cached scores, and v2 recommendations — while keeping provider calls within free/low tiers.

**Prerequisite:** [USER_GUIDE.md](USER_GUIDE.md) (what to use daily vs ignore).

---

## 1. Core idea: DB-first, not API-first

The backend is already built for this:

```
Provider APIs  →  SQLite historical_store  →  PriceService (DB hit first)
                                              →  Scans / Analyze / v2 score
```

A **full sleeve scan** does not re-download the whole universe every time if bars are in the DB (`PriceService.download_batch` only fetches **missing** symbols).

Your 24/7 job is to **refresh the DB on a schedule**, then **score from cache**. Polling Finnhub/FMP every minute for 500 tickers will exhaust quotas — avoid that.

---

## 2. Three-tier refresh model

| Tier | What | API cost | Frequency |
|------|------|----------|-------------|
| **A — Watchlist** | 5–20 symbols you care about | Low | 2–4× per trading day |
| **B — Active sleeve scan** | One bucket (e.g. medium) | Medium | 1–2× per trading day |
| **C — Universe / quant jobs** | Full universe quotes, IC panel, fundamentals | High | 1× after close |

**Live recommendations** should come from **Tier A + last Tier B scan**, not from running Tier B every 15 minutes.

---

## 3. What “live recommendation” means in this app

There is no single websocket feed. “Live” here means:

1. **Latest scan cache** — `GET /scan/latest/{bucket}` (refreshed on schedule).
2. **Watchlist scores** — `GET /analyze/watchlist` after `POST /watchlist/refresh`.
3. **v2 recommendation** — `GET /api/v2/score/{symbol}?sleeve=…` (rule-based + factors; LLM optional).

**Do not** call `refresh=true` on analyze/report/LLM on a loop.

---

## 4. Recommended `.env` profile (24/7)

Copy from `.env.example` and tune:

```bash
# --- Keep backend alive ---
SCHEDULER_ENABLED=true
SCHEDULER_TZ=America/New_York
SCHEDULER_CRON=15 16 * * 1-5          # 4:15 PM ET — after close, refresh DB
QUANT_JOBS_ENABLED=true
QUANT_IC_CRON=45 16 * * 1-5           # 4:45 PM ET — IC / outcomes (uses local DB)

# --- API savers on bulk paths ---
OPENBB_ON_SCAN=false                  # critical for scans
OPENBB_ENABLED=false                  # enable only if installed; use on Analyze for top picks
LLM_ENABLED=false                     # or true only for manual Summary clicks
PIT_FUNDAMENTALS_ENABLED=false        # heavy FMP; weekly manual job if needed

# --- Primary data: one price source ---
PRIMARY_PRICE_SOURCE=akshare
AKSHARE_ENABLED=true
# Disable extras you don't need 24/7:
# ALPHA_VANTAGE_ENABLED=false
# NEWSAPI_ENABLED=false

# --- Scan scope caps ---
UNIVERSE_SCAN_BATCH_SIZE=80           # default 100; lower = fewer fallback fetches
MAX_CANDIDATES_PER_BUCKET=15          # default 25
IC_PANEL_MAX_SYMBOLS=30                 # default 40

# --- Cache TTL (seconds) ---
PRICE_CACHE_TTL=900                   # 15 min — avoid hammering quotes
FUNDAMENTALS_CACHE_TTL=604800         # 7 days
SCAN_RESULT_TTL=14400                 # 4 hours — UI reads cache between scheduled scans

# --- Production job queue (optional) ---
JOB_QUEUE_BACKEND=db
```

Run with **production mode** (no `--reload`):

```bash
cd backend && .venv/bin/uvicorn main:app --host 127.0.0.1 --port 18731
# separate terminal:
cd backend && .venv/bin/python scripts/run_job_worker.py
```

---

## 5. Sample trading-day schedule (ET)

| Time | Action | How |
|------|--------|-----|
| **7:00 AM** | Refresh watchlist only | `POST /watchlist/refresh` |
| **9:35 AM** | Post-open watchlist tick | `POST /watchlist/refresh` |
| **12:00 PM** | Optional mid-day watchlist | `POST /watchlist/refresh` |
| **3:45 PM** | Pre-close scan (one sleeve) | `POST /scan/medium` (or penny) |
| **4:15 PM** | Daily DB pipeline | Scheduler `daily_pipeline` (quotes + fundamentals cap) |
| **4:45 PM** | Quant jobs | Scheduler `quant_daily_jobs` (regime, IC, outcomes) |
| **Weekends** | Nothing | Scheduler skips non-sessions (`SCHEDULER_MARKET_CALENDAR=XNYS`) |

### macOS cron example (watchlist + one scan)

```bash
crontab -e
```

```cron
# Watchlist refresh — 7:00 and 9:35 ET (adjust for your TZ)
0 7 * * 1-5  curl -s -X POST http://127.0.0.1:18731/watchlist/refresh
35 9 * * 1-5 curl -s -X POST http://127.0.0.1:18731/watchlist/refresh
# One medium scan pre-close
45 15 * * 1-5 curl -s -X POST http://127.0.0.1:18731/scan/medium -H 'Content-Type: application/json' -d '{}'
```

Use `launchd` on Mac if the machine sleeps — cron will miss fires.

---

## 6. Pick **one** active sleeve

Running penny + medium + compounder scans 4× daily ≈ 3× API load.

For a 24/7 algo mindset:

- **Day trading / momentum** → penny only, watchlist ≤ 15.
- **Swing** → medium only (default for most users).
- **Long-term** → compounder scan **once daily**; watchlist refresh weekly is enough.

Align with [USER_GUIDE.md](USER_GUIDE.md) §2.

---

## 7. API budget rules of thumb

| Provider | Risk if abused | Mitigation |
|----------|----------------|------------|
| **akshare** (primary price) | Batch download in scans | DB-first; `UNIVERSE_SCAN_BATCH_SIZE` cap |
| **Finnhub** | Per-minute limits | News/sentiment only on Analyze; not on scan loop |
| **FMP / AV** | Daily caps | `download_batch(..., use_alpha_vantage_fallback=False)` already; don’t enable AV on 24/7 |
| **LLM** | Token cost | `LLM_ENABLED=false` for automation; manual Summary only |
| **OpenBB** | Slow SEC pulls | `OPENBB_ON_SCAN=false`; governance on demand |

**Symptoms of exhaustion:** scan messages mention `provider_limited_partial_data`, empty fundamentals, stale watchlist “○” in UI.

**Recovery:** wait for quota reset; run `POST /data/scheduler/refresh-quotes` for watchlist symbols only (narrow list via scheduler code path or manual analyze).

---

## 8. Minimal “quant loop” workflow

```text
Overnight / after close:
  Scheduler → daily_pipeline → SQLite has fresh OHLC

Morning:
  cron → watchlist/refresh → GET /analyze/watchlist → top scores + alerts

Intraday:
  Read cached latest scan (Screen UI) — do NOT re-scan unless schedule says so

Decision:
  For top 3 symbols → GET /api/v2/score/{sym}?sleeve=medium
  Optional → open Research once (no refresh=true spam)

Journal:
  Log trades in Workspace → Journal (feeds outcome loop nightly)
```

---

## 9. What **not** to do 24/7

- Full universe scan every N minutes
- `OPENBB_ON_SCAN=true` on a schedule
- Auto `getResearchReport` / LLM narrative for every symbol
- `refresh=true` on analyze in a loop
- IC panel every hour (`IC_PANEL` walks many symbols × factors)
- Enable every provider “just in case”

---

## 10. Optional upgrades (when stable)

| Step | Benefit |
|------|---------|
| `JOB_QUEUE_BACKEND=db` + worker | Scheduler jobs don’t block API server |
| PostgreSQL ([POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md)) | Safer concurrent writes if multiple jobs |
| One Telegram/email hook on watchlist alert | True “push” without polling UI |
| [OPENALPHA_INTEGRATION.md](OPENALPHA_INTEGRATION.md) batch IC weekly | New factors without live API churn |

---

## 11. Quick checklist

- [ ] One primary sleeve chosen
- [ ] Watchlist ≤ 20 symbols
- [ ] `SCHEDULER_ENABLED=true`, crons after market close
- [ ] `OPENBB_ON_SCAN=false`, `LLM_ENABLED=false` for automation
- [ ] `UNIVERSE_SCAN_BATCH_SIZE` ≤ 80
- [ ] Cron for watchlist refresh 2×/day + one scan pre-close
- [ ] UI reads **latest scan cache** between runs
- [ ] v2 score only for finalists

See also: [RUNBOOK.md](RUNBOOK.md), [MANUAL_INTEGRATION.md](MANUAL_INTEGRATION.md).
