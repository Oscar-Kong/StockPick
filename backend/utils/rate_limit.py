"""Lightweight in-memory rate limiting for public demo (no Redis)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from utils.demo_guard import demo_action_disabled

_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)

_CATEGORY_PREFIX = {
    "/scan": "scan",
    "/analyze": "analyze",
    "/backtest": "backtest",
    "/api/v2/backtest": "backtest",
    "/portfolio/optimize": "portfolio",
    "/portfolio/policy-backtest": "backtest",
    "/portfolio/factor-exposure": "portfolio",
    "/research": "research",
    "/explain": "report",
    "/brokerage": "upload",
    "/trades": "upload",
}


def category_for_path(path: str, method: str) -> str | None:
    if method.upper() not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    for prefix, category in _CATEGORY_PREFIX.items():
        if path.startswith(prefix):
            return category
    if path.startswith("/api/v2/report") and method.upper() == "GET":
        return "report"
    return None


def check_rate_limit(category: str, client_key: str = "global") -> None:
    import config

    if not config.DEMO_MODE:
        return
    key = f"{category}:{client_key or 'global'}"
    now = time.monotonic()
    window = 60.0
    limit = max(1, int(config.DEMO_MAX_REQUESTS_PER_MINUTE))
    with _lock:
        bucket = _buckets[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            raise demo_action_disabled(
                f"Rate limit exceeded for {category}. Try again in a minute.",
                status_code=429,
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    with _lock:
        _buckets.clear()


def client_key_from_request(request) -> str:
    """Use direct peer address; do not trust client-supplied forwarding headers."""
    if request.client and request.client.host:
        return request.client.host
    return "global"
