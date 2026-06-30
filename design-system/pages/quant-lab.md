# Quant Lab — Research & Experiments

> **Route:** `/quant-lab` (+ section / legacy tab query params)  
> **Components:** `QuantLabPage`, section tabs, `OverviewTab`, `ExperimentStudio`, `ResultsTab`, `ModelsTab`, etc.  
> **Audit:** `docs/UI_AUDIT.md` §12.4, §15 Phase 4 (#5 Quant Lab), §16  
> **Implementation phase:** Phase 4 — chart/shell items partially in Phase 1 & 3  
> **Parent:** `design-system/MASTER.md`  
> **ui-ux-pro-max pattern:** Feature-rich research showcase — academic readable typography, progressive disclosure, block-based sections

---

## Audit alignment (June 2026 revised audit)

| Audit finding | Severity | This page response |
|---------------|----------|-------------------|
| Vertical crowding before workspace | Moderate (browser validation required) | Sticky tabs + collapsed evidence + **info drawer for product copy** (§12.4) |
| Information density acceptable | — | Goal is understandable workflow, not minimal UI (§12.4) |
| Async fragmentation | Major | Standardize `QuantLabTabShell` via Phase 3 async shell (§6.4) |
| Charts missing summaries | Major | Phase 1 on `ResultChart` (§9.1) |
| Reduced-motion gaps | Moderate | Skeleton pulse off under `prefers-reduced-motion` (§14) |

**Audit workflow hierarchy (§12.4)** — organize sections to match this mental model:

```text
Experiment setup → Validation config → Execution status → Results → Evidence → Interpretation → Comparison → Export/save
```

**Browser experiment (§12.4) before committing layout:**
- Sticky section sub-navigation
- Evidence panels collapsed by default
- Product explanation in info drawer (not removed)
- Restore last-used section from URL (already partially supported)

---

## Page purpose

Quant Lab is the **institutional research layer**: experiment design, backtest results, factor models, model monitoring, and legacy quant tooling.

**Preserve:** All seven primary sections + Legacy tab, evidence/scan relationship panels, research-only warnings, experiment configs, walk-forward, predictions, factor performance, model admin — all query-param deep links.

---

## Makeover vision

Reduce vertical stacking before content:

```text
Page header + ResearchOnlyBadge (one row)
├── Primary section tabs (sticky below header)
├── [Collapsed by default] Evidence · Scan relationship (accordion)
└── Section workspace (min-height fits content — no forced 12rem)
    ├── Overview | Ideas | Experiments | Results | Models | Monitor | Legacy
    └── Legacy: secondary tab row inside panel only
```

ui-ux-pro-max: **Feature-Rich Showcase** — hero metrics above fold, features below, but adapted to **compact dashboard** (not marketing hero).

---

## Layout changes

| Area | Current | Makeover | Priority |
|------|---------|----------|----------|
| Collapsible panels | Expanded by default above tabs | **Collapsed default**; move product explanation to info drawer (§12.4) | Major |
| Section tabs | 7 + Legacy in one bar | Primary 6 visible; Legacy in overflow “More” menu on `<900px` | Moderate |
| `min-h-[12rem]` | Empty padding when loading | `min-h-0`; skeleton fills natural height | Minor |
| Overview | Dense cards + tables | Top row: 4 `MetricTile` KPIs; below: two-column grid | Moderate |
| Experiments | `ExperimentStudio` form-heavy | Left config (40%) / right preview results (60%) on desktop | Major |
| Results | `ResultChart` without ChartMount | Chart + **numeric summary** + table toggle | Major |
| Legacy | Full second tab system | Visually de-emphasized: muted tab + “Legacy tools” banner | Minor |

---

## Section-specific upgrades

### Overview
- ui-ux-pro-max bullet KPIs: last run status, model version, data quality score, active experiments — all numeric text visible
- Trust badges inline, not separate card stack

### Ideas / Experiments
- Step flow: Idea → Configure → Run → Results (breadcrumb, not new routes)
- Run button: loading state disables + spinner (ui-ux-pro-max: prevent double submit)

### Results
- Chart: equity curve line + benchmark overlay
- Apply `ChartMount` to `ResultChart`
- Export + copy actions in panel toolbar

### Models / Model Monitor
- Wrap local `MetricCard` with shared `MetricTile` layer — do not delete until migrated (§6.2)
- Use `QuantLabTabShell` pattern **everywhere** in Quant Lab

### Legacy
- Keep all tabs; reduce visual weight (smaller tab text, no primary green)

---

## States (`QuantLabTabShell` as standard)

| State | Pattern |
|-------|---------|
| Loading | `LoadingSkeleton` via shell |
| Empty | `QuantLabEmptyState` with next-step CTA |
| Error | `ErrorState` with retry |
| Running experiment | Inline status pill + progress in section header |

Replace all `text-xs text-zinc-500` loading lines with shell.

---

## Responsive

| Breakpoint | Behavior |
|------------|----------|
| 375px | Section tabs scroll; overflow menu for Legacy |
| 768px | Experiment studio stacks to single column |
| 1024px | Two-column experiment layout |
| 1440px | Results chart + side metrics |

`ResearchOnlyBadge`: shorten tooltip on mobile; keep `aria-label`.

---

## Typography note

ui-ux-pro-max suggested academic fonts (Crimson Pro, Atkinson Hyperlegible) — **override: keep Geist Sans/Mono** per Master §4 for product consistency. Apply “academic readable” via:
- Slightly larger body (`14px`) in long-form result summaries only
- `QuantEquation` / KaTeX blocks unchanged

---

## Accessibility

- Section tabs: `role="tablist"` + `aria-selected`
- Research warning: `role="status"` (keep)
- Charts: table fallback + summary sentence
- Legacy tabs: keyboard nav same as primary

---

## Anti-patterns

- Removing Legacy tab before parity migration
- Full-width marketing hero for Quant Lab
- Three competing tab bars on one screen
- Hardcoded English empty strings in `ResultChart`

---

## Implementation checklist

### Phase 0
- [ ] Record all Quant Lab experiment capabilities (audit Phase 0 step 11)

### Phase 1 & 3
- [ ] `ResultChart` summary + `ChartMount` via shared chart wrapper (§9.1, §9.3)
- [ ] Async shell states including `running` / `partial`

### Phase 4 — Quant Lab
- [ ] Browser-test sticky tabs + collapsed evidence + info drawer
- [ ] Align section order to workflow hierarchy above
- [ ] Experiment studio split pane (if validated)
- [ ] Legacy overflow on narrow viewports — capability preserved
- [ ] i18n for all empty/loading strings
- [ ] No experiment API or scoring logic changes (§16)
