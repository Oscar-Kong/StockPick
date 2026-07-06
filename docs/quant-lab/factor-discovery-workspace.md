# Factor Discovery Workspace (Phase 8B)

> **Route:** `/quant-lab?section=factor-discovery`  
> **Backend:** `/api/v2/research/factor-discovery/mining/*`  
> **Feature flags:** `FACTOR_DISCOVERY_ENABLED`, `FACTOR_DISCOVERY_LLM_ENABLED`, `FACTOR_DISCOVERY_LOOP_ENABLED` (all default **false**)

The Factor Discovery workspace supports **controlled supervised research**. It does **not** provide investment approval, guaranteed alpha, sealed-test access, or production deployment.

## Navigation

Quant Lab primary tabs include **Factor Discovery** between Experiments and Results.

Internal views (query param `fdView`):

| View | `fdView` | Purpose |
|------|----------|---------|
| Sessions | `sessions` | Dashboard, filters, session detail |
| New Research | `new-research` | Multi-step draft + authorize flow |
| Review Queue | `review-queue` | Cross-session pending reviews |
| Factors | `factors` | Read-only LLM formula candidate registry |
| Readiness | `readiness` | Consolidated capability matrix |

Session detail: `fdView=sessions&sessionId=<id>`

## Readiness

`GET /api/v2/research/factor-discovery/mining/readiness` returns a single UI-safe contract:

- Feature flags and supervised/bounded-auto readiness
- LLM and data-provider status
- PIT, adjusted-price, and historical-store flags
- Blocking reasons and warnings
- `bounded_auto_ready: false` until backend explicitly enables it
- `no_sealed_access` and `no_production_integration` always true in Phase 8B

## State version conflicts

All mining mutations require `expected_state_version` (or legacy `state_version`).

- Missing version → HTTP **422** `MISSING_STATE_VERSION`
- Stale version → HTTP **409** `STATE_VERSION_CONFLICT` (no side effects)
- Success → mutation envelope with updated `state_version` and `allowed_actions`

The UI refetches session detail after 409 and preserves unsent form text where possible.

## Supervised workflow

1. Create draft session (New Research)
2. Authorize with reason + confirmation (separate action)
3. Start → orchestrator advances through hypothesis/formula review gates
4. Human approve/reject with reason + current state version
5. Monitor experiments (8s polling when active; no fabricated progress %)
6. Review promising candidates (evidence only — no sealed opening)

## Explicit non-goals (Phase 8B / 9A)

- Sealed-test opening
- Lifecycle promotion (validated / paper / production)
- Production Scan integration
- Bounded-auto as a selectable production mode
- Budget increases after authorization
- Real historical-data staging validation (Phase 9B)

## Phase 9A additions

- **Review Queue** — `GET /mining/review-queue` with lazy candidate detail load
- **Candidate review cards** — hypothesis, formula (AST + read-only DSL), revision (semantic diff + policy table)
- **Validation result panel** — sectioned evidence with integrity gating
- **Promising review** — rule-by-rule policy table (not investment approval)
- **Factor registry** — persisted definitions via `GET /factors` (not LLM-candidate-only list)
- **LLM interaction drawer** — metadata-only AI content display

## Related docs

- [factor-discovery-review-workflow.md](./factor-discovery-review-workflow.md)
- [factor-discovery-results-ui.md](./factor-discovery-results-ui.md)
- [factor-discovery-candidate-review-ui.md](./factor-discovery-candidate-review-ui.md)
- [factor-discovery-promising-review-ui.md](./factor-discovery-promising-review-ui.md)
- [factor-discovery-artifact-integrity-ui.md](./factor-discovery-artifact-integrity-ui.md)
- [factor-discovery-factor-registry.md](./factor-discovery-factor-registry.md)
- [factor-discovery-mining-loop.md](./factor-discovery-mining-loop.md)
