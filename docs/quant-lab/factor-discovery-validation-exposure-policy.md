# Factor Discovery — validation exposure policy

Repeated validation evidence in LLM prompts can overfit the holdout period. Phase 7 tracks every exposure in `factor_mining_exposures`.

## Context tiers

| Tier | LLM receives |
|------|----------------|
| `DISCOVERY_ONLY` | Discovery metrics, limitations, warnings |
| `DISCOVERY_PLUS_VALIDATION_SUMMARY` | Discovery + validation summary + acceptance gate + deterministic failure categories |
| `FULL_CLOSED_ARTIFACT` | Full closed metrics (no sealed metrics) |

The LLM cannot request a higher tier. Sealed metrics are never included.

## Default limits

| Limit | Default |
|-------|---------|
| Critiques per formula | 1 |
| Exposures per lineage | 2 |
| Revision rounds using validation evidence | 2 |

After exhaustion, further revisions require discovery-only context or a **new human-authorized session**.

## Service

`MiningExposureService.check_exposure()` before critique; `record()` after. Orchestrator `_step_analyze_results()` uses `DISCOVERY_PLUS_VALIDATION_SUMMARY` and increments `validation_exposures` usage.

## Failure categories

Deterministic categories from closed artifacts (`mining/critique_step.py`) — LLM may explain but not invent categories. See `FailureCategory` enum in `mining/models.py`.
