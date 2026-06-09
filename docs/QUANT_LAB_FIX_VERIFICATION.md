# Quant Lab Fix Verification

**Date:** 2026-06-09  
**Baseline:** commit `794c023` + stabilization pass

## What broke (audit summary)

See [QUANT_LAB_ERROR_AUDIT.md](./QUANT_LAB_ERROR_AUDIT.md) for full Phase 1 findings.

Highlights:

- **Runtime:** `audit.events` / `recent_jobs` undefined could crash tabs; prediction field mismatch (`score` vs `alpha_score`) was fixed earlier.
- **API contracts:** Loose `Record<string, unknown>` on admin endpoints; no response normalizers.
- **Structure:** Single 600-line `QuantLabTabs.tsx` file.
- **Tests:** No Quant Lab component tests; missing backend contract tests; `httpx`/`pytest` not in requirements.
- **Backend:** `GET /api/v2/weights/{sleeve}` returned `RuntimeBool` for `dynamic_enabled` (Pydantic validation error).

## What was fixed

### Phase 2 — Split tabs

| File | Role |
|------|------|
| `QuantLabTabs.tsx` | Re-exports only |
| `QuantLabTabShell.tsx` | Shared `FeatureDisabledNotice`, `BucketSelect`, empty state |
| `FactorPerformanceTab.tsx` | IC performance |
| `WalkForwardTab.tsx` | Walk-forward research |
| `PredictionsTab.tsx` | Predictions + feedback |
| `PairsTab.tsx` | Pairs research |
| `DataQualityTab.tsx` | Quant health + scheduler |
| `ModelAdminTab.tsx` | Version, weights, audit, factor catalog |

### Phase 3 — Hardening

- All tabs: loading / error / retry / empty / feature-disabled states
- Factor Performance: skip malformed factors; stale IC warning
- Walk-Forward: date inputs + validation; formatted horizon stats; no auto-run
- Predictions: independent partial failure handling
- Pairs: min 2 / max 20 symbols; statsmodels + no-cointegration messaging
- Data Quality: safe `recent_jobs ?? []`
- Model Admin: safe `events ?? []`; refresh button; strict admin type

### Phase 4 — API + types

- `frontend/src/lib/quantLabNormalizers.ts` — normalizes all Quant Lab responses
- `frontend/src/lib/quantLabFormatters.ts` — dates, symbols, horizon formatting
- `V2FactorsAdminResponse` type; API helpers return normalized strict types
- Tabs mount only when selected (`QuantLabPage` unchanged — lazy by tab)

### Phase 5 — Frontend tests

- `@testing-library/react`, `@testing-library/jest-dom`, `happy-dom`
- `QuantLabTabs.test.tsx` — 7 tab behavior tests
- `quantLabNormalizers.test.ts`, `quantLabFormatters.test.ts`

### Phase 6 — Backend contract tests

- `backend/tests/test_quant_lab_contracts.py` — 10 endpoint shape tests
- `backend/api/routes_v2.py` — `bool(DYNAMIC_WEIGHTS_ENABLED)` fix
- `backend/requirements.txt` — added `httpx`, `pytest`

## Commands run

```bash
# Frontend
cd frontend
npm test
npm run typecheck
npm run lint
npm run build

# Backend (Quant Lab contracts)
cd backend
pip install httpx pytest   # now in requirements.txt
python -m pytest tests/test_quant_lab_contracts.py -q
```

## Results

| Check | Result |
|-------|--------|
| `npm test` | **PASS** — 38 tests (7 files) |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS** — 0 errors (4 unrelated warnings) |
| `npm run build` | **PASS** — `/quant-lab` builds |
| `pytest test_quant_lab_contracts.py` | **PASS** — 10/10 |

Full backend suite (`pytest tests/ -q`): **127 passed, 3 failed** — pre-existing failures in `test_pairs_research.py` (statsmodels) and `test_quant_v2_phase3.py` (delisting filter), unrelated to this pass.

## Remaining known limitations

| Item | Notes |
|------|-------|
| `GET /api/v2/health/quant` | Still client-composed via `getQuantHealthSummary()` |
| Model Admin job Run buttons | `POST /api/v2/jobs/ic-panel` not wired in UI |
| IC panel duration | Long-running; use CLI or scheduler |
| Pairs cointegration | Requires `statsmodels` for full ADF tests |
| Placeholder data | **None** — all tabs use live API data |
| Endpoints not in Quant Lab UI | `GET /api/v2/factors/ic` (alias), `GET /api/v2/jobs/queue`, walk-forward run detail |

## Definition of done

- [x] `/quant-lab` route loads and builds
- [x] Every tab renders without crashing on empty/malformed API data
- [x] Walk-forward and pairs run only on user click
- [x] Feature-disabled (503) shows friendly UI
- [x] Frontend test/typecheck/lint/build pass
- [x] Quant Lab backend contract tests pass
