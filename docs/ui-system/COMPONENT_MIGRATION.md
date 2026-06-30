# PickerQuant Component Migration Map

**Phase:** 3 — Shared Component Consolidation  
**Updated:** 2026-06-30

---

## New primitives

| Primitive | Path | Purpose |
|-----------|------|---------|
| `AsyncStateShell` | `components/ui/AsyncStateShell.tsx` | Unified idle/loading/refreshing/success/empty/error/stale/partial states |
| `Surface` | `components/ui/Surface.tsx` | Card/panel variants: default, raised, interactive, data, inset, overlay |
| `MetricTile` | `components/ui/MetricTile.tsx` | Metrics: compact, summary, card, inline, emphasized |
| `ContentTabList` / `ContentTab` | `components/ui/ContentTabs.tsx` | True in-page tabs (`role="tablist"`) |
| `FilterToggle` / `SegmentedControl` | `components/ui/ContentTabs.tsx` | Filters with `aria-pressed` |
| `ChartShell` | `components/ui/ChartShell.tsx` | Chart mount + async states + text summary |
| `DenseTable*` helpers | `components/ui/DenseTable.tsx` | Loading rows, empty row, numeric cell, selection row |

---

## Compatibility wrappers

| Legacy | Wraps | Status |
|--------|-------|--------|
| `AsyncSection` | `AsyncStateShell` | ✅ Migrated |
| `EmptyState` | `Surface` + empty layout | ✅ Migrated |
| `ErrorState` | Used by `AsyncStateShell` | ✅ Retained |
| `LoadingSkeleton` | Used by `AsyncStateShell` / tables | ✅ Retained |
| `AppCard` / `SectionCard` | `Surface` | ✅ Migrated |
| `StatTile` | `MetricTile` compact | ✅ Migrated |
| `MetricCard` | `MetricTile` card | ✅ Migrated |
| `SummaryStripItem` | `MetricTile` summary | ✅ Migrated |
| `ChartMount` | Used by `ChartShell` | ✅ Retained |
| `AppTabBar` / `AppTabLink` | Route navigation (unchanged) | ✅ Retained |

---

## Migrated call sites (Phase 3)

All existing imports of wrapper components continue to work through compatibility layers:

* `AsyncSection` consumers (30+ files) — API unchanged
* `StatTile` consumers — API unchanged
* `MetricCard` consumers — API unchanged
* `SummaryStripItem` consumers — API unchanged
* `AppCard` consumers — API unchanged

New direct usage recommended for:

* `ChartShell` — adopt in chart components during Phase 4+
* `FilterToggle` — adopt in scan filter trays during Phase 4C
* `DenseTableLoadingRows` / `DenseTableEmptyRow` — adopt in scan/portfolio tables during Phase 4B/4C

---

## Remaining migrations (Phase 4–6)

| Area | Component | Target primitive |
|------|-----------|------------------|
| Price charts | `PriceChart` | `ChartShell` |
| Quant Lab charts | `ResultChart`, backtest charts | `ChartShell` |
| Scan filters | `ScanCommandBar` buttons | `FilterToggle` |
| Portfolio tables | Holdings grid | `DenseTable*` helpers |
| Quant Lab tabs | Internal tab bars | `ContentTabList` where not route nav |
| Page cards | Direct `surface-card` class usage | `Surface` |

---

## Not safe to delete yet

* `AsyncSection.tsx` — widely imported; delete Phase 6
* `StatTile.tsx`, `MetricCard.tsx` — wrapper exports
* `AppCard.tsx` — wrapper + `SectionCard`
* `ChartMount.tsx` — used by `PriceChart` and `ChartShell`
* `AppTabs.tsx` — route navigation contract

---

## Validation

* Lint, typecheck, tests, production build: pass (Phase 3 checkpoint)
* Component APIs preserved through wrappers
* No business logic or metric calculations changed
