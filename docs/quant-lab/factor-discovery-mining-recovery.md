# Factor Discovery — mining crash recovery

The orchestrator is resumable without repeating paid LLM calls or relaunching identical experiments when idempotent records exist.

## Recovery service

`MiningRecoveryService.recover_session(session_id)` returns:

- Current status and `state_version`
- Last event type
- Pending run id/status if a run was in flight
- `recoverable: true` for non-terminal sessions

Terminal sessions (`COMPLETED`, `CANCELLED`, `BUDGET_EXHAUSTED`, `FAILED`) raise `MiningRecoveryError`.

## Idempotency guarantees

| Stage | Protection |
|-------|------------|
| LLM calls | Interaction persistence + content hashes |
| Experiment launch | Idempotency key `mining:{session}:{lineage}:{formula_hash}` |
| Definitions | Immutable factor definition records |
| Statistical attempts | Research-family attempt ledger |
| Human pauses | State machine blocks skip of review states |

## Cancellation

`cancel_mining_session()` prevents new LLM calls and launches, preserves candidates/artifacts/events, marks session `CANCELLED`. In-flight external runs may complete but are not auto-consumed unless documented in session policy.

## Event log

`factor_mining_events` is authoritative for reconstruction. `event_log_hash` in session summary is deterministic over ordered semantic fields (excludes runtime noise).
