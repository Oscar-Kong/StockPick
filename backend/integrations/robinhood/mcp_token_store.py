"""Persist Robinhood MCP OAuth tokens locally (never commit storage/)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_DIR = Path(__file__).resolve().parents[3] / "storage" / "robinhood_mcp"
TOKEN_FILE = "oauth.json"


def token_path(base_dir: Path | None = None) -> Path:
    return (base_dir or DEFAULT_TOKEN_DIR) / TOKEN_FILE


class FileTokenStorage:
    """MCP OAuth token storage backed by a JSON file under storage/robinhood_mcp/."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or DEFAULT_TOKEN_DIR
        self.path = token_path(self.base_dir)

    def _load(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not read Robinhood MCP token file: %s", exc)
            return {}

    def _save(self, data: dict) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    async def get_tokens(self) -> OAuthToken | None:
        raw = self._load().get("tokens")
        if not raw:
            return None
        try:
            return OAuthToken.model_validate(raw)
        except Exception:
            return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._load()
        data["tokens"] = tokens.model_dump(mode="json")
        self._save(data)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        raw = self._load().get("client_info")
        if not raw:
            return None
        try:
            return OAuthClientInformationFull.model_validate(raw)
        except Exception:
            return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        data = self._load()
        data["client_info"] = client_info.model_dump(mode="json")
        self._save(data)


def has_valid_tokens(base_dir: Path | None = None) -> bool:
    path = token_path(base_dir)
    if not path.is_file():
        return False
    try:
        tokens = json.loads(path.read_text(encoding="utf-8")).get("tokens") or {}
    except (json.JSONDecodeError, OSError):
        return False
    access = (tokens.get("access_token") or tokens.get("accessToken") or "").strip()
    return bool(access)
