"""Hard timeouts via disposable child processes.

Thread-based ``future.result(timeout=…)`` cannot stop a running worker: exiting a
``ThreadPoolExecutor`` context still ``shutdown(wait=True)``. Use this helper when
a hung provider call must be terminated.

IPC uses a one-way Pipe and **recv-before-join**: draining large payloads before
``join`` avoids the classic Queue feeder-thread deadlock that false-timeouts
successful Yahoo bulk downloads.
"""
from __future__ import annotations

import logging
import multiprocessing as mp
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _process_worker(
    conn: Any,
    fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    try:
        conn.send(("ok", fn(*args, **kwargs)))
    except BaseException as exc:
        # Prefer a picklable string — arbitrary exception instances may not serialize.
        try:
            conn.send(("err", f"{type(exc).__name__}: {exc}"))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _terminate_process(proc: mp.Process) -> None:
    if not proc.is_alive():
        return
    proc.terminate()
    proc.join(2.0)
    if proc.is_alive():
        proc.kill()
        proc.join(1.0)


def run_with_process_timeout(
    fn: Callable[..., Any],
    /,
    *args: Any,
    timeout: float,
    **kwargs: Any,
) -> Any:
    """Run ``fn(*args, **kwargs)`` in a spawn child; terminate on timeout.

    ``fn`` must be importable at module top-level (picklable under spawn).

    Parent polls the pipe for a result up to ``timeout`` seconds, then joins the
    child. Terminate only when no payload arrives before the deadline.

    Raises:
        TimeoutError: no result within ``timeout`` (after terminate/kill).
        RuntimeError: child raised, or exited without a result.
    """
    if timeout <= 0:
        raise TimeoutError("process timeout must be positive")

    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(
        target=_process_worker,
        args=(child_conn, fn, args, kwargs),
        daemon=True,
    )
    proc.start()
    # Child owns its end; close in parent so EOF is detectable after child exits.
    child_conn.close()

    try:
        if not parent_conn.poll(timeout):
            logger.warning(
                "Terminating hung process after %.1fs (%s)",
                timeout,
                getattr(fn, "__name__", fn),
            )
            _terminate_process(proc)
            raise TimeoutError(f"process timed out after {timeout:.0f}s")

        try:
            status, payload = parent_conn.recv()
        except EOFError as exc:
            proc.join(2.0)
            code = proc.exitcode
            if code:
                raise RuntimeError(f"process exited with code {code}") from exc
            raise RuntimeError("process exited without a result") from exc
    finally:
        try:
            parent_conn.close()
        except Exception:
            pass
        if proc.is_alive():
            proc.join(5.0)
            if proc.is_alive():
                _terminate_process(proc)

    if status == "ok":
        return payload
    raise RuntimeError(str(payload))
