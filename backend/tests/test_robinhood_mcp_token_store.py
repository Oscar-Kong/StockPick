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


def test_atomic_save_creates_valid_json(tmp_path: Path):
    storage = FileTokenStorage(base_dir=tmp_path)
    asyncio.run(
        storage.set_tokens(
            OAuthToken(access_token="a", token_type="Bearer", expires_in=60, refresh_token="r")
        )
    )
    path = tmp_path / "oauth.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["tokens"]["access_token"] == "a"
    # Temp files should not remain.
    assert not list(tmp_path.glob(".oauth-*.tmp"))


def test_access_token_valid_false_when_expired(tmp_path: Path):
    from integrations.robinhood.mcp_token_store import access_token_valid, credentials_present

    path = tmp_path / "oauth.json"
    path.write_text(
        json.dumps(
            {
                "tokens": {"access_token": "a", "refresh_token": "r", "token_type": "Bearer"},
                "expires_at": time.time() - 10,
            }
        ),
        encoding="utf-8",
    )
    assert credentials_present(tmp_path) is True
    assert access_token_valid(tmp_path) is False


def test_concurrent_set_tokens_do_not_corrupt_json(tmp_path: Path):
    import threading

    storage = FileTokenStorage(base_dir=tmp_path)
    errors: list[BaseException] = []

    def writer(i: int) -> None:
        try:
            asyncio.run(
                storage.set_tokens(
                    OAuthToken(
                        access_token=f"access-{i}",
                        token_type="Bearer",
                        expires_in=3600,
                        refresh_token=f"refresh-{i}",
                    )
                )
            )
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert not errors
    data = json.loads((tmp_path / "oauth.json").read_text(encoding="utf-8"))
    assert "tokens" in data
    assert data["tokens"]["access_token"].startswith("access-")
