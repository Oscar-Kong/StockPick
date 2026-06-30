# PickerQuant Token Migration Map

**Phase:** 2 — Semantic Design Tokens  
**Updated:** 2026-06-30  
**Authority:** `design-system/MASTER.md`

---

## Summary

Phase 2 separates **interaction blue** from **financial green**. Primary actions, navigation selection, tabs, filters, and focus rings now use `--color-primary`. Buy signals, positive movement, and positive performance use `--color-buy`.

Dark mode remains default. Light token values are defined in `[data-theme="light"]` but the theme toggle is deferred to Phase 5.

---

## Legacy → Semantic mapping

| Legacy token | New semantic token | Role | Phase 6 action |
|--------------|-------------------|------|----------------|
| `--brand` | `--color-buy` | Buy / positive financial (alias only) | Remove alias |
| `--brand-soft` | `--color-buy-subtle` | Buy badge background | Remove alias |
| `--brand-text` | `--color-buy` | Positive financial text | Remove alias |
| `--background` | `--color-background` | Page background | Remove alias |
| `--foreground` | `--color-foreground` | Primary text | Remove alias |
| `--surface` | `--color-surface` | Card/panel surface | Remove alias |
| `--surface-elevated` | `--color-surface-raised` | Raised surface | Remove alias |
| `--surface-selected` | `--color-surface-selected` | Row/selection (blue tint) | Remove alias |
| `--negative` / `--danger` | `--color-sell` | Negative movement / destructive | Remove alias |
| `--warn` | `--color-hold` | Hold / caution | Remove alias |
| `--focus-ring` | `--color-ring` | Keyboard focus | Remove alias |
| `--text-secondary` | `--color-foreground-secondary` | Secondary text | Remove alias |
| `--text-tertiary` | `--color-foreground-muted` | Muted text | Remove alias |

---

## Hardcoded value inventory

### Migrated in Phase 2

| Pattern | Count (approx) | Classification | Replacement |
|---------|----------------|----------------|-------------|
| `var(--brand)` in `globals.css` | 78 | Interaction | `var(--color-primary)` |
| `#00c805` in shared components | 20+ | Mixed | Classified per use (see below) |
| `.btn-primary` | 1 | Interaction | `--color-primary` + `--color-on-primary` |
| `.app-tab--active` | 1 | Selection | `--color-primary` subtle mix |
| `.mobile-bottom-nav__link--active` | 1 | Selection | `--color-primary` |
| `.command-row--active` | 1 | Selection | `--color-primary-subtle` |
| `.scan-command-bar__btn--active` | 1 | Filter active | `--color-primary` |
| `.settings-nav__link--active` | 1 | Selection | `--color-primary` |
| `.watchlist-item--active` | 1 | Selection | `--color-primary` (not buy green) |
| `PRICE_CHART_SERIES close` | 1 | Positive price line | `#22c55e` (`--color-buy`) |
| Input focus rings (ScanControls, TradeJournal, ledger-ui) | 5+ | Interaction | `focus:border-primary` |

### Classified: interaction → primary

| File | Pattern | Notes |
|------|---------|-------|
| `ApiSettingsPanel.tsx` | Toggle active bg | Primary |
| `AnalysisSidebar.tsx` | Watchlist active border | Primary |
| `LibraryPage.tsx` | Selected list item border | Primary |
| `LanguageSettingsPanel.tsx` | Active language button | Primary |
| `SettingsMenu.tsx` | Active menu item | Primary |
| `ScanProgress.tsx` | Progress fill | Primary |
| `ScanPickSummaryCell.tsx` | Hover / AI badge | Primary |
| `ApiStatus.tsx` | Online dot, settings link hover | Primary |
| Link components | `text-brand` → `text-primary` | Navigation links |

### Classified: financial → buy green

| File | Pattern | Notes |
|------|---------|-------|
| `RecommendationBadge.tsx` | Buy/hold/sell | `signal-buy`, `signal-hold`, `signal-sell` |
| `DecisionBadge.tsx` | Buy badge | `text-brand` (alias to buy) |
| `PriceChart.tsx` | Positive period change | `text-positive` |
| `chartSeries.ts` | Close line | `#22c55e` |
| `PortfolioBacktestTab.tsx` | Equity line | `#22c55e` |
| `ScoreBreakdown.tsx` | Contribution bar | `#22c55e` |
| `AnalysisSidebar.tsx` | Factor contribution bar | `bg-buy` |
| `PositionSizingBlock.tsx` | Sizing panel | `border-buy/25` |
| `DataQualityBadge.tsx` | High score | `bg-buy/20 text-buy` |
| `scan-trade-hint__buy` | Buy % segment | `--color-buy` |

### Deferred to Phase 3+ (page-level Tailwind)

| Pattern | Files | Reason |
|---------|-------|--------|
| `emerald-*` / `green-*` in quant-lab pages | 15+ | Page-specific; classify during Phase 4E |
| `zinc-*` neutrals | 100+ | Map to `--color-foreground-*` in Phase 6 |
| `HealthStatusBadge`, `QuantLabTrustBadge` | 2 | Ambiguous success vs financial — review Phase 4 |
| Hardcoded chart colors in quant-lab | 5+ | Wrap with shared chart shell in Phase 3 |

---

## CSS utility classes added

| Class | Token | Use |
|-------|-------|-----|
| `.text-primary` | `--color-primary` | Links, informational emphasis |
| `.text-positive` | `--color-buy` | Positive P&L, fresh data, success metrics |
| `.text-buy` | `--color-buy` | Buy recommendation text |
| `.text-hold` | `--color-hold` | Hold recommendation text |
| `.text-brand` | `--color-buy` | **Deprecated alias** — use `.text-positive` or `.text-buy` |
| `.signal-buy` | buy + subtle bg | Recommendation badges |
| `.signal-hold` | hold + subtle bg | Hold badges |
| `.signal-sell` | sell + subtle bg | Sell badges |

---

## Migration order completed

1. ✅ Buttons (`.btn-primary`)
2. ✅ Desktop navigation (`.app-tab--active`, `.app-brand-mark`)
3. ✅ Mobile navigation (`.mobile-bottom-nav__*`)
4. ✅ Command Palette (`.command-row--active`, `.command-trigger`)
5. ✅ Shared tabs (`.app-tab--active`, settings nav)
6. ✅ Filters (`.scan-command-bar__btn--active`)
7. ✅ Inputs (focus rings in globals + component Tailwind)
8. ✅ Badges (`RecommendationBadge`, signal classes)
9. ✅ Tables (`.watchlist-item--active`, row selection tint)
10. ✅ Cards/panels (neutral aliases, home hero gradient)
11. ✅ Feedback (`.api-pill--ok`, progress bars)
12. ✅ Charts (`chartSeries.ts`, backtest/score charts)

---

## Verification checklist

- [x] Primary buttons use blue
- [x] Navigation selection uses blue
- [x] Tabs use blue for ordinary selection
- [x] Buy remains green
- [x] Hold remains amber
- [x] Sell remains red
- [x] Positive movement remains green
- [x] Row selection uses blue tint (not buy green)
- [x] No blind global replacement
- [x] Dark and light token values exist
- [x] Dark mode remains default
