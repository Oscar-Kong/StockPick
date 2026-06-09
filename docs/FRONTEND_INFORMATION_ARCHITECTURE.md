# Frontend Information Architecture

**Updated:** 2026-06-08

## Top navigation

| Route | Purpose | Audience |
|-------|---------|----------|
| `/` | Home — Quant Health, quick actions, resume | Everyone |
| `/scan` | Three bucket tabs, ranked candidates | Decision support |
| `/workspace` | Single-symbol terminal, compare, journal | Decision support |
| `/portfolio` | Optimize, policy backtest, factor exposure | Portfolio |
| `/quant-lab` | Factor IC, walk-forward, predictions, pairs, ops | Advanced quant |
| `/library` | Saved scans, reports, snapshots | Everyone |
| `/settings` | Language, API providers, scheduler | Ops |

**Secondary:** `/trader-intel` (nav actions link on md+ screens).

## Progressive disclosure

- **Decision support** — Scan rows + Workspace tabs show one primary recommendation (v2 when enabled).
- **Advanced research** — Quant Lab tabs; heavy endpoints run on user action only.
- **Admin / ops** — Settings + Quant Lab → Data Quality / Model Admin.

## Workspace (internal)

Compare and journal are **not** top-level nav items. URLs:

- `/workspace?tab=compare`
- `/workspace?tab=journal`

Redirects preserved: `/watchlist`, `/analyze`, `/trades`, `/penny|medium|compounder`, `/scans`, `/reports`.

## Shared UI components

Located under `frontend/src/components/ui/`, `badges/`, and `quant/`:

- Badges: score, source, risk, confidence, recommendation, health, stale data
- States: `EmptyState`, `ErrorState`, `LoadingSkeleton`, `RetryButton`
- Layout: `SectionHeader`, `CollapsibleSection`, `MetricCard`, `MetricGrid`, `DetailDrawer`
- Disclaimers: `ResearchWarning`, `NotFinancialAdviceFooter`

See [UI Feature Integration Audit](UI_FEATURE_INTEGRATION_AUDIT.md) for endpoint mapping.
