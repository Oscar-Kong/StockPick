# PickerQuant Ralph UI Makeover State

## Current phase

PHASE_2

## Overall status

IN_PROGRESS

## Completed phases

* [x] Phase 1 — Accessibility and Mobile Navigation
* [ ] Phase 2 — Semantic Design Tokens
* [ ] Phase 3 — Shared Component Consolidation
* [ ] Phase 4A — Application Shell and Navigation
* [ ] Phase 4B — Portfolio
* [ ] Phase 4C — Scan
* [ ] Phase 4D — Analyze/Workspace
* [ ] Phase 4E — Quant Lab
* [ ] Phase 4F — Library and Settings
* [ ] Phase 5 — Light Theme
* [ ] Phase 6 — Cleanup
* [ ] Phase 7 — Independent Review
* [ ] Phase 8 — Blocking and Major Fixes
* [ ] Phase 9 — Release Validation

## Current phase checklist

* [ ] Create `docs/ui-system/TOKEN_MIGRATION_MAP.md`
* [ ] Inventory and classify legacy color tokens
* [ ] Define dark and light semantic token values in `globals.css`
* [ ] Migrate buttons to `--color-primary`
* [ ] Migrate desktop navigation to blue selection
* [ ] Migrate mobile navigation to blue selection
* [ ] Migrate Command Palette selection to blue
* [ ] Migrate shared tabs to blue selection
* [ ] Migrate filters and segmented controls to blue
* [ ] Migrate inputs and selects focus to blue
* [ ] Migrate badges (non-financial) to semantic tokens
* [ ] Migrate tables (row selection) to blue tint
* [ ] Migrate cards and panels to neutral tokens
* [ ] Migrate feedback states
* [ ] Migrate shared chart presentation colors
* [ ] Create `docs/ui-system/TOKEN_USAGE.md`
* [ ] Document compatibility aliases for Phase 6
* [ ] Run lint, typecheck, tests, production build
* [ ] Git diff review

## Validation status

* [ ] Lint
* [ ] Type checking
* [ ] Tests
* [ ] Production build
* [ ] 390px validation
* [ ] 768px validation
* [ ] 1024px validation
* [ ] 1440px validation
* [ ] Dark-theme validation
* [ ] Light-theme validation when applicable
* [ ] Functionality inventory comparison
* [ ] Git diff review
* [ ] Business-logic protection review

## Pre-existing failures

| Issue | Where | Impact |
|-------|-------|--------|
| ESLint warning: unused `BACKEND_PORT` | `frontend/playwright.config.ts` | Non-blocking |

## Current blockers

None.

## Files changed in current phase

* `docs/ralph/UI_MAKEOVER_STATE.md` (this file)
* `docs/ui-system/TOKEN_MIGRATION_MAP.md` (pending)
* `docs/ui-system/TOKEN_USAGE.md` (pending)
* `frontend/src/app/globals.css` (pending)

## Last completed action

Initialized Phase 2 state file. Phase 1 checkpoint: `2dfbd85`.

## Next action

Create token migration map and introduce semantic CSS variables in `globals.css`.

## Phase commit

Phase 1: `2dfbd85` — New UI phase 1
