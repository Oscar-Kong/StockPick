# Research Reliability — verification

**Date:** 2026-06-05  
**Scope:** Client-side Research Reliability layer for Quant Lab (no backend API shape changes).

## Commands

```bash
cd frontend
npm test
npm run typecheck
npm run lint
npm run build
```

Backend pytest not required — reliability is computed entirely in the frontend from existing endpoints.

## Results

| Gate | Status |
|------|--------|
| `npm test` | 90 tests passed (12 files) |
| `npm run typecheck` | Pass |
| `npm run lint` | Pass |
| `npm run build` | Pass |

## Manual checklist

- [x] Every Quant Lab tab renders `data-testid="research-reliability-card"`
- [x] Empty IC → `insufficient_data` status
- [x] Disabled v2 → `disabled` status
- [x] Stale IC (`as_of_date` > 7 days) → `stale` status (unit test)
- [x] Walk-forward with thin periods → overfitting warnings panel + weak reliability
- [x] PBO placeholder: `pbo_available: false`, warning in UI
- [x] Factor rows show Promote / Keep / Watch / Retire / Insufficient evidence badges
- [x] `EvidenceToActionBoundary` on Quant Lab page
- [x] No auto-apply button on Walk-Forward tab
- [x] `ApplyChangesConfirm` still requires `window.confirm`

## New files

| File | Purpose |
|------|---------|
| `frontend/src/lib/researchReliability.ts` | Score model + per-tab compute functions |
| `frontend/src/lib/researchReliability.test.ts` | Unit tests |
| `frontend/src/components/quant-lab/ResearchReliabilityCard.tsx` | UI card |
| `frontend/src/components/quant-lab/ResearchReliabilityCard.test.tsx` | Component tests |
| `frontend/src/components/quant-lab/FactorLifecycleBadge.tsx` | Factor lifecycle badge |
| `frontend/src/components/product/EvidenceToActionBoundary.tsx` | Evidence → action copy |
| `docs/RESEARCH_RELIABILITY.md` | Design doc |
| `docs/RESEARCH_RELIABILITY_VERIFICATION.md` | This file |

## Not implemented (documented placeholders)

- PBO (Probability of Backtest Overfitting)
- CPCV / purged k-fold with embargo
- Deflated Sharpe ratio
- Backend trial-count metadata for walk-forward config search
