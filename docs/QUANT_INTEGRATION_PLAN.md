# Quant integration plan

Phased plan for optional quant frameworks (vectorbt, PyPortfolioOpt, Qlib, FinRL, LEAN) alongside the core Scan → Workspace flow.

## Principle

Quant Lab and offline jobs **validate** factors and policies; they do not re-rank today's live Scan unless a versioned scoring change is explicitly promoted ([ADR-0001](adr/0001-product-surface-boundaries.md)).

## Phases

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Shared contracts (`backend/quant/`, `quant_core/`) | ✅ |
| 2 | vectorbt + PyPortfolioOpt adapters | ✅ |
| 3 | Qlib offline alpha ingest | 🟡 |
| 4 | Policy backtests + allocation scaffold | 🟡 |
| 5 | LEAN handoff (export/import-summary) | 🟡 |
| 6 | FinRL / external training loop | ❌ |

## Runtime flags

See `.env.example` and [QUANT_STACK.md](QUANT_STACK.md) for `VBT_ENABLED`, `PYPFOPT_ENABLED`, `QLIB_ENABLED`, `FINRL_ENABLED`.

## Ops checklist

[MANUAL_INTEGRATION.md](MANUAL_INTEGRATION.md) — enable flags, run ingest, verify API endpoints.

## Remaining gaps

[ROUND2_REMAINING_WORK.md](ROUND2_REMAINING_WORK.md)
