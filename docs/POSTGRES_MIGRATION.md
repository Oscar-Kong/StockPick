# PostgreSQL Migration Path (Post-Demo)

The free public demo uses **SQLite on Render’s ephemeral disk**. For a real multi-user deployment, migrate to **Neon PostgreSQL** (or Railway Postgres) with authentication and per-user ownership.

## When to migrate

- Visitors need **private, persistent** portfolios and watchlists
- You need **account sign-up**, deletion, and data retention policies
- SQLite resets on Render redeploys are unacceptable
- You want **concurrent writes** without WAL lock contention

## Target architecture

```
Vercel (frontend)
    ↓ HTTPS
Render / Railway (FastAPI backend)
    ↓ DATABASE_URL
Neon PostgreSQL
```

StockPick already uses SQLAlchemy with `DATABASE_URL` and `data/db_engine.py` dialect detection.

## Steps

### 1. Create Neon database

1. Create a project at [neon.tech](https://neon.tech).
2. Copy the connection string: `postgresql+psycopg://user:pass@host/db?sslmode=require`
3. Set `DATABASE_URL` on Render (replace SQLite).

### 2. Install driver

Add to `backend/requirements.txt` (if not present):

```
psycopg[binary]>=3.1.0
```

### 3. Run migrations / bootstrap

- Use existing `init_db()` / `init_portfolio_db()` on first connect, or
- Run `backend/scripts/migrate_sqlite_to_postgres.py` for one-time data copy from a local SQLite export.

### 4. Add authentication

Not included in the demo. Recommended:

- **Clerk**, **Auth0**, or **Supabase Auth** on the frontend
- Backend middleware validates JWT and sets `user_id` on each request
- Never trust client-supplied `user_id`

### 5. Per-user data model

Add `user_id` (UUID or text) to tables that today assume a single account:

| Table / area | Change |
|--------------|--------|
| `brokerage_accounts` | `user_id` FK, remove hard-coded `DEFAULT_ACCOUNT_ID=1` for production |
| `portfolio_holdings` | Scoped by `account_id` → user’s account |
| `watchlist` | `user_id` column or separate watchlist per user |
| `saved_scans`, `saved_reports` | `user_id` |
| `trade_history` / journal | `user_id` |
| Research runs | `user_id` or org id |

### 6. Authorization

- Every mutating route checks `resource.user_id == current_user.id`
- Demo mode guards remain useful for a **hosted sandbox** tier

### 7. Rate limits & abuse

- Move from in-memory limits to Redis or Postgres-backed counters
- Per-user quotas for scans, LLM calls, backtests

### 8. Backups & deletion

- Enable Neon PITR / scheduled backups
- Implement `DELETE /account` → cascade holdings, watchlist, journal, uploads
- Document retention in privacy policy

### 9. Environment summary

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string |
| `DATABASE_POOL_SIZE` | Connection pool (e.g. `10`) |
| `DEMO_MODE` | `false` for private production |
| `ALLOWED_ORIGINS` | Vercel production URL |

### 10. Disable demo defaults

```
DEMO_MODE=false
DEMO_SEED_DATA=false
SCHEDULER_ENABLED=true  # if desired
```

## SQLite limitations (why migrate)

- Ephemeral filesystem on Render Free
- Single-writer locking under load
- No built-in replication
- Harder compliance story for user data

## References

- `backend/data/db_engine.py` — dialect helpers
- `backend/scripts/migrate_sqlite_to_postgres.py` — optional data migration
- [DEPLOYMENT.md](DEPLOYMENT.md) — current free demo setup
