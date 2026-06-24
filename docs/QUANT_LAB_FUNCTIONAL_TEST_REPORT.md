# Quant Lab functional test report

**Date:** 2026-06-22 (Phase 7 update)  
**Scope:** Release-readiness audit for redesigned `/quant-lab` workbench

## Executive summary

Phase 7 stabilized the redesigned Quant Lab: unified navigation (Overview → Ideas → Experiments → Results → Model Monitor), bounded job polling, list-query indexes, TypeScript/build gates, and expanded Playwright coverage.

**Research boundary preserved:** No path from experiment completion to live scan ranking updates without explicit review.

---

## Test counts (2026-06-22)

```bash
# Full backend
cd backend && .venv/bin/python -m pytest tests/ -q
# → 385 passed, 2 skipped

# Quant Lab targeted (research + contracts)
cd backend && .venv/bin/python -m pytest \
  tests/test_quant_lab_contracts.py \
  tests/test_quant_lab_integration.py \
  tests/test_research_foundation.py \
  tests/test_research_overview.py \
  tests/test_research_results.py \
  tests/test_experiment_studio.py \
  tests/test_model_monitor.py \
  tests/test_walk_forward_research_service.py \
  tests/test_pairs_research.py -q
# → 70 passed

# Frontend Quant Lab unit
cd frontend && npm test -- --run src/components/quant-lab src/lib/quantLab src/lib/researchReliability
# → 90 passed

# Typecheck + production build
cd frontend && npm run typecheck && npm run build
# → pass

# Playwright
cd frontend && npm run test:e2e
# → 12+ scenarios (quant-lab.spec.ts)
```

See [QUANT_LAB_REDESIGN_FINAL_REPORT.md](./QUANT_LAB_REDESIGN_FINAL_REPORT.md) for architecture and verification commands.

---

## Prior audit fixes (2026-06-18)

| Issue | Fix |
|-------|-----|
| Pairs not persisted | `pairs_research_runs` + store |
| scipy required for WF IC | `_rank_correlation()` fallback |
| Contract tests skipped on 503 | Explicit enabled/disabled tests |
| Duplicate health fetch | Controlled props in Data Quality |

---

## Remaining limitations

| Limitation | Reason |
|------------|--------|
| Live provider data in manual UI | Automated tests use seed DB |
| PBO / CPCV / deflated Sharpe | Not implemented — UI warns |
| Full live job E2E for all 6 templates | Engine paths covered by pytest; Playwright covers navigation |
| Change proposal → live weight apply | Review-only; manual gate |
