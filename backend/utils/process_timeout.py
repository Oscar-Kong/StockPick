"""Hard timeouts via disposable child processes.

Thread-based ``future.result(timeout=…)`` cannot stop a running worker: exiting a
``ThreadPoolExecutor`` context still ``shutdown(wait=True)``. Use this helper when
a hung provider call must be terminated.
"""
from __future__ import annotations

import logging
import multiprocessing as mp
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _process_worker(
    queue: mp.Queue,
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    try:
        queue.put(("ok", fn(*args, **kwargs)))
    except BaseException as exc:
        # Prefer a picklable string — arbitrary exception instances may not serialize.
        queue.put(("err", f"{type(exc).__name__}: {exc}"))


def run_with_process_timeout(
    fn: Callable[..., Any],
    /,
    *args: Any,
    timeout: float,
    **kwargs: Any,
) -> Any:
    """Run ``fn(*args, **kwargs)`` in a spawn child; terminate on timeout.

    ``fn`` must be importable at module top-level (picklable under spawn).

    Raises:
        TimeoutError: child still alive after ``timeout`` seconds (after terminate/kill).
        RuntimeError: child raised, or exited without a result.
    """
    if timeout <= 0:
        raise TimeoutError("process timeout must be positive")

    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue(1)
    proc = ctx.Process(
        target=_process_worker,
        args=(queue, fn, args, kwargs),
        daemon=True,
    )
    proc.start()
    proc.join(timeout)

    if proc.is_alive():
        logger.warning("Terminating hung process after %.1fs (%s)", timeout, getattr(fn, "__name__", fn))
        proc.terminate()
        proc.join(2.0)
        if proc.is_alive():
            proc.kill()
            proc.join(1.0)
        raise TimeoutError(f"process timed out after {timeout:.0f}s")

    if queue.empty():
        code = proc.exitcode
        if code:
            raise RuntimeError(f"process exited with code {code}")
        return None

    status, payload = queue.get_nowait()
    if status == "ok":
        return payload
    raise RuntimeError(str(payload))
