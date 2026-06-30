# Phase 0 Visual Validation Log

**Date:** June 30, 2026  
**Phase 1 update:** June 30, 2026  
**Method:** Playwright (Chromium headless) against `http://127.0.0.1:18730` (Phase 0); code + unit tests (Phase 1)  
**Viewports:** 390×844, 768×1024, 1024×768, 1440×900  
**Pages:** Portfolio `/`, Scan, Workspace, Quant Lab, Library, Settings

Screenshots were not archived in-repo in Phase 0; DOM visibility checks and HTTP status recorded below. Manual screenshot capture optional in Phase 4 polish.

---

## Cross-cutting navigation

| Finding (audit) | 390px | 768px+ | Classification |
|-----------------|-------|--------|----------------|
| Primary nav hidden below 768px (§7.1) | `.app-nav-center` not visible; **`.mobile-bottom-nav` present (Phase 1)** | Nav tabs visible (6 links) | **Resolved Phase 1** |
| Command Palette as only mobile nav aid | Bottom nav + More → Search; palette improved | Present | **Resolved Phase 1** |
| Settings in primary nav (§7.2) | Hidden with other tabs | Visible in tab bar | **Code-only** (unchanged; deferred) |
| Missing focus rings (§8.1) | `:focus-visible` on shared controls via `--color-ring` | Same | **Resolved Phase 1** (code + CSS) |

---

## Portfolio / Home (`/`)

| Finding | Result | Classification |
|---------|--------|----------------|
| Summary metrics scattered (§12.1) | Page renders ~1767–1888 chars body text; holdings data present when backend connected | **Unable to verify** layout quality without screenshot |
| Multiple banner stacking (§12.1) | `PublicDemoBanner`, `DataFreshnessBanner`, `DemoDataBanner`, `DismissibleNotice` all in component tree | **Partially confirmed** (code); stack height not measured |
| Tabs in page-header action area (§12.1) | `PortfolioWorkspace` uses `AppTabBar` in header actions for Today / Research / Activity | **Code-only finding** |
| Holdings table primary | `ActiveHoldingsDecisionTable` renders when holdings exist | **Browser confirmed** (content present) |
| Correlation heatmap (§9.2) | Numeric + `aria-label` + strength text per cell | **Resolved Phase 1** |

---

## Scan (`/scan`)

| Finding | Result | Classification |
|---------|--------|----------------|
| Header overcrowded (§12.2) | Scan page loads; ~3184–3281 chars body at all widths | **Unable to verify** clutter without screenshot |
| Horizontal-scroll table (§10.2) | `StockTable` + `DenseTable` with column customization | **Code-only** |
| Loading stage inconsistency (§12.2) | `ScanProgress`, `ScanInlineStatus` in codebase | **Code-only** |
| Bucket tabs / filters | `ScanCommandBar`, bucket routes via `/scan` | **Browser confirmed** (page loads with scan UI) |
| Scan filter focus | `scan-command-bar__btn:focus-visible` ring | **Resolved Phase 1** |

---

## Analyze / Workspace (`/workspace`)

| Finding | Result | Classification |
|---------|--------|----------------|
| Empty right margin 1024–1279px (§12.3) | Workspace layout uses full-height shell; margin not measured | **Unable to verify** |
| Mobile symbol selection discoverability (§12.3) | Empty workspace ~1690–2096 chars without `?symbol=` | **Partially confirmed** (empty state shown) |
| Many controls acceptable (§12.3) | `AnalysisPanel` + 9+ analysis tabs in code | **Code-only** |
| Chart text alternatives (§9.1) | `PriceChart` sr-only `ChartTextSummary` | **Resolved Phase 1** (touched charts) |

---

## Quant Lab (`/quant-lab`)

| Finding | Result | Classification |
|---------|--------|----------------|
| Information hierarchy (§12.4) | Overview section default; ~2324–2402 chars body | **Unable to verify** hierarchy without screenshot |
| Progressive disclosure | `CollapsibleSection` for evidence + scan relationship | **Code-only** |
| Section tabs | overview, ideas, experiments, results, models, model-monitor, legacy | **Browser confirmed** (tabs in DOM) |
| Result charts (§9.1) | `ResultChart` visible summary line | **Resolved Phase 1** |

---

## Library (`/library`)

| Finding | Result | Classification |
|---------|--------|----------------|
| Silent request failures (§11.1) | `.catch(() => undefined)` → empty UI on error | **Browser confirmed** (code path; empty vs error indistinguishable in happy path) |
| List/detail layout | Two-column grid `lg:grid-cols-[300px_1fr]` for scans/reports | **Code-only** |
| Mobile behavior | Same layout stacks at `<lg`; reachable via More menu | **Partially confirmed** |

---

## Settings (`/settings`)

| Finding | Result | Classification |
|---------|--------|----------------|
| Strong responsive structure (§12.6) | Native `<select>` for sections `<md`; sidebar `md+` | **Browser confirmed** (mobile select at 390px) |
| Theme toggle promised (§5.3) | Dark label in mobile More menu; no runtime theme switch | **Partially addressed Phase 1** |
| URL persistence `?section=` | `language`, `quant-health`, `api`, `ops` | **Browser confirmed** |

---

## Findings not reproduced / corrected

| Audit claim | Phase 0 outcome |
|-------------|-----------------|
| Correlation heatmap is color-only (§9.2) | **Resolved Phase 1** — strength labels + aria |
| Design-system path mismatch (§5.1) | **Resolved** — not a visual finding |
| Production build broken | **Not reproduced** — build passes |

---

## Viewport matrix (HTTP + nav visibility)

All routes returned **HTTP 200** at all four viewports (Phase 0).

| Viewport | `.app-nav-center` visible | `.mobile-bottom-nav` visible | Command trigger |
|----------|---------------------------|------------------------------|-----------------|
| 390px | No | **Yes (Phase 1)** | Yes |
| 768px | Yes | No | Yes |
| 1024px | Yes | No | Yes |
| 1440px | Yes | No | Yes |

---

## Phase 1 automated validation (June 30, 2026)

From `frontend/`:

| Command | Result |
|---------|--------|
| `npm run lint` | **Pass** (1 pre-existing playwright.config warning) |
| `npm run typecheck` | **Pass** |
| `npm test` | **Pass** — 43 files, 197 tests |
| `npm run build` | **Pass** — Next.js 16.2.6 |

---

## Recommended Phase 2 visual checks

1. Keyboard-only traversal on all pages at 390px with bottom nav open/closed
2. Confirm no content hidden behind fixed bottom bar on Portfolio holdings scroll
3. Library error state vs empty state (unchanged scope)
4. Extend chart summaries to remaining backtest/workspace charts in Phase 3 wrapper
