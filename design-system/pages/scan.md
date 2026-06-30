# Scan — Stock Screener Hub

> **Route:** `/scan?bucket=`  
> **Components:** `ScanHub` → `BucketPage` → `ScanCommandBar`, `StockTable`, `ScanProgress`  
> **Audit:** `docs/UI_AUDIT.md` §12.2, §10.2, §15 Phase 4 (#3 Scan), §16  
> **Implementation phase:** Phase 4 (after Phases 0–3)  
> **Parent:** `design-system/MASTER.md`  
> **ui-ux-pro-max pattern:** Real-Time Operations — status colors, data-dense scannable table, trust signals (fresh/stale, last run)

---

## Audit alignment (June 2026 revised audit)

| Audit finding | Severity | This page response |
|---------------|----------|-------------------|
| Plain loading text | Moderate | Structured scan phases (see States below) — not generic spinner (§12.2) |
| Horizontal-scroll table | Moderate | Keep scroll + sticky symbol column; **do not** default to cards (§12.2, §16) |
| Header overcrowding | Browser validation required | Test at 390/768/1024/1440 before header restructure (§12.2, §13.3) |
| Stale data patterns | Moderate | Reuse shared freshness component from Portfolio (§11.3) |
| Dense table inconsistency | Moderate | Route through shared `DenseTable` wrapper (§10.1) |
| Mobile table strategy | Moderate | Essential columns + drawer first; card layout only if drawer fails validation |

**Audit objective (§15):** Improve comparison, partial-result feedback, and detail inspection — not rebuild the dense-table foundation.

---

## Page purpose

Scan is a **live operations screen**: run bucket scans, monitor progress, review ranked results, and jump to Analyze or Library.

**Preserve:** Bucket tabs (penny, medium, compounder), scan polling, score breakdown, recommendation columns, stale/fresh badges, result counts, command bar actions, saved scans link.

---

## Makeover vision

```text
┌─────────────────────────────────────────────────────────┐
│ Scan header (compact — one visual unit)                 │
│  Title · Bucket chip · Last scan · Fresh/Stale · Count  │
├─────────────────────────────────────────────────────────┤
│ Bucket tabs (segmented control)                         │
├─────────────────────────────────────────────────────────┤
│ Command bar (sticky on scroll)                          │
│  Run · Filter · Column picker · Saved scans             │
├─────────────────────────────────────────────────────────┤
│ Progress strip (only when scan active)                  │
├─────────────────────────────────────────────────────────┤
│ Results table (primary — full bleed width)              │
└─────────────────────────────────────────────────────────┘
```

ui-ux-pro-max: **Real-Time / Operations** — show live status where possible; green/amber/red for status only; neutral chrome.

---

## Layout changes

| Area | Current | Makeover | Priority |
|------|---------|----------|----------|
| Header | Title, meta, bucket tabs stacked — crowded on mobile | Split: row 1 = title + status; row 2 = bucket tabs full width | Moderate |
| Meta row | Last scan, fresh, count, library link inline | Group as **status cluster** with dividers; library link → ghost button | Minor |
| Command bar | Below header | **Sticky** below nav when scrolling results | Major |
| Results | `StockTable` horizontal scroll | Add mobile **compact column preset** + row tap → `StockDetailDrawer` | Major |
| Loading | Plain `<p>` Suspense fallback | `LoadingSkeleton` matching table rows | Moderate |

---

## Table upgrades (Master §10.4 + ui-ux-pro-max)

### Desktop
- Sticky header + sticky first column (Symbol)
- Right-align: score, price, change %, market cap
- Recommendation column: `RecommendationBadge` with **text + %** always visible
- Sort indicators on headers

### Mobile (375–767px)
- ui-ux-pro-max: avoid viewport-wide horizontal scroll when possible
- Default columns: Symbol, Signal (Buy/Hold/Sell + %), Score, Change %
- Secondary: tap row → drawer with full metrics + “Open in Workspace” CTA
- Optional: swipe hint on first visit

### Score breakdown
- Keep `ScanScoreBreakdown` in drawer — progressive disclosure
- Do not expand all breakdown rows in main table

---

## Status & trust signals

| Signal | Treatment |
|--------|-------------|
| Fresh scan | Green text label “Fresh” + timestamp — not green background on entire header |
| Stale | `StaleDataBadge` + amber subtle border on table wrapper |
| Scan running | `ScanProgress` as thin progress strip under command bar — not modal |
| Zero results | `EmptyState`: “No results — adjust filters or run scan” + CTA |

---

## States

Audit §12.2 recommends **phase-specific loading copy** during active scans (i18n):

```text
Preparing universe → Downloading data → Filtering candidates → Ranking results → Finalizing evidence → Partial results available
```

| State | Current | Target |
|-------|---------|--------|
| Loading hub | Plain text | Skeleton header + 8 table row skeletons |
| Loading scan | Generic | Phase labels above progress strip; `partial` async state when rows arrive early (§6.4) |
| Loading results | In BucketPage | Skeleton rows matching final table structure |
| Error | Inline | `ErrorState` + retry run scan |
| Empty | Varies | Unified `EmptyState` with filter/run CTA |
| Stale | Partial | `StaleDataBadge` + table wrapper indicator (keep) |
| Refreshing | — | Preserve visible results + top banner (§6.4 `refreshing`) |

---

## Responsive

- Bucket tabs: `overflow-x-auto` (keep) + scroll snap
- Command bar: wrap to two rows on mobile; primary “Run scan” always visible
- `PageContainer full` — keep full bleed for table (Master §9)

---

## Accessibility

- `StockTable` column picker: keep `aria-expanded`
- Sort buttons: `aria-sort`
- Stale/fresh: text status, not color-only
- Focus-visible on command bar controls
- Table caption via `DenseTable` `sr-only` caption prop

---

## Color rules (Master §3)

- Green/red in table cells: price movement and Buy/Sell badges only
- Active bucket tab: **blue** underline or border (primary), not brand green
- Scan “Run” button: blue primary

---

## Anti-patterns

- Marketing hero above results
- Hiding recommendation % behind icon-only dots
- Full-page spinner blocking command bar during refresh
- **Converting scan table to cards by default** (audit §16)
- Removing bucket descriptions or freshness without measured clutter (§12.2)

---

## Implementation checklist

### Phase 0
- [ ] Record all Scan columns and filters (audit Phase 0 step 9)

### Phase 4 — Scan
- [ ] Browser-validate header crowding at required breakpoints
- [ ] Restructure header into two compact rows (if validated)
- [ ] Sticky command bar
- [ ] Phase-labeled scan progress + partial results state
- [ ] `LoadingSkeleton` for hub + results
- [ ] Sticky symbol column + row drawer (not card grid)
- [ ] Shared freshness/status cluster (reuse across Scan/Home)
- [ ] Tab active state → interaction blue token (Phase 2)
