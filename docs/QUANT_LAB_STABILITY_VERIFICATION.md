# Quant Lab Stability Verification

**Date:** 2026-06-05  
**Scope:** Second stabilization pass — defensive tabs, research-only guards, shared shell, tests

---

## What was fixed

### Documentation
- Added [QUANT_LAB_STABILITY_AUDIT.md](./QUANT_LAB_STABILITY_AUDIT.md) — tab-by-tab endpoint, state, and crash-risk matrix.
- Updated [QUANT_LAB.md](./QUANT_LAB.md) with stability doc links and UX notes.

### Shared tab shell
- `QuantLabTabLayout` — title, description (`ReactNode`), status badge, controls, loading/error/disabled/partial-warning, body.
- Re-exports: `QuantLabEmptyState`, `FeatureDisabledNotice`, `StaleDataBadge`, `TabRefreshRow`.
- All six tabs use the same structure.

### Tab hardening
| Tab | Key changes |
|-----|-------------|
| **Factor Performance** | 7-day IC stale badge + warning; malformed factor rows skipped; feature-disabled on 503 |
| **Walk-Forward** | User Run only; date + horizon validation; last-run hint from `localStorage`; research-only extended warning; `periods_scored === 0` empty state |
| **Predictions** | `Promise.allSettled` — predictions and feedback fail independently; stale outcome warning |
| **Pairs** | User Run only; 2–20 symbol validation; statsmodels-unavailable messaging; research-only extended warning |
| **Data Quality** | Quant Health embedded (non-fatal errors); scheduler warning + failed-job count |
| **Model Admin** | `Promise.allSettled` per panel; independent error messages; V2 disabled notice |

### i18n (EN + ZH)
- `researchOnlyExtended`, `forwardHorizons`, `walkForwardNoHorizons`, `walkForwardNoRunYet`, `pairsNoRunYet`, `lastWalkForwardRun`, `schedulerUnavailableWarning`, `schedulerFailedJobs`

### Backend
- Added `python-multipart` to `requirements.txt` (required for FastAPI TestClient / form routes in contract tests).

### Tests
- Expanded `QuantLabTabs.test.tsx` to **24 tests** covering render, loading/empty/error/disabled, malformed responses, Walk-Forward/Pairs click-only API calls.

---

## Tests run

### Frontend (`frontend/`)

| Command | Result |
|---------|--------|
| `npm test` | **PASS** — 55 tests, 7 files |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS** — 0 errors, 5 warnings (none blocking; 1 in `WalkForwardTab` resolved) |
| `npm run build` | **PASS** — `/quant-lab` static route builds |

### Backend (`backend/`)

| Command | Result |
|---------|--------|
| `.venv/bin/python -m pytest tests/test_quant_lab_contracts.py -q` | **PASS** — 10/10 |

Note: Backend tests require a venv with `pip install -r requirements.txt` (includes `ta`, `httpx`, `pytest`, `python-multipart`).

---

## Definition of done checklist

| Criterion | Status |
|-----------|--------|
| `/quant-lab` loads without crashing | ✅ |
| Every tab handles empty/error/disabled/malformed | ✅ |
| Walk-Forward and Pairs run only on click | ✅ (tested) |
| Research-only warnings visible | ✅ |
| All frontend gates pass | ✅ |
| Backend contract tests pass | ✅ |

---

## Remaining limitations

1. **No dedicated `/api/v2/health/quant`** — Data Quality still composes health client-side via `getQuantHealthSummary()` (7 parallel calls). Failures are non-fatal per section.
2. **Walk-Forward last run** — Stored in browser `localStorage` only; not loaded from `GET /research/walk-forward/{run_id}` on tab open.
3. **Factor IC population** — Still requires manual IC panel job (`POST /api/v2/jobs/ic-panel`); tab shows empty state until data exists.
4. **Predictions empty vs feedback-only** — When feedback loads but predictions list is empty, summary stats show without the "no predictions" empty banner (intentional partial-data UX).
5. **Backend test environment** — Fresh clone must create `.venv` and install requirements; system Python is externally managed on macOS Homebrew.

---

## Placeholder / static data

None of the Quant Lab tabs use hard-coded placeholder metrics. All displayed values come from API responses or normalized empty defaults.

---

## Related

- [QUANT_LAB_STABILITY_AUDIT.md](./QUANT_LAB_STABILITY_AUDIT.md)
- [QUANT_LAB.md](./QUANT_LAB.md)
