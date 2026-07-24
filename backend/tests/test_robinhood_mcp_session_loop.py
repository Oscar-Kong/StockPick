"""MCP client must tolerate multiple asyncio.run() boundaries (sync HTTP + workers)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from integrations.robinhood.mcp_client import RobinhoodMcpClient


def test_session_opens_across_separate_event_loops():
    """Regression: shared asyncio.Lock used to fail on the second asyncio.run()."""
    client = RobinhoodMcpClient()
    enter_count = {"n": 0}

    class _FakeSession:
        async def initialize(self):
            return None

        async def call_tool(self, *args, **kwargs):
            raise AssertionError("not used")

    class _CM:
        async def __aenter__(self):
            enter_count["n"] += 1
            return (_FakeSession(), MagicMock(), None) if False else self

        async def __aexit__(self, *args):
            return None

    # streamablehttp_client yields (read, write, _) — and ClientSession(read, write)
    # needs to be an async CM yielding a session with initialize().

    class _StreamsCM:
        async def __aenter__(self):
            enter_count["n"] += 1
            return (MagicMock(), MagicMock(), None)

        async def __aexit__(self, *args):
            return None

    class _SessionCM:
        def __init__(self, *args, **kwargs):
            self.session = _FakeSession()

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, *args):
            return None

    async def once():
        async with client._session() as session:
            assert session is not None

    with patch("integrations.robinhood.mcp_client.streamablehttp_client", side_effect=lambda *a, **k: _StreamsCM()):
        with patch("integrations.robinhood.mcp_client.ClientSession", side_effect=_SessionCM):
            with patch.object(client, "_build_oauth", return_value=MagicMock()):
                asyncio.run(once())
                asyncio.run(once())

    assert enter_count["n"] == 2
