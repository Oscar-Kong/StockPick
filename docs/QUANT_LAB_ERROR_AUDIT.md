# Quant Lab Error Audit

**Date:** 2026-06-09  
**Baseline commit:** `794c023` — "error tests and module health"  
**Scope:** `/quant-lab` route, `QuantLabTabs`, API client, backend contracts

---

## Phase 1 — Reproduction summary

### Frontend commands

| Command | Result |
|---------|--------|
| `npm test` | **PASS** — 22 tests, 4 files (none cover Quant Lab UI) |
| `npm run typecheck` | **PASS** |
| `npm run lint` | **PASS** — 0 errors, 4 warnings (none in Quant Lab files) |
| `npm run build` | **PASS** — `/quant-lab` static route builds |

### Backend commands

| Command | Result |
|---------|--------|
| `python -m pytest tests/ -q` | **FAIL** — 127 passed, **3 failed** (see § Backend test failures) |
| Note | `pytest` not listed in `requirements.txt`; must be installed in venv manually |

---

## Findings by category

### A. TypeScript / compile

No TypeScript errors in Quant Lab files at audit time.

| ID | File | Line | Issue | Root cause | Proposed fix |
|----|------|------|-------|------------|--------------|
| TS-1 | `api.ts` | 660–665 | `getV2FactorsAdmin` returns `Record<string, unknown>` | Loose typing | Add `V2FactorsAdminResponse` + normalizer |
| TS-2 | `ModelAdminTab.tsx` | 508 | `factorsAdmin` state typed as `Record<string, unknown>` | Same as TS-1 | Use strict admin response type |

---

### B. Lint

No Quant Lab lint errors. Project-wide hook-deps warnings in unrelated files only.

---

### C. Build

Build succeeds. Next.js workspace-root warning (multiple lockfiles) is unrelated to Quant Lab.

---

### D. Runtime / crash risks (frontend)

| ID | File | Line | Issue | Category | Root cause | Proposed fix |
|----|------|------|-------|----------|------------|--------------|
| RT-1 | `QuantLabTabs.tsx` | 588, 600 | `audit.events.length` when `events` may be undefined | Runtime | Backend or partial JSON may omit `events` | Use `(audit.events ?? []).length` |
| RT-2 | `QuantLabTabs.tsx` | 488, 492 | `status.recent_jobs.length` when array missing | Runtime | Scheduler response not validated | Normalize scheduler response; default `[]` |
| RT-3 | `QuantLabTabs.tsx` | 104–106 | `f.factor_id` / empty `horizons` can yield duplicate/null keys | Runtime | Malformed factor rows | Skip invalid factors; fallback key |
| RT-4 | `PredictionsTab` (historical) | — | `p.score.toFixed(1)` crash | Runtime | API returns `alpha_score`, not `score` | **Fixed** in prior session via `predictions.ts` |
| RT-5 | `PairsTab.tsx` | 356–363 | No max symbol cap | Runtime / perf | User can POST huge symbol lists | Cap at 20 symbols; show validation message |
| RT-6 | `WalkForwardTab.tsx` | 132–145 | No date-range validation | Runtime / UX | Invalid range could 400 from backend | Validate start < end before POST |
| RT-7 | `WalkForwardTab.tsx` | 200–206 | `JSON.stringify(stats)` for horizons | UX | Raw dump unreadable | Format structured horizon stats |
| RT-8 | `ModelAdminTab.tsx` | 513–541 | No retry on partial failure | UX | Failed fetches leave stale empty UI | Add `load()` + retry button |
| RT-9 | `getQuantHealthSummary` | `api.ts` 758+ | Heavy compose (7 parallel calls) on Data Quality tab mount | Performance | No dedicated `/api/v2/health/quant` | Accept for now; partial sections on failure already handled |

---

### E. API contract mismatches

| ID | Frontend expectation | Backend actual | Impact | Proposed fix |
|----|---------------------|----------------|--------|--------------|
| AC-1 | `PredictionSnapshotItem.score`, `.resolved` | `alpha_score`, `outcome` | Was crash; now mapped | **Fixed** — keep normalizers |
| AC-2 | `FeedbackSummaryResponse.stale` | Not returned | Stale badge logic wrong | Derive stale from snapshots/outcomes counts |
| AC-3 | `GET /api/v2/health/quant` | Does not exist | Client composes health | Document; optional future endpoint |
| AC-4 | `FactorPerformanceResponse.factors[].horizons` | May be `{}` | Empty rows | Filter in normalizer |
| AC-5 | `PairsResearchResponse.notes` | Always array from backend | Safe optional chain | Normalize to `[]` |
| AC-6 | `V2AuditResponse.events` | Usually array; not guaranteed in errors | Crash risk RT-1 | Normalizer defaults `[]` |

---

### F. Backend test failures (not all Quant Lab)

| Test | File | Error | Quant Lab related? | Proposed fix |
|------|------|-------|-------------------|--------------|
| `test_engle_granger_cointegrated_pair` | `test_pairs_research.py:54` | `sufficient` is False | **Yes** — Pairs tab backend | statsmodels missing / fallback ADF; adjust test or install statsmodels |
| `test_run_pairs_research_with_panel` | `test_pairs_research.py:94` | Same | **Yes** | Same |
| `test_penny_delisting_filter` | `test_quant_v2_phase3.py:62` | delisting rule not in `failed_rules` | No | Filter logic / env reload issue |

### G. Missing backend contract tests

No dedicated tests for:

- `GET /api/v2/predictions`
- `GET /api/v2/feedback/summary`
- `GET /api/v2/weights/{sleeve}`
- `GET /api/v2/audit`
- `GET /api/v2/factors/admin`
- `POST /research/walk-forward`
- `POST /research/pairs`
- `GET /data/scheduler/status`

Only `GET /api/v2/factors/performance` has smoke coverage in `test_round2_api.py`.

---

### H. Missing frontend component tests

| Gap | Impact |
|-----|--------|
| No `@testing-library/react` / `happy-dom` in devDependencies | Cannot render tab components |
| `vitest.config.ts` uses `environment: "node"`, includes only `*.test.ts` | `.tsx` component tests excluded |
| Zero tests for any Quant Lab tab | Regressions undetected |

---

### I. Backend runtime (IC panel — ops, not UI compile)

| Issue | Category | Status |
|-------|----------|--------|
| SQLite `database is locked` during `POST /api/v2/jobs/ic-panel` | Backend runtime | **Fixed** — `busy_timeout`, `no_autoflush` |
| IC panel 15h hang on StockTwits | Backend runtime | **Fixed** — `IC_PANEL_OFFLINE=1` during panel |

---

### J. Structural / maintainability

| ID | Issue | Proposed fix |
|----|-------|--------------|
| ST-1 | `QuantLabTabs.tsx` ~606 lines, 6 tabs + scheduler | Split into one file per tab (Phase 2) |
| ST-2 | Shared `FeatureDisabledNotice` inline | Move to `QuantLabTabShell.tsx` |
| ST-3 | No response normalizers in API layer | Add `quantLabNormalizers.ts` (Phase 4) |

---

## Priority fix order

1. Split files (maintainability, enables tab tests)
2. Normalizers + strict types (contract safety)
3. Harden null/undefined paths in all tabs
4. Add frontend component tests + backend contract tests
5. Document verification in `QUANT_LAB_FIX_VERIFICATION.md`

---

## Definition-of-done gaps at audit time

| Requirement | Audit status |
|-------------|--------------|
| `/quant-lab` loads | PASS (build) |
| Every tab renders without crash | PARTIAL — RT-1, RT-2, RT-3 risks remain |
| Walk-forward / pairs on click only | PASS |
| Feature-disabled friendly UI | PASS (503 handling present) |
| Malformed responses don't crash | PARTIAL — needs normalizers |
| `npm test/typecheck/lint/build` | PASS |
| Backend tests | FAIL (3 unrelated + missing contract tests) |
