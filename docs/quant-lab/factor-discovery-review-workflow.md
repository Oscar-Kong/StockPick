# Factor Discovery Review Workflow (UI)

Human review gates in the supervised mining loop.

## Hypothesis review

- **Approve** allows formula translation — does **not** approve the factor for production.
- **Reject** requires reason + `expected_state_version`.
- Cards show economic rationale, data support, and LLM critic output (structured fields only).

API:

- `POST .../hypotheses/{candidate_id}/approve`
- `POST .../hypotheses/{candidate_id}/reject`

## Formula review

- Canonical DSL is **read-only** during approval.
- **Approve** creates or permits an immutable draft definition — experiment launch follows separate workflow gates.
- Shows formula hash, compiler metadata, and review recommendation.

API:

- `POST .../formulas/{candidate_id}/approve`
- `POST .../formulas/{candidate_id}/reject`

## Revision review

- Side-by-side parent vs proposed DSL (structural diff in detail drawer — Phase 8B table view in session detail).
- **Approve** creates a new immutable factor version; parent unchanged.

API:

- `POST .../revisions/{candidate_id}/approve`
- `POST .../revisions/{candidate_id}/reject`

## Promising candidate review

When lineage status is `PROMISING_FOR_HUMAN_REVIEW`:

- Show rule-by-rule promising policy results
- Prominent: research evidence only; sealed test unopened; no lifecycle promotion
- Actions: view artifact, pause/complete session where allowed

## Allowed actions authority

`GET .../sessions/{id}` returns `allowed_actions` and `action_disabled_reasons`. The UI disables controls accordingly; server checks still enforce policy.

## Confirmation dialogs

Required for authorize, approve, reject, pause, resume, and cancel (with terminal-state explanation for cancel).
