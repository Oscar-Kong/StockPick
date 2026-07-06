# Issue tracker: GitHub

Issues and PRDs for StockPick live as **GitHub Issues** on `Oscar-Kong/StockPick`. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments`
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

`gh` infers the repo from `git remote -v` when run inside the clone.

## Pull requests as a triage surface

**PRs as a request surface: no.**

External PRs are not pulled into the triage queue. Use normal PR review workflow instead.

## When a skill says "publish to the issue tracker"

Create a GitHub issue with acceptance criteria and links to relevant docs (`CONTEXT.md` terms, ADRs, spec paths).

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
