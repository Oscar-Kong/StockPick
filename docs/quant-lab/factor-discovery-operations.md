# Factor Discovery operations (Phase 6A)

## Operational status

```python
from services.factor_discovery.operations import factor_discovery_operational_status

factor_discovery_operational_status()
```

Reports:

- `FACTOR_DISCOVERY_ENABLED`
- `FACTOR_RESEARCH_DATA_PROVIDER`
- Provider capability flags and blocking reasons
- Failed / pending sealed receipt counts
- Validation artifact count

No secrets or full filesystem paths in responses.

## Feature flags

| Flag | Default | Notes |
|------|---------|-------|
| `FACTOR_DISCOVERY_ENABLED` | `false` | Gates Quant Lab experiment launch |
| `FACTOR_RESEARCH_DATA_PROVIDER` | `disabled` | See [factor-discovery-data-provider.md](./factor-discovery-data-provider.md) |

Shipped defaults above are the Settings / `RuntimeBool` registry defaults. A local `.env` may enable flags for supervised development; that is a process-env overlay and does **not** rewrite the shipped default. `registry.reset()` (including pytest's `isolated_backend_env`) restores the shipped-off baseline. String knobs (`FACTOR_DISCOVERY_LLM_PROVIDER`, `FACTOR_DISCOVERY_LOOP_MODE`) are also forced to `disabled` in that fixture so "disabled by default" tests stay hermetic.

## Failed runs

Failed Factor Discovery runs index into Research Results without a validation artifact. Summaries include stage, error code, and safe summary.

## Sealed receipt failure policy

Failed sealed receipts remain in `FAILED` status. Ordinary retry is blocked (`SEALED_RECEIPT_FAILED`). Recovery requires explicit `recovery_authorization` (administrative; not automated in Phase 6A).

## LLM phase readiness

Phase 6B adds schema-constrained LLM workflows (`backend/services/factor_discovery/llm/`) with human review gates. See [factor-discovery-llm-architecture.md](./factor-discovery-llm-architecture.md).

| Flag | Default | Notes |
|------|---------|-------|
| `FACTOR_DISCOVERY_LLM_ENABLED` | `false` | Gates LLM API routes |
| `FACTOR_DISCOVERY_LLM_PROVIDER` | `disabled` | `existing_default` \| `fixture` (test/dev only) |

Operational status includes `llm_capabilities`, `llm_interaction_count`, and `failed_llm_interaction_count`.

Phase 6B does **not** allow an LLM to approve factors, reveal sealed tests, modify lifecycle status, launch experiments, or affect production Scan.

## Mining loop (Phase 7)

Bounded research-session orchestrator with immutable budgets. See [factor-discovery-mining-loop.md](./factor-discovery-mining-loop.md).

| Flag | Default | Notes |
|------|---------|-------|
| `FACTOR_DISCOVERY_LOOP_ENABLED` | `false` | Gates mining API routes |
| `FACTOR_DISCOVERY_LOOP_MODE` | `disabled` | `supervised` \| `bounded_auto` when loop enabled |
| `FACTOR_DISCOVERY_LOOP_MAX_ADVANCE_STEPS` | `10` | Hard cap per `advance` request |

Operational status includes `loop_enabled`, `loop_ready`, `loop_blocking_reasons`, active/paused mining session counts, and validation exposure totals.

Phase 7 does **not** open sealed tests, promote lifecycle status, or affect production Scan.

## Schema

Factor Discovery tables are created via `QuantBase.metadata.create_all` plus additive `_migrate_factor_discovery_columns()`. Repeated initialization is idempotent on SQLite and Postgres.
