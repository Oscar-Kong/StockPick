# Robinhood MCP — live portfolio sync

Pull **live** Robinhood positions and buying power into StockPick via Robinhood's official Trading MCP — no CSV exports.

**Endpoint:** `https://agent.robinhood.com/mcp/trading`

Robinhood docs: [Agentic Trading overview](https://robinhood.com/us/en/support/articles/agentic-trading-overview/)

---

## What this does

| Tool (read-only) | Data |
|------------------|------|
| `get_equity_positions` | Current holdings → StockPick Home / Today |
| `get_equity_orders` | Filled order history → Activity transaction ledger (auto-import) |
| `get_pnl_trade_history` | Per-trade **realized P/L (YTD)** — equities, partial sells, **prediction/event contracts** (World Cup, etc.) → Today performance KPI |
| `get_portfolio` | Buying power, portfolio value |
| `get_accounts` | Pick account (optional `ROBINHOOD_MCP_ACCOUNT_ID` = Robinhood `account_number`) |

StockPick **does not** call trade tools (`place_equity_order`, etc.) — portfolio read sync only.

After sync, StockPick **re-prices holdings** (Finnhub/AkShare live quotes in session) and — from the in-app **Sync Robinhood** button — **re-runs the daily decision** so Today marks, shares, and portfolio value stay aligned with Robinhood. The CLI script does the same by default (`./scripts/sync-robinhood-mcp.sh`); pass `--no-decision` to skip the decision step. The raw API defaults to `run_decision=false` but still refreshes prices.

**In the app:** Portfolio → **Today** — **Sync Robinhood** in the header. **Activity** is a single trading-history list (year/month filters) that replaces CSV import and the editable ledger; it refreshes on each Robinhood sync. **Refresh data** also syncs Robinhood in the background when MCP is authenticated, then refreshes prices and the daily decision.

---

## Why Cursor MCP showed "errored"

Cursor's cached status (`mcps/.../STATUS.md`) means the server failed before OAuth completed. Common causes:

1. **Not authenticated** — `.cursor/mcp.json` alone is not enough; you must connect in **Cursor Settings → Tools & MCP → Connect** and finish Robinhood login in the browser (desktop).
2. **Rollout** — Agentic Trading may not be enabled on your account yet (Robinhood emails when eligible).
3. **Two auth paths** — Cursor IDE OAuth and StockPick backend OAuth use **separate token stores**. For **in-app automation**, use the StockPick login script below (not only Cursor Connect).

---

## Setup (StockPick backend — recommended for daily trading)

### 1. Install deps

```bash
cd backend && source .venv/bin/activate && pip install -r requirements.txt
```

### 2. One-time OAuth login

```bash
./scripts/robinhood-mcp-login.sh
```

Opens Robinhood in your browser. Tokens save to `storage/robinhood_mcp/oauth.json` (gitignored).

### 3. Sync portfolio

```bash
./scripts/sync-robinhood-mcp.sh
# or
curl -X POST http://127.0.0.1:18731/api/brokerage/sync/robinhood-mcp
```

Check status:

```bash
./scripts/sync-robinhood-mcp.sh --status
./scripts/sync-robinhood-mcp.sh --status --probe   # live connectivity test
curl http://127.0.0.1:18731/brokerage/robinhood-mcp/status
curl -X POST http://127.0.0.1:18731/brokerage/robinhood-mcp/test
```

In the app: Portfolio → Today shows the usual cockpit for cash-only MCP accounts (buying power + empty holdings). MCP status / Test connection is under **Troubleshoot connection** — only surface it when auth fails or you suspect a problem.

### 4. Automate (daily trader)

Add to cron or run after market close:

```bash
0 17 * * 1-5 cd /path/to/stockpick && ./scripts/sync-robinhood-mcp.sh
```

Or trigger from StockPick refresh jobs (`sync_brokerage_if_configured` prefers MCP when authenticated).

---

## Setup (Cursor chat — optional)

For asking the agent in chat ("what are my Robinhood positions?"):

1. `.cursor/mcp.json` includes `robinhood-trading`.
2. **Cursor Settings → Tools & MCP → Connect** → complete Robinhood OAuth.
3. Confirm tools list shows `get_portfolio`, `get_equity_positions`, etc.

This path does **not** automatically update StockPick Home — run `./scripts/sync-robinhood-mcp.sh` or `POST /api/brokerage/sync/robinhood-mcp` to persist into the app.

---

## Environment flags

```bash
ROBINHOOD_MCP_ENABLED=true
ROBINHOOD_MCP_URL=https://agent.robinhood.com/mcp/trading
ROBINHOOD_MCP_REDIRECT_URI=http://127.0.0.1:8765/callback
# Optional: specific account if you have several
# ROBINHOOD_MCP_ACCOUNT_ID=
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Cursor MCP "errored" | Settings → Tools & MCP → disconnect/reconnect; complete OAuth on desktop |
| `401 authentication required` | Run `./scripts/robinhood-mcp-login.sh` |
| `Robinhood MCP session expired` / opaque `TaskGroup` sync error | Access token expired and refresh failed — run `./scripts/robinhood-mcp-login.sh` again. StockPick blanks stale access tokens so refresh is attempted; if refresh returns 404, a full browser login is required. |
| Sync says authenticated but fails immediately | Same as above — `oauth.json` can still exist while tokens are dead. Re-login refreshes `storage/robinhood_mcp/oauth.json` (and writes absolute `expires_at`). |
| `502 MCP sync failed` | Check rollout eligibility; reconnect OAuth |
| Positions empty after sync | Often real: Robinhood reports `equity_value=0` (cash-only). Confirm with `./scripts/sync-robinhood-mcp.sh --status --probe` or Portfolio → **Troubleshoot connection**. If you expect shares, set `ROBINHOOD_MCP_ACCOUNT_ID` to the account that holds them (default uses `is_default`). |
| UI shows red “sync failed / taking longer” but status is Connected | Soft client timeout while the job was still running (or cash-only sync finished with 0 positions). Re-sync or refresh Today — empty equity is success, not failure. MCP diagnostics stay collapsed unless auth is broken. |
| Phantom symbol (e.g. `ZZZZ`) on Today with 0 holdings | Leftover from a journal/API healthcheck trade that wrote a decision snapshot. Cash-only MCP sync now clears that snapshot; dashboard also drops decision rows not in open holdings. |
| UI says "Import needed" but sync succeeded | Fixed for cash-only MCP: synced $0 equity is not treated as missing import. Re-sync or refresh Today. |
| Activity / ledger after sync | MCP sync replaces trade history from filled orders each run; holdings always come from live positions |

---

## Related

- [USER_GUIDE.md](USER_GUIDE.md)
- [API_REFERENCE.md](API_REFERENCE.md) — `/api/brokerage/sync/robinhood-mcp`
- [RUNBOOK.md](RUNBOOK.md)
