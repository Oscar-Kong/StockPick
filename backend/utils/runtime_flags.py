"""Runtime boolean overrides persisted to data_store (survives restarts)."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in _TRUTHY


class RuntimeBool:
    """Bool-like flag that reads env default + JSON override at check time."""

    __slots__ = ("_registry", "key", "_default")

    def __init__(self, registry: RuntimeFlagRegistry, key: str, default: bool) -> None:
        self._registry = registry
        self.key = key
        self._default = default

    def __bool__(self) -> bool:
        return self._registry.get(self.key, self._default)

    @property
    def value(self) -> bool:
        return bool(self)

    def set(self, enabled: bool) -> None:
        self._registry.set(self.key, enabled)


class RuntimeFlagRegistry:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._defaults: dict[str, bool] = {}
        self._overrides: dict[str, bool] = {}
        self._load()

    def register(self, key: str, env_default: str) -> RuntimeBool:
        default = _parse_bool(env_default, False)
        self._defaults[key] = default
        return RuntimeBool(self, key, default)

    def get(self, key: str, default: bool) -> bool:
        with self._lock:
            if key in self._overrides:
                return self._overrides[key]
        return default

    def set(self, key: str, enabled: bool) -> None:
        if key not in self._defaults:
            raise KeyError(f"Unknown runtime flag: {key}")
        with self._lock:
            if enabled == self._defaults[key]:
                self._overrides.pop(key, None)
            else:
                self._overrides[key] = enabled
            self._save()

    def effective(self, key: str) -> bool:
        default = self._defaults.get(key, False)
        return self.get(key, default)

    def list_effective(self) -> dict[str, bool]:
        return {key: self.effective(key) for key in self._defaults}

    def list_overrides(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._overrides)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._overrides.clear()
            else:
                self._overrides.pop(key, None)
            self._save()

    def default_for(self, key: str) -> bool:
        return self._defaults.get(key, False)

    def is_overridden(self, key: str) -> bool:
        with self._lock:
            return key in self._overrides

    def known_keys(self) -> frozenset[str]:
        return frozenset(self._defaults)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._overrides = {
                    str(k): bool(v) for k, v in raw.items() if isinstance(v, bool)
                }
        except Exception:
            self._overrides = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = dict(sorted(self._overrides.items()))
        self._path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


_registry: RuntimeFlagRegistry | None = None


def get_registry(data_dir: Path | None = None) -> RuntimeFlagRegistry:
    global _registry
    if _registry is None:
        base = data_dir or Path(__file__).resolve().parent.parent / "data_store"
        _registry = RuntimeFlagRegistry(base / "runtime_settings.json")
    return _registry
