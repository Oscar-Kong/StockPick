# Factor Discovery — candidate review UI (Phase 9A)

Quant Lab route: `/quant-lab?section=factor-discovery&fdView=review-queue`

## Components

| Component | API | Purpose |
|-----------|-----|---------|
| `HypothesisReviewCard` | `GET /candidates/hypotheses/{id}` | Rationale, deterministic support, LLM critique, approve/reject |
| `FormulaReviewCard` | `GET /candidates/formulas/{id}` | Read-only canonical DSL, AST tree, compiler warnings |
| `RevisionReviewCard` | `GET /candidates/revisions/{id}` | Parent/proposed DSL, semantic chips, policy `RuleTable` |
| `LlmInteractionDrawer` | `GET /llm/interactions/{id}` | Provider/model/tokens; no raw secrets |
| `ReviewConfirmDialog` | — | Reason required; preserves reason on HTTP 409 |

## Review mutations

All approve/reject calls include `expected_state_version`, `actor`, and `reason`.

On **409** `STATE_VERSION_CONFLICT`: dialog stays open, reason preserved, session/queue/detail refetched, user must resubmit explicitly.

## Approval language

- Hypothesis: approving permits formula translation only.
- Formula: approving creates immutable draft definition only.
- Revision: approving creates new immutable version; prior results unchanged.

## Non-goals

No bulk approval, no DSL editing during approval, no lifecycle or Scan actions.
