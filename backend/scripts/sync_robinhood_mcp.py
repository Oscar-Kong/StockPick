#!/usr/bin/env python3
"""Sync live Robinhood portfolio into StockPick via official Trading MCP."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from data.cache import init_db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Robinhood portfolio via MCP")
    parser.add_argument("--status", action="store_true", help="Show MCP auth status only")
    parser.add_argument("--no-decision", action="store_true", help="Skip daily decision refresh")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    init_db()
    from services.portfolio_snapshot_service import (
        get_current_portfolio,
        import_robinhood_mcp_and_decide,
        robinhood_mcp_status,
    )

    if args.status:
        status = robinhood_mcp_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print(f"Enabled: {status['enabled']}")
            print(f"Authenticated: {status['authenticated']}")
            print(f"Endpoint: {status['endpoint']}")
        return 0 if status.get("authenticated") else 1

    try:
        result = import_robinhood_mcp_and_decide(run_decision=not args.no_decision)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        print("Run: python scripts/robinhood_mcp_login.py", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Sync failed: {exc}", file=sys.stderr)
        return 1

    portfolio = get_current_portfolio()
    if args.json:
        print(json.dumps({"sync": result, "portfolio": portfolio}, indent=2, default=str))
    else:
        print(f"Synced {result.get('holdings_count', 0)} positions from Robinhood MCP")
        print(f"Buying power: ${float(result.get('cash') or 0):,.2f}")
        for h in portfolio.get("holdings") or []:
            print(
                f"  {h['symbol']:8} {float(h['shares']):>12.4f} @ ${float(h['avg_cost']):>8.4f}  [{h.get('bucket')}]"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
