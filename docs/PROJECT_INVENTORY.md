# Project inventory

Canonical map of StockPick product surfaces, routes, and API-only features. See also [USER_GUIDE.md](USER_GUIDE.md) and [README.md](../README.md).

## Primary routes

| Route | Surface | Affects live scan rankings? |
|-------|---------|----------------------------|
| `/` | Portfolio (Today · Daily Plan · Research · Activity); Today includes the read-only active-position monitor | No |
| `/scan` | Scan | **Yes** (on new scan) |
| `/workspace` | Workspace (watchlist + analyze) | No |
| `/quant-lab` | Quant Lab | No |
| `/library` | Library | No |
| `/settings` | Settings | No |
| `/trader-intel` | Trader Intel presets | No |

Legacy redirects: `/portfolio` → `/?tab=research`; `/trades` → `/?tab=activity`.

## API-only / wiring in progress

| Feature | Status | Doc |
|---------|--------|-----|
| Allocation recommendation | Scaffold | [QUANT_STACK.md](QUANT_STACK.md) |
| LEAN export / import-summary | Scaffold | [API_REFERENCE.md](API_REFERENCE.md) |
| Alpha ingest UI | API-only | [OPENALPHA_INTEGRATION.md](OPENALPHA_INTEGRATION.md) |
| Scheduler jobs | Ops | [RUNBOOK.md](RUNBOOK.md) |

The active-position monitor is a shipped Portfolio Today surface backed by
`GET/POST /portfolio/active-monitor`; external push notifications and minute-bar
volume/spread ingestion remain follow-up work.

## Active sleeves

- **penny** (primary) — short-term momentum
- **compounder** — long-term quality
- Legacy `medium` normalizes to `penny` at API boundaries
