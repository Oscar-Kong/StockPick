# Factor Discovery — Validation Engine (Phase 4)

Deterministic research validation on **already-executed** factor panels. Does not parse DSL, modify formulas, persist registry rows, or connect to Scan.

> **Passing Phase 4 validation does not authorize paper trading, production Scan use, or lifecycle promotion.** It means the frozen factor passed the configured research tests on the supplied data.

## Entry point

```python
from engines.factor.discovery.validation_engine import validate_factor_execution

artifact = validate_factor_execution(
    plan=compiled_plan,
    execution_result=execution_result,
    input_panel=input_panel,
    period_split=discovery_period_split,
    validation_config=config,
    factor_direction=FactorDirection.HIGHER_IS_BETTER,
    sealed_test_access=None,  # explicit SealedTestAccess required to open sealed test
)
```

Module: `backend/engines/factor/discovery/validation_engine.py`

## Canonical session semantics

- `CanonicalSessionCalendar` (`sessions.py`) derives ordered sessions from the panel union calendar.
- `align_panel_to_canonical_sessions()` reindexes to full `(session × symbol)` grid; missing rows remain NaN (no forward-fill).
- Executor aligns panels before operator execution so `lag(x, n)` means **n canonical sessions**, not n sparse observations.
- Outcomes use the same calendar: horizon `h` = `h` sessions forward on the canonical index.

## Forward outcomes

Contract: `FactorOutcomePanel` (`outcomes.py`).

Convention (default `execution_timing=next_session`):

```text
score_date = session t
entry_price = adjusted_close[t + 1]
exit_price  = adjusted_close[t + 1 + h]
forward_return_h = exit / entry - 1
```

- Eligibility at score date `t` only; future eligibility ignored.
- Missing horizon-end price → missing outcome (no jump to later dates).
- Outcomes never added to executable input panel or field registry.

## Period resolution

| Concept | Type | Role |
|---------|------|------|
| Research intent | `DiscoveryPeriodSplit` | Calendar-date boundaries |
| Runtime sessions | `ResolvedResearchPeriods` | Actual panel sessions per role |

`resolve_research_periods()` maps split dates onto canonical sessions; embargo dates excluded.

## Score orientation

`HIGHER_IS_BETTER` → oriented score = raw score  
`LOWER_IS_BETTER` → oriented score = `-raw_score`

IC, quantiles, and portfolio simulation use oriented scores. Execution result is not mutated.

## Metrics (reuse)

| Metric | Source |
|--------|--------|
| Per-date Pearson / Rank IC | `walk_forward_research_service.cross_section_metrics()` |
| Quantile breakdown | `scan_evaluation_metrics.score_decile_breakdown()` |
| Turnover | `walk_forward_research_service.turnover_rate()` (one-way) |
| Sharpe / drawdown | `engines/backtest/metrics.py` |

Primary IC is mean of **per-date** cross-sectional Rank IC, not a single pooled correlation.

## Monotonicity

- `monotonicity_spearman_mean`: Spearman correlation between quantile index and mean quantile return (per date, averaged).
- `extreme_order_correct_pct`: fraction of dates where top-minus-bottom spread > 0.

## Portfolio validation

Research-only long-only top-quantile simulation (`portfolio_validation.py`):

- Rebalance every `rebalance_every_sessions`
- Equal weight with `max_position_weight` cap
- Transaction cost: `one_way_cost_bps × turnover` per rebalance (one-way convention)
- Gross and net returns reported

## Walk-forward

`walk_forward.py` — expanding or rolling folds over discovery+validation sessions only. Sealed test excluded from fold tuning. Formula frozen across folds.

## Robustness

Deterministic slices: calendar year, sector (PIT column), market-cap bucket. Slices below minimum sample → `INSUFFICIENT_DATA`.

## Statistical limitations

- Overlapping horizons flagged in `limitations`.
- Naive t-stat on IC series labeled in metrics (`naive_t_stat_note`).
- Bonferroni / Benjamini–Hochberg when `declared_hypothesis_family_size` supplied; otherwise `UNAVAILABLE`.

## Sealed test

Without `SealedTestAccess`: metadata only (`SEALED`), **no sealed metrics computed**.

`SealedTestAccess` requires `approval_reference`, matching `expected_formula_hash` and `expected_plan_hash`.

Phase 4 cannot enforce global one-time access across processes — Phase 5 must persist receipts.

## Validation artifact

`FactorValidationArtifact` — JSON-serializable (`validation_models.py`). Includes hashes:

- `validation_config_hash`
- `outcome_panel_hashes` per horizon
- `period_resolution_hash`
- `validation_artifact_hash`

## Phase 4 non-goals

- DB migrations, registry persistence, experiment launch, LLM, UI, Scan adapter, lifecycle promotion
- `FACTOR_DISCOVERY_ENABLED` remains `false`

## Phase 5 prerequisites

1. Persist `FactorValidationArtifact` + sealed-test receipts
2. Experiment ledger with hypothesis-family size for multiple-testing
3. Factor registry migration and lifecycle transitions
4. Public experiment launch wiring
