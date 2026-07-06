# Factor Discovery — revision policy

Revisions must remain structurally connected to their lineage. LLM prose does not determine eligibility — AST diff and policy rules do.

## Proposal schema

`FactorRevisionProposal` (`mining/models.py`) requires parent candidate/hash, lineage, revision round, addressed failure categories, proposed DSL, and `performance_unproven=true`.

Prohibited in proposals: outcome fields, Python/SQL, threshold/period/snapshot changes, sealed-test requests, lifecycle claims.

## Structural constraints

`revision_diff.validate_revision_policy()` enforces:

- No identical child hash
- No cycle to_name to earlier evaluated formula in lineage
- Max one field added/removed per revision
- Max depth increase of 1
- AST node increase bounded by `max_ast_nodes // 4`

## Validation pipeline

```text
schema → parser → compiler → field capability → formula hash → complexity → lineage policy
```

Implementation: `mining/revision_step.py`

## Approval

| Mode | Rule |
|------|------|
| `supervised` | Human `POST .../revisions/{id}/approve` required |
| `bounded_auto` | Automatic only when `auto_policy.auto_approve_revisions=true` and structural checks pass with no pause trigger |

Automatic approval never promotes factor lifecycle beyond session-authorized compile transition.

## Duplicate revisions

Semantically identical DSL → same canonical formula hash → duplicate event persisted, no relaunch, lineage may stop under `stop_on_duplicate_only_round`.
