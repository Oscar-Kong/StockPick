# Product surface boundaries: Scan, Quant Lab, Portfolio

StockPick separates **production screening** from **research validation** and **portfolio decision-support**. Scan (`POST /scan/{bucket}`) is the only surface that updates live ranked candidates when a new scan runs. Quant Lab loads persisted evidence and runs experiments on user action; it never silently re-ranks today's scan. Portfolio (`/`) presents daily decisions, research tools, and ledger activity — it informs the user but does not place trades or act as an execution layer.

This boundary exists so offline evaluation (walk-forward, scan-eval harness, factor IC) cannot leak into live rankings without an explicit, reviewable change proposal. Agents and contributors must preserve it when wiring new features.

**Canonical detail:** [QUANT_LAB.md](../QUANT_LAB.md), [USER_GUIDE.md](../USER_GUIDE.md), [CONTEXT.md](../../CONTEXT.md).
