# Factor Discovery Results UI

Validation artifacts in the workspace are **research evidence**, not trade recommendations.

## Presentation rules

Never display Buy / Sell / Production ready / Validated alpha as affirmative states.

Always show:

- Discovery vs validation Rank IC (not sealed metrics)
- Gross vs net returns and transaction costs
- Walk-forward fold table and pass rate
- Multiple-testing family size and correction method
- Limitations panel
- Sealed status: **unopened**

## Sections (target layout)

1. Summary — factor, formula, validation status, promising flag, key failures
2. Predictive signal — Rank IC, coverage, robust p-value
3. Quantile behavior — monotonicity, spread, turnover
4. Cost and turnover — gross/net, drawdown
5. Walk-forward — fold table, worst fold
6. Robustness — year/sector buckets when PIT-safe
7. Redundancy — correlation vs benchmark (missing data ≠ low correlation)
8. Multiple testing — family size at evaluation
9. Limitations — always visible

Phase 8B ships session-detail experiment links; full artifact drawer expands in a follow-up when run detail API is wired to persisted validation JSON.

## Charts

Use existing chart components where series exist in artifacts. Do not plot sealed periods. Do not truncate axes to exaggerate performance.
