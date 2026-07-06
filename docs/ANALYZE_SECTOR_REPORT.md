# Analyze sector report

Developer reference for Workspace analyze APIs, sector context, and v2 scoring hooks.

## Primary endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v2/score/{symbol}` | Canonical v2 score when `V2_SCORING_ENABLED` |
| `GET /analyze/{symbol}` | Legacy analyze payload (tabs, factors, sentiment) |
| `GET /watchlist` | Watchlist with optional analyze summaries |

Workspace uses `scoring_facade.score_symbol_canonical` so Analyze scores match Scan Stage B for the same symbol ([ARCHITECTURE.md](ARCHITECTURE.md)).

## Sector context

Sector/industry labels come from fundamentals reconciliation and screener metadata. Sector reports are **display context** — they do not change ranking scores.

## v2 hooks

- `ScoringEngine` factor attribution persisted via `HistoricalStore`
- OpenBB governance adjustment when `OPENBB_ON_SCAN` / analyze paths enable it
- `data_confidence` gates strong recommendations per quant rules

## UI

Investor-facing copy: [ANALYZE_PANEL.md](ANALYZE_PANEL.md). Stats guide: [ANALYZE_PANEL_STATS_GUIDE.md](ANALYZE_PANEL_STATS_GUIDE.md). Page spec: `design-system/pages/analyze.md`.

## Related

- [API_REFERENCE.md](API_REFERENCE.md)
- [INSTITUTIONAL_QUANT_ARCHITECTURE.md](INSTITUTIONAL_QUANT_ARCHITECTURE.md)
