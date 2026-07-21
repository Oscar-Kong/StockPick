# Round 2 remaining work

Engineering backlog for quant integration, portfolio tooling, and production hardening. Status key: ✅ shipped · 🟡 partial · ❌ not started.

## Quant runtime

| Item | Status | Notes |
|------|--------|-------|
| vectorbt backtests | ✅ | `VBT_ENABLED` |
| PyPortfolioOpt allocator | ✅ | `PYPFOPT_ENABLED` |
| Qlib alpha ingest | 🟡 | Offline ingest; screeners consume |
| Policy backtest engine | ✅ | Portfolio Research tab |
| Allocation recommender | 🟡 | API scaffold |
| LEAN export | 🟡 | Export/import-summary scaffold |
| FinRL / full RL loop | ❌ | External training only |

## Scan & scoring

| Item | Status | Notes |
|------|--------|-------|
| ScoringEngine parity mode | ✅ | `SCAN_SCORING_MODE` |
| Single Stage B weight table | ✅ | `sleeve_signals` shared by engine + legacy screeners; Analyze via facade |
| Scan evaluation harness | ✅ | [SCAN_EVALUATION.md](SCAN_EVALUATION.md) |
| Factor discovery Phases 0–11 | ✅ | [FACTOR_RESEARCH_FINAL_ACCEPTANCE.md](FACTOR_RESEARCH_FINAL_ACCEPTANCE.md) |
| Production discovered factors | ❌ | Separate flag from OpenAlpha |

## Portfolio & ops

| Item | Status | Notes |
|------|--------|-------|
| Robinhood MCP sync | ✅ | [ROBINHOOD_MCP.md](ROBINHOOD_MCP.md) |
| Home auto-refresh | ✅ | `refresh_orchestrator` |
| Postgres migration path | 🟡 | [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md) |
| Multi-user auth | ❌ | Post-demo |

See [INSTITUTIONAL_QUANT_ARCHITECTURE.md](INSTITUTIONAL_QUANT_ARCHITECTURE.md) for target v2 engines and [QUANT_INTEGRATION_PLAN.md](QUANT_INTEGRATION_PLAN.md) for integration sequencing.
