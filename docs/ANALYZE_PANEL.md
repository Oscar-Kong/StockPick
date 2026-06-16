# Analyze Panel — Business & Finance Guide

How to read and use **Workspace → Research** (single-stock underwriting). This is written for investors and operators, not developers.

**For a complete dictionary of every stat, badge, and tab field**, see **[ANALYZE_PANEL_STATS_GUIDE.md](ANALYZE_PANEL_STATS_GUIDE.md)**.

---

## Purpose

After you **scan** and add names to your **watchlist**, Analyze answers:

- Which **holding-period model** fits (days vs weeks vs years)?
- How attractive is the setup on a **0–100 composite**?
- Are **technicals, fundamentals, and data** strong enough to size a position?
- What **event risks** (earnings, valuation, filings) should change timing?

---

## Three investment sleeves

| Sleeve | Typical hold | What you are hunting |
|--------|--------------|----------------------|
| **Penny** | ~3–10 days | Short momentum, volume, tradable volatility |
| **Medium** | ~4–8 weeks | Swing: trend/breakout + RS vs market and sector |
| **Compounder** | Years | Quality growth, margins, smooth long trend, macro fit |

**Assigned sleeve** — the score and summary use one model (often medium unless the watchlist tags another).

**Bucket fit (three tiles)** — same stock scored under all three sleeves; use when the name sits between styles.

**Outside typical filters** — still shows a score, but the summary warns the name **fails** that sleeve’s normal universe rules.

---

## Headline bar

| Item | Meaning |
|------|---------|
| **Price** | Reference last price for scoring |
| **Sleeve** | Active holding-period model |
| **Score (0–100)** | Composite attractiveness for that sleeve (not a return forecast) |
| **Risk** | Sizing/diligence hint (penny often high; medium maps score to low/med/high) |

**Refresh** — re-score with today’s market and data.

---

## How the composite score is built

1. **Factors (0–100 each)** — momentum, technicals, sentiment, fundamentals, etc. (see Quant tab).
2. **Weighted blend** — each factor has an importance %; bars show **contribution**.
3. **Regime adjustment** — SPY volatility and sector strength nudge the score.
4. **Data trust** — disagreement across data vendors reduces the score.
5. **Governance (when on)** — SEC/insider/offering flags for medium & compounder.

The **headline score** can differ slightly from the sum of bars because steps 3–5 apply after the weighted average.

### Factor weights by sleeve (summary)

**Penny:** 5d momentum, volume spike, RSI, social buzz, volatility fit.

**Medium:** 20d RS vs SPY, technical setup, sector RS, quant alpha, sentiment, optional governance.

**Medium risk labels:** score ≥75 → low; &lt;50 → high.

**Compounder:** revenue/EPS consistency, ROIC/margins, 5Y smooth growth, moat proxies, macro, small quant alpha, optional governance.

---

## Technicals (sidebar)

| Metric | Interpretation |
|--------|----------------|
| **Trend** | High = above 50-day average |
| **RS vs SPY** | 50 ≈ market; above = outperforming ~20d |
| **Breakout** | High = near top of recent range |
| **% from 52w high** | Distance below trailing peak (e.g. −10% = 10% below high) |

---

## Data quality & Data tab

**Data quality %** = trust in fundamental **inputs** (P/E, cap, revenue), not “company quality.”

| Range | Action |
|-------|--------|
| 70%+ | OK for screen-level sizing |
| 40–70% | Verify key fields; score already haircut |
| &lt;40% | Do not trust fundamentals until manual check |

**Data tab** — one row per field with **confidence** (low / medium / high) after cross-vendor check.

---

## Alerts

| Theme | Why it matters |
|-------|----------------|
| Earnings soon | Event risk (~7 days) |
| Stale scan | Watchlist data &gt;24h old |
| Score drop | Large fall vs last snapshot |
| Reconcile / low data quality | Vendor disagreement |
| Valuation | Stretched price vs fundamentals |
| Governance | Offerings, insider selling, 8-K |

---

## Views (when to use each)

Current Analyze tabs (grouped **Core / Research / Workspace** in the toolbar; each tab shows a one-line hint):

| Tab | Use for |
|-----|---------|
| **Overview** | Price chart (left), v2 recommendation + position sizing (right) |
| **Score breakdown** | Factor table + contribution bars — which inputs drove the score |
| **Risk** | Volatility, liquidity, macro, event risk, risk index |
| **Diagnostics** | Return distribution stats (momentum vs mean reversion vs noise) |
| **Valuation** | DCF / peer fair value, margin of safety, sensitivity grid |
| **Backtest** | Historical rule-based strategy test (not a forecast) |
| **Similar signal** | Research-only historical analogs |
| **Report** | LLM structured memo; save to Library |
| **Notes** | Your watchlist notes |

**Navigation:** ← / → (or `[` / `]`) moves through the watchlist without leaving Analyze.

**Sidebar (desktop):** collapsible sections for technicals, quality/timing, bucket fit, signals, fundamentals — visible on all tabs.

**Mobile / narrow:** tap **Insights** to open the same sidebar in a slide-over sheet.

See [ANALYZE_PANEL_STATS_GUIDE.md](ANALYZE_PANEL_STATS_GUIDE.md) for field-by-field definitions.

**Compare** (Workspace tab) ranks 2–4 tickers quickly; **Analyze** is full underwriting for one name.

---

## Recommended workflow

1. Scan → watchlist  
2. Analyze under the sleeve matching your **actual** hold period  
3. Check bucket fit if sleeve is ambiguous  
4. Read Quant + technicals  
5. Clear data quality and alerts before size  
6. Notes / Report for documentation; Journal when you trade  

---

## Score zones (rule of thumb)

| Zone | Reading |
|------|---------|
| 75+ | Strong fit for that sleeve |
| 50–74 | Mixed — read factors; may fail hard filters |
| &lt;50 | Weak for that sleeve |

---

## Glossary

| Term | Meaning |
|------|---------|
| Composite score | 0–100 sleeve-specific attractiveness |
| Factor / signal | One scored input (momentum, sentiment, …) |
| Contribution | Factor score × weight (bar chart) |
| Relative strength | Performance vs SPY or sector ETF |
| Bucket fit | Scores under penny, medium, compounder |
| Data quality | Trust in vendor-agreed fundamentals |
| Hard filter | Minimum rules to be a “normal” candidate |

---

*Not financial advice. Model weights and thresholds may change with configuration.*
