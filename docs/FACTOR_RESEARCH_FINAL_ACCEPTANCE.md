# Factor Research — Final Acceptance Report (Phase 11)

**Date:** 2026-07-02  
**Final status:** **`PHASE_11_COMPLETE`**

---

## 1. Executive summary

The eleven-phase factor-discovery program is complete. Quant Lab provides a governed, auditable research workflow from idea through extended staging, promotion review, and shadow scoring — **without silently modifying live scan rankings, factor weights, portfolio decisions, or orders**.

Acceptance evidence:
- Fixture acceptance: `PHASE_11_COMPLETE` (~18s)
- Real-database acceptance: `PHASE_11_COMPLETE` (~0.7s, artifact-backed PIT)
- Backend: **912 passed**, 2 skipped
- Frontend: typecheck ✅, tests **224 passed**, build ✅
- Secrets scan: ✅ clean

---

## 2. Phase 0–11 traceability

See [PHASE_0_TO_11_TRACEABILITY.md](./PHASE_0_TO_11_TRACEABILITY.md).

Phase 9B.1 corrected history is recorded there (debugging aborts ≠ acceptance failure; recursion/audit fixes; ~4s preflight; `READY_FOR_EXTENDED_STAGING`).

---

## 3. Architecture after completion

```text
Research idea
  → experiment definition (Quant Lab)
  → immutable snapshot (FactorResearchSnapshotService)
  → supervised research run (staging run suite / mining orchestrator)
  → extended staging matrix (9B.2)
  → reproducibility validation
  → promotion candidate (Phase 10 governance)
  → evidence bundle + gate review
  → shadow scoring (isolated)
  → manual integration decision OUTSIDE Quant Lab
```

Live scan path (`ScoringEngine` → `FactorEngine.build_signals` → `WeightStore`) has **no** discovery factor hook.

---

## 4. Data readiness

| Check | Fixture | Real DB |
|-------|---------|---------|
| Database | ✅ | ✅ |
| Historical store | ✅ (fixtures) | ✅ |
| PIT universe | ✅ seeded | ✅ via extended staging artifact |
| Extended staging | ✅ contract | ✅ 30/30 cells, `READY_FOR_PROMOTION_REVIEW` |

Limitations: [FACTOR_RESEARCH_LIMITATIONS.md](./FACTOR_RESEARCH_LIMITATIONS.md)

---

## 5. Leakage and PIT

- PIT membership via `universe_pit` + audits
- Negative controls in extended staging
- Forward labels isolated in validation engine
- Leakage audit float-cast fix (real int64 volume)
- **Remaining:** fundamentals publication-date PIT not in staging provider

---

## 6. Statistical reliability

See [RESEARCH_RELIABILITY.md](./RESEARCH_RELIABILITY.md). Staging candidates intentionally weak (acceptance FAIL) — infrastructure validation, not factor optimization.

---

## 7. Reproducibility

- Extended staging: 4/4 representative runs `EXACT_MATCH` (9B.2 report)
- Reproduce service + snapshot hashing
- Evidence bundles hash-verified on read

---

## 8. Extended staging (9B.2)

- Run ID: `extstage_463c9085924e`
- Status: `READY_FOR_PROMOTION_REVIEW`
- Artifact: `backend/data/factor_discovery/extended_staging/latest.json`

---

## 9. Promotion governance (10)

- Lifecycle: experimental → … → approved_for_manual_integration
- 17 versioned gates in `gate_policy_v1.json`
- Immutable evidence bundles
- Audit events on every transition
- **No live weight mutation** (tested)

---

## 10. Shadow isolation

- `FactorShadowScoringService` computes hypothetical scores separately
- `FactorEngine.build_signals()` unchanged
- Flags default off: `FACTOR_SHADOW_SCORING_ENABLED=false`

---

## 11. Frontend acceptance

Quant Lab workflow components verified:
- Overview, Ideas, Experiment Studio, Results (abort hooks), Model Monitor
- Factor Discovery: sessions, review queue, registry, readiness, **Promotion Review**
- Advisory labels on Promotion Review panel

Manual browser QA recommended; no factor-discovery Playwright E2E yet.

---

## 12. Performance (acceptance run)

| Step | Fixture mode |
|------|--------------|
| Total acceptance | ~18s |
| Fixture test subset | ~17s |
| Real preflight (when enabled) | ~4s (9B.1 historical) |
| Extended staging (full) | ~93s (9B.2 historical) |

No per-date universe audit regression (9B.1 SQL aggregate fix preserved).

---

## 13. Security

- `./scripts/check-secrets.sh`: **pass**
- No API keys in diagnostics endpoints
- Promotion/evidence paths under controlled data directories
- LLM explain endpoint: structured summary only; cannot override gates

---

## 14. Code consolidation (Phase 11)

Added (canonical):
- `services/factor_discovery/acceptance/final_acceptance.py`
- `services/factor_discovery/isolation_audit.py`
- `scripts/run_factor_research_acceptance.py`

Not removed (still active): staging, promotion, mining, LLM services from Phases 7–10.

---

## 15. Exact test results

```bash
# Backend
cd backend && pytest
# 912 passed, 2 skipped

# Frontend
cd frontend && npm run typecheck  # pass
cd frontend && npm test           # 224 passed
cd frontend && npm run build      # pass
cd frontend && npm run lint       # 8 pre-existing errors (ResultsTab hooks) — non-blocking

# Safety
./scripts/check-secrets.sh        # pass

# Acceptance
python backend/scripts/run_factor_research_acceptance.py --mode fixture  # PHASE_11_COMPLETE
python backend/scripts/run_factor_research_acceptance.py --mode real     # PHASE_11_COMPLETE (warn: staging flag off)
```

---

## 16. Known limitations

See [FACTOR_RESEARCH_LIMITATIONS.md](./FACTOR_RESEARCH_LIMITATIONS.md).

---

## 17. Deferred work (post Phase 11)

| Item | Priority |
|------|----------|
| Production Scan adapter + manual integration service | When promoting a factor |
| Factor drift monitor | Operational |
| Full panel shadow on scan universe | Enhancement |
| Fix ResultsTab ESLint react-hooks/refs | UI hygiene |
| Factor-discovery E2E spec | QA automation |

---

## 18. Live system unchanged

Confirmed:
- No `scan_adapter.py`
- `FactorLifecycleService.transition(PRODUCTION)` blocked
- Promotion candidate create/approve does not modify `FactorWeight`
- `FACTOR_MODEL_VERSION` / `STRATEGY_VERSION` unchanged by research workflow
- No broker/order integration in factor discovery path

---

## 19. Final status

# **`PHASE_11_COMPLETE`**

Acceptance artifacts: `backend/data/factor_discovery/acceptance/latest.json`
