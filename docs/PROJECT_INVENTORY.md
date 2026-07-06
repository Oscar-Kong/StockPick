# Project inventory

Canonical map of StockPick product surfaces, routes, and API-only features. See also [USER_GUIDE.md](USER_GUIDE.md) and [README.md](../README.md).

## Primary routes

| Route | Surface | Affects live scan rankings? |
|-------|---------|----------------------------|
| `/` | Portfolio (Today · Research · Activity) | No |
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

## Active sleeves

- **penny** (primary) — short-term momentum
- **compounder** — long-term quality
- Legacy `medium` normalizes to `penny` at API boundaries
