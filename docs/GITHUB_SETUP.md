# Publishing to GitHub (secrets-safe)

How to put this repo on GitHub **without leaking API keys, LLM tokens, or local trading data**.

---

## What must never be committed

| Item | Why | Status |
|------|-----|--------|
| `.env` | All API keys and LLM proxy credentials | Listed in `.gitignore` |
| `backend/data_store/` | SQLite DB, runtime toggles, LEAN exports, cached fundamentals | Listed in `.gitignore` |
| `storage/dev/*.log` | Error URLs can include `apikey=` query params | Listed in `.gitignore` |
| `backend/.venv/`, `quant/.venv/` | Local Python envs | Listed in `.gitignore` |
| `frontend/node_modules/`, `.next/` | Build artifacts | Listed in `.gitignore` |

**Safe to commit:** `.env.example`, `frontend/.env.local.example` (placeholders only).

---

## First-time setup (local)

```bash
cd "/path/to/Stock picker 美股"

# 1. Secrets stay local
cp .env.example .env
# Edit .env with YOUR keys — never add .env to git

cp frontend/.env.local.example frontend/.env.local   # optional; default API URL is fine

# 2. Initialize git (if not already)
git init

# 3. Run secret scan before every push
chmod +x scripts/check-secrets.sh
./scripts/check-secrets.sh
```

---

## Pre-push checklist

Run:

```bash
./scripts/check-secrets.sh
```

Manual checks:

- [ ] `git status` does **not** list `.env`, `backend/data_store/`, or `storage/`
- [ ] `.env.example` contains only placeholders (`your_key_here`, etc.)
- [ ] No API keys pasted in README, docs, or code comments
- [ ] If you ever committed secrets before: **rotate all keys** at each provider (FMP, Finnhub, AV, NewsAPI, LLM proxy)

Optional — install git hook (blocks `git push` if scan fails):

```bash
chmod +x scripts/install-git-hooks.sh
./scripts/install-git-hooks.sh
```

---

## Create the GitHub repo

```bash
# After check-secrets.sh passes:
git add .
git status   # verify .env is NOT listed
git commit -m "Initial commit"

# Create empty repo on GitHub (no README), then:
git remote add origin git@github.com:YOUR_USER/YOUR_REPO.git
git branch -M main
git push -u origin main
```

Use **private** repo if the code is personal research tooling.

---

## If secrets were already exposed

1. **Rotate immediately** at every provider dashboard.
2. Remove from git history (only if already pushed):

   ```bash
   # Example: use git-filter-repo or BFG — destructive; coordinate with any collaborators
   ```

3. Enable [GitHub secret scanning](https://docs.github.com/en/code-security/secret-scanning) on the repo.

---

## What collaborators need

They clone the repo and run:

```bash
cp .env.example .env
# fill keys
./scripts/dev-up.sh
```

No secrets are stored in the repository.

---

## Related

- [RUNBOOK.md](RUNBOOK.md) — local dev
- [README.md](../README.md) — configuration variables (names only)
