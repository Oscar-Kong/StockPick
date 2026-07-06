#!/usr/bin/env python3
"""One-time Robinhood MCP OAuth login for StockPick live portfolio sync."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from data.cache import init_db  # noqa: E402


def main() -> int:
    init_db()
    from integrations.robinhood.mcp_client import run_oauth_login

    print("Opening Robinhood login in your browser…")
    print("Complete sign-in on desktop. Tokens save to storage/robinhood_mcp/oauth.json")
    try:
        asyncio.run(run_oauth_login())
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 1
    except Exception as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1
    print("\nNext: python scripts/sync_robinhood_mcp.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
