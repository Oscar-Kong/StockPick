# How to Use Stock Picker — User Guide

This guide is the **mental map** for the project. Use it when the app feels crowded or you are not sure where to start.

**Related docs (by role):**

| If you want… | Read |
|--------------|------|
| Daily workflows (this guide) | **USER_GUIDE.md** (here) |
| **24/7 scans without exhausting APIs** | [QUANT_247_OPS.md](QUANT_247_OPS.md) |
| OpenAlpha-inspired research factors | [OPENALPHA_INTEGRATION.md](OPENALPHA_INTEGRATION.md) |
| API keys & toggles | [RUNBOOK.md](RUNBOOK.md) |
| Business meaning of Analyze tabs | [ANALYZE_PANEL.md](ANALYZE_PANEL.md) |
| **Every Analyze stat explained** | [ANALYZE_PANEL_STATS_GUIDE.md](ANALYZE_PANEL_STATS_GUIDE.md) |
| Full product route list | [PROJECT_INVENTORY.md](PROJECT_INVENTORY.md) |
| Future / institutional design | [INSTITUTIONAL_QUANT_ARCHITECTURE.md](INSTITUTIONAL_QUANT_ARCHITECTURE.md) — *reference, not daily* |
| Round 2 engineering backlog | [ROUND2_REMAINING_WORK.md](ROUND2_REMAINING_WORK.md) — *for builders* |

---

## 1. One-sentence purpose

**Find US stock ideas in three time horizons, analyze them locally, optionally size and backtest — without sending your watchlist to the cloud.**

---

## 2. The three sleeves (ignore everything else at first)

Everything in screening and scoring rolls up to **one of three buckets**:

| Sleeve | Hold period | You use it when… |
|--------|-------------|------------------|
| **Penny** | Days → ~2 weeks | Momentum / volume / short-term trades |
| **Medium** | Weeks → few months | Swing setups with RS vs SPY + fundamentals |
| **Compounder** | Years | Quality growers, macro + governance matter |

**Rule of thumb:** Pick **one primary sleeve** per symbol. The app assigns a bucket automatically; you can override in Workspace.

---

## 3. The five places that matter (UI map)

You only need **five routes** for 90% of work:

```
Home (/)           → jump in, resume last work
Screen (/scan)     → discover ranked candidates
Research (/workspace) → watchlist + deep dive + journal
Compare (/workspace?tab=compare) → peer metrics (also in top nav)
Journal (/workspace?tab=journal) → trade log (also in top nav)
Library (/library) → saved scans & reports
Portfolio (/portfolio) → basket weights & policy backtest (optional)
```

Inside **Research → Analyze**, use **Overview** for v2 recommendation, valuation, similar-signal, and position sizing (visible on all screen sizes; the right sidebar keeps technicals and factor weights).

Everything else is **secondary**:

| Route | Status |
|-------|--------|
| `/settings` | API keys & language — set once |
| `/trader-intel` | Optional strategy templates |
| `/penny`, `/medium`, `/compounder` | Redirects to `/scan?bucket=…` |
| `/analyze`, `/watchlist`, `/trades`, `/reports`, `/scans` | Redirects — old bookmarks |

**Ignore until you need them:** allocation API, LEAN export, alpha ingest UI, scheduler — they exist but have no dedicated page ([PROJECT_INVENTORY.md](PROJECT_INVENTORY.md)).

---

## 4. Recommended workflows

### A. “I want new ideas today” (15 min)

1. Open **Screen** → pick **Penny**, **Medium**, or **Compounder**.
2. Run scan (defaults are fine).
3. Click **Summary** on a row; add 1–3 names to watchlist.
4. Open **Research** → analyze each symbol (Overview + Chart).

### B. “I already have tickers” (ongoing)

1. **Research** → **+ Add** on watchlist (or paste list in Import).
2. Select symbol → read **Overview**, **Quant**, **Report** tab if needed.
3. Save notes; optional **Generate narrative** if LLM is on.

### C. “I want to compare peers” (10 min)

1. **Research** → **Compare** tab.
2. Pick 2–4 symbols → read the metrics table.

### D. “I traded — log it” (5 min)

1. **Research** → **Journal** tab.
2. Manual entry or screenshot upload.
3. Review process-quality score (not just PnL).

### E. “I want portfolio-level math” (advanced)

1. **Portfolio** → paste symbols or **Use watchlist**.
2. **Optimize weights** *or* **Policy backtest** — not both on day one.

### F. “I want to research new factors” (offline)

See [OPENALPHA_INTEGRATION.md](OPENALPHA_INTEGRATION.md) — batch IC eval, combo optimizer, optional live toggle.

---

## 5. Research workspace tabs — what to read

Inside **Research → Analyze**, tabs are ordered by **how often you need them**:

| Tab | Read when… | Skip when… |
|-----|------------|------------|
| **Overview** | Always — v2 recommendation, valuation, sizing, chart | — |
| **Score breakdown** | Which factors drove the score | You trust the headline score |
| **Risk** | Volatility, liquidity, event risk before sizing | Penny scalp with fixed size |
| **Diagnostics** | Is the price series momentum or noise? | You only care about fundamentals |
| **Valuation** | DCF / peer fair value / margin of safety | Penny momentum-only |
| **Backtest** | Validating a rule-based story | Short-term penny flip |
| **Similar signal** | Historical analog context (research only) | You want live signals only |
| **Report** | Writing up a thesis for Library | Quick watchlist check |
| **Notes** | Your personal thesis / reminders | — |

**Sidebar (desktop):** technicals, bucket fit, and signal weights on every tab.

Full stat definitions: [ANALYZE_PANEL_STATS_GUIDE.md](ANALYZE_PANEL_STATS_GUIDE.md).

---

## 6. What creates “messy sectors” (and how to simplify)

### Problem: Too many signals

The score is a **weighted blend** of factors (momentum, volume, RS vs SPY, sentiment, optional Qlib, optional OpenAlpha legs). You do **not** need every leg to agree.

**Simplify:**

- Trust **top 2–3 signals** in Score breakdown tab + **risk level** chip.
- Ignore experimental factors unless `OPENALPHA_FACTORS_ENABLED=true` ([OPENALPHA_INTEGRATION.md](OPENALPHA_INTEGRATION.md)).

### Problem: Sector / industry everywhere

Sector appears in: scan metrics, analyze sidebar, compare table, reports, factor IC by sector.

**Simplify:**

- **Screening:** sector is a filter hint, not a hard rule.
- **Analyze:** use sector for **context** (“is this a hot sector?”), not as a second score.
- **Compare:** only matters when peers are in the **same industry**.

### Problem: Too many docs

| Tier | Docs |
|------|------|
| **Daily** | USER_GUIDE (here), RUNBOOK, ANALYZE_PANEL |
| **Weekly / quant** | OPENALPHA_INTEGRATION, QUANT_STACK, MANUAL_INTEGRATION |
| **Architecture / backlog** | INSTITUTIONAL_QUANT_ARCHITECTURE, ROUND2_REMAINING_WORK |

### Problem: Too many `.env` flags

**Minimum to run:**

```bash
# backend/.env — defaults work for local dev
AKSHARE_ENABLED=true
FINNHUB_ENABLED=true   # if you have a key
```

**Turn on only when you need the feature:**

| Flag | When |
|------|------|
| `LLM_ENABLED` | AI narrative, scan Summary blurbs |
| `OPENBB_ENABLED` | Governance / macro enrichments |
| `QLIB_ENABLED` | ML alpha leg in medium/compounder |
| `OPENALPHA_FACTORS_ENABLED` | Experimental formula legs in live scans |
| `PYPFOPT_ENABLED` | Real portfolio optimizer (else fallback) |
| `VBT_ENABLED` | VectorBT backtest engine |

Full list: `.env.example` + [RUNBOOK.md](RUNBOOK.md).

---

## 7. Data you can trust vs noise

| Source | Role |
|--------|------|
| **Price / OHLCV** | Primary — drives most signals |
| **Fundamentals** | Reconciled across FMP / AV / akshare |
| **Sentiment / news** | Tie-breaker, not gospel |
| **LLM text** | Research aid — not investment advice |
| **Backtest** | Historical sanity check — not forecast |

Check **Data quality %** badge; below ~60%, treat fundamentals and LLM as weak.

---

## 8. Language

Gear icon (top right) → **English** / **中文**. UI labels and buttons translate instantly — **scores, scans, and analysis data are not re-fetched** when you switch language. API-generated report or pick-summary text stays in the language it was generated until you explicitly request a new run.

---

## 9. Quick decision tree

```text
Have tickers already?
  YES → Research (watchlist → Analyze)
  NO  → Screen (pick sleeve → run scan → add to watchlist)

Need portfolio weights?
  YES → Portfolio (2+ symbols)
  NO  → stay in Research

Need saved artifact?
  Scan snapshot / Report → Library

Researching factor ideas offline?
  OPENALPHA_INTEGRATION.md → alpha_batch_eval.py
```

---

## 10. What “done” looks like for a session

A good session ends with:

1. **1 sleeve** chosen intentionally (penny *or* medium *or* compounder).
2. **≤10 watchlist** names you will actually follow up.
3. **Notes or journal entry** on names you might trade.
4. Optional: **one saved scan** or **one saved report** in Library.

You do **not** need to touch Portfolio, Trader Intel, Round 2 admin APIs, or architecture docs every session.

---

## 11. Getting unstuck

| Symptom | Fix |
|---------|-----|
| Empty scan | Widen price/volume filters; check backend on `:18731` |
| Stale watchlist prices | Refresh rail (↻) in Research |
| LLM Summary empty | `LLM_ENABLED` + proxy keys in `.env` |
| Portfolio optimize fails | Need 2+ symbols with history; optional `requirements-quant.txt` |
| Overwhelmed by factors | Disable `OPENALPHA_FACTORS_ENABLED`; read Overview only |

Start backend + frontend: `./scripts/dev-up.sh` or see [README](../README.md).
