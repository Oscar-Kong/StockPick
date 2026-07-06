# Home — Daily Decision Cockpit

> **Route:** `/` (default tab: Today)  
> **Component:** `PortfolioToday` via `PortfolioWorkspace`  
> **Audit:** `docs/UI_AUDIT_REVISED.md` §12.1 (Portfolio/Home), §15 Phase 4, §16 guardrails  
> **Implementation phase:** Phase 4 (page redesign) — after Phase 0 baseline, Phase 1 a11y/nav, Phase 2 tokens, Phase 3 shared components  
> **Parent:** `design-system/MASTER.md`  
> **ui-ux-pro-max pattern:** Real-Time Operations Dashboard — dark, data-dense, status colors (green/amber/red), scannable metrics

---

## Audit alignment (June 2026 revised audit)

| Audit finding | Severity | This page response |
|---------------|----------|-------------------|
| Tabs in page-header actions | Moderate | Move tabs below title — **browser-validate** wrapping first (§13.3) |
| Multiple banner types stacking | Moderate | One notification rail — **browser-validate** before merging (§12.1) |
| Metric component duplication | Moderate | Use `MetricTile` via **wrap** migration, not delete StatTile/SummaryStrip (§6.2) |
| Async state fragmentation | Major | Adopt shared async shell: `loading` · `refreshing` · `empty` · `error` · `stale` · `partial` (§6.4) |
| Green used for interaction | Major | Phase 2: blue primary buttons; green = Buy/P/L only — **no global codemod** (§5.2) |
| Missing keyboard focus | Blocking | Phase 1: focus rings on Run/Refresh/row actions before layout work (§8.1) |
| Mobile nav below 768px | Major (Blocking at release) | Phase 1 shell change — not Home-only (§13.2) |
| Scattered summary metrics | Browser validation required | Confirm at 390/768/1024/1440 before Band 2 redesign (§12.1) |
| Sidebar split (35/65) | Browser validation required | Do not ship grid change until holdings table remains primary in browser (§12.1) |

**Naming (audit §4.3):** Audit treats Portfolio/Home as one route family. This file covers the **Today / daily cockpit** tab only; **Daily Plan**, Activity, and Research are separate Portfolio tabs (tab order: Today · Plan · Activity · Research).

---

## Page purpose

The Home page is the **operational cockpit**: answer “What should I do with my portfolio today?” without extra clicks. It is not a marketing landing page.

**Preserve:** Buy/Hold/Sell percentages, confidence, decision queue, **Daily Trading Plan** (dedicated **Daily Plan** tab — policy-gated short-term plan), holdings table, risk alerts, penny opportunities, Run Now / Refresh, data freshness banners, demo-data indicators, all API contracts.

---

## Makeover vision

Transform Home from “header + stacked panels” into a **three-band command layout**:

```text
┌─────────────────────────────────────────────────────────┐
│ Band 1 — Cockpit header (compact, single row on desktop)│
│  Title · Status pill · Freshness · Primary actions      │
├─────────────────────────────────────────────────────────┤
│ Band 2 — Performance hero (Robinhood-style)             │
│  Total value · range % · 1D/1W/1M/6M/1Y area chart      │
│  KPI row: Today P/L · Unrealized P/L · Realized P/L     │
├─────────────────────────────────────────────────────────┤
│ Band 3 — Split workspace (Today tab)                    │
│  ┌──────────────────────┬──────────────────────────┐  │
│  │ Action queue (left)   │ Holdings table (primary) │  │
│  │ Penny ops (optional)  │ Expandable row details   │  │
│  │ Risk alerts           │                          │  │
│  └──────────────────────┴──────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Performance hero (`PortfolioPerformancePanel`):** Full-width glass card with gradient area chart; range pills as segmented control (role=tablist); KPI strip uses semantic green/red for P/L only. Data from `GET /portfolio/performance`; **YTD-only** — unrealized = open-position cost basis; realized = `{year}` closed trades; chart replays `{year}` ledger from first trade date (MCP deposits calibrated from live buying power). Refreshes after Robinhood MCP sync via `performanceRefreshKey`.

ui-ux-pro-max guidance: use **bullet charts / visible numeric KPIs** beside any visual indicators — never color-only status (chart domain: Performance vs Target, AAA accessibility).

---

## Layout changes

| Area | Current | Makeover | Priority |
|------|---------|----------|----------|
| Hero | `DailyDecisionHero` separate from today toolbar — duplicated meta | Single compact cockpit bar; merge hero into Band 1 | Major |
| Summary | `PortfolioSummaryStrip` below hero | **Shipped:** `PortfolioPerformancePanel` — value + chart + P/L KPIs (Band 2) | Moderate |
| Tabs | Portfolio tabs in `PageHeader` actions | Move workspace tabs **below** page title (match Scan pattern); Home = default tab | Moderate |
| Holdings | `ActiveHoldingsDecisionTable` full width | Primary column 65%; action queue + alerts in 35% sidebar on `lg+` | Major |
| Empty state | `EmptyPortfolioState` centered | Action-oriented card: Import CSV CTA + link to Activity + sample screenshot hint | Moderate |
| Banners | Demo + freshness + dismissible notices stack | Collapse to **one** status rail with expandable detail | Moderate |

### Spacing (Master §5)

- Band gap: `24px` (`--space-6`)
- Within-band gap: `12–16px`
- Card padding: `16px` — no `48px+` hero padding
- Table row height: `44px` sticky

---

## Component upgrades

### Cockpit header
- Replace ad-hoc `border-white/8 bg-zinc-800/60` chips with semantic `.badge` tokens
- Primary action: **blue** `btn-primary` (Master §10.1) — reserve green for positive P/L and Buy signals only
- Show `DataFreshnessBanner` inline as a compact timestamp + stale badge, not full-width block

### Summary strip
- ui-ux-pro-max: **Bullet chart grid** for 3–6 KPIs — value always visible as text, optional thin range bar behind
- Include: portfolio value, day change ($ and %), cash, decision mix (Buy/Hold/Sell counts with labels), concentration warning if present
- Use `tabular-nums` on all values

### Holdings table
- Keep expandable rows + keyboard (`ActiveHoldingsDecisionTable` pattern is good)
- Mobile (<768px): essential columns only (Symbol, Rec + %, P/L, Weight); secondary fields in row drawer
- ui-ux-pro-max: horizontal scroll only when column comparison essential; prefer drawer for detail

### Action queue & alerts
- Pin `DailyActionQueue` above fold on mobile (before table scroll)
- `RiskAlertsPanel`: max 3 visible, “View all” expands — avoid pushing holdings below fold

---

## States (Master §15 + ui-ux-pro-max)

| State | Pattern |
|-------|---------|
| Loading | Keep `LoadingSkeleton variant="home"` — shape must match three-band layout |
| Empty | `EmptyState` with Import + Activity links; explain demo vs live |
| Error | `ErrorState` with retry — already good |
| Stale | `StaleDataBadge` on header + dimmed values with tooltip “calculated from stale prices” |
| Refresh | Inline banner in Band 1, not duplicate disabled buttons everywhere |

---

## Responsive

| Breakpoint | Behavior |
|------------|----------|
| 390px | Single column; action queue first; bottom nav (Phase 1 — global shell) |
| 768px | Summary strip 2×3 grid |
| 1024px | Split workspace 35/65 |
| 1440px | Full table columns; no extra empty margins |

---

## Accessibility

- Cockpit status: text label + icon, not color-only (`CockpitStatusPill` — verify)
- All icon buttons: `aria-label`
- Holdings table: `aria-expanded` on rows (keep)
- Focus-visible on Run Now, Refresh, row expand
- Skip link: “Skip to holdings table”

---

## Anti-patterns (do not apply)

- Marketing hero with large empty space (Master §18)
- Animated counting portfolio value
- Hiding Buy/Hold/Sell % behind extra clicks
- Green primary buttons

---

## Implementation checklist

### Before Phase 4 (prerequisites)
- [ ] Phase 0: screenshot baseline at 390 / 768 / 1024 / 1440 (`docs/ui-baseline/`)
- [ ] Phase 1: visible focus on shared buttons; mobile nav; icon `aria-label` audit
- [ ] Phase 3: `MetricTile` compatibility layer; async-state shell; upgraded `AsyncSection`

### Phase 4 — Home (Today tab only)
- [ ] Browser-confirm banner stacking and metric scattering
- [ ] Merge hero + toolbar into single cockpit bar
- [ ] Move Portfolio tabs below page title (coordinate with `portfolio.md`)
- [ ] Bullet-style summary strip with labeled KPIs (wrap existing SummaryStrip)
- [x] Sidebar layout for queue/alerts on desktop — **only if** holdings table stays primary (penny ops under action queue)
- [ ] Mobile column reduction + row drawer (not full card conversion)
- [ ] Phase 2 token cleanup per component — classify each green use (§5.2)
- [ ] Inventory all actions/metrics before/after (audit Phase 0 step 8)
- [ ] Verify no calculation or recommendation logic changes (§16)
