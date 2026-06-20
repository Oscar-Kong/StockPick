# Quant Lab functional test report

**Date:** 2026-06-18  
**Scope:** Full audit, repair, and automated test pass for `/quant-lab`

## Executive summary

Quant Lab was failing or misleading primarily due to:

1. **Pairs research not persisted** — Evidence Overview always showed “No saved run” despite successful POST runs.
2. **Walk-forward rank IC required scipy** — Service tests failed in environments without `scipy`, breaking cross-section metrics.
3. **Analyze-adjacent JSON bugs** (prior session) — numpy scalars caused 500s that surfaced as CORS/`Failed to fetch` in the browser.
4. **Contract tests skipped on 503** — Features appeared tested while disabled paths were silently skipped.
5. **Data Quality duplicate fetches** — Tab and `QuantHealthCard` both called `getQuantHealthSummary()`.

Repairs add **pairs persistence** (`pairs_research_runs`), **deterministic fixtures**, **explicit enabled/disabled contract tests**, **frontend hydration for pairs**, and **Playwright E2E** scaffolding.

**Research boundary preserved:** No changes connect Quant Lab outputs to live scan rankings, portfolio recommendations, or order execution.

---

## Initial baseline failures

| Check | Result |
|-------|--------|
| `test_walk_forward_research_service` | 2 failed (`scipy` missing for Spearman) |
| `test_quant_lab_contracts` | Passed but used `_skip_503()` — not acceptable proof |
| Frontend `quant-lab` Vitest | 33/33 passed (mocked APIs) |
| Pairs evidence | Always `available: false` |
| Playwright | Not present |

---

## Root causes fixed

| Issue | Root cause | Fix |
|-------|------------|-----|
| Walk-forward IC tests | `pandas.Series.corr(method="spearman")` imports scipy | `_rank_correlation()` fallback without scipy |
| Pairs “No saved run” | No DB table or persist path | `PairsResearchRun` model + `pairs_research_store.py` |
| Misleading API-down errors | 500 responses without CORS headers (separate fix) | numpy `json_safe` in analyze path |
| Disabled feature tests | Patched `config` but routes import constants at load | Patch `api.routes_v2.SCORE_ENGINE_V2_ENABLED` |
| Duplicate health fetch | Independent `QuantHealthCard` mount fetch | Controlled props from `DataQualityTab` |
| Empty pairs tab on reload | `getPairsLatest` unused | Hydrate from `/research/pairs/latest` + `/research/pairs/{run_id}` |

---

## Tab status matrix

| Tab | Status | Notes |
|-----|--------|-------|
| Factor Performance | **PASS** | Empty state when no IC; seeded contract tests |
| Walk-Forward | **PASS** | scipy-free metrics; synthetic pipeline test |
| Prediction Outcomes | **PASS** | Partial failure handling; seeded snapshots |
| Pairs Trading | **FIXED** | Persist + latest + UI hydration |
| Data Quality | **FIXED** | Single health fetch; scheduler partial failure |
| Model Admin | **PASS** | `Promise.allSettled` per panel (existing) |
| Evidence Overview | **FIXED** | Pairs card uses persisted runs |
| Page / URL tabs | **PASS** | E2E covers all six tabs + refresh |

---

## Test counts (verification run)

```bash
# Backend Quant Lab targeted
cd backend && pytest -q tests/test_quant_lab_contracts.py \
  tests/test_quant_lab_integration.py \
  tests/test_walk_forward_research_service.py \
  tests/test_pairs_research.py
# → 36 passed, 1 skipped

# Playwright E2E (9 scenarios)
cd frontend && npm run test:e2e
# → 9 passed

# Full backend suite
cd backend && pytest -q
# → 319+ passed (re-run after changes)

# Frontend unit
cd frontend && npm test -- --run src/components/quant-lab
# → 33 passed

# Typecheck
cd frontend && npm run typecheck
# → pass
```

### Playwright E2E

```bash
cd frontend
npx playwright install chromium   # first time only
npm run test:e2e
```

Uses `scripts/quant-lab-e2e-up.sh` (ports **18930/18931**, DB `storage/dev/quant_lab_e2e.db`).

Traces/screenshots: `frontend/playwright-report/` on failure.

---

## Deterministic seed command

```bash
cd backend
python scripts/seed_quant_lab_demo.py --sleeve medium
# Default DB: storage/dev/quant_lab_demo.db

DATABASE_URL=sqlite:///./storage/dev/quant_lab_demo.db \
  python -m uvicorn main:app --port 18731
```

Fixtures module: `backend/tests/fixtures/quant_lab_fixtures.py`

---

## Remaining limitations

| Limitation | Reason |
|------------|--------|
| Live Yahoo/provider data in manual UI | Not used in automated tests; use seed DB |
| `statsmodels` optional | Cointegration uses ADF fallback when missing; real statsmodels path tested when installed |
| IC panel job E2E | Job runner not fully E2E’d; contract + fixture seed cover read path |
| PBO / full overfitting suite | Marked unavailable unless computed — no fake pass |
| `exchange_calendars` | Optional; walk-forward uses weekday fallback |

### Optional dependencies

- `statsmodels` — full Engle–Granger path
- `scipy` — faster Spearman (fallback exists)
- `exchange_calendars` — PIT session calendar

---

## Files changed (summary)

**Backend:** `pairs_research_store.py`, `pairs_research_service.py`, `quant_lab_summary_service.py`, `routes_research.py`, `quant_models.py`, `quant_db.py`, `walk_forward_research_service.py`, `schemas_v2.py`, test fixtures + contract/integration tests, `seed_quant_lab_demo.py`

**Frontend:** `PairsTab.tsx`, `DataQualityTab.tsx`, `QuantHealthCard.tsx`, `api.ts`, Playwright config + `e2e/quant-lab.spec.ts`

**Docs:** `QUANT_LAB.md`, this report, manual checklist, `RUNBOOK.md`
