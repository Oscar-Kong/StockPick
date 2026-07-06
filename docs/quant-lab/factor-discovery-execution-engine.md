# Factor Discovery — Deterministic Execution Engine (Phase 3)

Phase 3 executes a `CompiledFactorPlan` against a **caller-supplied** `FactorInputPanel`. No live data, no database, no experiment orchestration.

**Package:** `backend/engines/factor/discovery/`

---

## Public API

```python
from engines.factor.discovery import compute_factor_panel, FactorInputPanel, FactorExecutionConfig

result = compute_factor_panel(plan, panel)
```

---

## Input panel contract

`FactorInputPanel` (`panel_models.py`):

| Field | Requirement |
|-------|-------------|
| `frame` | `DataFrame` with `MultiIndex(date, symbol)`, sorted ascending |
| `eligibility` | `bool` Series aligned to frame index |
| `data_source_policy_id` | Must match `CompiledFactorPlan.data_source_policy_id` |
| `provider_id` | Pinned provider or fixture identifier |
| `prices_adjusted` | `True` when plan requires adjusted prices |
| `field_provenance` | Per-field `PanelFieldProvenance` with PIT state |

### Canonical session grid (Phase 4 hardening)

Before execution, `compute_factor_panel()` calls `align_panel_to_canonical_sessions()`:

- Union of all panel dates defines `CanonicalSessionCalendar`
- Full `(session × symbol)` grid; missing observations are NaN rows (no forward-fill)
- Time-series operators (`lag`, `pct_change`, rolling) therefore use **canonical session counts**
- Validation outcomes use the same calendar — see [validation engine](./factor-discovery-validation-engine.md)

Validation rejects: duplicate index rows, outcome fields, non-finite numerics, policy mismatch, mixed adjusted/unadjusted metadata, empty panels.

---

## Lookback convention

**Conservative stacking (Phase 2 retained):** `required_history_sessions` = child lookback + operator window.

Examples:

- `lag(x, 1)` → 1 prior session
- `rolling_mean(x, 5)` → 5 sessions (full window including current row)
- `rolling_mean(pct_change(x, 21), 63)` → 84 sessions

Execution uses `rolling_min_periods_policy=full_window` by default (no partial windows).

---

## Primitive vs derived fields

| Type | Examples | Source |
|------|----------|--------|
| Primitive | `adjusted_close`, `volume`, `market_cap`, `free_cash_flow` | Panel columns + provenance |
| Derived | `return_1d`, `return_126d`, `relative_volume` | `derived_fields.py` registry |

Derived returns use `adjusted_close.pct_change(n)` per symbol (no future rows).

`return_126d` requires ≥126 sessions of history per symbol.

---

## PIT fundamentals

`free_cash_flow` must be supplied PIT-aligned with `PitProvenanceState.VERIFIED_PIT` and `publication_lag_sessions_applied` recorded in provenance. Values before effective publication+lag must be `NaN`.

---

## Operator semantics

- **Time-series:** per-symbol, ascending date, no cross-symbol leakage
- **Cross-sectional:** per-date across eligible symbols only
  - `RANK` / `PERCENTILE_RANK`: average ranks, normalized to [0, 1]
  - `ZSCORE`: population std (`ddof=0`); zero variance → `NaN` (configurable)
  - `WINSORIZE`: quantile clip per date using AST bounds
- **Neutralization:** AST order preserved
  - Sector/industry: group demean per date
  - Market cap: OLS residual vs `log(market_cap)` per date

---

## Hashes

| Hash | Scope |
|------|-------|
| `formula_hash` | AST semantics only |
| `plan_hash` | Formula + registry + policy + compiler |
| `panel_content_hash` | Panel data + eligibility + provenance |
| `execution_hash` | Plan + panel + execution config + executor version |

---

## Formula hash and winsorize scrubbing

`canonical_ast_payload()` removes `winsorize_lower` / `winsorize_upper` from **non-WINSORIZE** cross-section nodes only. These defaults are non-semantic for `RANK`, `ZSCORE`, etc. WINSORIZE nodes always include bounds in the formula hash.

---

## Typed errors

`execution_errors.py`: `InvalidInputPanelError`, `PanelPolicyMismatchError`, `PointInTimeViolationError`, `AdjustedPriceViolationError`, `MissingFieldDataError`, `OperatorExecutionError`, `NeutralizationError`, `DerivedFieldError`, etc.

---

## Phase 3 non-goals

No experiment launch, IC, walk-forward, lifecycle promotion, DB persistence, LLM, Scan, or live data fetch.

> Successful execution means the formula was calculated consistently. It does not mean the factor is predictive, profitable, or Scan-eligible.

---

## Phase 4 prerequisites

1. Factor discovery experiment service with discovery/validation/sealed-test periods
2. Pinned provider loading (not fixture panels)
3. Lifecycle service (`DRAFT → COMPILED`)
4. IC / validation pipeline
