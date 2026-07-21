"""Tests for Robinhood MCP OAuth token storage expiry handling."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from mcp.shared.auth import OAuthToken

from integrations.robinhood.mcp_token_store import FileTokenStorage, has_valid_tokens


def test_get_tokens_blanks_expired_access_to_force_refresh(tmp_path: Path):
    storage = FileTokenStorage(base_dir=tmp_path)
    issued = time.time() - 3600
    payload = {
        "tokens": {
            "access_token": "stale-access",
            "token_type": "Bearer",
            "expires_in": 600,
            "refresh_token": "still-good-refresh",
            "scope": "internal",
        },
        "expires_at": issued + 600,  # expired ~40 minutes ago
    }
    path = tmp_path / "oauth.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    token = asyncio.run(storage.get_tokens())
    assert token is not None
    assert token.access_token == ""
    assert token.refresh_token == "still-good-refresh"


def test_get_tokens_infers_expiry_from_mtime_when_expires_at_missing(tmp_path: Path):
    storage = FileTokenStorage(base_dir=tmp_path)
    path = tmp_path / "oauth.json"
    path.write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": "stale-access",
                    "token_type": "Bearer",
                    "expires_in": 60,
                    "refresh_token": "refresh",
                }
            }
        ),
        encoding="utf-8",
    )
    # Pretend the file was written long ago so mtime + expires_in is in the past.
    old = time.time() - 10_000
    import os

    os.utime(path, (old, old))

    token = asyncio.run(storage.get_tokens())
    assert token is not None
    assert token.access_token == ""
    assert token.refresh_token == "refresh"


def test_set_tokens_persists_absolute_expires_at(tmp_path: Path):
    storage = FileTokenStorage(base_dir=tmp_path)
    before = time.time()
    asyncio.run(
        storage.set_tokens(
            OAuthToken(
                access_token="a",
                token_type="Bearer",
                expires_in=3600,
                refresh_token="r",
            )
        )
    )
    after = time.time()
    data = json.loads((tmp_path / "oauth.json").read_text(encoding="utf-8"))
    assert before + 3600 <= float(data["expires_at"]) <= after + 3600


def test_has_valid_tokens_true_with_refresh_only(tmp_path: Path):
    path = tmp_path / "oauth.json"
    path.write_text(
        json.dumps({"tokens": {"access_token": "", "refresh_token": "r", "token_type": "Bearer"}}),
        encoding="utf-8",
    )
    assert has_valid_tokens(tmp_path) is True


def test_fresh_tokens_keep_access(tmp_path: Path):
    storage = FileTokenStorage(base_dir=tmp_path)
    asyncio.run(
        storage.set_tokens(
            OAuthToken(
                access_token="fresh",
                token_type="Bearer",
                expires_in=3600,
                refresh_token="r",
            )
        )
    )
    token = asyncio.run(storage.get_tokens())
    assert token is not None
    assert token.access_token == "fresh"
