# Factor Discovery — LLM Security

## Safety model

The LLM is a **research assistant**, not an execution engine.

### Allowed

- Normalize research objectives
- Propose economic hypotheses
- Translate approved hypotheses to Factor DSL
- Critique candidates and interpret persisted artifacts
- Recommend human review actions

### Prohibited

- Execute Python/SQL or access databases directly
- Calculate factor values, IC, or portfolio metrics
- Invent unavailable fields or override parser/compiler errors
- Open sealed tests or approve lifecycle transitions
- Launch experiments or modify Scan weights

## Defenses

1. **Structured Pydantic schemas** — `extra=forbid`; invalid output rejected
2. **Deterministic post-validation** — field registry, forbidden outcome fields, parser/compiler
3. **Evidence validator** — interpretation paths and numeric values must match integrity-verified artifacts
4. **Human review gates** — actor ≠ `llm`; non-empty reason required
5. **Context minimization** — no sealed metrics for closed artifacts; no raw panels
6. **Budgets & rate limits** — per-family daily caps; candidate limits
7. **Prompt delimiters** — user input treated as data in JSON payloads
8. **Fixture provider blocked in production** — `FIXTURE_LLM_FORBIDDEN`

## Logging & privacy

Logged: interaction ID, operation, provider, model, status, duration, token counts, error codes.

Not logged or persisted: API keys, authorization headers, sealed metric payloads, environment secrets.

Audit records store **prompt hashes** and structured payloads, not unbounded raw prompts where avoidable.
