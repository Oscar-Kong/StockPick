"""Orchestrate targeted data refresh for the home dashboard."""
from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from data.freshness_store import clear_freshness_flag, mark_freshness_updated, set_freshness_flag
from data.portfolio_store import get_current_holdings
from data.price_service import PriceService
from models.schemas import Bucket
from services.data_freshness_service import assess_freshness
from services.portfolio_snapshot_service import refresh_holdings_snapshot, sync_brokerage_if_configured
from services.scan_manager import scan_manager

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_home_refresh_running = False
_active_home_job_id: str | None = None
_refresh_started_at: datetime | None = None
_last_auto_refresh_at: datetime | None = None
_last_price_refresh_at: datetime | None = None

# Home refresh must not block on long-running penny scans.
MAX_HOME_REFRESH_SECONDS = 600
AUTO_REFRESH_COOLDOWN_SECONDS = 300


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clear_home_refresh_state() -> None:
    global _home_refresh_running, _active_home_job_id, _refresh_started_at
    _home_refresh_running = False
    _active_home_job_id = None
    _refresh_started_at = None


def _maybe_recover_stuck_refresh() -> None:
    """Clear the in-progress flag if a background refresh exceeded the watchdog."""
    global _home_refresh_running, _active_home_job_id, _refresh_started_at
    timed_out_job: str | None = None
    with _lock:
        if not _home_refresh_running or _refresh_started_at is None:
            return
        age = (_utcnow() - _refresh_started_at).total_seconds()
        if age <= MAX_HOME_REFRESH_SECONDS:
            return
        timed_out_job = _active_home_job_id
        logger.warning(
            "Home refresh watchdog: clearing stuck flag after %ss (job=%s)",
            int(age),
            timed_out_job,
        )
        _home_refresh_running = False
        _active_home_job_id = None
        _refresh_started_at = None
    if timed_out_job:
        _finish_job(timed_out_job, status="failed", error="Home refresh timed out")


def is_home_refresh_running() -> bool:
    _maybe_recover_stuck_refresh()
    with _lock:
        return _home_refresh_running


def get_active_home_job_id() -> str | None:
    _maybe_recover_stuck_refresh()
    with _lock:
        return _active_home_job_id


def auto_refresh_allowed() -> bool:
    """Throttle stale-while-revalidate auto refresh on repeated dashboard loads."""
    with _lock:
        if _last_auto_refresh_at is None:
            return True
        age = (_utcnow() - _last_auto_refresh_at).total_seconds()
        return age >= AUTO_REFRESH_COOLDOWN_SECONDS


def mark_auto_refresh_started() -> None:
    global _last_auto_refresh_at
    with _lock:
        _last_auto_refresh_at = _utcnow()


def get_refresh_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _register_job(job_id: str, *, scope: str, force: bool) -> None:
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "scope": scope,
            "force": force,
            "status": "running",
            "started_at": _utcnow().isoformat() + "Z",
            "finished_at": None,
            "error": None,
            "result": None,
        }


def _finish_job(job_id: str, *, status: str, result: dict | None = None, error: str | None = None) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["status"] = status
        job["finished_at"] = _utcnow().isoformat() + "Z"
        job["result"] = result
        job["error"] = error


def _price_ttl_ok(*, force: bool) -> bool:
    global _last_price_refresh_at
    if force:
        return False
    if _last_price_refresh_at is None:
        status = assess_freshness("latest_prices")
        return not status.is_stale
    age = (_utcnow() - _last_price_refresh_at).total_seconds()
    from services.data_freshness_service import price_stale_after_seconds

    return age < price_stale_after_seconds()


def refresh_prices_for_holdings(*, force: bool = False) -> dict:
    global _last_price_refresh_at
    if not force and _price_ttl_ok(force=False):
        return {"skipped": True, "reason": "prices_fresh"}

    holdings = get_current_holdings()
    if not holdings:
        return {"skipped": True, "reason": "no_holdings"}

    refreshed = 0
    errors: list[str] = []
    symbols = [h["symbol"] for h in holdings]
    max_workers = min(8, max(1, len(symbols)))

    def _fetch(sym: str) -> tuple[str, str | None]:
        try:
            PriceService().get_history(sym, period="1d")
            return sym, None
        except Exception as exc:
            return sym, str(exc)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_fetch, sym) for sym in symbols]
        for fut in as_completed(futures):
            sym, err = fut.result()
            if err:
                errors.append(f"{sym}: {err}")
                logger.debug("Price refresh failed for %s: %s", sym, err)
            else:
                refreshed += 1

    if refreshed > 0:
        _last_price_refresh_at = _utcnow()
        mark_freshness_updated("latest_prices", source="price_service", extra={"symbols": refreshed})
    elif errors:
        return {"status": "failed", "refreshed": 0, "errors": errors[:5]}
    else:
        return {"skipped": True, "reason": "no_prices_refreshed"}
    return {"refreshed": refreshed, "errors": errors[:5]}


def refresh_penny_scan_if_needed(*, force: bool = False, blocking: bool = False) -> dict:
    status = assess_freshness("penny_scan")
    if not force and not status.is_stale and not status.is_missing:
        return {"skipped": True, "reason": "penny_scan_fresh"}

    job = scan_manager.create_job(Bucket.penny)

    def _run() -> None:
        try:
            scan_manager.run_scan(job.job_id)
            mark_freshness_updated("penny_scan", source="scan_manager")
        except Exception as exc:
            logger.warning("Penny scan refresh failed: %s", exc)

    if blocking:
        try:
            _run()
            return {"status": "ok", "job_id": job.job_id, "results": len(job.results)}
        except Exception as exc:
            logger.warning("Penny scan refresh failed: %s", exc)
            return {"status": "failed", "error": str(exc)[:200]}

    thread = threading.Thread(target=_run, name=f"penny-refresh-{job.job_id[:8]}", daemon=True)
    thread.start()
    return {"status": "started", "job_id": job.job_id, "async": True}


def refresh_daily_decision_if_needed(*, force: bool = False) -> dict:
    status = assess_freshness("daily_decision")
    if not force and not status.is_stale and not status.is_missing:
        return {"skipped": True, "reason": "decision_fresh"}

    holdings = get_current_holdings()
    if not holdings:
        return {"skipped": True, "reason": "no_holdings"}

    from services.portfolio_decision_service import run_stored_portfolio_decision

    try:
        decision = run_stored_portfolio_decision(trigger="refresh", persist=True)
        mark_freshness_updated("daily_decision", source="portfolio_decision")
        mark_freshness_updated("risk_metrics", source="portfolio_decision")
        mark_freshness_updated("data_quality", source="portfolio_decision")
        return {"status": "ok", "items": len(decision.items)}
    except Exception as exc:
        logger.warning("Daily decision refresh failed: %s", exc)
        return {"status": "failed", "error": str(exc)[:200]}


def refresh_if_stale(scope: str, *, force: bool = False) -> dict:
    """Refresh a single scope if stale (or when force=True)."""
    scope = scope.lower()
    if scope == "prices":
        return refresh_prices_for_holdings(force=force)
    if scope == "penny_scan":
        return refresh_penny_scan_if_needed(force=force)
    if scope == "portfolio":
        return _refresh_holdings(force=force)
    if scope == "daily_decision":
        return refresh_daily_decision_if_needed(force=force)
    if scope == "home":
        return refresh_home_dashboard(force=force)
    if scope == "all":
        return refresh_home_dashboard(force=force)
    raise ValueError(f"Unknown refresh scope: {scope}")


def _refresh_holdings(*, force: bool = False) -> dict:
    status = assess_freshness("portfolio_holdings")
    if not force and not status.is_stale and not status.is_missing:
        return {"skipped": True, "reason": "holdings_fresh"}

    sync = sync_brokerage_if_configured()
    snap = refresh_holdings_snapshot()
    mark_freshness_updated("portfolio_holdings", source="portfolio_snapshot")
    mark_freshness_updated("closed_positions", source="portfolio_snapshot")
    clear_freshness_flag("portfolio_holdings", "holdings_dirty")
    clear_freshness_flag("closed_positions", "needs_refresh")
    return {"sync": sync, "holdings": len(snap.get("holdings") or [])}


def _execute_home_refresh(*, force: bool = False) -> dict:
    """Dependency-ordered refresh steps (caller manages concurrency guard)."""
    steps: dict[str, Any] = {}

    try:
        # 1. Holdings / brokerage sync
        h_status = assess_freshness("portfolio_holdings")
        if force or h_status.is_stale or h_status.is_missing:
            steps["holdings"] = _refresh_holdings(force=force)
        else:
            steps["holdings"] = {"skipped": True}

        # 2. Latest prices
        p_status = assess_freshness("latest_prices")
        if force or p_status.is_stale or p_status.is_missing:
            steps["prices"] = refresh_prices_for_holdings(force=force)
        else:
            steps["prices"] = {"skipped": True}

        # 3. Daily decision — critical for home values; run before optional penny scan
        d_status = assess_freshness("daily_decision")
        prices_ran = not steps.get("prices", {}).get("skipped")
        holdings_ran = not steps.get("holdings", {}).get("skipped")
        if force or d_status.is_stale or d_status.is_missing or prices_ran or holdings_ran:
            steps["daily_decision"] = refresh_daily_decision_if_needed(force=force or prices_ran or holdings_ran)
        else:
            steps["daily_decision"] = {"skipped": True}

        # 4. Risk / data quality — updated as part of decision refresh
        steps["risk_data_quality"] = {"deferred": "with_daily_decision"}

        # 5. Penny scan (never medium) — non-blocking so home refresh can finish quickly
        pen_status = assess_freshness("penny_scan")
        if force or pen_status.is_stale or pen_status.is_missing:
            steps["penny_scan"] = refresh_penny_scan_if_needed(force=force, blocking=False)
        else:
            steps["penny_scan"] = {"skipped": True}

        mark_freshness_updated("home_dashboard", source="refresh_orchestrator")
        return {"status": "ok", "steps": steps}
    except Exception as exc:
        logger.exception("Home refresh failed")
        return {"status": "failed", "error": str(exc)[:200]}


def _begin_home_refresh(*, force: bool) -> str | None:
    """Reserve the home refresh slot; returns job_id or None if already running."""
    global _home_refresh_running, _active_home_job_id, _refresh_started_at
    _maybe_recover_stuck_refresh()
    with _lock:
        if _home_refresh_running and not force:
            return None
        if _home_refresh_running and force:
            logger.info("Force home refresh requested — superseding in-progress slot")
        _home_refresh_running = True
        _refresh_started_at = _utcnow()
        job_id = str(uuid.uuid4())
        _active_home_job_id = job_id
    _register_job(job_id, scope="home", force=force)
    return job_id


def try_begin_auto_refresh() -> str | None:
    """Atomic check+reserve+stamp-cooldown for stale-while-revalidate auto refresh.

    Previously `_attach_auto_refresh` called `is_home_refresh_running()`,
    `auto_refresh_allowed()`, `start_home_refresh_async()`, and
    `mark_auto_refresh_started()` as four separate lock acquisitions. Two
    near-simultaneous dashboard GETs could both observe "not running" before
    either reserved the slot, then advance the cooldown twice while only one
    actually did work.

    This helper performs the check / cooldown / reservation under a single
    `_lock` acquire, then drops the lock before spawning the thread. Returns
    the job_id of the refresh that THIS caller successfully started, or None
    if another caller beat us to it OR the cooldown forbids a new auto
    refresh right now.
    """
    global _home_refresh_running, _active_home_job_id, _refresh_started_at, _last_auto_refresh_at

    _maybe_recover_stuck_refresh()
    with _lock:
        if _home_refresh_running:
            return None
        if _last_auto_refresh_at is not None:
            age = (_utcnow() - _last_auto_refresh_at).total_seconds()
            if age < AUTO_REFRESH_COOLDOWN_SECONDS:
                return None
        job_id = str(uuid.uuid4())
        _home_refresh_running = True
        _refresh_started_at = _utcnow()
        _active_home_job_id = job_id
        _last_auto_refresh_at = _utcnow()

    # Lock released — safe to do I/O-ish work.
    _register_job(job_id, scope="home", force=False)
    _spawn_home_refresh_thread(job_id=job_id, force=False)
    return job_id


def _spawn_home_refresh_thread(*, job_id: str, force: bool) -> None:
    """Spawn the background worker for an already-reserved home refresh job."""

    def _run() -> None:
        try:
            result = _execute_home_refresh(force=force)
            status = "completed" if result.get("status") != "failed" else "failed"
            _finish_job(job_id, status=status, result=result, error=result.get("error"))
        except Exception as exc:
            _finish_job(job_id, status="failed", error=str(exc)[:500])
        finally:
            with _lock:
                _clear_home_refresh_state()

    thread = threading.Thread(target=_run, name=f"home-refresh-{job_id[:8]}", daemon=True)
    thread.start()


def refresh_home_dashboard(*, force: bool = False) -> dict:
    """Run dependency-ordered refresh for home cockpit data (synchronous)."""
    job_id = _begin_home_refresh(force=force)
    if not job_id:
        return {"skipped": True, "reason": "home_refresh_already_running"}
    try:
        result = _execute_home_refresh(force=force)
        status = "completed" if result.get("status") != "failed" else "failed"
        _finish_job(job_id, status=status, result=result, error=result.get("error"))
        return {"job_id": job_id, **result}
    except Exception as exc:
        _finish_job(job_id, status="failed", error=str(exc)[:500])
        return {"job_id": job_id, "status": "failed", "error": str(exc)[:200]}
    finally:
        with _lock:
            _clear_home_refresh_state()


def start_home_refresh_async(*, force: bool = False) -> str | None:
    """Start background home refresh; returns job_id or None if already running."""
    job_id = _begin_home_refresh(force=force)
    if not job_id:
        return None
    _spawn_home_refresh_thread(job_id=job_id, force=force)
    return job_id


def mark_holdings_dirty(*, closed_positions: bool = True) -> None:
    set_freshness_flag("portfolio_holdings", "holdings_dirty", True)
    if closed_positions:
        set_freshness_flag("closed_positions", "needs_refresh", True)
