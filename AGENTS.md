# StockPick — Agent Guide

StockPick (PickerQuant) is a local-first US equities **research and decision-support** platform. FastAPI backend, Next.js frontend, SQLite/Postgres storage.

**Start here for humans:** [docs/USER_GUIDE.md](docs/USER_GUIDE.md) · [README.md](README.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

**Domain language:** [CONTEXT.md](CONTEXT.md) — use these terms in issues, tests, and PR descriptions.

---

## Agent skills

Matt Pocock engineering skills (`~/.agents/skills/`) read this repo's configuration from the files below. Run `/setup-matt-pocock-skills` only if you need to re-scaffold after switching issue trackers.

### Issue tracker

GitHub Issues on `Oscar-Kong/StockPick` (`gh` CLI). External PRs are **not** a triage surface. See [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md).

### Triage labels

Five canonical roles mapped to GitHub label strings. See [docs/agents/triage-labels.md](docs/agents/triage-labels.md).

### Domain docs

Single-context layout: root `CONTEXT.md` + `docs/adr/`. Consumer rules and canonical doc pointers: [docs/agents/domain.md](docs/agents/domain.md).

### Domain wiki (Obsidian)

Synthesized product/architecture context lives in a separate Obsidian vault: `~/Documents/stockpick-brain` (start at `wiki/index.md`). Query it with the `second-brain-query` skill before surface-boundary or architecture decisions. Repo docs remain source of truth. Cursor rule: `.cursor/rules/stockpick-brain.mdc`.

### Skill routing

| Intent | Skill |
|--------|-------|
| Unsure which skill fits | `ask-matt` |
| Sharpen a feature before coding | `grill-with-docs` or `domain-modeling` |
| Product / architecture context from wiki | `second-brain-query` (vault: `~/Documents/stockpick-brain`) |
| Build or fix with tests | `tdd` |
| Hard bug or regression | `diagnosing-bugs` |
| Structural cleanup | `improve-codebase-architecture` + `codebase-design` |
| Break a plan into issues | `to-issues` |
| Review a branch | `review` |
| Full lifecycle workflows in-repo | `.cursor/skills/skills/using-agent-skills/SKILL.md` |

---

## Product surfaces (do not conflate)

| Surface | Route | Role | Affects live scan rankings? |
|---------|-------|------|----------------------------|
| **Scan** | `/scan` | Production stock-screening workflow (Stage A → Stage B → ranked list) | **Yes** — on new scan |
| **Workspace** | `/workspace` | Single-symbol analysis and watchlist | No |
| **Portfolio** / **Home** | `/` | Decision-support: Today decisions, Research tools, Activity ledger | **No** — not trade execution |
| **Quant Lab** | `/quant-lab` | Research, validation, experiments, evaluation | **No** — evidence only |

**Portfolio and Home provide decision-support information. They do not place trades or act as automated execution.**

**Robinhood MCP (live portfolio):** `./scripts/robinhood-mcp-login.sh` then `./scripts/sync-robinhood-mcp.sh` — read-only sync into StockPick. See [docs/ROBINHOOD_MCP.md](docs/ROBINHOOD_MCP.md).

Quant Lab validates factors, weights, and outcomes through ideas, experiments, and reviewable change proposals — it does not re-rank today's scan. See [docs/QUANT_LAB.md](docs/QUANT_LAB.md) and [docs/adr/0001-product-surface-boundaries.md](docs/adr/0001-product-surface-boundaries.md).

Active sleeves: **penny** (primary), **compounder**. Legacy `medium` maps to `penny` at API boundaries via `core.sleeve.normalize_sleeve()`.

---

## Engineering constraints

### Recommendations and evidence

- Recommendations must stay **explainable**, **reproducible**, and tied to **measurable evidence** (factor attribution, IC, walk-forward, prediction snapshots, scan-eval harness).
- LLM layers extract structured signals only; final scores come from the quant engine.
- Strong recommendations require sufficient `data_confidence` per `.cursor/rules/quant-stock-picker.mdc`.

### Financial integrity (quant / scan / backtest)

Avoid **look-ahead bias**, **survivorship bias**, **alphabetical universe-selection bias**, and accidental **data leakage**.

Controls already in the codebase — preserve and extend them:

- Point-in-time data: `universe_pit`, `feature_provenance`, dated snapshots, `truncate_history(..., as_of)` in scan evaluation.
- Scan evaluation negative control: `alphabetical_baseline` algorithm version.
- Forward-return labels must never feed back into scoring features.
- Backtests: transaction costs, slippage, benchmark (SPY), drawdown, turnover.

Deep reference: [docs/SCAN_EVALUATION.md](docs/SCAN_EVALUATION.md), [docs/INSTITUTIONAL_QUANT_ARCHITECTURE.md](docs/INSTITUTIONAL_QUANT_ARCHITECTURE.md), `.cursor/rules/quant-stock-picker.mdc`.

### Preserve working behavior

- Do not remove functionality to simplify UI or refactors.
- Include **regression tests** for behavior changes (backend: `backend/tests/`; frontend: `frontend` test suite).
- Bump `FACTOR_MODEL_VERSION` or `STRATEGY_VERSION` when scoring behavior changes.

### Frontend

Robinhood-inspired **compact, readable** analytics UI. Before UI changes:

1. [design-system/MASTER.md](design-system/MASTER.md)
2. `design-system/pages/[page].md` when it exists
3. `.cursor/rules/pickerquant-ui.mdc`

Preserve Buy / Hold / Sell percentages and semantic colors. Support desktop, laptop, and mobile.

### Architecture

- Prefer **fewer files and less duplication** without creating oversized modules.
- Deep modules: small interface, substantial implementation behind a clean seam (`codebase-design` vocabulary).
- Shared infra: `backend/core/`; feature logic: `backend/services/` (migrating toward `backend/domains/`).

---

## Commands

```bash
# Backend (from backend/, venv active)
python -m pytest tests/ -q                    # full suite
python -m pytest tests/test_<area>.py -q      # targeted
python -m py_compile main.py                  # quick syntax check

# Frontend (from frontend/)
npm run lint
npm run typecheck
npm test
npm run build                                 # production build after UI changes

# Secrets check before push
./scripts/check-secrets.sh
```

---

## Completion checklist (every implementation)

Before marking work done, report all four:

1. **Validation commands** — exact commands run and pass/fail.
2. **Tests run** — which tests were added or executed; note gaps if any.
3. **Remaining risks** — bias caveats, untested paths, feature-flag dependencies, follow-ups.
4. **Documentation updates** — per [.cursor/rules/update-documentation.mdc](.cursor/rules/update-documentation.mdc); list files touched or state why none were needed.

Do not commit unless the user asks.
