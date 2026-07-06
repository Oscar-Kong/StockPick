# Factor Discovery — LLM Research Layer (Phase 6B)

Schema-constrained LLM assistance for Factor Discovery research. **Disabled by default** via `FACTOR_DISCOVERY_LLM_ENABLED=false` and `FACTOR_DISCOVERY_LLM_PROVIDER=disabled`.

> LLM-generated hypotheses, formulas, critiques, and interpretations are **untrusted research suggestions**. Deterministic parsing, compilation, execution, validation, persistence, and **human approval** remain authoritative.

---

## Scope (Phase 6B)

| In scope | Out of scope (Phase 7+) |
|----------|-------------------------|
| Research-request normalization | Autonomous generate→test→revise loop |
| Hypothesis generation & critique | Automatic experiment launch |
| DSL translation + parser/compiler verification | Lifecycle auto-promotion |
| Formula review | Sealed-test opening |
| Run interpretation with evidence validation | Factor Discovery frontend |
| Human review gates | Production Scan integration |

---

## Package layout

```
backend/services/factor_discovery/llm/
  client.py              # Provider abstraction (existing_default, fixture, disabled)
  capabilities.py        # Pre-flight capability report
  models.py              # Pydantic request/response schemas
  prompt_registry.py     # Versioned prompt templates
  hypothesis_service.py
  hypothesis_critic_service.py
  formula_translation_service.py
  formula_review_service.py
  interpretation_service.py
  review_service.py      # Human approve/reject
  definition_service.py  # DRAFT FactorDefinition after formula approval
  evidence_validator.py
  interaction_repository.py
  candidate_repository.py
  budgets.py
  errors.py
```

---

## Persistence

| Table | Purpose |
|-------|---------|
| `factor_llm_interactions` | Append-only audit: prompt hashes, tokens, status, idempotency |
| `factor_llm_candidates` | HYPOTHESIS / FORMULA / CRITIQUE / INTERPRETATION candidates |
| `factor_llm_review_events` | Human review transitions |

No API keys or raw secrets are stored.

---

## API routes (`/api/v2/research/factor-discovery/llm/…`)

Gated by `FACTOR_DISCOVERY_LLM_ENABLED` (503 when false).

- `POST …/hypotheses/generate`
- `POST …/hypotheses/{id}/critique|approve|reject`
- `POST …/hypotheses/{id}/formulas/generate`
- `POST …/formulas/{id}/review|approve|reject`
- `POST …/runs/{run_id}/interpret`
- `GET …/interactions/{id}`
- `GET …/candidates`

Formula approval creates an immutable **DRAFT** `FactorDefinitionRecord`; lifecycle transition to COMPILED remains a separate explicit action.

---

## Feature flags

| Flag | Default | Notes |
|------|---------|-------|
| `FACTOR_DISCOVERY_ENABLED` | `false` | Experiment execution |
| `FACTOR_DISCOVERY_LLM_ENABLED` | `false` | LLM layer |
| `FACTOR_DISCOVERY_LLM_PROVIDER` | `disabled` | `existing_default` \| `fixture` (test/dev only) |

Enabling one flag does **not** enable the other.

---

## Provider

Reuses `services/llm_explainer._call_llm()` (OpenAI-compatible proxy) behind `ExistingDefaultLlmClient`. Structured output = prompt JSON + Pydantic validation (no native JSON mode requirement).

Operational diagnostics: `factor_discovery_operational_status()` includes `llm_capabilities`.

See also: [factor-discovery-llm-prompts.md](factor-discovery-llm-prompts.md), [factor-discovery-llm-security.md](factor-discovery-llm-security.md), [factor-discovery-human-review-policy.md](factor-discovery-human-review-policy.md).
