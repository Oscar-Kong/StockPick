# Quant Lab Stability Audit

**Date:** 2026-06-05  
**Scope:** `/quant-lab` — all tabs, API contracts, loading/error/empty/disabled states, crash risk, expensive endpoints

---

## Summary

| Tab | Auto-load | Expensive endpoints | Crash risk (after hardening) |
|-----|-----------|---------------------|------------------------------|
| Factor Performance | Yes | Low (cached IC read) | **None** |
| Walk-Forward | No (user Run) | **High** (multi-period backtest) | **None** |
| Predictions | Yes | Low | **None** |
| Pairs | No (user Run) | **Medium–High** (price matrix + stats) | **None** |
| Data Quality | Yes | Medium (composed health) | **None** |
| Model Admin | Yes | Low | **None** |

Heavy research endpoints (`POST /research/walk-forward`, `POST /research/pairs`, scheduler mutations, IC panel enqueue) are **not** auto-invoked from Quant Lab.

---

## Shared UI primitives

| Component | Location | Used by |
|-----------|----------|---------|
| `QuantLabTabLayout` | `quant-lab/QuantLabTabShell.tsx` | All tabs |
| `QuantLabEmptyState` | same | Factor, Walk-Forward, Pairs, Predictions, Model Admin, Scheduler |
| `FeatureDisabledNotice` | same | Factor, Predictions, Model Admin |
| `StaleDataBadge` | re-export from `badges/StaleDataBadge` | Factor IC, Predictions outcomes |
| `LoadingSkeleton` | `ui/LoadingSkeleton` | Via `QuantLabTabLayout`, QuantHealthCard |
| `ErrorState` + `RetryButton` | `ui/ErrorState`, `ui/RetryButton` | Factor, Walk-Forward, Pairs, QuantHealth |
| `ResearchWarning` | `ui/ResearchWarning` | Walk-Forward, Pairs, page header |

---

## Tab-by-tab matrix

### 1. Factor Performance

| Field | Detail |
|-------|--------|
| **Endpoints** | `GET /api/v2/factors/performance?sleeve=` |
| **Auto-load** | Yes — on mount and sleeve change |
| **User action** | Refresh button; sleeve select |
| **Loading** | `QuantLabTabLayout` skeleton |
| **Error** | `ErrorState` + retry; message via `parseApiError` |
| **Empty** | "No factor IC data yet" when normalized rows empty |
| **Disabled** | 503 / `SCORE_ENGINE_V2_ENABLED` → `FeatureDisabledNotice` |
| **Malformed** | `normalizeFactorPerformanceResponse`; `factorPerformanceRows` skips bad rows |
| **Stale** | `StaleDataBadge` + warning when `as_of_date` > 7 days old |
| **Expensive** | No — read-only IC summary |
| **Can crash** | No |

---

### 2. Walk-Forward

| Field | Detail |
|-------|--------|
| **Endpoints** | `POST /research/walk-forward` (user-triggered only) |
| **Auto-load** | **No** — empty until Run |
| **User action** | Sleeve, dates, horizon checkboxes, Run |
| **Loading** | Button disabled + "Running…"; no auto skeleton on mount |
| **Error** | `ErrorState` + retry after failed run |
| **Empty** | "No walk-forward run yet" before first run; "No periods scored" when `periods_scored === 0` |
| **Disabled** | N/A (research route always available; failures are errors) |
| **Malformed** | `normalizeWalkForwardResearchResponse`; safe optional chaining on stats |
| **Validation** | Date range, ≥1 horizon (20/60/90), sleeve via `BucketSelect` |
| **Last run** | `localStorage` last successful run shown when no current result |
| **Research warning** | Extended offline-research message visible |
| **Expensive** | **Yes** — multi-period walk-forward simulation |
| **Can crash** | No |

---

### 3. Prediction Outcomes

| Field | Detail |
|-------|--------|
| **Endpoints** | `GET /api/v2/predictions`, `GET /api/v2/feedback/summary` |
| **Auto-load** | Yes — both on mount |
| **User action** | Refresh |
| **Loading** | Tab skeleton until both settle |
| **Error** | Independent — `Promise.allSettled`; partial warning shows failed endpoint |
| **Empty** | "No predictions yet" when both empty and no errors |
| **Disabled** | Either endpoint 503 → full tab disabled notice |
| **Malformed** | `normalizePredictionsListResponse`; `predictionDisplayScore` / `predictionReturnPct` guard nulls |
| **Stale** | `arePredictionOutcomesStale` → badge + home stale copy |
| **Expensive** | No |
| **Can crash** | No |

---

### 4. Pairs Trading

| Field | Detail |
|-------|--------|
| **Endpoints** | `POST /research/pairs` (user-triggered only) |
| **Auto-load** | **No** |
| **User action** | Symbol textarea, Run |
| **Loading** | Skeleton while running |
| **Error** | `ErrorState` + retry |
| **Empty** | "No pairs search yet" before run; "No pairs" when result empty |
| **Disabled** | N/A |
| **Malformed** | `normalizePairsResearchResponse`; defaults `pairs`/`notes` to `[]` |
| **Validation** | Min 2 symbols, max 20 (`PAIRS_MAX_SYMBOLS`) |
| **Statsmodels** | Banner when `statsmodels_available === false` |
| **No cointegration** | Dedicated message at 5% threshold |
| **Research warning** | Extended offline-research message; output never merged into scan rankings |
| **Expensive** | **Yes** — O(n²) pair evaluation |
| **Can crash** | No |

---

### 5. Data Quality

| Field | Detail |
|-------|--------|
| **Endpoints** | `getQuantHealthSummary()` (composes `/health`, progress, latest scans ×3, scheduler, factor perf) + `GET /data/scheduler/status` |
| **Auto-load** | Yes — Quant Health card + scheduler panel |
| **User action** | Refresh on scheduler panel; links in Quant Health card |
| **Loading** | Per-section (QuantHealthCard skeleton; scheduler text) |
| **Error** | Quant Health: non-fatal card error + retry; Scheduler: amber warning, page stays up |
| **Empty** | "No scheduler jobs" when jobs array empty |
| **Disabled** | Missing providers → warning section, not fatal |
| **Malformed** | `Promise.allSettled` in health compose; `normalizeSchedulerStatusResponse` |
| **Failed jobs** | Count + summary when `status === failed` |
| **Expensive** | Medium (7 parallel calls in health summary) — acceptable for diagnostics |
| **Can crash** | No |

---

### 6. Model / Admin

| Field | Detail |
|-------|--------|
| **Endpoints** | `GET /api/v2/version`, `/api/v2/weights/{sleeve}`, `/api/v2/audit`, `/api/v2/factors/admin` |
| **Auto-load** | Yes — all four via `Promise.allSettled` |
| **User action** | Refresh |
| **Loading** | Tab skeleton |
| **Error** | Per-panel amber messages; other panels still render |
| **Empty** | "No audit events"; model admin empty when all panels null |
| **Disabled** | V2 off → `FeatureDisabledNotice` |
| **Malformed** | Normalizers for audit/factors admin; `(audit.events ?? [])` |
| **Expensive** | No |
| **Can crash** | No |

---

## Endpoints explicitly NOT auto-run from Quant Lab

| Endpoint | Reason |
|----------|--------|
| `POST /research/walk-forward` | Heavy research — Run button only |
| `POST /research/pairs` | Heavy research — Run button only |
| `POST /api/v2/jobs/ic-panel` | Job enqueue — ops/docs only |
| `POST /data/scheduler/run` | Scheduler mutation |
| `POST /data/scheduler/refresh-quotes` | Scheduler mutation |
| `POST /data/scheduler/refresh-fundamentals` | Scheduler mutation |
| Alpha ingest / rebalance job endpoints | Not exposed in Quant Lab UI |

---

## Normalization layer

All Quant Lab API helpers in `frontend/src/lib/api.ts` pass responses through `quantLabNormalizers.ts` before tabs consume them. This covers null roots, missing arrays, and partial objects.

---

## Related documents

- [QUANT_LAB.md](./QUANT_LAB.md)
- [QUANT_LAB_ERROR_AUDIT.md](./QUANT_LAB_ERROR_AUDIT.md) — first-pass error audit
- [QUANT_LAB_STABILITY_VERIFICATION.md](./QUANT_LAB_STABILITY_VERIFICATION.md) — test results after this pass
