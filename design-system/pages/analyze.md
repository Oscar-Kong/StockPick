# Analyze — Research Workspace

> **RouteMap:** Audit §5.1 and §15 use filename `workspace.md` for this route; this file is the same scope.  
> **Route:** `/workspace?symbol=` (legacy `/analyze` redirects here)  
> **Components:** `WorkspacePage`, `WatchlistRail`, `AnalysisPanel`, `AnalysisTabNav`  
> **Audit:** `docs/UI_AUDIT_REVISED.md` §12.3, §9.1, §9.3, §15 Phase 4 (#4 Analyze), §16  
> **Implementation phase:** Phase 4 — chart a11y and focus in Phase 1  
> **Parent:** `design-system/MASTER.md` · **Alias file:** `workspace.md`  
> **ui-ux-pro-max pattern:** Two-column analytical workspace — content-first, minimal nav clutter, persistent metrics rail

---

## Audit alignment (June 2026 revised audit)

| Audit finding | Severity | This page response |
|---------------|----------|-------------------|
| Many controls/views acceptable for role | Moderate | Refine hierarchy — **do not** simplify to consumer dashboard (§12.3) |
| Mobile symbol selection discoverability | Moderate | Empty state: search, recent symbols, watchlist preview (§12.3) |
| Empty right margin 1024–1279px | Browser validation required | Do not change grid until confirmed in browser (§12.3, §13.3) |
| Charts missing text alternatives | Major | Phase 1: sr-only summary + table toggle on `PriceChart` (§9.1) |
| Chart mount inconsistency | Moderate | Extend `ChartMount` pattern via shared chart wrapper (§9.3) |
| Tab semantics incomplete | Moderate | `aria-controls` on content tabs only — **not** on route nav links (§16) |
| Density is intentional | — | Group related tabs; inspector/drawer for secondary evidence on narrow screens (§12.3) |

**Audit recommendations to add:**
- Prefer a flat five-tab row (Overview · Drivers · Risk · Evidence · Research) — avoid labeled group chrome that competes with tab labels
- Keep price chart full-width; pair decision summary with position sizing in a balanced row
- Show latest data date prominently in toolbar
- Use inspector/drawer for secondary evidence below `lg`

**Shared surfaces:** `GlassPanel` (`components/ui/GlassPanel.tsx`) — `hero` for price hero + watchlist preview; `default`/`compact` for chart and side panels (`analysis-glass-panel` tokens).

---

## Page purpose

Analyze is the **deep symbol research workspace**: watchlist navigation, five analysis sections (Overview / Drivers / Risk / Evidence / Research), and persistent metric context.

**Preserve:** Decision Overview, V2 score/risk/position sizing, factor attribution, price chart ranges, research report save, watchlist import, prev/next symbol nav, every analysis capability (moved into the five sections — do not delete features).

**Loading:** Rail loads independently of symbol analysis. Snapshot-first then `/analyze/{symbol}/core`. Do not block `AnalysisPanel` on watchlist matrix refresh.
---

## Makeover vision

```text
┌──────────┬──────────────────────────────────────────────────┐
│Watchlist │ Analysis workspace (fill viewport)               │
│ rail     │ ┌──────────────────────────────────────────────┐ │
│ 17–20rem │ │ Toolbar: symbol · bucket · prev/next · stats │ │
│          │ ├──────────────────────────────────────────────┤ │
│          │ │ Tab nav (underline style — Master §10.5)     │ │
│          │ ├────────────────────┬─────────────────────────┤ │
│          │ │ Primary content    │ Metrics rail (lg+)    │ │
│          │ │ (chart, tables…)   │ StatTile stack        │ │
│          │ └────────────────────┴─────────────────────────┘ │
└──────────┴──────────────────────────────────────────────────┘
```

ui-ux-pro-max: **minimal single-column focus on mobile** — one primary task per viewport; metrics collapse to horizontal strip.

---

## Layout changes

| Area | Current | Makeover | Priority |
|------|---------|----------|----------|
| Empty state | Centered text, large dead zone | Split layout always visible: watchlist + “Select a symbol” panel with search + import CTA | Major |
| Metrics rail | Hidden until `lg` — empty right gap on md | Show **compact horizontal stat strip** at md; vertical rail at lg+ | Major |
| Tab nav | Segmented `AppTabBar` / grouped CORE·RESEARCH·WORKSPACE labels | Flat Master §10.5 underline tabs — static row, not scrollable | Done (2026-07-23) |
| Toolbar | Multiple rows (meta + stats) | Single toolbar with **latest data date** prominent; stats inline scroll on mobile | Partial — hero shows score/risk/bucket/quality/bar; score source moved to Score tab context |
| Watchlist rail | Hidden on mobile; native `<select>` | Keep select but add **watchlist sheet** (bottom drawer) showing scores + rec badges | Partial — desktop rail upgraded (score bar, skeleton, glass header) |

---

## Tab content upgrades

### Overview / Score / Risk
- Chart full-width; decision + trade plan share a row with position sizing; drivers / execution / evidence / delta span full width below so cards share one left edge
- Decision Overview: shared `analysis-decision-block` padding (beats `.analysis-section { padding: 0 }`), metric tiles, hold-hint callout, thesis cards, invalidation deduped vs bear case, drivers collapse when one side empty
- Keep existing blocks; wrap in `data-panel` with consistent `--space-4` padding
- `UnifiedRiskPanel`, `ScoreBreakdown`: collapse secondary sections by default
- Alerts render as compact inline chips (not stacked full-width bars)

### Chart tab (`PriceChart`)
- ui-ux-pro-max: Line chart for price; provide **sr-only summary** (“AAPL up 3.2% over selected range”)
- Keep `ChartMount` — apply same pattern to any secondary charts
- Range buttons: `aria-pressed` (keep) + focus-visible ring
- MA checkbox: explicit `<label>` association

### Research report
- Sticky save action in panel header
- Print-friendly typography without changing data

### Backtest / Diagnostics (in tabs)
- Visible numeric summary above charts (CAGR, DD, win rate)

---

## Watchlist rail

| Desktop | Mobile |
|---------|--------|
| Filter input + sort | Bottom sheet trigger “Watchlist (N)” |
| Row: symbol, score, rec badge | Same row density; tap → select symbol |
| Alert count badge | Visible on sheet header |

Loading: skeleton rows, not `text-zinc-500` one-liner.

---

## States

| State | Target |
|-------|--------|
| Loading symbol | Keep `AnalysisLoading` pulse — add reduced-motion static fallback |
| Error | `ErrorState` in primary column (keep) |
| V2 fallback | `V2FallbackBanner` compact inline banner |
| No symbol | Illustrated empty panel + recent symbols list |

---

## Responsive (`100dvh` shell)

| Breakpoint | Behavior |
|------------|----------|
| 375px | Symbol select + bottom sheet watchlist; analysis tabs are a static non-scrolling row |
| 768px | Optional collapsible rail icon |
| 1024px | Horizontal stat strip + single column — **validate grid before changing** (§12.3) |
| 1280px | Two-column grid + vertical metrics rail |

Avoid oversized empty margins 1024–1279px — **browser-confirm before grid edits** (audit §12.3).

---

## Secondary evidence (audit §12.3)

On viewports below `lg`, move to inspector/drawer instead of permanent side columns:
- Factor attribution detail
- Similar signals
- Extended diagnostics
- Research report metadata

Keep in main column: price chart, recommendation/score summary, unified risk headline.

---

## Accessibility

- `AnalysisTabNav`: add `aria-controls` + panel `id` linkage (audit gap)
- Tab list: parent `role="tablist"` if using underline pattern
- Skip link: “Skip to analysis content”
- Chart: textual summary + data table toggle (“View as table”)
- Watchlist actions: `aria-label` on remove/import

---

## Anti-patterns

- Second tab bar duplicating workspace tabs
- Hiding score/risk behind extra modal
- layout-shifting chart on load (keep `ChartMount`)

---

## Implementation checklist

### Phase 0
- [ ] Record all Analyze views and controls (audit Phase 0 step 10)

### Phase 1
- [ ] Chart textual summaries + table fallback (§9.1)
- [ ] Focus-visible on chart range controls and tab nav (§8.1)
- [ ] Reduced-motion static skeleton fallback (§14)

### Phase 4 — Analyze/Workspace
- [ ] Browser-confirm 1024–1279px empty margin
- [ ] Empty workspace: search + recent symbols + watchlist preview (§12.3)
- [x] Flat Master §10.5 underline tabs (group chrome removed 2026-07-23)
- [ ] Inspector drawer for secondary evidence on narrow screens
- [ ] md horizontal stats strip (if validated)
- [ ] Mobile watchlist bottom sheet — keep native `<select>` unless usability test proves replacement (§16)
- [x] Complete tab `aria-controls` on **content** tabs only (2026-07-03)
- [x] Preserve all analysis fetch logic and tab configs (§16)
