"""Robinhood official Trading MCP — read-only portfolio sync into StockPick."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
import webbrowser
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import OAuthClientProvider
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from integrations.robinhood.base import BrokerageProvider, classify_holding_bucket
from integrations.robinhood.mcp_decode import (
    RobinhoodToolError,
    decode_tool_result,
    looks_like_ticker,
    positions_payload_is_genuinely_empty,
)
from integrations.robinhood.mcp_orders import MCP_MAX_ORDER_PAGES, _order_cursor, parse_mcp_equity_orders
from integrations.robinhood.mcp_pnl import MCP_MAX_PNL_PAGES, RealizedPnlSummary, _pnl_cursor, parse_pnl_trade_history_pages
from integrations.robinhood.mcp_token_store import FileTokenStorage, has_valid_tokens
from integrations.robinhood.models import BrokerageSyncResult, ReconstructedHolding, ParsedCsvRow

logger = logging.getLogger(__name__)

ROBINHOOD_MCP_URL = os.getenv("ROBINHOOD_MCP_URL", "https://agent.robinhood.com/mcp/trading").strip()
ROBINHOOD_MCP_REDIRECT_URI = os.getenv(
    "ROBINHOOD_MCP_REDIRECT_URI", "http://127.0.0.1:8765/callback"
).strip()
_LOGIN_SCRIPT = "./scripts/robinhood-mcp-login.sh"
READ_TOOLS = frozenset({
    "get_accounts",
    "get_portfolio",
    "get_equity_positions",
    "get_equity_orders",
    "get_pnl_trade_history",
    "get_realized_pnl",
})

_CONTAINER_KEYS = ("positions", "equity_positions", "holdings", "results", "data", "items")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def tool_timeout_sec() -> float:
    return max(1.0, _env_float("ROBINHOOD_MCP_TOOL_TIMEOUT_SEC", 15.0))


def sync_timeout_sec() -> float:
    return max(15.0, _env_float("ROBINHOOD_MCP_SYNC_TIMEOUT_SEC", 90.0))


def probe_timeout_sec() -> float:
    return max(10.0, _env_float("ROBINHOOD_MCP_PROBE_TIMEOUT_SEC", 45.0))


def init_timeout_sec() -> float:
    return max(1.0, _env_float("ROBINHOOD_MCP_INIT_TIMEOUT_SEC", 10.0))


@dataclass
class SnapshotCompleteness:
    positions_ok: bool = False
    portfolio_ok: bool = False
    orders_ok: bool = False
    orders_truncated: bool = False
    history_complete: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def publication_allowed(self) -> bool:
        return self.positions_ok and self.portfolio_ok


@dataclass
class LivePortfolioSnapshot:
    holdings: list[ReconstructedHolding]
    buying_power: float
    portfolio_value: float | None
    account_id: str | None
    raw_positions: Any
    raw_portfolio: Any
    order_rows: list[ParsedCsvRow] = field(default_factory=list)
    orders_imported: int = 0
    orders_skipped: int = 0
    completeness: SnapshotCompleteness = field(default_factory=SnapshotCompleteness)


@dataclass
class _OrderFetchResult:
    rows: list[ParsedCsvRow]
    truncated: bool
    pages_fetched: int
    ok: bool
    error: str | None = None


def _enabled() -> bool:
    flag = os.getenv("ROBINHOOD_MCP_ENABLED", "true").strip().lower()
    return flag not in ("0", "false", "no", "off")


def _tool_json(result: Any) -> Any:
    """Deprecated wrapper — prefer decode_tool_result (checks isError, structuredContent)."""
    return decode_tool_result(result, tool="unknown")


def _walk_numbers(node: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(node, dict):
        for key in keys:
            if key in node and node[key] is not None:
                try:
                    return float(node[key])
                except (TypeError, ValueError):
                    continue
        for value in node.values():
            found = _walk_numbers(value, keys)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _walk_numbers(item, keys)
            if found is not None:
                return found
    return None


def _normalize_symbol_keyed(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Promote ticker-keyed maps into list-of-dicts with injected symbol."""
    out: list[dict[str, Any]] = []
    for key, value in node.items():
        if not isinstance(value, dict):
            continue
        if not looks_like_ticker(str(key)):
            continue
        if _position_symbol(value) and _position_quantity(value) is not None:
            out.append(value)
            continue
        injected = {"symbol": str(key).upper().strip(), **value}
        if _position_quantity(injected) is not None:
            out.append(injected)
    return out


def _iter_position_dicts(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, list):
        out: list[dict[str, Any]] = []
        for item in node:
            out.extend(_iter_position_dicts(item))
        return out
    if not isinstance(node, dict):
        return []
    symbol = _position_symbol(node)
    qty = _position_quantity(node)
    if symbol and qty is not None and qty > 0:
        return [node]

    out: list[dict[str, Any]] = []
    for key in _CONTAINER_KEYS:
        if key not in node:
            continue
        child = node[key]
        if isinstance(child, dict):
            keyed = _normalize_symbol_keyed(child)
            if keyed:
                out.extend(keyed)
                continue
        out.extend(_iter_position_dicts(child))

    if not out:
        keyed = _normalize_symbol_keyed(node)
        if keyed:
            return keyed
        for value in node.values():
            if isinstance(value, (dict, list)):
                out.extend(_iter_position_dicts(value))
    return out


def _position_symbol(row: dict[str, Any]) -> str | None:
    symbol = row.get("symbol")
    if isinstance(symbol, dict):
        symbol = symbol.get("symbol") or symbol.get("ticker")
    if not symbol:
        inst = row.get("instrument")
        if isinstance(inst, dict):
            symbol = inst.get("symbol") or inst.get("ticker")
        elif isinstance(inst, str):
            symbol = inst
    if not symbol:
        return None
    return str(symbol).upper().strip()


def _position_quantity(row: dict[str, Any]) -> float | None:
    for key in ("quantity", "shares", "qty", "total_quantity"):
        if row.get(key) is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    return None


def _position_avg_cost(row: dict[str, Any]) -> float:
    for key in (
        "average_buy_price",
        "average_price",
        "avg_cost",
        "cost_basis_per_share",
        "price",
    ):
        if row.get(key) is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                continue
    qty = _position_quantity(row) or 0
    for key in ("cost_basis", "total_cost", "equity"):
        if row.get(key) is not None and qty:
            try:
                return float(row[key]) / qty
            except (TypeError, ValueError, ZeroDivisionError):
                continue
    return 0.0


def parse_equity_positions(payload: Any) -> list[ReconstructedHolding]:
    rows = _iter_position_dicts(payload)
    by_symbol: dict[str, ReconstructedHolding] = {}
    for row in rows:
        symbol = _position_symbol(row)
        qty = _position_quantity(row)
        if not symbol or qty is None or qty <= 0:
            continue
        avg = _position_avg_cost(row)
        by_symbol[symbol] = ReconstructedHolding(
            symbol=symbol,
            shares=qty,
            avg_cost=avg,
            bucket=classify_holding_bucket(symbol, avg),
        )
    return sorted(by_symbol.values(), key=lambda h: h.symbol)


def assess_positions_parse(payload: Any) -> tuple[list[ReconstructedHolding], list[str]]:
    """Parse holdings and emit warnings when a non-empty payload yields zero rows."""
    holdings = parse_equity_positions(payload)
    warnings: list[str] = []
    if holdings:
        return holdings, warnings
    if positions_payload_is_genuinely_empty(payload):
        return holdings, warnings
    warnings.append(
        "Positions payload was non-empty but no equity holdings could be parsed "
        "(possible schema change or symbol-keyed shape missed)"
    )
    return holdings, warnings


def parse_buying_power(portfolio_payload: Any) -> float:
    value = _walk_numbers(
        portfolio_payload,
        (
            "buying_power",
            "cash_available_for_withdrawal",
            "uninvested_cash",
            "cash",
            "available_cash",
        ),
    )
    return max(0.0, float(value or 0))


def parse_portfolio_value(portfolio_payload: Any) -> float | None:
    value = _walk_numbers(
        portfolio_payload,
        ("portfolio_value", "equity", "total_equity", "market_value", "total_value"),
    )
    return float(value) if value is not None else None


def parse_equity_value(portfolio_payload: Any) -> float | None:
    value = _walk_numbers(portfolio_payload, ("equity_value",))
    return float(value) if value is not None else None


def _count_accounts(accounts_payload: Any) -> int:
    if isinstance(accounts_payload, dict):
        nested = accounts_payload.get("data")
        if isinstance(nested, dict) and isinstance(nested.get("accounts"), list):
            return len(nested["accounts"])
        if isinstance(accounts_payload.get("accounts"), list):
            return len(accounts_payload["accounts"])
    if isinstance(accounts_payload, list):
        return len(accounts_payload)
    return 0


def _pick_account_id(accounts_payload: Any, preferred: str | None) -> str | None:
    if preferred:
        return preferred

    accounts_list: list[dict[str, Any]] = []
    if isinstance(accounts_payload, dict):
        nested = accounts_payload.get("data")
        if isinstance(nested, dict) and isinstance(nested.get("accounts"), list):
            accounts_list = [a for a in nested["accounts"] if isinstance(a, dict)]
        elif isinstance(accounts_payload.get("accounts"), list):
            accounts_list = [a for a in accounts_payload["accounts"] if isinstance(a, dict)]
    elif isinstance(accounts_payload, list):
        accounts_list = [a for a in accounts_payload if isinstance(a, dict)]

    if accounts_list:
        default = next((a for a in accounts_list if a.get("is_default")), None)
        picked = default or accounts_list[0]
        acct_id = picked.get("account_number") or picked.get("id") or picked.get("account_id")
        return str(acct_id) if acct_id else None

    if isinstance(accounts_payload, dict):
        acct_id = accounts_payload.get("account_number") or accounts_payload.get("id") or accounts_payload.get("account_id")
        if acct_id:
            return str(acct_id)
    return None


_REAUTH_HINT = (
    f"Robinhood MCP session expired. Re-authenticate with: {_LOGIN_SCRIPT}"
)


def _flatten_exc(exc: BaseException) -> BaseException:
    """Unwrap ExceptionGroup to the first meaningful leaf error."""
    cur: BaseException = exc
    while isinstance(cur, BaseExceptionGroup) and cur.exceptions:
        cur = cur.exceptions[0]
    return cur


def _auth_error(exc: BaseException) -> ValueError:
    leaf = _flatten_exc(exc)
    if isinstance(leaf, RobinhoodToolError):
        return ValueError(f"Robinhood MCP tool error ({leaf.tool}): {leaf.message[:300]}")
    msg = str(leaf)
    lowered = msg.lower()
    if (
        _REAUTH_HINT in msg
        or "session expired" in lowered
        or "redirect handler" in lowered
        or "oauth" in type(leaf).__name__.lower()
        or "token refresh failed" in lowered
    ):
        return ValueError(_REAUTH_HINT)
    return ValueError(f"Robinhood MCP sync failed: {msg[:300]}")


def _is_retryable_exc(exc: BaseException) -> bool:
    leaf = _flatten_exc(exc)
    if isinstance(leaf, RobinhoodToolError):
        return leaf.retryable
    if isinstance(leaf, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    msg = str(leaf).lower()
    markers = (
        "timeout",
        "timed out",
        "connection reset",
        "connection refused",
        "temporarily",
        "429",
        "502",
        "503",
        "504",
        "rate_limit",
        "rate limit",
    )
    return any(m in msg for m in markers)


def _retry_delay_sec(attempt: int) -> float:
    """attempt is 0-based after first failure."""
    base = 0.6 if attempt == 0 else 1.8
    return base + random.uniform(0.0, 0.9)


class RobinhoodMcpClient(BrokerageProvider):
    source = "robinhood_mcp"

    def __init__(self, *, token_storage: FileTokenStorage | None = None) -> None:
        self.storage = token_storage or FileTokenStorage()

    def is_configured(self) -> bool:
        return _enabled() and has_valid_tokens(self.storage.base_dir)

    def _build_oauth(self) -> OAuthClientProvider:
        async def _redirect_handler(url: str) -> None:
            raise ValueError(_REAUTH_HINT)

        async def _callback_handler() -> tuple[str, str | None]:
            raise ValueError(_REAUTH_HINT)

        return OAuthClientProvider(
            server_url=ROBINHOOD_MCP_URL,
            client_metadata=OAuthClientMetadata(
                client_name="StockPick",
                redirect_uris=[AnyUrl(ROBINHOOD_MCP_REDIRECT_URI)],
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                token_endpoint_auth_method="none",
            ),
            storage=self.storage,
            # Sync path must never open a browser; force a clear re-auth error instead.
            redirect_handler=_redirect_handler,
            callback_handler=_callback_handler,
        )

    @asynccontextmanager
    async def _session(self):
        """Open a fresh MCP session for this asyncio.run() boundary.

        Do not cache sessions/locks across event loops — StockPick calls MCP via
        ``asyncio.run()`` from sync HTTP handlers and worker threads.
        One session is still reused for all tools inside a single fetch/probe.
        """
        oauth = self._build_oauth()
        try:
            async with streamablehttp_client(ROBINHOOD_MCP_URL, auth=oauth) as (read, write, _):
                async with ClientSession(read, write) as session:
                    async with asyncio.timeout(init_timeout_sec()):
                        await session.initialize()
                    yield session
        except (asyncio.CancelledError, GeneratorExit):
            raise
        except BaseException as exc:
            raise _auth_error(exc) from exc

    async def _call_read_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if name not in READ_TOOLS:
            raise ValueError(f"Tool {name} is not allowed in read-only mode")
        async with self._session() as session:
            return await self._call_tool(session, name, arguments or {})

    @staticmethod
    async def _call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> Any:
        timeout = tool_timeout_sec()
        last_exc: BaseException | None = None
        for attempt in range(3):
            try:
                result = await session.call_tool(
                    name,
                    arguments,
                    read_timeout_seconds=timedelta(seconds=timeout),
                )
                return decode_tool_result(result, tool=name)
            except BaseException as exc:
                last_exc = exc
                if attempt >= 2 or not _is_retryable_exc(exc):
                    raise
                delay = _retry_delay_sec(attempt)
                logger.warning(
                    "Robinhood MCP tool %s failed (attempt %s/3): %s; retry in %.2fs",
                    name,
                    attempt + 1,
                    _flatten_exc(exc),
                    delay,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    async def _fetch_filled_orders(self, session: ClientSession, account_number: str) -> _OrderFetchResult:
        merged: list[ParsedCsvRow] = []
        cursor: str | None = None
        pages = 0

        try:
            for _ in range(MCP_MAX_ORDER_PAGES):
                args: dict[str, Any] = {"account_number": account_number, "state": "filled"}
                if cursor:
                    args["cursor"] = cursor
                payload = await self._call_tool(session, "get_equity_orders", args)
                pages += 1
                merged.extend(parse_mcp_equity_orders(payload))
                cursor = _order_cursor(payload)
                if not cursor:
                    return _OrderFetchResult(rows=merged, truncated=False, pages_fetched=pages, ok=True)
            return _OrderFetchResult(
                rows=merged,
                truncated=bool(cursor),
                pages_fetched=pages,
                ok=True,
            )
        except Exception as exc:
            logger.exception("Robinhood MCP order history fetch failed")
            return _OrderFetchResult(
                rows=merged,
                truncated=False,
                pages_fetched=pages,
                ok=False,
                error=str(_flatten_exc(exc))[:300],
            )

    async def _fetch_pnl_trade_history(self, session: ClientSession, account_number: str, *, span: str = "ytd") -> list[Any]:
        pages: list[Any] = []
        cursor: str | None = None
        for _ in range(MCP_MAX_PNL_PAGES):
            args: dict[str, Any] = {"account_number": account_number, "span": span}
            if cursor:
                args["cursor"] = cursor
            payload = await self._call_tool(session, "get_pnl_trade_history", args)
            pages.append(payload)
            cursor = _pnl_cursor(payload)
            if not cursor:
                break
        return pages

    async def fetch_ytd_realized_pnl(self) -> RealizedPnlSummary | None:
        """Per-trade realized P/L from Robinhood (equities + prediction markets + …)."""
        if not self.is_configured():
            return None
        preferred = os.getenv("ROBINHOOD_MCP_ACCOUNT_ID", "").strip() or None
        try:
            async with self._session() as session:
                accounts = await self._call_tool(session, "get_accounts", {})
                account_id = _pick_account_id(accounts, preferred)
                if not account_id:
                    return None
                pages = await self._fetch_pnl_trade_history(session, account_id, span="ytd")
        except Exception:
            logger.exception("Robinhood MCP realized P/L fetch failed")
            return None
        if not pages:
            return None
        summary = parse_pnl_trade_history_pages(pages)
        if summary.trade_count == 0 and summary.total == 0:
            return summary
        return summary

    def fetch_ytd_realized_pnl_sync(self) -> RealizedPnlSummary | None:
        if not _enabled() or not self.is_configured():
            return None
        try:
            return asyncio.run(self.fetch_ytd_realized_pnl())
        except Exception:
            logger.exception("Robinhood MCP realized P/L sync fetch failed")
            return None

    async def fetch_live_portfolio(self, *, include_orders: bool = True) -> LivePortfolioSnapshot:
        preferred = os.getenv("ROBINHOOD_MCP_ACCOUNT_ID", "").strip() or None
        completeness = SnapshotCompleteness()

        async def _run() -> LivePortfolioSnapshot:
            async with self._session() as session:
                accounts = await self._call_tool(session, "get_accounts", {})
                account_id = _pick_account_id(accounts, preferred)

                if not account_id:
                    raise ValueError("No Robinhood account_number found — set ROBINHOOD_MCP_ACCOUNT_ID")

                account_args = {"account_number": account_id}
                positions_raw = await self._call_tool(session, "get_equity_positions", account_args)
                completeness.positions_ok = True
                holdings, pos_warnings = assess_positions_parse(positions_raw)
                completeness.warnings.extend(pos_warnings)

                portfolio_raw = await self._call_tool(session, "get_portfolio", account_args)
                completeness.portfolio_ok = True

                order_rows: list[ParsedCsvRow] = []
                if include_orders:
                    order_result = await self._fetch_filled_orders(session, account_id)
                    order_rows = order_result.rows
                    completeness.orders_ok = order_result.ok
                    completeness.orders_truncated = order_result.truncated
                    if order_result.error:
                        completeness.warnings.append(f"Order history incomplete: {order_result.error}")
                    if order_result.truncated:
                        completeness.warnings.append(
                            f"Order history truncated after {order_result.pages_fetched} pages "
                            f"(max {MCP_MAX_ORDER_PAGES}); retaining previous ledger"
                        )
                    completeness.history_complete = (
                        order_result.ok and not order_result.truncated
                    )
                else:
                    completeness.orders_ok = True
                    completeness.history_complete = False
                    completeness.warnings.append("Order history not requested")

                return LivePortfolioSnapshot(
                    holdings=holdings,
                    buying_power=parse_buying_power(portfolio_raw),
                    portfolio_value=parse_portfolio_value(portfolio_raw),
                    account_id=account_id,
                    raw_positions=positions_raw,
                    raw_portfolio=portfolio_raw,
                    order_rows=order_rows,
                    completeness=completeness,
                )

        try:
            async with asyncio.timeout(sync_timeout_sec()):
                return await _run()
        except TimeoutError as exc:
            raise ValueError(
                f"Robinhood MCP sync exceeded {sync_timeout_sec():.0f}s deadline"
            ) from exc

    async def _probe_async(self) -> dict[str, Any]:
        """Lightweight live check: accounts + portfolio + positions (no order history)."""
        t0 = time.monotonic()
        preferred = os.getenv("ROBINHOOD_MCP_ACCOUNT_ID", "").strip() or None

        async def _run() -> dict[str, Any]:
            async with self._session() as session:
                accounts = await self._call_tool(session, "get_accounts", {})
                account_id = _pick_account_id(accounts, preferred)
                if not account_id:
                    raise ValueError("No Robinhood account_number found — set ROBINHOOD_MCP_ACCOUNT_ID")
                account_args = {"account_number": account_id}
                positions_raw = await self._call_tool(session, "get_equity_positions", account_args)
                portfolio_raw = await self._call_tool(session, "get_portfolio", account_args)

            holdings, pos_warnings = assess_positions_parse(positions_raw)
            cash = parse_buying_power(portfolio_raw)
            portfolio_value = parse_portfolio_value(portfolio_raw)
            equity_value = parse_equity_value(portfolio_raw)
            latency_ms = int((time.monotonic() - t0) * 1000)

            if holdings:
                message = f"Connected — {len(holdings)} equity position(s)"
                ok = True
                error = None
            elif positions_payload_is_genuinely_empty(positions_raw) and not pos_warnings:
                message = "Connected — account is cash-only (0 equity positions)"
                ok = True
                error = None
            else:
                message = (
                    "Connected — positions response could not be parsed "
                    "(not treating as cash-only)"
                )
                ok = False
                error = pos_warnings[0] if pos_warnings else "Unparseable positions payload"
            return {
                "ok": ok,
                "latency_ms": latency_ms,
                "account_id": account_id,
                "accounts_count": _count_accounts(accounts),
                "holdings_count": len(holdings),
                "cash": cash,
                "equity_value": equity_value,
                "portfolio_value": portfolio_value,
                "error": error,
                "needs_reauth": False,
                "message": message,
                "warnings": pos_warnings,
            }

        async with asyncio.timeout(probe_timeout_sec()):
            return await _run()

    def probe_connection(self) -> dict[str, Any]:
        """Sync wrapper for UI/CLI connectivity test."""
        if not _enabled():
            return {
                "ok": False,
                "latency_ms": 0,
                "account_id": None,
                "accounts_count": 0,
                "holdings_count": 0,
                "cash": None,
                "equity_value": None,
                "portfolio_value": None,
                "error": "Robinhood MCP disabled",
                "needs_reauth": False,
                "message": "Set ROBINHOOD_MCP_ENABLED=true to enable live sync",
            }
        if not self.is_configured():
            return {
                "ok": False,
                "latency_ms": 0,
                "account_id": None,
                "accounts_count": 0,
                "holdings_count": 0,
                "cash": None,
                "equity_value": None,
                "portfolio_value": None,
                "error": "Not authenticated",
                "needs_reauth": True,
                "message": f"Not authenticated — run {_LOGIN_SCRIPT}",
            }
        t0 = time.monotonic()
        try:
            return asyncio.run(self._probe_async())
        except Exception as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            err = _auth_error(exc)
            needs_reauth = _REAUTH_HINT in str(err) or "session expired" in str(err).lower()
            return {
                "ok": False,
                "latency_ms": latency_ms,
                "account_id": None,
                "accounts_count": 0,
                "holdings_count": 0,
                "cash": None,
                "equity_value": None,
                "portfolio_value": None,
                "error": str(err)[:400],
                "needs_reauth": needs_reauth,
                "message": (
                    f"Session expired — re-run {_LOGIN_SCRIPT}"
                    if needs_reauth
                    else f"MCP probe failed: {str(err)[:200]}"
                ),
            }

    def sync_holdings(self) -> BrokerageSyncResult:
        if not _enabled():
            return BrokerageSyncResult(
                source="robinhood_mcp",
                message="Robinhood MCP disabled — set ROBINHOOD_MCP_ENABLED=true",
            )
        if not self.is_configured():
            return BrokerageSyncResult(
                source="robinhood_mcp",
                message="Robinhood MCP not authenticated — run: python scripts/robinhood_mcp_login.py",
            )
        try:
            snapshot = asyncio.run(self.fetch_live_portfolio())
        except Exception as exc:
            logger.exception("Robinhood MCP sync failed")
            return BrokerageSyncResult(source="robinhood_mcp", message=f"MCP sync failed: {exc}")
        return BrokerageSyncResult(
            source="robinhood_mcp",
            holdings_count=len(snapshot.holdings),
            message=f"Fetched {len(snapshot.holdings)} positions from Robinhood MCP",
        )


async def run_oauth_login(*, open_browser: bool = True) -> None:
    """Complete Robinhood MCP OAuth and persist tokens for automated sync."""
    storage = FileTokenStorage()
    loop = asyncio.get_running_loop()
    code_future: asyncio.Future[tuple[str, str | None]] = loop.create_future()

    parsed = urlparse(ROBINHOOD_MCP_REDIRECT_URI)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8765
    path = parsed.path or "/callback"

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if urlparse(self.path).path != path:
                self.send_error(404)
                return
            qs = parse_qs(urlparse(self.path).query)
            code = (qs.get("code") or [None])[0]
            state = (qs.get("state") or [None])[0]
            if code and not code_future.done():
                loop.call_soon_threadsafe(code_future.set_result, (code, state))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"Robinhood MCP connected. Close this tab and return to StockPick."
            )

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = HTTPServer((host, port), CallbackHandler)
    thread = Thread(target=server.handle_request, daemon=True)
    thread.start()

    async def redirect_handler(url: str) -> None:
        if open_browser:
            webbrowser.open(url)

    async def callback_handler() -> tuple[str, str | None]:
        return await code_future

    oauth = OAuthClientProvider(
        server_url=ROBINHOOD_MCP_URL,
        client_metadata=OAuthClientMetadata(
            client_name="StockPick",
            redirect_uris=[AnyUrl(ROBINHOOD_MCP_REDIRECT_URI)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method="none",
        ),
        storage=storage,
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )

    async with streamablehttp_client(ROBINHOOD_MCP_URL, auth=oauth) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            logger.info("Robinhood MCP authenticated. Tools: %s", ", ".join(names))
            print("Robinhood MCP authenticated.")
            print("Read-only tools available:", ", ".join(sorted(names)))
