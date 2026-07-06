# GitHub setup (no secrets)

Checklist before pushing StockPick to a public or shared remote.

## Never commit

- `.env` (real API keys)
- `backend/data_store/` (SQLite, watchlists, trades)
- `storage/` (Robinhood MCP tokens)
- Generated artifacts under `backend/data/scan_eval/` and `backend/data/factor_discovery/{snapshots,acceptance,extended_staging,staging_input/batches}/`

`.gitignore` already excludes these. Copy `.env.example` → `.env` locally only.

## Pre-push scan

```bash
./scripts/check-secrets.sh
```

Fails if tracked files contain likely API keys or `.env` content.

## Safe templates

- `.env.example` — committed; placeholder values only
- `frontend/.env.local.example` — if present

## Remote setup

1. Create repo (private recommended until keys are rotated).
2. `git remote add origin <url>`
3. Verify `git status` shows no `.env` or `*.db` staged.
4. Push only after `check-secrets.sh` passes.

See [RUNBOOK.md](RUNBOOK.md) for local start and [DEPLOYMENT.md](DEPLOYMENT.md) for demo deploy env vars.
