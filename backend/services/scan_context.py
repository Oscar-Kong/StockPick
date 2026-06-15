"""Thread-local flag: bulk universe scan vs single-symbol analyze/watchlist."""
from __future__ import annotations

import threading

_local = threading.local()


def set_bulk_scan(active: bool) -> None:
    _local.active = active


def is_bulk_scan() -> bool:
    return bool(getattr(_local, "active", False))
