# Deployment Guide (Free Public Demo)

StockPick can run as a **safe shared demo** at **$0/month** using:

| Layer | Platform | Root directory |
|-------|----------|----------------|
| Frontend | [Vercel Hobby](https://vercel.com) | `frontend` |
| Backend | [Render Free Web Service](https://render.com) | `backend` |
| Database | SQLite (ephemeral on Render Free) | `DATABASE_URL` |

This is a **single shared demo**, not multi-user production. Visitors explore sample data; writes are restricted server-side when `DEMO_MODE=true`.

---

## A. Render backend

1. Push this repository to GitHub.
2. In Render: **New → Blueprint** (optional) and point at `render.yaml`, **or** **New → Web Service**.
3. Connect the GitHub repo and select your branch.
4. Set **Root Directory** to `backend`.
5. **Build command:** `pip install -r requirements.txt`
6. **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. **Health check path:** `/health`
8. Set environment variables (minimum):

| Variable | Value |
|----------|--------|
| `APP_ENV` | `production` |
| `DEMO_MODE` | `true` |
| `DEMO_SEED_DATA` | `true` |
| `DATABASE_URL` | `sqlite:///./data/stockpick_demo.db` |
| `SCHEDULER_ENABLED` | `false` |
| `QUANT_JOBS_ENABLED` | `false` |
| `LISTING_MASTER_ENABLED` | `false` |

9. Add **secret** keys in the Render dashboard (never commit): `FINNHUB_API_KEY`, `FMP_API_KEY`, optional `GPT_PROXY_*`, etc. See [Environment variables](#environment-variables).
10. Deploy and copy the service URL (e.g. `https://stockpick-api.onrender.com`).
11. Verify: `curl https://YOUR-RENDER-URL/health` → `{"status":"ok","demo_mode":true,...}`

---

## B. Vercel frontend

1. Import the GitHub repo in Vercel.
2. **Root Directory:** `frontend`
3. **Framework:** Next.js (auto-detected)
4. **Environment variable:**

| Variable | Value |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | Your Render backend URL (no trailing slash) |

5. Deploy and copy the production URL (e.g. `https://stockpick.vercel.app`).

---

## C. Final CORS step

1. Return to Render → your web service → **Environment**.
2. Set:

```
ALLOWED_ORIGINS=https://YOUR-VERCEL-URL.vercel.app
```

Use the **exact** production origin (comma-separated for multiple).

3. Redeploy the backend.
4. Open the Vercel site and confirm the footer shows **API online**.

---

## D. Free-tier limitations

- **Render sleeps** after ~15 minutes of inactivity; first request may take 30–90s.
- **Morning scan email** at 9:20 AM ET requires an always-on backend **or** an external cron hitting `POST /ops/notifications/morning-scan/send` (see [RUNBOOK](RUNBOOK.md#morning-scan-email)).
- **SQLite on Render Free** is **ephemeral** — redeploys/restarts can reset saved watchlist/scans.
- **Shared demo** — no private accounts; all visitors see the same sample portfolio.
- **Heavy jobs** (scheduler, IC panel, LEAN, unrestricted scans) are disabled or rate-limited.
- **Optional integrations** (OpenBB, Qlib, FinRL, VectorBT) should stay off unless you accept cold-start cost.
- **Educational use only** — not financial advice.

---

## E. Environment variables

| Variable | Where | Required | Secret | Purpose | Demo default |
|----------|-------|----------|--------|---------|--------------|
| `NEXT_PUBLIC_API_URL` | Vercel | Yes | Public | Backend base URL | — |
| `ALLOWED_ORIGINS` | Render | Yes (prod) | Public | CORS allowlist | — |
| `APP_ENV` | Render | Yes | No | `production` / `development` | `production` |
| `DEMO_MODE` | Render | Yes | No | Enable public demo guards | `true` |
| `DEMO_SEED_DATA` | Render | Yes | No | Auto-seed sample portfolio | `true` |
| `DATABASE_URL` | Render | Yes | No | SQLite or Postgres URL | `sqlite:///./data/stockpick_demo.db` |
| `FINNHUB_API_KEY` | Render | Optional* | Secret | Quotes / news | dashboard |
| `FMP_API_KEY` | Render | Optional* | Secret | Fundamentals | dashboard |
| `ALPHA_VANTAGE_API_KEY` | Render | Optional | Secret | Fallback data | — |
| `FRED_API_KEY` | Render | Optional | Secret | Macro | — |
| `GPT_PROXY_API_KEY` | Render | Optional | Secret | LLM reports | — |
| `GPT_PROXY_BASE_URL` | Render | Optional | Secret | LLM endpoint | — |
| `GPT_PROXY_MODEL` | Render | Optional | Secret | LLM model id | — |
| `DEMO_MAX_SCAN_SYMBOLS` | Render | No | No | Scan cap | `75` |
| `DEMO_MAX_REQUESTS_PER_MINUTE` | Render | No | No | Rate limit | `30` |
| `OPENBB_ENABLED` | Render | No | No | OpenBB integration | `false` |
| `QLIB_ENABLED` | Render | No | No | Qlib workflows | `false` |
| `VBT_ENABLED` | Render | No | No | VectorBT | `false` |
| `PYPFOPT_ENABLED` | Render | No | No | PyPortfolioOpt | `false` |
| `FINRL_ENABLED` | Render | No | No | FinRL | `false` |
| `LEAN_EXPORT_ENABLED` | Render | No | No | LEAN export | `false` |
| `SCHEDULER_ENABLED` | Render | No | No | Background scheduler | `false` |
| `SCAN_EMAIL_ENABLED` | Render | No | No | Morning scan email job | `false` |
| `SCAN_EMAIL_TO` | Render | When email on | No | Recipient(s) | — |
| `SMTP_USER` | Render | When email on | No | Gmail address | — |
| `SMTP_PASSWORD` | Render | When email on | **Secret** | Gmail App Password | dashboard |
| `APP_PUBLIC_URL` | Vercel/Render | When email on | No | Public app URL for email links | your Vercel URL |

\*At least one market-data key is recommended for live quotes; AkShare may work without keys for limited US data.

---

## F. Local production-like verification

```bash
# Backend
cd backend
export APP_ENV=production DEMO_MODE=true DEMO_SEED_DATA=true
export DATABASE_URL=sqlite:///./data/local_demo.db
export ALLOWED_ORIGINS=http://localhost:18730
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 18731

# Frontend (another terminal)
cd frontend
export NEXT_PUBLIC_API_URL=http://127.0.0.1:18731
npm ci && npm run dev
```

---

## G. Future Postgres upgrade

See [POSTGRES_MIGRATION.md](POSTGRES_MIGRATION.md) for Neon PostgreSQL, auth, and per-user data.

---

## H. Launch checklist

### Before first deployment

- [ ] Full core test suite passes (`cd backend && pytest -q tests`, `cd frontend && npm run lint && npm test && npm run typecheck && npm run build`)
- [ ] No active secrets in the repository (`.env` gitignored; keys only in Render/Vercel dashboards)
- [ ] `DEMO_MODE=true` and `DEMO_SEED_DATA=true` on Render
- [ ] Demo route guards verified (see `backend/tests/test_demo_routes.py`)
- [ ] Render environment variables prepared (see table above)
- [ ] Vercel `NEXT_PUBLIC_API_URL` prepared (Render URL, no trailing slash)

### Render deployment

1. Deploy backend from `backend/` root.
2. Verify `GET /health` → `200`, lightweight JSON, no secrets.
3. Verify `GET /health/ready` → `200`, database available.
4. Copy the Render service URL.

### Vercel deployment

1. Set `NEXT_PUBLIC_API_URL` to the Render URL.
2. Deploy frontend from `frontend/` root.
3. Copy the production Vercel URL.

### CORS finalization

1. Set `ALLOWED_ORIGINS` on Render to the **exact** Vercel production origin (comma-separated if needed).
2. Redeploy the backend.
3. Verify browser preflight from the Vercel site (Network tab → API calls succeed).
4. Confirm footer shows **API online** after cold start.

### Post-deployment smoke test

- [ ] Home loads sample demo portfolio
- [ ] Scan works within demo limits
- [ ] Analyze works for a major symbol
- [ ] Portfolio summary / optimize / rebalance preview respond
- [ ] Disabled actions return `DEMO_ACTION_DISABLED` (not raw 500)
- [ ] No API keys in browser network requests
- [ ] Admin / scheduler / CSV upload / trade write blocked
- [ ] Cold-start state is understandable (banner + retry)
- [ ] Mobile layout acceptable
- [ ] No repeated 500s in logs

### Rollback

| Action | Steps |
|--------|--------|
| Roll back Vercel | Vercel → Deployments → promote previous deployment |
| Roll back Render | Render → Events → rollback to prior deploy |
| Disable public access | Pause Render service or set `DEMO_MODE=false` and redeploy |
| Rotate keys | Render/Vercel dashboards → regenerate keys → update env → redeploy |
| Reset demo SQLite | Redeploy Render (ephemeral disk) or delete `data/stockpick_demo.db` on persistent tier |

### CI quality gate

GitHub Actions runs a **single unified gate**: frontend lint/test/typecheck/build plus backend `pytest -q tests`. Optional integrations (statsmodels pairs tests) skip cleanly when the package is unavailable; CI installs `statsmodels` via `requirements.txt`.

### Test groups

| Command | Purpose |
|---------|---------|
| `pytest -q tests` | Default core suite (required in CI) |
| `pytest -q tests -m optional` | Optional dependency tests only |
| `pytest -q tests/test_demo_deployment.py tests/test_demo_routes.py` | Demo guard smoke |

---

## Related docs

- [RUNBOOK.md](RUNBOOK.md) — local dev and flags
- [API_REFERENCE.md](API_REFERENCE.md) — `/health` response shape
- [PROJECT_INVENTORY.md](PROJECT_INVENTORY.md) — feature map
