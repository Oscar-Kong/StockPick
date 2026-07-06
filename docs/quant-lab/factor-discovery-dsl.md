# Factor Discovery — Controlled DSL (factor-dsl-v1)

Phase 2 ships a **closed, non-executable** expression language for Factor Discovery. Parsing and compilation are library-only; `FACTOR_DISCOVERY_ENABLED` remains `false`.

**Implementation:** `backend/engines/factor/discovery/`

---

## DSL version

| Constant | Value |
|----------|-------|
| `FACTOR_DSL_V1` | `factor-dsl-v1` |
| `COMPILER_VERSION` | `factor-compiler-v1` |

Future syntax changes require a new DSL version or a backward-compatible addition documented here.

---

## Public APIs

| Function | Module | Purpose |
|----------|--------|---------|
| `parse_factor_expression(source, …)` | `parser.py` | DSL text → validated `AstNode` |
| `format_factor_expression(node)` | `formatter.py` | AST → canonical DSL |
| `compile_factor_expression(expr, …)` | `compiler.py` | AST → `CompiledFactorPlan` |
| `compile_factor_definition(defn, …)` | `compiler.py` | `FactorDefinition` + metadata checks |
| `build_default_field_registry()` | `field_registry.py` | Research field whitelist |

---

## Grammar (summary)

- **Function calls:** `name(arg1, arg2, kw="value")`
- **Field references:** bare identifiers (`return_126d`) — not followed by `(`
- **Numeric literals:** finite decimals/integers only (no scientific notation, no `nan`/`inf`)
- **String literals:** only as whitelisted keyword values (policies), never as code

### Supported operators

Map 1:1 to `models/schemas_factor_discovery.py` enums:

| Category | DSL functions |
|----------|---------------|
| Unary | `abs`, `negate`, `log(invalid_policy=)`, `sign` |
| Binary | `add`, `subtract`, `multiply`, `divide(zero_policy=)`, `min`, `max` |
| Time-series | `lag`, `delta`, `pct_change`, `rolling_mean`, `rolling_std`, `rolling_min`, `rolling_max`, `rolling_sum`, `rolling_correlation(left,right,window)` |
| Cross-sectional | `rank`, `percentile_rank`, `zscore`, `winsorize(lower=,upper=)` |
| Neutralization | `sector_neutralize`, `industry_neutralize`, `market_cap_neutralize` |

**Division** always records an effective `zero_policy` (`null`, `zero`, `epsilon`).

**Log** always records `invalid_policy` (`null` → `null_on_non_positive`, `abs_log`).

**Winsorize** requires `0 <= lower < upper <= 1`; defaults `0.01` / `0.99` are stored in the AST.

### Deferred in v1

| Feature | Behavior |
|---------|----------|
| `where(...)` / `CONDITIONAL` AST | Parser rejects `where()`; compiler raises `UnsupportedNodeError` on `ConditionalNode` |

---

## Forbidden syntax

Rejected by tokenizer/parser:

- Python operators (`+`, `-`, `*`, `/`), attribute access, indexing
- Dunder / underscore identifiers, imports, lambdas, assignment
- `eval`, `exec`, `compile`, `ast.parse`, `ast.literal_eval`
- Unknown functions, unknown/duplicate keywords, positional args after keywords
- Trailing unparsed content, non-finite numbers, scientific notation
- Windows/periods that are non-integer, ≤ 0, or above configured limits

---

## Parser limits

Defaults in `FactorDslLimits` (`limits.py`):

| Limit | Default |
|-------|---------|
| Max source length | 16,384 chars |
| Max tokens | 2,048 |
| Max AST nodes | 256 |
| Max AST depth | 32 |
| Max identifier length | 128 |
| Max numeric literal length | 64 |
| Max rolling window | 2,520 sessions |
| Max lag/periods | 2,520 sessions |

---

## Field registry

`FactorFieldRegistry` (`field_registry.py`) validates fields at **compile** time (not parse time).

| Class | Error |
|-------|-------|
| Unknown identifier | `UnknownFieldError` |
| Outcome / label field | `ForbiddenFieldError` |
| Registered but unavailable | `FactorCompileError` (`unavailable_field`) |
| Policy-incompatible (e.g. `close` under adjusted policy) | `FactorCompileError` (`policy_incompatible_field`) |

### Research-safe fields (fixtures)

`adjusted_close`, `market_cap`, `free_cash_flow`, `return_126d`, `return_1d`, `relative_volume` — derived panel fields emit compiler **warnings** (Phase 3 must materialize from pinned sources).

### Unavailable (registered, not compilable)

`operating_cash_flow_growth`, `gross_margin_volatility`

### Forbidden outcome examples

`forward_return_5d`, `forward_return_21d`, `future_return`, `target_return`

---

## Data-source policy

`research_adjusted_daily_v1` (`FactorDataSourcePolicy`):

- Adjusted prices required
- Single provider per run (pinned in experiment config — Phase 3)
- Mixed adjusted/unadjusted series forbidden

Compilation checks field metadata against the selected policy; no data loading in Phase 2.

---

## CompiledFactorPlan

Frozen Pydantic model (`compiler.py`) — **not executable**. Includes:

- Canonical AST + canonical DSL + `formula_hash_value`
- `plan_hash_value` (formula + registry version + policy + compiler version + fields)
- Required fields, lookback/lag, cross-sectional/time-series/neutralization/PIT flags
- Operator set, warnings, `unsupported_capabilities: ["CONDITIONAL"]`

### formula_hash vs plan_hash

| Hash | Scope |
|------|-------|
| `formula_hash()` | Mathematical formula semantics only (AST) |
| `plan_hash()` | Formula + compilation context (registry version, policy, compiler version, field list) |

---

## Lookback convention

Conservative **session** counts (inclusive window stacking):

| Operator | Required prior sessions |
|----------|-------------------------|
| `lag` / `delta` / `pct_change` | `child_lookback + periods` |
| `rolling_*` (except correlation) | `child_lookback + window` |
| `rolling_correlation` | `max(left_lookback, right_lookback) + window` |

Examples:

- `pct_change(price, 21)` → 21
- `rolling_mean(pct_change(price, 21), 63)` → 84
- `lag(rolling_mean(price, 63), 21)` → 84

---

## Golden fixtures

| JSON | DSL |
|------|-----|
| `simple_field_rank.json` | `simple_field_rank.dsl` |
| `lagged_momentum.json` | `lagged_momentum.dsl` |
| `safe_division_fcf_mcap.json` | `safe_division_fcf_mcap.dsl` |
| `sector_neutral_composite.json` | `sector_neutral_composite.dsl` |
| `nested_rolling.json` | `nested_rolling.dsl` |

Tests verify `DSL → parse → formula_hash` matches JSON fixtures and `JSON → format → parse` round-trip.

---

## Phase 2 non-goals

No factor execution, pandas eval, data loading, IC/backtests, LLM, DB persistence, UI, Scan adapter, or enabling `FACTOR_DISCOVERY_ENABLED`.

**Successful compilation does not imply** profitability, PIT safety in production, or Scan eligibility.

---

## Phase 1 contract corrections (Phase 2)

| Item | Change |
|------|--------|
| Sealed-test duration | `min_sealed_test_sessions` → **`min_sealed_test_days`** (calendar days; session counting deferred to calendar-aware validation) |
| Embargo | `embargo_sessions` → **`embargo_days`** |
| Rolling correlation | `RollingNode.right` required when `op == ROLLING_CORRELATION`; forbidden for other rolling ops |
| Winsorize | `winsorize_lower` / `winsorize_upper` replace `winsorize_limit` |
| Default policy id | `research_adjusted_daily_v1` |

---

## Phase 3 next steps

1. Panel execution engine consuming `CompiledFactorPlan`
2. Pinned price-provider loading per `research_adjusted_daily_v1`
3. Fundamental publication-lag resolution for PIT fields
4. Discovery / validation / sealed-test experiment runner
5. Lifecycle service promoting `DRAFT → COMPILED` explicitly
