# Quant Lab Last-Run Verification

**Date:** 2026-06-05  
**Scope:** Last-run evidence cards, trust indicators, read-only summary endpoints

---

## What was added

### Backend
- `services/quant_lab_summary_service.py` — builds last-run summaries from real storage
- `GET /research/walk-forward/latest?sleeve=` — latest persisted walk-forward run
- `GET /research/pairs/latest` — returns `available: false` (pairs not persisted yet)
- `GET /api/v2/quant-lab/evidence?sleeve=` — combined evidence for all five cards
- Schemas: `QuantLabLastRunSummary`, `QuantLabEvidenceResponse`

### Frontend
- `QuantLabEvidencePanel` — five last-run cards at top of `/quant-lab`
- `QuantLabLastRunCard` + `QuantLabTrustBadge`
- `quantLabLastRun.ts` — normalizers and card helpers
- Walk-Forward tab loads latest persisted run via GET (not POST) on sleeve change
- Validation copy: *"Quant Lab validates the scoring system. It does not automatically change scan rankings."*

### Trust indicators
Fresh · Stale · Insufficient sample · Feature disabled · No saved run · Research only · Needs attention

---

## Tests run

### Frontend

| Command | Result |
|---------|--------|
| `npm test` | **PASS** — 61 tests, 9 files |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS** — 0 errors, 4 warnings (unrelated) |
| `npm run build` | **PASS** — `/quant-lab` builds |

### Backend

| Command | Result |
|---------|--------|
| `python -m pytest tests/test_quant_lab_contracts.py -q` | **PASS** — 13/13 |

New tests:
- `quantLabLastRun.test.ts` — normalizer coverage
- `QuantLabEvidencePanel.test.tsx` — available/unavailable/stale cards, no auto-run
- `QuantLabTabs.test.tsx` — walk-forward GET latest on mount, POST only on click
- `test_walk_forward_latest_contract`, `test_pairs_latest_contract`, `test_quant_lab_evidence_contract`

---

## Definition of done

| Criterion | Status |
|-----------|--------|
| Last known evidence shown before running jobs | ✅ |
| No heavy POST on page load | ✅ |
| Fresh/stale/missing visible via trust badges | ✅ |
| Pairs honestly reports no saved run | ✅ |
| Tests pass | ✅ |

---

## Limitations

1. **Pairs research** is not persisted — `GET /research/pairs/latest` always returns `available: false` until storage is added.
2. **Walk-forward tab** auto-loads latest run detail via GET only (read-only).
3. **Evidence sleeve** is fixed to `medium` on the overview panel; tab-level sleeve selectors unchanged.

---

## Related

- [QUANT_LAB.md](./QUANT_LAB.md)
- [QUANT_LAB_STABILITY_AUDIT.md](./QUANT_LAB_STABILITY_AUDIT.md)
