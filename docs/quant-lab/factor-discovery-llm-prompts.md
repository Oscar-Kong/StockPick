# Factor Discovery — LLM Prompt Templates

Versioned templates in `backend/services/factor_discovery/llm/prompt_registry.py`.

| Template ID | Version | Operation |
|-------------|---------|-----------|
| `factor_research_request_normalizer_v1` | 1.0.0 | Request normalization |
| `factor_hypothesis_generator_v1` | 1.0.0 | Hypothesis batch generation |
| `factor_hypothesis_critic_v1` | 1.0.0 | Hypothesis critique |
| `factor_dsl_translator_v1` | 1.0.0 | Approved hypothesis → DSL |
| `factor_formula_reviewer_v1` | 1.0.0 | Post-compile formula review |
| `factor_run_interpreter_v1` | 1.0.0 | Completed-run interpretation |

All templates embed mandatory safety rules:

- No Python, SQL, or code execution
- No fabricated IC, Sharpe, p-values, or backtest results
- No sealed-test performance disclosure unless formally opened
- No lifecycle approval language (VALIDATED, PAPER, PRODUCTION)
- No outcome/forward-return fields as inputs
- Only fields from the supplied catalog
- Deterministic services are authoritative

Template ID and version are persisted on each `FactorLlmInteraction`. Content changes require a **version bump**.

Response schema version: `factor-llm-v1` (`LLM_RESPONSE_SCHEMA_VERSION` in `models.py`).
