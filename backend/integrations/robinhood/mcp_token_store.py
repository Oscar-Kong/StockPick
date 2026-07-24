"""Persist Robinhood MCP OAuth tokens locally (never commit storage/)."""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_DIR = Path(__file__).resolve().parents[3] / "storage" / "robinhood_mcp"
TOKEN_FILE = "oauth.json"
# Refresh a few minutes early so sync does not race the hard expiry.
_EXPIRY_SKEW_SEC = 120
_PROCESS_LOCK = threading.RLock()

try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix
    fcntl = None  # type: ignore[assignment]


def token_path(base_dir: Path | None = None) -> Path:
    return (base_dir or DEFAULT_TOKEN_DIR) / TOKEN_FILE


def _infer_expires_at(data: dict, token: OAuthToken, path: Path) -> float | None:
    """Absolute unix expiry. Prefer stored expires_at; else file mtime + expires_in."""
    raw = data.get("expires_at")
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    if token.expires_in is None or not path.is_file():
        return None
    try:
        return float(path.stat().st_mtime) + int(token.expires_in)
    except (TypeError, ValueError, OSError):
        return None


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

    def _atomic_write(self, data: dict) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".oauth-",
            suffix=".tmp",
            dir=str(self.base_dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(payload)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def _save(self, data: dict) -> None:
        """Persist JSON with process + optional file lock. Caller may already hold _PROCESS_LOCK."""
        if fcntl is None:
            self._atomic_write(data)
            return
        lock_path = self.base_dir / ".oauth.lock"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                self._atomic_write(data)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    async def get_tokens(self) -> OAuthToken | None:
        with _PROCESS_LOCK:
            data = self._load()
            raw = data.get("tokens")
            if not raw:
                return None
            try:
                token = OAuthToken.model_validate(raw)
            except Exception:
                return None

            expires_at = _infer_expires_at(data, token, self.path)
            now = time.time()
            expired = expires_at is not None and now >= (expires_at - _EXPIRY_SKEW_SEC)

            # MCP SDK never sets token_expiry_time when loading from storage, so an
            # expired access_token is still treated as valid until the server 401s —
            # then it tries a browser grant with no redirect handler. Blank the
            # access token when we know it is stale so refresh_token is used instead.
            if expired and token.refresh_token:
                return token.model_copy(update={"access_token": ""})
            return token

    async def set_tokens(self, tokens: OAuthToken) -> None:
        with _PROCESS_LOCK:
            data = self._load()
            data["tokens"] = tokens.model_dump(mode="json")
            if tokens.expires_in is not None:
                try:
                    data["expires_at"] = time.time() + int(tokens.expires_in)
                except (TypeError, ValueError):
                    data.pop("expires_at", None)
            else:
                data.pop("expires_at", None)
            self._save(data)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        with _PROCESS_LOCK:
            data = self._load()
            raw = data.get("client_info")
            if not raw:
                return None
            try:
                return OAuthClientInformationFull.model_validate(raw)
            except Exception:
                return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        with _PROCESS_LOCK:
            data = self._load()
            data["client_info"] = client_info.model_dump(mode="json")
            self._save(data)


def credentials_present(base_dir: Path | None = None) -> bool:
    """True when the token file has a non-empty access or refresh token string."""
    path = token_path(base_dir)
    if not path.is_file():
        return False
    try:
        tokens = json.loads(path.read_text(encoding="utf-8")).get("tokens") or {}
    except (json.JSONDecodeError, OSError):
        return False
    access = (tokens.get("access_token") or tokens.get("accessToken") or "").strip()
    refresh = (tokens.get("refresh_token") or tokens.get("refreshToken") or "").strip()
    return bool(access or refresh)


def access_token_valid(base_dir: Path | None = None) -> bool:
    """True when credentials exist and access token is not past expiry skew."""
    path = token_path(base_dir)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    tokens = data.get("tokens") or {}
    access = (tokens.get("access_token") or tokens.get("accessToken") or "").strip()
    if not access:
        return False
    raw = data.get("expires_at")
    try:
        expires_at = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        expires_at = None
    if expires_at is None:
        return True
    return time.time() < (expires_at - _EXPIRY_SKEW_SEC)


def has_valid_tokens(base_dir: Path | None = None) -> bool:
    """Backward-compatible alias for credentials_present (access or refresh)."""
    return credentials_present(base_dir)
