# Analyze Panel — Stats & Metrics Guide

**Where:** Research (`/workspace`) → select a symbol.

This guide explains **every number, badge, and section** in the Analyze panel: what it measures, how to read it, and what it does *not* mean.

For workflow (“when to use which section”), see [ANALYZE_PANEL.md](ANALYZE_PANEL.md). For Quant Lab validation (factor IC, walk-forward), see [QUANT_LAB.md](QUANT_LAB.md).

---

## 1. How the panel is laid out

```
┌─────────────────────────────────────────────────────────────┐
│  TOOLBAR: price · sleeve · score · source · risk · sections │
├─────────────────────────────────────────────────────────────┤
│  META: data quality badge · alerts · freshness              │
├──────────────────────────────┬──────────────────────────────┤
│  MAIN (left)                 │  SIDEBAR (right, desktop)    │
│  Overview / Drivers / Risk / │  Technicals, bucket fit,     │
│  Evidence / Research         │  signals, fundamentals       │
└──────────────────────────────┴──────────────────────────────┘
```

- **Toolbar** — headline identity: price, sleeve, score, risk, score engine badge.
- **Meta row** — data trust, event warnings, and cache freshness before you read details.
- **Five sections** — Overview (decision brief), Drivers, Risk, Evidence, Research.
- **Sidebar** — same key stats on every section (technicals, bucket fit, signal weights).

**Loading:** snapshot (cached) paints first; `/analyze/{symbol}/core` refreshes base + v2 from one shared enrich. The watchlist rail never blocks symbol analysis.

**Refresh** re-runs scoring with current market data. **Language switch** only translates labels; it does not re-score (see [USER_GUIDE.md](USER_GUIDE.md) §8).

---

## 2. Two score engines (read the badge)

| Badge | Engine | What it means |
|-------|--------|----------------|
| **ScoringEngine v2** | Quant factor model | Headline score from normalized factors, regime weights, risk deductions. Preferred when enabled. |
| **Legacy screener** | Rule-based screener | Original weighted signals from the scan pipeline. Used when v2 is off or unavailable. |

When both exist, you may see:

- **Score** — primary (usually v2).
- **Legacy** chip — old screener score for comparison.
- **Parity delta** (Score tab) — v2 minus legacy; large gaps mean the models disagree.

Neither score is a **return forecast**. Both are **0–100 attractiveness** for the active **sleeve** (holding-period model).

---

## 3. Toolbar stats

| Stat | Range / format | Meaning |
|------|----------------|---------|
| **Price** | USD | Last price used when the analyze run completed. |
| **Sleeve** | Penny / Medium / Compounder | Which holding-period model drives scoring. Often matches watchlist tag or auto-assignment. |
| **Score** | 0–100 | Composite attractiveness for that sleeve. Higher = stronger fit under the model, not “will go up X%.” |
| **Risk** | Low / Medium / High | Position-sizing and diligence hint. Penny names are often high risk regardless of score. |
| **Market regime** (v2 Overview) | e.g. `low_vol`, `risk_off` | Broad market state used to pick dynamic factor weights. |

### Score zones (rule of thumb)

| Score | Reading |
|-------|---------|
| **75+** | Strong sleeve fit — worth full diligence. |
| **50–74** | Mixed — read factor breakdown; may fail hard filters. |
| **<50** | Weak for this sleeve — check bucket fit for a better match. |

---

## 4. Meta row: data quality & alerts

### Data quality badge

**Data quality %** = trust in **fundamental inputs** (P/E, market cap, revenue, etc.), not “business quality.”

| Range | Action |
|-------|--------|
| **70%+** | Reasonable for screen-level decisions. |
| **40–70%** | Verify key fields manually; score may already be reduced. |
| **<40%** | Do not rely on valuation/fundamental factors until you confirm data. |

Built from cross-vendor reconciliation: when providers disagree, confidence drops.

### Alerts

Pills with severity (high / medium / low). Common types:

| Theme | Meaning |
|-------|---------|
| **Earnings soon** | Report within ~7 days — event risk. |
| **Stale scan / data** | Watchlist or quote data may be old. |
| **Score drop** | Large fall vs previous snapshot. |
| **Reconcile / low DQ** | Vendor disagreement on fundamentals. |
| **Valuation** | Price stretched vs model or peers. |
| **Governance** | Offerings, insider activity, filings (when enabled). |

---

## 5. Sidebar (visible on every tab, desktop)

### Technicals

| Stat | Typical range | How to read it |
|------|---------------|----------------|
| **Trend** | 0–100 | Strength of trend vs 50-day average. Higher = more bullish structure. |
| **RS vs SPY** | ~0–100+ | 20-day relative strength vs S&P 500. ~50 ≈ market; above = outperforming. |
| **Breakout** | 0–100 | Proximity to top of recent range. High = near breakout / extension. |
| **% from 52w high** | Negative % | Distance below trailing 52-week peak (e.g. −15% = 15% below high). |

### Quality & timing

| Stat | Meaning |
|------|---------|
| **Data quality** | Same % as meta badge. |
| **Earnings** | Days until next earnings date. |
| **Valuation badges** | Warnings (e.g. stretched P/E, earnings soon). |

### Bucket fit (three tiles)

Same symbol scored under **Penny**, **Medium**, and **Compounder** sleeves. Highlighted tile = **assigned** sleeve.

Use when you are unsure which horizon fits: a name may score 80 as Medium but 45 as Compounder.

Each tile shows a **0–100 score** for that sleeve’s rules and factor mix.

### Signal weights / factor attribution

List of **signals** (legacy) or **factors** (v2) with:

| Field | Meaning |
|-------|---------|
| **Name** | Factor or signal label (e.g. momentum, RS vs SPY). |
| **Contribution** | Points added to the composite (bar length). Top drivers first. |
| **Value** | Raw normalized factor score (0–100 scale) before weighting. |

**Contribution** = how much this input moved the headline score. **Value** = how strong the input was on its own.

### Fundamentals (when available)

| Field | Meaning |
|-------|---------|
| **Sector / Industry** | GICS-style classification. |
| **Market cap** | Reconciled market capitalization. |
| **P/E** | Trailing or reconciled price/earnings. |
| **Revenue growth** | YoY or TTM growth rate. |
| **Profit margins** | Net or operating margin. |

Missing fields usually mean low data confidence or non-applicable (e.g. negative earnings).

---

## 6. Tab: Overview

Primary decision surface when v2 is enabled.

### v2 score block

Repeats headline **score**, **ScoringEngine v2** badge, and **market regime**.

### Recommendation block (v2)

| Stat | Meaning |
|------|---------|
| **Recommendation** | `strong_buy` → `avoid` / `high_risk_no_decision`. Model action label, not an order. |
| **Confidence** | 0–100 — internal confidence in the recommendation. |
| **Alpha pillar** | Momentum/quality/technical strength sub-score. |
| **Valuation pillar** | Cheap vs expensive sub-score. |
| **Catalyst pillar** | Events, revisions, near-term drivers. |
| **Time horizon** | Expected hold window (days) plus upside/downside % bands. |
| **Data confidence** | Separate from data quality % — gates strong buy labels. |
| **Gates** | Hard blocks (e.g. insufficient data) that cap the recommendation. |
| **Bull / Bear case** | Short narrative scenarios. |

### Valuation block (v2)

| Stat | Meaning |
|------|---------|
| **Verdict** | cheap / fair / expensive / extremely_expensive |
| **DCF fair value** | Discounted cash flow mid estimate ($). |
| **Peer fair value** | Relative to comparable multiples ($). |
| **Bull / Bear price** | Optimistic / pessimistic DCF ($). |
| **Margin of safety (MoS)** | % cushion vs fair value (positive = below fair). |
| **Implied growth** | Reverse-DCF: growth rate market implies at current price. |
| **Sensitivity grid** | Fair value across WACC (rows) × terminal growth (columns). |

### Earnings setup (v2)

| Stat | Meaning |
|------|---------|
| **Next earnings** | Days until report. |
| **EPS revision 30d** | Analyst EPS estimate change over 30 days (%). |
| **Revenue revision 30d** | Same for revenue estimates. |
| **Up / Down** | Analyst upgrade vs downgrade count. |
| **Drift 5d / 20d** | Average post-earnings price drift from history (%). |
| **Catalyst score** | Composite near-term event strength. |

### Similar signal (v2, research-only)

Historical analogs when past setups looked like today’s factor profile.

| Stat | Meaning |
|------|---------|
| **Sample N** | Number of historical matches. |
| **Avg return** | Mean forward return over the horizon (%). |
| **Win rate** | % of analogs with positive forward return. |
| **Top analogs** | Example symbol + date + that episode’s return. |

Marked **Research only** — context, not a live trade signal. Validate in [Quant Lab](QUANT_LAB.md).

### Position sizing (v2)

| Stat | Meaning |
|------|---------|
| **Recommended weight** | Suggested portfolio % for this name. |
| **Max sleeve weight** | Hard cap for the sleeve (penny lower than compounder). |
| **Stop loss %** | Suggested stop distance below entry. |
| **Conviction** | 0–100 — model conviction after risk and data quality. |
| **Rationale** | Text explaining size constraints. |

### Portfolio impact (v2, when holdings loaded)

Beta impact and correlation vs your tracked portfolio — diversification check, not a score component.

### Price chart

~6 months of daily **OHLC** closes. Visual sanity check; not used directly in the composite score.

### Legacy fallback

If v2 is unavailable, Overview shows a **text summary** from the legacy screener instead of Round 2 blocks.

---

## 7. Tab: Score breakdown

### Factor attribution table (v2)

| Column | Meaning |
|--------|---------|
| **Field** | Factor display name. |
| **Score** | Normalized factor reading (0–100). |
| **Weight** | Current model weight for this sleeve/regime. |
| **Contribution** | Signed points added to composite (green + / red −). |

### Bar chart (legacy or v2-mapped signals)

Horizontal bars = **contribution** per signal. Tooltip shows raw **value** and **weight**.

Sum of contributions ≈ headline score before regime/risk adjustments.

---

## 8. Tab: Risk

Loaded on demand. Unified risk view (v2).

### Headline risk metrics

| Stat | Meaning |
|------|---------|
| **Risk index** | 0–100 composite risk (higher = riskier). ≥65 red, ≥40 amber. |
| **Safety score** | Inverse framing — higher = safer. |
| **Deduction pts** | Points subtracted from the composite score for risk. |

### Volatility (when sufficient data)

| Stat | Meaning |
|------|---------|
| **Realized vol** | Historical annualized volatility. |
| **EWMA vol** | Exponentially weighted (reacts faster to recent moves). |
| **Downside vol** | Volatility of negative returns only. |
| **VaR** | Value at Risk — typical worst daily loss at a confidence level. |
| **Expected shortfall** | Average loss in the tail beyond VaR. |
| **Vol regime** | e.g. low / normal / elevated — bucket for current vol state. |

### Other sections

| Section | Content |
|---------|---------|
| **Macro** | Rates, VIX, sector stress lines affecting risk. |
| **Liquidity** | Thin volume, wide spreads, ADV warnings. |
| **Event risk** | Earnings, splits, corporate actions. |
| **Alerts** | Risk-specific messages overlapping meta alerts. |

---

## 9. Tab: Diagnostics

Statistical health of **price returns** (research context). Loaded on demand.

| Stat | Meaning |
|------|---------|
| **Interpretation badge** | `possible momentum`, `possible mean reversion`, `mostly noise`, `high tail risk`, or `insufficient data`. |
| **Observations** | Count of return bars and price bars used. |
| **Mean return** | Average daily (or bar) return. |
| **Ann. vol** | Annualized volatility of returns. |
| **Skewness** | Asymmetry of return distribution (negative = left tail). |
| **Excess kurtosis** | Fat tails vs normal (>0 = more extreme moves). |
| **Autocorr lag-1** | Today’s return correlated with yesterday (+ momentum, − mean reversion). |
| **Stationarity (ADF)** | Augmented Dickey-Fuller test — low p-value suggests mean-reverting series. |
| **Jarque-Bera** | Normality test on returns — low p-value = non-normal tails. |

Use to sanity-check whether a **momentum vs mean-reversion** story matches the data. Not a buy/sell signal.

---

## 10. Tab: Valuation

Dedicated view of the v2 **ValuationBlock** (same fields as Overview valuation section). Empty if v2 valuation engine is disabled or data is insufficient.

---

## 11. Tab: Backtest

Rule-based **historical simulation** on this symbol and sleeve:

| Concept | Meaning |
|---------|---------|
| **Horizon** | Lookback window (e.g. 1y, 3y). |
| **Hold days / stop / target** | Entry rule parameters. |
| **Total return / Sharpe** | Past performance of the rule — **not** predictive. |
| **Sweep** | Tests many parameter combos — watch overfitting; see Quant Lab walk-forward. |

Backtest uses costs when institutional mode is on. Past backtest ≠ future results.

---

## 12. Tab: Similar signal

Same **SimilarSignalBlock** as Overview (research-only historical analogs). Shown separately for users who want analog stats without scrolling Overview.

---

## 13. Tab: Report

| Action | Meaning |
|--------|---------|
| **Generate narrative** | LLM structured memo (v2 schema when enabled). Does **not** override the quant score. |
| **Save report** | Persists to Library for audit trail. |

Report sections may repeat score, factors, valuation, and risk in prose. Language follows backend/LLM settings, not necessarily UI language.

---

## 14. Tab: Notes

Personal **watchlist notes** for this symbol. Saved to backend; not used in scoring.

---

## 15. Three sleeves — what changes the stats

| Sleeve | Typical hold | Score emphasizes |
|--------|--------------|------------------|
| **Penny** | Days – ~2 weeks | Short momentum, volume spike, RSI, volatility fit |
| **Medium** | Weeks – months | RS vs SPY, breakout, sector RS, sentiment, optional governance |
| **Compounder** | Years | Revenue/EPS quality, margins, smooth growth, macro, governance |

**Medium risk mapping (legacy):** score ≥75 → low risk label; <50 → high.

Hard filters may exclude names from a sleeve’s normal universe even if a score is shown.

---

## 16. Common mistakes

| Mistake | Reality |
|---------|---------|
| “Score 85 = +85% return” | Score is relative attractiveness, not a price target. |
| “High data quality = good company” | It means **vendor agreement**, not investment quality. |
| “Similar signal win rate = edge” | Small sample + research-only; validate offline. |
| “Backtest Sharpe = live Sharpe” | Overfitting, costs, and regime change aren’t fully captured. |
| “Recommendation = auto trade” | It’s a model label; you still size and time the entry. |

---

## 17. Quick reference glossary

| Term | Definition |
|------|------------|
| **Composite score** | 0–100 sleeve-specific attractiveness |
| **Factor / signal** | One scored input (momentum, valuation, etc.) |
| **Contribution** | Points a factor adds to the composite |
| **Weight** | Model importance of a factor (sums ~1 across factors) |
| **Sleeve / bucket** | Penny, Medium, or Compounder horizon |
| **Bucket fit** | Scores under all three sleeves |
| **Regime** | Market state adjusting factor weights |
| **Parity delta** | v2 score minus legacy score |
| **IC** (Quant Lab) | Factor predictive power — not shown in Analyze, but validates factors |

---

## 18. Related routes

| Route | Relationship |
|-------|--------------|
| **Screen** | Where candidates get initial scores before Analyze |
| **Quant Lab** | Validates whether factors and weights are trustworthy |
| **Portfolio** | Basket-level risk and optimization |

---

*Not financial advice. Thresholds and factor sets depend on backend configuration (`SCORE_ENGINE_V2_ENABLED`, sleeve factor packs, etc.).*
