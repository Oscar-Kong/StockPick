# Quant Lab

**Route:** `/quant-lab`

Advanced research and operational diagnostics. Does **not** auto-update live scan rankings or primary recommendations.

## Tabs (implemented)

| Tab | API | UX |
|-----|-----|-----|
| Factor Performance | `GET /api/v2/factors/performance` | Sleeve filter; stale IC warning; empty state when no IC rows |
| Walk-Forward | `POST /research/walk-forward` | **Run** button; shows run_id and aggregate horizons |
| Prediction Outcomes | `GET /api/v2/predictions`, `/feedback/summary` | Uses `alpha_score` + `outcome` fields (not legacy `score`/`resolved`) |
| Pairs Trading | `POST /research/pairs` | Min 2 symbols; summary stats; insufficient-data warnings |
| Data Quality | `getQuantHealthSummary`, `/data/scheduler/status` | Embedded Quant Health card (no double border) + scheduler jobs |
| Model Admin | `/api/v2/version`, `/weights`, `/audit`, `/factors/admin` | Feature-disabled notice on 503; factor catalog count |

## Related

- [Frontend Information Architecture](FRONTEND_INFORMATION_ARCHITECTURE.md)
- [UI API Coverage Map](UI_API_COVERAGE_MAP.md)
