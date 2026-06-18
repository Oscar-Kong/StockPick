# Cursor Skills — Quick Manual

This repo includes the **[agent-skills](https://github.com/addyosmani/agent-skills)** pack under `.cursor/skills/`. Skills are step-by-step workflows the agent follows (not passive reference docs). Use them when you want consistent quality gates: spec before code, tests before merge, structured reviews, etc.

---

## Copy-paste prompt (use this now)

Paste the block below into a **new Cursor Agent chat** to run the full skills workflow on this repo. Replace the task line with what you want done today.

```markdown
You are working in the Stock Picker 美股 repo (FastAPI backend + Next.js frontend).

## Task
[PASTE YOUR TASK HERE — e.g. "Fix Home portfolio refresh slowness" or "Add manual trade sync indicator on Journal"]

## Mandatory process
1. Read `.cursor/skills/skills/using-agent-skills/SKILL.md` and pick the matching skills for this task.
2. Read `.cursor/rules/update-documentation.mdc` — update affected docs in the same change (README, docs/API_REFERENCE.md, etc.).
3. For non-trivial work: follow `.cursor/skills/skills/spec-driven-development/SKILL.md` (short inline spec in chat is OK if the change is small).
4. Implement with:
   - `.cursor/skills/skills/incremental-implementation/SKILL.md` (small slices, one concern per commit-sized diff)
   - `.cursor/skills/skills/test-driven-development/SKILL.md` (pytest for backend; run relevant tests before finishing)
5. If UI: also follow `.cursor/skills/skills/frontend-ui-engineering/SKILL.md` and `.cursor/skills/vercel-react-best-practices/SKILL.md`.
6. If API/schema: also follow `.cursor/skills/skills/api-and-interface-design/SKILL.md`.
7. If quant/scoring: also follow `.cursor/rules/quant-stock-picker.mdc`.

## Project map (start here)
- Portfolio workspace: `frontend/src/components/portfolio/PortfolioWorkspace.tsx`, `backend/services/home_dashboard_service.py`, `backend/services/refresh_orchestrator.py`
- Portfolio / Robinhood CSV: `backend/services/portfolio_snapshot_service.py`, `backend/integrations/robinhood/`
- Trade journal → portfolio sync: `backend/api/routes_trades.py`, `frontend/src/components/TradeJournal.tsx`
- User-facing guide: `docs/USER_GUIDE.md`

## Constraints
- Do not git commit unless I ask.
- Minimize scope — fix the task, no drive-by refactors.
- Surface assumptions before coding if requirements are ambiguous.
- When done, show the skill verification checklist and list doc files you updated.

Begin by stating which skills you will use and your plan in 5 bullets, then execute.
```

### Shorter variants

**Bug fix**

```markdown
Follow `.cursor/skills/skills/debugging-and-error-recovery/SKILL.md` then TDD for this repo.

Bug: [describe symptom, route, symbol, e.g. "Journal trade doesn't show on Home"]

Reproduce → root cause → minimal fix → pytest → update docs if behavior changed. No commit unless I ask.
```

**Pre-merge review**

```markdown
Review my current git diff using `.cursor/skills/agents/code-reviewer.md` and `.cursor/skills/skills/code-review-and-quality/SKILL.md`.

Report: correctness, tests, docs, scope creep, and blockers. Do not change code unless I say fix.
```

**Home / frontend performance**

```markdown
Audit Home (`/`) using `.cursor/skills/agents/web-performance-auditor.md`, then apply fixes per `.cursor/skills/skills/performance-optimization/SKILL.md`.

Focus: load time, refresh polling, unnecessary re-fetches. TDD where you change behavior. Update docs if UX changes.
```

---

## Where things live

| Path | What it is |
|------|------------|
| `.cursor/skills/skills/*/SKILL.md` | **Core workflows** (TDD, spec, review, debugging, …) |
| `.cursor/skills/agents/*.md` | **Specialist personas** (code reviewer, security auditor, …) |
| `.cursor/skills/commands/*.toml` | **Slash-command recipes** (for Claude Code–compatible tools) |
| `.cursor/skills/references/` | Checklists used alongside skills (security, performance, a11y) |
| `.cursor/skills/docs/` | Upstream setup guides (`cursor-setup.md`, `getting-started.md`, …) |
| `.cursor/skills/hooks/` | Session hooks (Claude Code plugin; optional in Cursor) |

**Ignore for daily use:** `temp-skills/` and `temp-omc/` — vendor copies / experiments. Use the top-level `skills/`, `agents/`, and `commands/` folders.

---

## Three layers (how they fit together)

```
You (or a slash command)
    │
    ├── Skill     → HOW to do the work (steps + exit criteria)
    ├── Persona   → WHO reviews it (perspective + report format)
    └── Command   → WHEN to run a packaged workflow (/spec, /review, …)
```

- **Skills** are mandatory process when the task matches (e.g. bug → debugging skill).
- **Personas** are single-role reviewers; they do **not** call each other.
- **Commands** compose skills/personas into repeatable entry points.

Start with the meta-skill if you are unsure which one applies:  
`.cursor/skills/skills/using-agent-skills/SKILL.md`

---

## Using skills in Cursor

Cursor does not auto-load every skill file (context limits). Pick one of these patterns:

### 1. Ask explicitly (simplest)

In chat, name the skill and path:

> Follow `.cursor/skills/skills/test-driven-development/SKILL.md` for this change.

> Use the `code-reviewer` persona from `.cursor/skills/agents/code-reviewer.md` on this diff.

The agent should read the file and follow its steps and verification checklist.

### 2. Pin as project rules (always-on)

Copy 2–3 essential skills into `.cursor/rules/` so Cursor loads them automatically:

```bash
mkdir -p .cursor/rules
cp .cursor/skills/skills/test-driven-development/SKILL.md .cursor/rules/tdd.md
cp .cursor/skills/skills/code-review-and-quality/SKILL.md .cursor/rules/review.md
cp .cursor/skills/skills/incremental-implementation/SKILL.md .cursor/rules/incremental.md
```

Add phase-specific rules only while you need them (frontend, security, performance), then remove them to save context.

See also: `.cursor/skills/docs/cursor-setup.md`

### 3. Launch a specialist subagent

For focused review, ask Cursor to run a subagent with a persona, e.g.:

> Review this PR using the security-auditor persona in `.cursor/skills/agents/security-auditor.md`

Parallel reviews (review + security + tests) mirror the `/ship` command pattern described in `.cursor/skills/agents/README.md`.

---

## Core skills (lifecycle map)

| Phase | Skill folder | When to invoke |
|-------|----------------|----------------|
| Discover | `using-agent-skills` | “Which skill applies?” |
| Clarify idea | `interview-me`, `idea-refine` | Vague feature request |
| Define | `spec-driven-development` | Non-trivial feature or behavior change |
| Plan | `planning-and-task-breakdown` | Spec exists, need tasks |
| Build | `incremental-implementation` + `test-driven-development` | Writing code |
| UI | `frontend-ui-engineering` | React/Next/CSS work |
| API | `api-and-interface-design` | New/changed HTTP contracts |
| Debug | `debugging-and-error-recovery` | Failures, regressions |
| Review | `code-review-and-quality` | Before merge |
| Security | `security-and-hardening` | Auth, inputs, secrets |
| Performance | `performance-optimization` | Slow pages/APIs |
| Ship | `shipping-and-launch` | Pre-deploy checklist |

Full discovery flowchart: `.cursor/skills/skills/using-agent-skills/SKILL.md`

---

## Specialist personas

| Persona | File | Use for |
|---------|------|---------|
| Code reviewer | `agents/code-reviewer.md` | Five-axis review before merge |
| Security auditor | `agents/security-auditor.md` | OWASP-style pass on changes |
| Test engineer | `agents/test-engineer.md` | Coverage gaps, Prove-It tests |
| Web performance auditor | `agents/web-performance-auditor.md` | Core Web Vitals, LCP/INP, traces |

Example prompts:

- *“Review this diff with `agents/code-reviewer.md`.”*
- *“Audit Home dashboard load using `agents/web-performance-auditor.md`.”*

---

## Slash commands (Claude Code / compatible CLIs)

The `commands/*.toml` files define prompts for tools that support slash commands. In plain Cursor chat, paste the same intent:

| Command file | What it runs |
|--------------|--------------|
| `commands/spec.toml` | `/spec` → spec-driven-development → `SPEC.md` |
| `commands/planning.toml` | `/plan` → task breakdown → `tasks/plan.md` |
| `commands/build.toml` | `/build` or `/build auto` → incremental + TDD |
| `commands/test.toml` | `/test` → test-driven-development |
| `commands/review.toml` | `/review` → code-review-and-quality |
| `commands/ship.toml` | `/ship` → parallel review + security + tests |
| `commands/webperf.toml` | `/webperf` → web-performance-auditor |
| `commands/code-simplify.toml` | `/code-simplify` → code-simplification |

**Typical sequence for a medium feature:**

1. `/spec` (or ask for spec-driven-development)
2. `/plan`
3. `/build` one task at a time — or `/build auto` after you approve the full plan
4. `/review` before opening a PR
5. `/ship` before merging to main

Artifacts (`SPEC.md`, `tasks/plan.md`) are living docs during development; delete or gitignore before merge if you do not want them permanent.

---

## Recommended setup for this project

**Always useful (copy to `.cursor/rules/` or mention often):**

1. `test-driven-development` — backend pytest + frontend tests
2. `code-review-and-quality` — before PRs
3. `incremental-implementation` — avoid huge diffs

**Use on demand:**

- Home / dashboard UI → `frontend-ui-engineering` + `vercel-react-best-practices/SKILL.md`
- API or schema changes → `api-and-interface-design` + update `docs/API_REFERENCE.md` (see `.cursor/rules/update-documentation.mdc`)
- Quant / scoring work → existing `.cursor/rules/quant-stock-picker.mdc` **plus** `test-driven-development`
- Slow Home refresh → `web-performance-auditor` persona + `performance-optimization` skill

---

## Global Cursor skills (outside this repo)

Cursor also ships user-level skills under `~/.cursor/skills-cursor/` (e.g. **canvas**, **babysit**, **split-to-prs**, **create-skill**). Those apply across all projects; the `.cursor/skills/` pack in this repo is project-specific engineering workflow.

---

## Tips

1. **Do not load all skills at once** — pick 2–3 for the current phase.
2. **Name the skill in your prompt** — “follow the TDD skill” beats “write tests.”
3. **Skills include exit criteria** — ask the agent to show the verification checklist when done.
4. **Personas ≠ orchestrators** — run `/review` or ask for one persona; do not ask a persona to “decide what to run next.”
5. **Upstream docs** — `.cursor/skills/docs/getting-started.md` and `skill-anatomy.md` for authoring new skills.

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [`.cursor/skills/docs/getting-started.md`](../.cursor/skills/docs/getting-started.md) | Upstream quick start |
| [`.cursor/skills/docs/cursor-setup.md`](../.cursor/skills/docs/cursor-setup.md) | Rules directory setup |
| [`.cursor/skills/agents/README.md`](../.cursor/skills/agents/README.md) | Personas vs skills vs commands |
| [`.cursor/rules/update-documentation.mdc`](../.cursor/rules/update-documentation.mdc) | When code changes require doc updates |
