# Factor Promotion Governance (Phase 10)

Controlled promotion review workflow for Factor Discovery. **Advisory only** — nothing in this phase activates live scan scoring.

## Lifecycle

```text
experimental → staged → promotion_candidate → shadow → approved_for_manual_integration
                                    ↘ rejected / archived
```

| Status | Meaning |
|--------|---------|
| `experimental` | Created from staging; under initial review |
| `staged` | Linked to immutable evidence bundle |
| `promotion_candidate` | All blocking gates visible; ready for shadow |
| `shadow` | Shadow scoring enabled (research path only) |
| `approved_for_manual_integration` | Eligible for a **separate** human-controlled integration step |
| `rejected` / `archived` | Terminal review outcomes |

**Approval does not activate live scoring.** Production integration requires an explicit Phase 11+ step with `ChangeProposal` and version bump.

## Promotion gates

Versioned thresholds live in:

`backend/services/factor_discovery/promotion/gate_policy_v1.json`

Each gate returns `pass`, `fail`, `warning`, or `not_applicable`. **Failed blocking gates remain visible** even when other metrics look strong.

## Evidence bundles

Immutable JSON artifacts:

`backend/data/factor_discovery/promotion_evidence/fpev_*.json`

Contains staging manifest hashes, gate decisions, diagnostics, negative controls, and reproducibility proof. Bundles are hash-verified on read.

## API (requires flags)

```bash
FACTOR_PROMOTION_GOVERNANCE_ENABLED=true
FACTOR_SHADOW_SCORING_ENABLED=true   # shadow evaluations only
```

| Method | Path |
|--------|------|
| GET | `/api/v2/research/factor-discovery/promotion/readiness` |
| GET/POST | `/api/v2/research/factor-discovery/promotion-candidates` |
| GET | `/api/v2/research/factor-discovery/promotion-candidates/{id}` |
| GET | `/api/v2/research/factor-discovery/promotion-candidates/{id}/evidence` |
| POST | `/api/v2/research/factor-discovery/promotion-candidates/{id}/transitions` |
| POST | `/api/v2/research/factor-discovery/promotion-candidates/{id}/shadow-evaluations` |
| GET | `/api/v2/research/factor-discovery/promotion-candidates/{id}/audit` |

## Candidate vs live factor

| | Promotion candidate | Live factor |
|--|---------------------|-------------|
| Affects scan ranking | **No** | Yes |
| In `FactorWeight` table | **No** | Yes |
| Status | Governance lifecycle | `FactorDefinition` catalog |
| Activation | Manual integration only | Production config |

## Quant Lab UI

Factor Discovery → **Promotion Review** tab. Labels: *Research only · Shadow only · Does not affect live ranking · Manual integration required*.

See also [FACTOR_SHADOW_SCORING.md](./FACTOR_SHADOW_SCORING.md).
