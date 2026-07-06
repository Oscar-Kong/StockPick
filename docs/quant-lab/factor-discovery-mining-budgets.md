# Factor Discovery — mining budgets

Immutable budget records are persisted on session authorization (`budget_policy_json`, `budget_hash`). Runtime increases are forbidden; cancel and create a new session to change limits.

## Policy model

`FactorMiningBudgetPolicy` (`mining/models.py`, version `factor-mining-v1`):

| Limit | Default | Enforced before |
|-------|---------|-----------------|
| `max_hypothesis_generation_calls` | 3 | LLM hypothesis step |
| `max_hypotheses` | 5 | Candidate persistence |
| `max_hypotheses_approved_for_translation` | 3 | Formula translation |
| `max_total_formula_candidates` | 10 | Formula translation |
| `max_formulas_reaching_evaluation` | 10 (env override) | Experiment launch |
| `max_revision_rounds_per_lineage` | 2 (env override) | Revision approval |
| `max_total_revision_attempts` | 6 | Revision step |
| `max_llm_interactions` | 50 | Each LLM call |
| `max_validation_exposures_per_lineage` | 2 (env override) | Critique context |
| `max_validation_critiques_per_formula` | 1 | Per-formula critique |
| `max_ast_nodes` / `max_formula_depth` / `max_lookback` | 32 / 8 / 252 | Compile + revision |

## Enforcement

`budget_service.check_budget()` runs **before** side effects. `reserve_usage()` persists counters in `usage_json` on the session row.

Statistical hypothesis family size comes from the research-family attempt ledger — duplicate formula hashes do not inflate distinct-formula counts.

## Terminal state

`BUDGET_EXHAUSTED` is terminal for the session. Summary includes `budget_used` via `FactorMiningSummaryService`.

## Env defaults

```env
FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_REVISION_ROUNDS=2
FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_EVALUATED_FORMULAS=10
FACTOR_DISCOVERY_LOOP_DEFAULT_MAX_VALIDATION_EXPOSURES=2
```
