# Ralph Phase Status

**Recorded:** June 30, 2026  
**Validator:** Ralph Loop Phase 2 readiness check (no Phase 2 implementation)

---

## Last completed phase

Phase 1 — Accessibility and Mobile Navigation

**Implementation status:** Code present in the working tree and matches the Phase 1 task list (with two partial items noted in the audit). **Not committed**; mixed with unrelated portfolio-ledger and Quant Lab feature work.

---

## Phase 1 verification

* [ ] Phase 1 committed — `HEAD` is `7cfbd7d` (“Added daily email update feature”); no Phase 1 commit on `main`
* [ ] Working tree clean — 43 modified tracked files + 30+ untracked paths (see Git section)
* [x] Lint result recorded — `npm run lint` **pass** (1 pre-existing warning)
* [x] Type-check result recorded — `npm run typecheck` **pass**
* [x] Test result recorded — `npm test` **pass** (43 files, 197 tests)
* [x] Production-build result recorded — `npm run build` **pass** (11 routes)
* [ ] No business logic changed — portfolio ledger backend, dedupe, snapshot logic modified in same tree
* [ ] No API contract changed — new `/api/brokerage/*` ledger and CSV preview/approve endpoints
* [ ] No financial data behavior changed — holdings rebuild, ledger CRUD, CSV import flow changed

### Phase 1 scope review (7 allowed items)

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| 1 | Visible keyboard focus states | ✅ In scope | `globals.css` `:focus-visible` ring via `--color-ring` on buttons, tabs, nav, command palette, scan filters, mobile nav, drawers, collapsibles. |
| 2 | Accessible labels for icon-only controls | 🟡 Partial | Shell components: `CommandPaletteTrigger`, `MobileBottomNav` More, `CollapsibleSection`, correlation cells. Full page audit deferred per audit. |
| 3 | Discoverable mobile navigation | ✅ In scope | `MobileBottomNav.tsx` + CSS; wired from `Nav.tsx`; `MobileBottomNav.test.tsx`. |
| 4 | Command Palette focus handling | ✅ In scope | Focus trap, restore on close, `aria-modal`, combobox/listbox, `aria-activedescendant`, live region (`CommandPalette.tsx`). |
| 5 | Accessible correlation heatmap values | ✅ In scope | `correlationLabels.ts`, numeric + `aria-label` + strength text in `PortfolioCorrelationHeatmap.tsx`. |
| 6 | Textual summaries for important charts | 🟡 Partial | `ChartTextSummary` + `chartSummary.ts` on `PriceChart` (sr-only), `ResultChart`, `PortfolioBacktestTab`. Full wrapper rollout deferred. |
| 7 | Reduced-motion handling | ✅ In scope | `@media (prefers-reduced-motion: reduce)` in `globals.css` covers skeletons, drawers, tabs, command overlay, Recharts, collapsibles. |

### Out-of-scope changes in the same working tree

These are **not** Phase 1 and block a clean Phase 2 baseline:

**Backend (8 modified + 2 untracked)**

- `backend/api/routes_brokerage.py` — ledger CRUD, CSV preview/approve
- `backend/data/portfolio_store.py`, `backend/services/portfolio_snapshot_service.py`
- `backend/services/portfolio_ledger_service.py` (new)
- `backend/models/schemas.py`, `backend/integrations/robinhood/ledger_dedupe.py`
- Related tests

**Frontend feature work (not Phase 1)**

- `PortfolioWorkspace.tsx`, `PortfolioActivity.tsx` — CSV preview flow, ledger panel
- `CsvImportReviewPanel.tsx`, `PortfolioLedgerPanel.tsx`, `ledger-ui.tsx` (new)
- `frontend/src/lib/api.ts`, `types.ts` — new brokerage API wrappers/types
- `QuantLabPage.tsx` + `ModelsTab.tsx`, `QuantEquation.tsx`, `quantLabModels.ts` (new Models section)
- Large `i18n` additions for ledger/models
- `next.config.ts`, `package.json` — KaTeX for model equations

**Docs tied to non–Phase 1 work**

- `docs/API_REFERENCE.md`, `docs/RUNBOOK.md`, `docs/USER_GUIDE.md`, `docs/QUANT_LAB.md`

### Phase 1–only file set (for isolation/commit)

```
frontend/src/app/globals.css          (focus, reduced-motion, mobile-nav CSS)
frontend/src/components/MobileBottomNav.tsx
frontend/src/components/MobileBottomNav.test.tsx
frontend/src/components/Nav.tsx
frontend/src/components/Nav.test.tsx
frontend/src/components/CommandPalette.tsx
frontend/src/components/AppTabs.tsx
frontend/src/components/ui/CollapsibleSection.tsx
frontend/src/components/ui/ChartTextSummary.tsx
frontend/src/lib/chartSummary.ts
frontend/src/lib/chartSummary.test.ts
frontend/src/lib/correlationLabels.ts
frontend/src/lib/correlationLabels.test.ts
frontend/src/components/PriceChart.tsx
frontend/src/components/quant-lab/ResultChart.tsx
frontend/src/components/portfolio/PortfolioCorrelationHeatmap.tsx
frontend/src/components/portfolio/PortfolioBacktestTab.tsx  (chart summary portions only)
frontend/src/components/scan/ScanScoreBreakdown.tsx       (focus-related only)
design-system/                                          (Phase 0 artifact)
docs/UI_AUDIT_REVISED.md
docs/ui-baseline/
.cursor/rules/pickerquant-ui.mdc
```

---

## Frontend validation (June 30, 2026)

Run from `frontend/`:

| Command | Result | Detail |
|---------|--------|--------|
| `npm run lint` | **Pass** | 1 warning: unused `BACKEND_PORT` in `playwright.config.ts` (pre-existing). |
| `npm run typecheck` | **Pass** | — |
| `npm test` | **Pass** | 43 files, 197 tests (includes Phase 1: `MobileBottomNav`, `chartSummary`, `correlationLabels`). |
| `npm run build` | **Pass** | Next.js 16.2.6; 11 routes compiled. |

---

## Next phase

Phase 2 — Semantic Design Tokens

Per `design-system/MASTER.md` and `docs/UI_AUDIT_REVISED.md` §Phase 2:

1. Introduce semantic tokens matching the Master file (`--color-primary`, `--color-buy`, etc.).
2. Separate interaction blue from financial green.
3. Map existing surfaces and text colors.
4. Define dark and light token sets (apply dark to shared primitives first).
5. No global color replacement; classify every green use.

**Migration order:** Buttons → Navigation → Tabs → Inputs → Badges → Tables → Cards → Charts → page components.

---

## Known pre-existing failures

These predated Phase 1 and were **not** introduced by accessibility work:

| Issue | Where | Impact |
|-------|-------|--------|
| ESLint warning: unused `BACKEND_PORT` | `frontend/playwright.config.ts` | Non-blocking; lint still exits 0. |
| React “Maximum update depth” stderr during test | `PublicDemoBanner.test.tsx` / `DismissibleNotice` | Tests pass; noisy stderr only. |
| E2E not run in baseline | `npm run test:e2e` | Requires `scripts/quant-lab-e2e-up.sh`; not executed in this check. |

No Phase 1 regressions detected: all four frontend gates pass on the current tree.

---

## Phase 2 starting risks

### Remaining hardcoded green values

| Location | Value / pattern | Current role |
|----------|-----------------|--------------|
| `globals.css` `:root` | `--brand: #00c805`, `--brand-soft`, `--brand-text` | Robinhood green — used for **interaction** and logo |
| `globals.css` | `#6bff96` gradient in progress/skeleton bars | Decorative loading |
| `globals.css` | ~85 `var(--brand)` references | Primary buttons, active tabs, nav selection, scan/command highlights |
| Component Tailwind | `emerald-*`, `green-*` in 30+ files | Mix of financial signals, success, health, and interaction |
| `ledger-ui.tsx` (untracked) | `emerald-*` focus rings and buy styling | **Interaction + buy** — high misclassification risk |
| `lib/chartSeries.ts`, `TradeJournal.tsx`, etc. | `#00c805` literals | Charts and legacy journal UI |

**Rule:** Do not globally replace `#00c805`, `emerald-*`, or `green-*` (audit §5.2).

### Remaining hardcoded neutral colors

| Pattern | Scale | Notes |
|---------|-------|-------|
| `zinc-*` Tailwind | 100+ files | De facto neutral palette; not mapped to `--color-foreground-*` |
| `globals.css` legacy | `--background`, `--surface`, `--surface-elevated`, `--surface-muted`, `--surface-border` | Parallel to Master `--color-surface-*` |
| `text-secondary`, `text-tertiary` | Utility classes in CSS | Not aligned with `--color-foreground-secondary/muted` |

### Legacy token aliases

```text
--brand / --brand-soft / --brand-text     → Robinhood green (interaction today)
--focus-ring                              → brand-tinted (superseded by --color-ring blue for focus-visible)
--color-ring                              → #60a5fa (Phase 1 focus — correct per Master)
--color-background / --color-foreground   → partial aliases only
--surface-* / --foreground / --background → legacy shell tokens (dominant)
```

### Components using green for interaction

| Component / selector | Mechanism |
|----------------------|-----------|
| `.btn-primary` | `background: var(--brand)` |
| `.app-tab--active` | brand tint + `color: var(--brand)` |
| `.mobile-bottom-nav__link--active` | `color: var(--brand)` |
| `.mobile-bottom-nav__lang-btn--active` | brand border/color |
| Desktop nav (`AppTabLink` → `.app-tab--active`) | Same as tabs |
| `scan-command-bar__btn` active states | brand mixes in `globals.css` |
| Command palette selected row | brand background mixes |
| `ledger-ui.tsx` inputs/buttons | `focus:border-emerald-500` (untracked feature UI) |

### Components using green for financial meaning

| Component | Meaning |
|-----------|---------|
| `RecommendationBadge`, `RecommendationBlock` | Buy / strong_buy |
| `DecisionMixBar`, `DecisionBadge` | Buy % segments |
| `PortfolioCorrelationHeatmap` legend | Low correlation (financial context) |
| `FactorAttributionTable`, `ValuationBlock` | Positive contribution / cheap |
| `ScanScoreBreakdown`, `ScoreBadge`, `ConfidenceBadge` | High scores |
| `portfolioRiskColors.ts` | Risk tier coloring |
| Price charts (`chartSeries.ts`) | Positive price movement |

### Files requiring careful classification

**High priority (shared primitives — migrate first in Phase 2)**

- `frontend/src/app/globals.css` — buttons, tabs, nav, scan bar, command palette, mobile nav
- `frontend/src/components/ui/buttons.tsx` (if used alongside CSS classes)
- `frontend/src/components/AppTabs.tsx`
- `frontend/src/components/Nav.tsx` / `MobileBottomNav.tsx`

**Financial — do not remap to blue**

- `frontend/src/components/badges/RecommendationBadge.tsx`
- `frontend/src/components/dashboard/daily-decision/DecisionMixBar.tsx`
- `frontend/src/lib/chartSeries.ts`
- `frontend/src/lib/portfolioRiskColors.ts`

**Ambiguous — classify before editing**

- `ledger-ui.tsx`, `PortfolioLedgerPanel.tsx` — buy/sell + form focus (feature branch; isolate from Phase 2 token PR if possible)
- `ApiSettingsPanel.tsx`, `HealthStatusBadge.tsx` — “configured” / “ok” success vs financial
- `QuantLabTrustBadge.tsx`, `ResearchReliabilityCard.tsx` — reliability “fresh” vs buy signal
- `ScanEvaluationResultPanel.tsx` — “best” highlight vs recommendation

**Deferred to Phase 3+**

- Page-level `zinc-*` density (`ExperimentStudio.tsx`, `ResultsTab.tsx`, `TradeJournal.tsx`)
- Full `ChartTextSummary` wrapper rollout
- Light theme (`[data-theme="light"]`) — Phase 5 per audit

---

## Git state (June 30, 2026)

```
Branch: main (up to date with origin/main)
HEAD:   7cfbd7d — Added daily email update feature
Status: dirty — Phase 1 + portfolio ledger + Quant Lab Models + design-system docs uncommitted
```

**Recommendation before Phase 2 Ralph Loop:**

1. Split or stash non–Phase 1 work (portfolio ledger backend/frontend, Models tab).
2. Commit Phase 1 accessibility/navigation as a dedicated commit (or branch).
3. Confirm `git diff` touches only the Phase 1 file set above.
4. Re-run the four frontend gates on the isolated commit.

---

## Phase 2 readiness

| Criterion | Ready? |
|-----------|--------|
| Phase 1 implementation complete | ✅ (in working tree) |
| Phase 1 committed and tree clean | ❌ |
| No backend / API / calculation drift in baseline | ❌ |
| Frontend lint / typecheck / test / build | ✅ |
| Design system authority (`design-system/MASTER.md`) | ✅ |
| Phase 2 risk inventory documented | ✅ (this file) |

**Verdict:** The repository is **not ready** to start the Phase 2 Ralph Loop on `main` as-is. Complete Phase 1 isolation and commit first; keep ledger and Models work on a separate branch or commit series so token migration diffs stay reviewable and guardrails remain enforceable.
