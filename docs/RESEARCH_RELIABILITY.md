# Research Reliability

Quant Lab **Research Reliability** is a client-side validation layer that scores whether each tab’s evidence is trustworthy enough to inform future model or scoring changes. It does **not** change live scan rankings.

## Status levels

| Status | Meaning |
|--------|---------|
| **Reliable** | Score ≥ 80, no warnings or blockers, data fresh |
| **Usable with warnings** | Evidence exists but caveats apply — review warnings before acting |
| **Weak evidence** | Thin sample, poor metrics, or heavy research gaps |
| **Insufficient data** | Missing or empty inputs — do not draw conclusions |
| **Stale** | Persisted evidence is older than freshness thresholds (e.g. IC > 7 days) |
| **Disabled** | Backend feature flag off (e.g. `SCORE_ENGINE_V2_ENABLED`) |
| **Research only** | Offline research (walk-forward, pairs) — never auto-applied to scans |

Each tab shows a **0–100 score**, top reasons, warnings, blockers, and a **suggested next action**.

## How scores are computed

Implementation: `frontend/src/lib/researchReliability.ts`

### Factor Performance

Inputs: IC `as_of_date` freshness, factor count, average `sample_n`, mean IC, horizon coverage.

- Stale IC → **stale** status
- Empty factors → **insufficient_data**
- Strong fresh IC across ≥5 factors → **reliable**

**Factor lifecycle** (per factor row):

| Badge | Criteria (primary horizon) |
|-------|----------------------------|
| **Promote** | IC ≥ 0.05, n ≥ 100, IC panel fresh |
| **Keep** | IC ≥ 0.02, adequate sample |
| **Watch** | IC ≥ 0, stale IC, or borderline sample |
| **Retire** | IC < 0 with adequate sample |
| **Insufficient evidence** | n < 30 or missing IC |

### Walk-Forward

Inputs: `periods_scored`, rebalance windows, horizons, aggregate rank IC / hit rate / spread, run staleness.

Always capped as **research only** — walk-forward validates history; it does not prove future edge.

**Overfitting warnings** (also listed in reliability warnings):

- Too few windows or scored periods
- No transaction costs modeled
- No purged / embargo cross-validation (CPCV not implemented)
- No deflated Sharpe / **PBO not implemented** (`pbo_available: false`)
- Result reflects a single best run, not a trial distribution

See [Why walk-forward alone can overfit](#why-walk-forward-alone-can-overfit).

### Prediction Outcomes

Inputs: resolved vs unresolved counts, outcome age, `mean_prediction_error_pct`, missing realized returns.

### Pairs Trading

Inputs: symbol count, cointegrated pairs, p-values / statsmodels availability, observation length.

Always **research only** — pairs are not mixed into scan rankings.

### Data Quality

Inputs: Quant Health overall + sections, scheduler enabled, failed job count, stale scan/IC hints from health sections.

### Model Admin

Inputs: v2 version loaded, factor catalog, dynamic weights flag, audit events, per-panel load errors.

## Evidence → action boundary

Component: `frontend/src/components/product/EvidenceToActionBoundary.tsx`

> Quant Lab validates the model. It does not change live scan rankings. To affect future scans, research evidence must be reviewed and applied through an explicit model or weight change.

- No Quant Lab UI **auto-applies** weights or scoring changes
- `ApplyChangesNotice` / `ApplyChangesConfirm` gate any future apply actions behind explicit confirmation

## Why walk-forward alone can overfit

Walk-forward backtests often look strong because:

1. **Multiple configurations** — trying many date ranges, horizons, or sleeves and keeping the best run inflates apparent Sharpe (multiple-testing bias).
2. **No transaction costs** — turnover and spreads erode paper returns.
3. **Leakage** — without purged k-fold or embargo (CPCV), labels can leak across train/test splits.
4. **Single best run** — one saved run is a point estimate, not a distribution.

**Not implemented yet** (placeholders warn in UI):

- **PBO** (Probability of Backtest Overfitting)
- **CPCV** (Combinatorial Purged Cross-Validation)
- **Deflated Sharpe** ratio adjustment
- Trial count / config search metadata from backend

### Model Monitor (Phase 6–7)

Aggregates factor health, prediction calibration readiness, data integrity blockers, research job history, and **evidence review** queue. Integrity blockers are listed explicitly — they never produce a positive score modifier.

Server-side **decision boundary** (`backend/services/research_decision_boundary.py`):

| Setting | Default | Effect |
|---------|---------|--------|
| `RESEARCH_MAX_ORDINARY_MODIFIER` | `0` | Supporting evidence does not change live scores |
| Major / integrity impacts | gated | Require evidence review before any modifier |

Audit events: `research_evidence_consumed` when boundary is invoked with `audit=True`.

## What Research Reliability is not

- Not a trading signal or scan rank
- Not a substitute for institutional-grade backtest hygiene
- Not persisted server-side for tab cards (recomputed on render); server persists run-level `evidence_impact` on the unified index

## Related docs

- [Quant Lab](./QUANT_LAB.md)
- [Quant Lab Redesign Final Report](./QUANT_LAB_REDESIGN_FINAL_REPORT.md)
- [Research Reliability verification](./RESEARCH_RELIABILITY_VERIFICATION.md)
