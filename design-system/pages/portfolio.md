# Portfolio — Research & Activity Workspace

> **Route:** `/?tab=research` · `/?tab=activity` · `?panel=`  
> **Components:** `PortfolioResearch`, `PortfolioActivity`, sub-tabs (optimize, backtest, exposure, rebalance, ledger, CSV)  
> **Audit:** `docs/UI_AUDIT.md` §12.1, §9.2, §9.3, §15 Phase 4 (#2 Portfolio), §16  
> **Implementation phase:** Phase 4 — correlation/chart a11y items also in Phase 1 (§15)  
> **Parent:** `design-system/MASTER.md`  
> **ui-ux-pro-max pattern:** Portfolio Grid + institutional research — neutral surfaces, data-first, minimal decorative accent

---

## Audit alignment (June 2026 revised audit)

| Audit finding | Severity | This page response |
|---------------|----------|-------------------|
| Correlation heatmap color-only | Major | Phase 1: numeric cell values + legend — **before** layout redesign (§9.2) |
| Charts missing text alternatives | Major | Phase 1: visible CAGR / max DD / Sharpe above backtest chart (§9.1) |
| Metric duplication | Moderate | `MetricTile` wraps `MetricCard`/`StatTile` — gradual migration (§6.2) |
| Card/surface duplication | Moderate | Single surface primitive with variants — wrap, don’t delete (§6.3) |
| Async fragmentation | Major | Shared shell with `refreshing` + `partial` for backtest runs (§6.4) |
| Token drift | Major | Component-by-component green classification — no `#00c805` codemod (§5.2) |
| Allocation info repeated | Browser validation required | Confirm duplication before removing panels (§12.1) |
| Reorganize without reducing functionality | Required | Inventory every panel + `?panel=` link before moving (Master §14, audit Phase 0) |

**Scope:** Research and Activity tabs. Today / daily cockpit is in `home.md`. Audit §15 lists **Portfolio** as one Phase 4 item — implement Home + Portfolio tabs in coordinated commits.

---

## Page purpose

Portfolio (non-Today tabs) is the **management and research layer**: optimize holdings, run backtests, inspect exposure, rebalance, import brokerage data, and review ledger activity.

**Preserve:** All research panels, backtest results, factor exposure, allocation charts, CSV import/review, ledger CRUD, rebalance calculations, correlation heatmap data, every `?panel=` deep link.

---

## Makeover vision

Reorganize scattered research panels into a **persistent two-pane shell**:

```text
Portfolio Header (shared with Home — tabs below title)
├── Tab: Today | Research | Activity
│
Research tab:
┌──────────────┬────────────────────────────────────────┐
│ Panel nav    │ Active panel workspace                   │
│ (vertical)   │  — Optimize / Backtest / Exposure /    │
│              │    Allocation / Risk / Advanced          │
└──────────────┴────────────────────────────────────────┘

Activity tab:
┌──────────────┬────────────────────────────────────────┐
│ Activity nav │ CSV import · Ledger · Cash · Journal     │
└──────────────┴────────────────────────────────────────┘
```

Mirror **Settings page pattern** (side nav desktop + mobile `<select>`) — already the best responsive nav in the app.

---

## Layout changes

| Area | Current | Makeover | Priority |
|------|---------|----------|----------|
| Research sub-nav | Nested tabs / panels vary by sub-component | Left `panel nav` with `aria-current="page"`; URL `?tab=research&panel=` | Major |
| Activity | Mixed toolbar + inline sections | Same side-nav shell as Research | Major |
| Metric cards | `MetricCard`, local duplicates, inline stats | `MetricTile` compatibility layer wrapping existing components (§6.2) | Moderate |
| Cards | `app-card`, `surface-card`, inline zinc borders | `AppCard` variants only | Moderate |
| Correlation heatmap | Color-only cells | Add numeric legend + cell labels on focus/hover; sr-only summary row | Major |
| Backtest chart | Recharts without text summary | Equity curve + **visible** CAGR, max DD, Sharpe as text (ui-ux-pro-max chart a11y) | Major |

---

## Panel-specific upgrades

### Research — Optimize / Backtest
- ui-ux-pro-max chart guidance: **Line chart** for equity curve with paginated time range; max ~500 points visible; OHLC only if data supports it
- Place KPI bullets above chart: total return, benchmark delta, drawdown — AAA-accessible numerics always visible
- Collapse advanced parameters into “Advanced” `CollapsibleSection` — progressive complexity (Master §1.5)

### Research — Exposure / Allocation
- Replace duplicate metric cards with one `SummaryStrip` per section
- Sector bars: label + percentage text on every segment (not color-only)
- Keep `PortfolioFactorExposurePanel` data; tighten padding to `--space-4`

### Research — Rebalance
- Action column: primary blue button for “Apply preview”; destructive red only for irreversible actions
- Preview table: sticky header via `DenseTable`

### Activity — CSV import
- `CsvImportReviewPanel`: step indicator (Upload → Preview → Confirm)
- Error rows: inline `ErrorState` per section, not silent skip

### Activity — Ledger
- `ledger-ui.tsx`: migrate `emerald-*` / `zinc-*` to semantic tokens
- Dense table row height 44px; right-align amounts

---

## States

| State | Pattern |
|-------|---------|
| Loading | `LoadingSkeleton` matching panel shape — not plain text |
| Empty | `EmptyState` per panel (“No backtest yet — configure and run”) |
| Error | `ErrorState` with retry — replace `AsyncSection` inline red text |
| Stale | Inherit Home freshness banner; panel-level stale badge on backtest results |

---

## Responsive

| Breakpoint | Behavior |
|------------|----------|
| <768px | Mobile `<select>` for panel nav (copy Settings) |
| 768–1024px | Collapsible panel nav drawer |
| 1024px+ | Fixed 220px side nav |

Research tables: horizontal scroll wrapper + “essential columns” mode on mobile.

---

## Accessibility

- Side nav: `aria-current="page"` on active panel
- Heatmap: provide sortable data table fallback (ui-ux-pro-max OHLC/chart fallback pattern)
- Form fields in ledger: visible labels, not placeholder-only
- Focus trap in CSV review modal if used

---

## Anti-patterns

- Removing rebalance/backtest/exposure panels to “simplify”
- Repeating same allocation stats in multiple cards (Master §14)
- Gauge charts without numeric value beside chart

---

## Implementation checklist

### Phase 1 (before layout redesign)
- [ ] Correlation heatmap: numeric values readable without color (§9.2)
- [ ] Backtest chart: textual summary + table toggle (§9.1)
- [ ] Focus-visible on rebalance/apply and ledger actions (§8.1)

### Phase 4 — Research & Activity
- [ ] Phase 0 inventory: all panels, metrics, actions, deep links
- [ ] Extract `PortfolioShell` with Settings-style side nav
- [ ] Map every existing panel to `?panel=` — record moves in inventory doc
- [ ] Unify async states via shared shell (§6.4)
- [ ] Token migration in `ledger-ui`, `PortfolioRebalanceTab` — per-component (§5.2)
- [ ] Browser-validate allocation/risk panels don’t duplicate Home holdings info
- [ ] No API or calculation changes (§16)
