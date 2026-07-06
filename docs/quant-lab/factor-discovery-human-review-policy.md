# Factor Discovery — Human Review Policy (LLM)

Every consequential LLM output requires explicit human review before downstream actions.

## Candidate review states

| Status | Meaning |
|--------|---------|
| `PENDING_REVIEW` | Default after LLM generation |
| `APPROVED` | Human approved for next step |
| `REJECTED` | Human rejected |
| `SUPERSEDED` | Replaced by newer candidate |

## Rules

1. Approval/rejection requires a **human actor** (not `llm`) and **non-empty reason**
2. Review events are **append-only** (`factor_llm_review_events`)
3. Candidate JSON is **immutable**; only review metadata changes

## Workflow gates

| Step | Approval enables | Does NOT enable |
|------|------------------|-----------------|
| Hypothesis `APPROVED` | DSL translation request | Experiment launch, definition creation |
| Formula `APPROVED` + `COMPILED_FOR_REVIEW` | DRAFT `FactorDefinitionRecord` | COMPILED lifecycle, experiment launch |
| Interpretation | Human reading only | Lifecycle change, sealed opening |

Experiment launch, lifecycle transitions, and sealed-test access remain **separate explicit operations** outside the LLM namespace.
