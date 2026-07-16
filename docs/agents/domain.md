# Domain Docs — StockPick

How engineering skills should consume this repo's domain documentation.

## Before exploring, read these

1. **`CONTEXT.md`** at the repo root — ubiquitous language for product surfaces, screening, and research-integrity terms. Use these words in issues, test names, and refactor proposals.
2. **`docs/adr/`** — architectural decisions. Read ADRs that touch the area you are about to change.
3. **Domain wiki (optional synthesis)** — Obsidian vault at `~/Documents/stockpick-brain` (`wiki/index.md`). Use the `second-brain-query` skill for cross-cutting product/architecture recall. **Repo docs win on conflict.** See `.cursor/rules/stockpick-brain.mdc`.
4. **Area-specific canonical docs** (do not duplicate into CONTEXT.md):

| Topic | Canonical doc |
|-------|----------------|
| Product mental map | [USER_GUIDE.md](../USER_GUIDE.md) |
| Module layout | [ARCHITECTURE.md](../ARCHITECTURE.md) |
| Quant Lab behavior | [QUANT_LAB.md](../QUANT_LAB.md) |
| Scan evaluation / bias controls | [SCAN_EVALUATION.md](../SCAN_EVALUATION.md) |
| Quant accuracy rules | `.cursor/rules/quant-stock-picker.mdc` |
| UI design | `design-system/MASTER.md`, `.cursor/rules/pickerquant-ui.mdc` |
| HTTP contracts | [API_REFERENCE.md](../API_REFERENCE.md) |
| Ops and flags | [RUNBOOK.md](../RUNBOOK.md) |
| Doc update map | `.cursor/rules/update-documentation.mdc` |

If `CONTEXT.md` or `docs/adr/` entries are missing for your topic, proceed silently — `/domain-modeling` creates them when terms or decisions crystallize.

## File structure

Single-context repo:

```
/
├── CONTEXT.md              ← glossary only (no implementation detail)
├── docs/adr/               ← hard-to-reverse decisions
└── docs/agents/            ← skill configuration (this folder)
```

## Use the glossary's vocabulary

When naming domain concepts (issues, tests, modules), use terms from `CONTEXT.md`. Do not drift to synonyms listed under `_Avoid_`.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly:

> _Contradicts ADR-0001 (product surface boundaries) — worth reopening because…_

## StockPick-specific guardrails

Skills working on quant, scan, or portfolio code must respect:

- **Scan** is production screening; **Quant Lab** is validation only.
- **Portfolio** is decision-support, not trade execution.
- Preserve PIT discipline and scan-eval controls documented in [SCAN_EVALUATION.md](../SCAN_EVALUATION.md).
- Completed work reports validation commands, tests run, remaining risks, and doc updates per [AGENTS.md](../../AGENTS.md).
