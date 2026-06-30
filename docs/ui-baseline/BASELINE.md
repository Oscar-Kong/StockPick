# PickerQuant UI Baseline — Phase 0

**Recorded:** June 30, 2026  
**Purpose:** Validation baseline before design-system upgrade (Phases 1–6)

---

## Design-system structure (verified)

```text
design-system/
├── MASTER.md                 ← canonical (1284 lines, v2.0)
├── pickerquant/MASTER.md       ← redirect stub only
└── pages/
    ├── README.md
    ├── home.md                 ← / Today tab
    ├── portfolio.md            ← /?tab=research|activity
    ├── scan.md
    ├── analyze.md              ← full workspace spec
    ├── workspace.md            ← audit alias → analyze.md
    ├── quant-lab.md
    ├── library.md
    └── settings.md
```

`.cursor/rules/pickerquant-ui.mdc` references `design-system/MASTER.md` and `design-system/pages/[page].md` — **aligned**.

---

## Frontend stack (verified)

| Layer | Implementation |
|-------|----------------|
| Framework | Next.js 16 App Router (`frontend/`) |
| Styling | Tailwind CSS v4 + `globals.css` (~3500 lines) |
| Fonts | Geist Sans, Geist Mono |
| i18n | Client `useTranslation` provider |
| Charts | Recharts + custom visualizations |
| API | Typed wrappers in `frontend/src/lib/api*.ts` |
| State in URL | Portfolio tabs, Settings section, Library tab, Quant Lab section, Workspace symbol |

---

## Routes (production build, June 30 2026)

| Route | Page component | Layout |
|-------|----------------|--------|
| `/` | `PortfolioWorkspace` | Standard + `PageContainer` |
| `/scan` | Scan bucket UI | Standard |
| `/workspace` | Analyze workspace | Full-height `workspace/layout.tsx` |
| `/analyze` | Redirect to workspace | Dynamic |
| `/quant-lab` | `QuantLabPage` | Standard |
| `/library` | `LibraryPage` | Workspace-style scroll |
| `/settings` | Settings sections | Responsive shell |
| `/trader-intel` | Trader intel | Standard (nav link hidden `<768px`) |

---

## Shared UI primitives (verified paths)

| Category | Files |
|----------|-------|
| Shell | `Nav.tsx`, `CommandPalette.tsx`, `SettingsMenu.tsx`, `PublicDemoBanner.tsx`, `ApiStatus.tsx` |
| Buttons | `ui/buttons.tsx` (`.btn-primary`, `.btn-secondary`, `.btn-ghost`) |
| Cards | `ui/AppCard.tsx`, `.app-card`, `.surface-card`, `.data-panel` in CSS |
| Tables | `ui/DenseTable.tsx`, `StockTable.tsx`, local `<table>` in Library |
| Tabs | `AppTabs.tsx` (`AppTabBar`, `AppTabLink`, `AppTabButton`) |
| Async | `AsyncSection.tsx`, `LoadingSkeleton.tsx`, `EmptyState.tsx`, `ErrorState.tsx` |
| Badges | `badges/RecommendationBadge.tsx`, `ConfidenceBadge.tsx`, `StaleDataBadge.tsx` |
| Metrics | `MetricCard.tsx`, `StatTile.tsx`, `SummaryStrip` (daily-decision) |
| Theme | CSS variables in `globals.css` (`--brand`, `--surface-*`); dark-only runtime |

---

## Automated validation (June 30, 2026)

Run from `frontend/`:

| Command | Exact invocation | Result | Error detail | Predates UI work? | Blocks visual validation? |
|---------|------------------|--------|--------------|-------------------|---------------------------|
| Lint | `npm run lint` | **Pass** | 1 warning: unused `BACKEND_PORT` in `playwright.config.ts` | Yes (e2e config) | No |
| Typecheck | `npm run typecheck` | **Pass** | — | — | No |
| Unit tests | `npm test` | **Pass** | 40 files, 189 tests | — | No |
| Production build | `npm run build` | **Pass** | Next.js 16.2.6; 11 routes | Earlier session had `SCAN_EVAL_ALGORITHM_VERSIONS` type error — **resolved** | No |

### Notes

* Terminal history showed a prior build failure on `ScanEvaluationConfigFields.tsx`; current tree typechecks and builds cleanly.
* `PublicDemoBanner.test.tsx` logs a React "Maximum update depth" stderr warning during test run; tests still pass.
* E2E (`npm run test:e2e`) not run in Phase 0 — requires `scripts/quant-lab-e2e-up.sh` on ports 18930/18931.

---

## Dev workflow (verified)

Per `docs/RUNBOOK.md`:

```bash
./scripts/dev-up.sh          # backend :18731 + frontend :18730
# or
cd frontend && npm run dev   # http://127.0.0.1:18730
```

Phase 0 browser checks used running dev server at `http://127.0.0.1:18730` (HTTP 200 on all primary routes).

---

## Architecture findings (code-only, unchanged)

* Green `--brand` / `#00c805` used for interaction and financial semantics (audit §5.2)
* No `:focus-visible` on shared button classes (audit §8.1)
* `.app-nav-center { display: none }` below 768px (audit §7.1)
* Library swallows fetch errors (audit §11.1)
* Light theme tokens in Master; runtime is dark-only (audit §5.3)

---

## Phase 0 exit criteria

| Criterion | Status |
|-----------|--------|
| Canonical design-system paths | ✅ |
| Page files complete | ✅ |
| Functionality inventory | ✅ `FUNCTIONALITY_INVENTORY.md` |
| Visual validation log | ✅ `VISUAL_VALIDATION.md` |
| Audit revised with browser tags | ✅ `UI_AUDIT_REVISED.md` |
| No UI/code redesign in Phase 0 | ✅ |

**Next:** Phase 2 — semantic token foundation.
