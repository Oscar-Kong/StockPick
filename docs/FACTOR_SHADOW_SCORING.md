# Factor Shadow Scoring (Phase 10)

Shadow scoring computes **hypothetical** candidate-factor impact beside the current live score. It never modifies live rankings, weights, or portfolio decisions.

## Principles

1. Same decision timestamp and PIT-safe data path as live scoring (via `build_candidate`)
2. Live score computed first via `ScoringEngine.score()` — **unchanged**
3. Shadow score = live signals + optional candidate proxy signal at low `shadow_weight` (default 0.05)
4. Results persisted to `factor_shadow_evaluation_runs` for Quant Lab review
5. Default scan responses **exclude** shadow metadata

## Configuration

```bash
FACTOR_SHADOW_SCORING_ENABLED=true
```

Requires `FACTOR_PROMOTION_GOVERNANCE_ENABLED=true` and candidate status `promotion_candidate`, `shadow`, or `approved_for_manual_integration`.

## Metrics tracked

Per symbol and run:

- live rank / shadow rank / rank change
- live score / shadow score / score change
- candidate contribution
- disagreement rate
- top-N membership changes

Runs are **sleeve-scoped** (Penny and Compounder evaluated separately).

## API

```http
POST /api/v2/research/factor-discovery/promotion-candidates/{id}/shadow-evaluations
{
  "as_of_date": "2026-06-01",
  "symbols": ["AAPL", "MSFT"],
  "shadow_weight": 0.05
}
```

```http
GET /api/v2/research/factor-discovery/promotion-candidates/{id}/shadow-evaluations
```

## Safety guarantees

- `FactorEngine.build_signals()` is not modified for shadow
- `FactorWeight` rows are not created or updated
- `FACTOR_MODEL_VERSION` is not bumped
- No broker or order integration

Shadow v1 uses a lightweight proxy signal when the discovery panel executor is unavailable for single-symbol contexts. Full panel shadow replay is a follow-up enhancement.
