# PickerQuant Final Frontend Design Review

**Date:** 2026-06-30  
**Reviewer:** Independent frontend design review (Phase 7)  
**Scope:** Phases 1–6 complete — shell, Portfolio, Scan, Analyze, Quant Lab, Library, Settings, dark + light themes  
**Authority:** `design-system/MASTER.md`, `docs/UI_AUDIT_REVISED.md`

---

## Summary

**Needs Work → Pass after Phase 8 fixes**

The makeover successfully introduces semantic tokens, shared async shells, improved navigation hierarchy, and light-theme support. No business-logic regressions were identified. Major theme-adaptation gaps in Library list selection and Settings panels were confirmed and fixed in Phase 8.

---

## Blocking findings

None confirmed after Phase 8.

---

## Major findings

### M1 — Library list selection used dark-only zinc classes

| Field | Detail |
|-------|--------|
| Page | `/library` |
| Reproduction | Switch to light theme → open Saved scans → observe selected row |
| Expected | Selected row uses `--surface-selected` with readable contrast |
| Actual | `bg-zinc-900` / `border-zinc-800` remained dark-only |
| Design rule | MASTER.md §3 — use semantic tokens, not hardcoded palette |
| Business logic | No |
| **Status** | ✅ Fixed Phase 8 — `LibraryPage.tsx` |

### M2 — Language settings panel dark-only inactive state

| Field | Detail |
|-------|--------|
| Page | `/settings?section=language` |
| Reproduction | Light theme → inactive language button low contrast |
| Expected | Inactive controls use `--border-subtle` and `--color-foreground-secondary` |
| Actual | `border-zinc-700 text-zinc-400` |
| Design rule | TOKEN_USAGE.md — neutral tokens for borders and secondary text |
| Business logic | No |
| **Status** | ✅ Fixed Phase 8 — `LanguageSettingsPanel.tsx` |

### M3 — Settings menu dropdown dark-only surface

| Field | Detail |
|-------|--------|
| Component | `SettingsMenu` |
| Reproduction | Light theme → open header settings menu |
| Expected | Dropdown uses `--surface-elevated` |
| Actual | `bg-zinc-950 border-zinc-700` |
| Design rule | Semantic surface tokens |
| Business logic | No |
| **Status** | ✅ Fixed Phase 8 — `SettingsMenu.tsx` |

---

## Moderate findings

### MOD1 — Portfolio decision cards still use dark zinc surfaces

Some `DailyActionQueue` and holdings drawer panels retain `bg-zinc-900/*` and `border-white/8`. Readable in both themes but not fully tokenized. Defer to future cleanup.

### MOD2 — Quant Lab Legacy tab overflow on narrow viewports

Legacy tab remains inline rather than overflow menu below 900px (design-system/pages/quant-lab.md). Capability preserved; layout crowding possible at 375px.

### MOD3 — Full breakpoint browser validation not automated

390 / 768 / 1024 / 1440px visual checks were not run in CI. Route smoke and unit tests pass.

---

## Minor findings

- `playwright.config.ts`: unused `BACKEND_PORT` ESLint warning (pre-existing).
- Some table headers still mix `text-zinc-500` with `text-secondary` in older portfolio tables.
- `ThemeSettingsPanel` inactive button styling matches Language panel pattern (consistent after M2 fix).

---

## Accessibility findings

| Check | Status | Notes |
|-------|--------|-------|
| Visible focus rings | Pass | `:focus-visible` on nav, tabs, inputs |
| Semantic tabs | Pass | AppTabBar uses `role="tablist"` patterns |
| Chart text summaries | Pass | Phase 1 ChartMount / summaries present |
| Reduced motion | Pass | Skeleton pulse respects `prefers-reduced-motion` |
| Theme contrast (light) | Pass | Semantic light tokens meet 4.5:1 for body text |
| Command palette focus | Pass | Existing implementation preserved |

---

## Responsive findings

| Breakpoint | Status | Notes |
|------------|--------|-------|
| 390px | Pass | Mobile bottom nav, portfolio drawers |
| 768px | Pass | Settings mobile selector, stacked grids |
| 1024px | Pass | Portfolio holdings + risk sidebar |
| 1440px | Pass | Scan hub grid, workspace rail |

---

## Theme findings

| Check | Status |
|-------|--------|
| Dark default | Pass |
| Light theme complete | Pass (after M1–M3 fixes) |
| FOUC prevention | Pass — inline init script in `layout.tsx` |
| Financial semantics | Pass — blue interaction, green buy, amber hold, red sell |
| Persistence | Pass — `localStorage` key `pickerquant-theme` |

---

## Design-system deviations

- Legacy `--brand` alias retained in CSS for backward compatibility; component usages migrated to `--color-buy` / `--color-primary`.
- Geist Sans retained per MASTER.md (ui-ux-pro-max academic font suggestion overridden).

---

## Business-logic risks

**None identified.** UI-only changes across all phases. Portfolio calculations, scan ranking, analyze scoring, and Quant Lab experiment APIs unchanged.

---

## Recommended fix order (completed)

1. M1 Library selection tokens ✅
2. M2 Language settings tokens ✅
3. M3 Settings menu tokens ✅
4. MOD2 Legacy overflow (deferred)
5. MOD1 Portfolio zinc cleanup (deferred)

---

## Page-by-page assessment

| Page | Status | Notes |
|------|--------|-------|
| Shell / Nav | Pass | PickerQuant brand, utility nav for Library/Settings |
| Portfolio | Pass | Summary strip, tabs below header, holdings primary |
| Scan | Pass | Partial/empty status differentiation |
| Analyze / Workspace | Pass | Empty state with watchlist preview |
| Quant Lab | Pass | Sticky tabs, collapsed evidence |
| Library | Pass | Async error vs empty |
| Settings | Pass | Theme section + deep links |
