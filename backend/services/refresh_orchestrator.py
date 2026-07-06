"""Deep PortfolioRefresh module — home cockpit and scheduled data refresh."""
from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Literal

from data.freshness_store import clear_freshness_flag, mark_freshness_updated, set_freshness_flag
from data.portfolio_store import get_current_holdings
from data.price_service import PriceService
from models.schemas import Bucket
from services.data_freshness_service import assess_freshness
from services.portfolio_snapshot_service import refresh_holdings_snapshot, sync_brokerage_if_configured
from services.scan_service import scan_service

logger = logging.getLogger(__name__)

RefreshScope = Literal["holdings", "prices", "decision", "penny_scan", "home", "decision_chain", "all"]
RefreshMode = Literal["sync", "background"]
RefreshTrigger = Literal["manual", "auto", "scheduled", "ops", "refresh"]

MAX_HOME_REFRESH_SECONDS = 600
AUTO_REFRESH_COOLDOWN_SECONDS = 300


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PortfolioRefresh:
    """Single entry for portfolio/home data refresh with dependency ordering."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._home_refresh_running = False
        self._active_home_job_id: str | None = None
        self._refresh_started_at: datetime | None = None
        self._last_auto_refresh_at: datetime | None = None
        self._last_price_refresh_at: datetime | None = None

    def is_running(self, scope: RefreshScope = "home") -> bool:
        if scope != "home":
            return False
        self._maybe_recover_stuck_refresh()
        with self._lock:
            return self._home_refresh_running

    def active_job(self, scope: RefreshScope = "home") -> str | None:
        if scope != "home":
            return None
        self._maybe_recover_stuck_refresh()
        with self._lock:
            return self._active_home_job_id

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def mark_inputs_dirty(self, *, closed_positions: bool = True) -> None:
        set_freshness_flag("portfolio_holdings", "holdings_dirty", True)
        if closed_positions:
            set_freshness_flag("closed_positions", "needs_refresh", True)

    def refresh(
        self,
        scope: RefreshScope,
        *,
        force: bool = False,
        mode: RefreshMode = "sync",
        trigger: RefreshTrigger = "manual",
        blocking: bool = False,
    ) -> dict:
        scope = scope.lower()  # type: ignore[assignment]
        if scope == "prices":
            return self.refresh_prices_for_holdings(force=force)
        if scope == "penny_scan":
            return self.refresh_penny_scan_if_needed(force=force, blocking=blocking)
        if scope == "holdings" or scope == "portfolio":
            return self._refresh_holdings(force=force)
        if scope == "daily_decision" or scope == "decision":
            return self.refresh_daily_decision_if_needed(force=force, trigger=trigger)
        if scope == "decision_chain":
            return self._execute_decision_chain(force=force, trigger=trigger)
        if scope in ("home", "all"):
            if mode == "background":
                job_id = self.start_home_async(force=force)
                if not job_id:
                    return {"skipped": True, "reason": "home_refresh_already_running"}
                return {"job_id": job_id, "status": "running"}
            return self.refresh_home_sync(force=force)
        raise ValueError(f"Unknown refresh scope: {scope}")

    def try_begin_auto_refresh(self) -> str | None:
        """Atomic cooldown + slot reservation for stale-while-revalidate dashboard loads."""
        with self._lock:
            self._maybe_recover_stuck_refresh_unlocked()
            if self._home_refresh_running:
                return None
            if self._last_auto_refresh_at is not None:
                age = (_utcnow() - self._last_auto_refresh_at).total_seconds()
                if age < AUTO_REFRESH_COOLDOWN_SECONDS:
                    return None
            job_id = str(uuid.uuid4())
            self._home_refresh_running = True
            self._refresh_started_at = _utcnow()
            self._active_home_job_id = job_id
            self._last_auto_refresh_at = _utcnow()

        self._register_job(job_id, scope="home", force=False)
        self._spawn_home_refresh_thread(job_id=job_id, force=False)
        return job_id

    def start_home_async(self, *, force: bool = False) -> str | None:
        job_id = self._begin_home_refresh(force=force)
        if not job_id:
            return None
        self._spawn_home_refresh_thread(job_id=job_id, force=force)
        return job_id

    def refresh_home_sync(self, *, force: bool = False) -> dict:
        job_id = self._begin_home_refresh(force=force)
        if not job_id:
            return {"skipped": True, "reason": "home_refresh_already_running"}
        try:
            result = self._execute_home_refresh(force=force)
            status = "completed" if result.get("status") != "failed" else "failed"
            self._finish_job(job_id, status=status, result=result, error=result.get("error"))
            return {"job_id": job_id, **result}
        except Exception as exc:
            self._finish_job(job_id, status="failed", error=str(exc)[:500])
            return {"job_id": job_id, "status": "failed", "error": str(exc)[:200]}
        finally:
            with self._lock:
                self._clear_home_refresh_state()

    def refresh_prices_for_holdings(self, *, force: bool = False) -> dict:
        if not force and self._price_ttl_ok():
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
                PriceService().refresh_latest_price(sym, force=force)
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
            self._last_price_refresh_at = _utcnow()
            mark_freshness_updated("latest_prices", source="price_service", extra={"symbols": refreshed})
        elif errors:
            return {"status": "failed", "refreshed": 0, "errors": errors[:5]}
        else:
            return {"skipped": True, "reason": "no_prices_refreshed"}
        return {"refreshed": refreshed, "errors": errors[:5]}

    def refresh_penny_scan_if_needed(self, *, force: bool = False, blocking: bool = False) -> dict:
        status = assess_freshness("penny_scan")
        if not force and not status.is_stale and not status.is_missing:
            return {"skipped": True, "reason": "penny_scan_fresh"}

        job = scan_service.create_job(Bucket.penny)

        def _run() -> None:
            try:
                scan_service.run_scan(job.job_id)
                mark_freshness_updated("penny_scan", source="scan_service")
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

    def refresh_daily_decision_if_needed(
        self, *, force: bool = False, trigger: RefreshTrigger = "refresh"
    ) -> dict:
        status = assess_freshness("daily_decision")
        if not force and not status.is_stale and not status.is_missing:
            return {"skipped": True, "reason": "decision_fresh"}

        holdings = get_current_holdings()
        if not holdings:
            return {"skipped": True, "reason": "no_holdings"}

        from services.portfolio_decision_service import run_stored_portfolio_decision

        decision_trigger = trigger if trigger in ("scheduled", "refresh") else "refresh"
        try:
            decision = run_stored_portfolio_decision(trigger=decision_trigger, persist=True)
            mark_freshness_updated("daily_decision", source="portfolio_decision")
            mark_freshness_updated("risk_metrics", source="portfolio_decision")
            mark_freshness_updated("data_quality", source="portfolio_decision")
            return {"status": "ok", "items": len(decision.items)}
        except Exception as exc:
            logger.warning("Daily decision refresh failed: %s", exc)
            return {"status": "failed", "error": str(exc)[:200]}

    def _price_ttl_ok(self) -> bool:
        if self._last_price_refresh_at is None:
            status = assess_freshness("latest_prices")
            return not status.is_stale
        age = (_utcnow() - self._last_price_refresh_at).total_seconds()
        from services.data_freshness_service import price_stale_after_seconds

        return age < price_stale_after_seconds()

    def _refresh_holdings(self, *, force: bool = False) -> dict:
        sync = sync_brokerage_if_configured()
        status = assess_freshness("portfolio_holdings")
        if not force and not status.is_stale and not status.is_missing:
            return {"skipped": True, "reason": "holdings_fresh", "sync": sync}

        snap = refresh_holdings_snapshot()
        mark_freshness_updated("portfolio_holdings", source="portfolio_snapshot")
        mark_freshness_updated("closed_positions", source="portfolio_snapshot")
        clear_freshness_flag("portfolio_holdings", "holdings_dirty")
        clear_freshness_flag("closed_positions", "needs_refresh")
        return {"sync": sync, "holdings": len(snap.get("holdings") or [])}

    def _execute_decision_chain(self, *, force: bool, trigger: RefreshTrigger) -> dict:
        """Holdings → prices → decision without penny scan (scheduled path)."""
        steps: dict[str, Any] = {}
        h_status = assess_freshness("portfolio_holdings")
        if force or h_status.is_stale or h_status.is_missing:
            steps["holdings"] = self._refresh_holdings(force=force)
        else:
            steps["holdings"] = {"skipped": True}

        p_status = assess_freshness("latest_prices")
        if force or p_status.is_stale or p_status.is_missing:
            steps["prices"] = self.refresh_prices_for_holdings(force=force)
        else:
            steps["prices"] = {"skipped": True}

        d_status = assess_freshness("daily_decision")
        prices_ran = not steps.get("prices", {}).get("skipped")
        holdings_ran = not steps.get("holdings", {}).get("skipped")
        if force or d_status.is_stale or d_status.is_missing or prices_ran or holdings_ran:
            steps["daily_decision"] = self.refresh_daily_decision_if_needed(
                force=force or prices_ran or holdings_ran,
                trigger=trigger,
            )
        else:
            steps["daily_decision"] = {"skipped": True}

        return {"status": "ok", "steps": steps, "trigger": trigger}

    def _execute_home_refresh(self, *, force: bool = False) -> dict:
        steps: dict[str, Any] = {}
        try:
            h_status = assess_freshness("portfolio_holdings")
            if force or h_status.is_stale or h_status.is_missing:
                steps["holdings"] = self._refresh_holdings(force=force)
            else:
                steps["holdings"] = {"skipped": True}

            p_status = assess_freshness("latest_prices")
            if force or p_status.is_stale or p_status.is_missing:
                steps["prices"] = self.refresh_prices_for_holdings(force=force)
            else:
                steps["prices"] = {"skipped": True}

            d_status = assess_freshness("daily_decision")
            prices_ran = not steps.get("prices", {}).get("skipped")
            holdings_ran = not steps.get("holdings", {}).get("skipped")
            if force or d_status.is_stale or d_status.is_missing or prices_ran or holdings_ran:
                steps["daily_decision"] = self.refresh_daily_decision_if_needed(
                    force=force or prices_ran or holdings_ran
                )
            else:
                steps["daily_decision"] = {"skipped": True}

            steps["risk_data_quality"] = {"deferred": "with_daily_decision"}

            pen_status = assess_freshness("penny_scan")
            if force or pen_status.is_stale or pen_status.is_missing:
                steps["penny_scan"] = self.refresh_penny_scan_if_needed(force=force, blocking=False)
            else:
                steps["penny_scan"] = {"skipped": True}

            mark_freshness_updated("home_dashboard", source="portfolio_refresh")
            return {"status": "ok", "steps": steps}
        except Exception as exc:
            logger.exception("Home refresh failed")
            return {"status": "failed", "error": str(exc)[:200]}

    def _clear_home_refresh_state(self) -> None:
        self._home_refresh_running = False
        self._active_home_job_id = None
        self._refresh_started_at = None

    def _maybe_recover_stuck_refresh_unlocked(self) -> None:
        if not self._home_refresh_running or self._refresh_started_at is None:
            return
        age = (_utcnow() - self._refresh_started_at).total_seconds()
        if age <= MAX_HOME_REFRESH_SECONDS:
            return
        timed_out_job = self._active_home_job_id
        logger.warning(
            "Home refresh watchdog: clearing stuck flag after %ss (job=%s)",
            int(age),
            timed_out_job,
        )
        self._clear_home_refresh_state()
        if timed_out_job:
            self._finish_job(timed_out_job, status="failed", error="Home refresh timed out")

    def _maybe_recover_stuck_refresh(self) -> None:
        timed_out_job: str | None = None
        with self._lock:
            if not self._home_refresh_running or self._refresh_started_at is None:
                return
            age = (_utcnow() - self._refresh_started_at).total_seconds()
            if age <= MAX_HOME_REFRESH_SECONDS:
                return
            timed_out_job = self._active_home_job_id
            logger.warning(
                "Home refresh watchdog: clearing stuck flag after %ss (job=%s)",
                int(age),
                timed_out_job,
            )
            self._clear_home_refresh_state()
        if timed_out_job:
            self._finish_job(timed_out_job, status="failed", error="Home refresh timed out")

    def _register_job(self, job_id: str, *, scope: str, force: bool) -> None:
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "scope": scope,
                "force": force,
                "status": "running",
                "started_at": _utcnow().isoformat() + "Z",
                "finished_at": None,
                "error": None,
                "result": None,
            }

    def _finish_job(self, job_id: str, *, status: str, result: dict | None = None, error: str | None = None) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = status
            job["finished_at"] = _utcnow().isoformat() + "Z"
            job["result"] = result
            job["error"] = error

    def _begin_home_refresh(self, *, force: bool) -> str | None:
        self._maybe_recover_stuck_refresh()
        with self._lock:
            if self._home_refresh_running and not force:
                return None
            if self._home_refresh_running and force:
                logger.info("Force home refresh requested — superseding in-progress slot")
            self._home_refresh_running = True
            self._refresh_started_at = _utcnow()
            job_id = str(uuid.uuid4())
            self._active_home_job_id = job_id
        self._register_job(job_id, scope="home", force=force)
        return job_id

    def _spawn_home_refresh_thread(self, *, job_id: str, force: bool) -> None:
        def _run() -> None:
            try:
                result = self._execute_home_refresh(force=force)
                status = "completed" if result.get("status") != "failed" else "failed"
                self._finish_job(job_id, status=status, result=result, error=result.get("error"))
            except Exception as exc:
                self._finish_job(job_id, status="failed", error=str(exc)[:500])
            finally:
                with self._lock:
                    self._clear_home_refresh_state()

        thread = threading.Thread(target=_run, name=f"home-refresh-{job_id[:8]}", daemon=True)
        thread.start()


portfolio_refresh = PortfolioRefresh()

# Backwards-compatible module-level API (tests patch these names on this module).
def is_home_refresh_running() -> bool:
    return portfolio_refresh.is_running("home")


def get_active_home_job_id() -> str | None:
    return portfolio_refresh.active_job("home")


def get_refresh_job(job_id: str) -> dict | None:
    return portfolio_refresh.get_job(job_id)


def refresh_prices_for_holdings(*, force: bool = False) -> dict:
    return portfolio_refresh.refresh_prices_for_holdings(force=force)


def refresh_penny_scan_if_needed(*, force: bool = False, blocking: bool = False) -> dict:
    return portfolio_refresh.refresh_penny_scan_if_needed(force=force, blocking=blocking)


def refresh_daily_decision_if_needed(*, force: bool = False) -> dict:
    return portfolio_refresh.refresh_daily_decision_if_needed(force=force)


def refresh_if_stale(scope: str, *, force: bool = False) -> dict:
    return portfolio_refresh.refresh(scope, force=force)  # type: ignore[arg-type]


def refresh_home_dashboard(*, force: bool = False) -> dict:
    return portfolio_refresh.refresh_home_sync(force=force)


def start_home_refresh_async(*, force: bool = False) -> str | None:
    return portfolio_refresh.start_home_async(force=force)


def try_begin_auto_refresh() -> str | None:
    return portfolio_refresh.try_begin_auto_refresh()


def mark_holdings_dirty(*, closed_positions: bool = True) -> None:
    portfolio_refresh.mark_inputs_dirty(closed_positions=closed_positions)


# Test / legacy shims — tests patch these names on this module.
def _execute_home_refresh(*, force: bool = False) -> dict:
    return portfolio_refresh._execute_home_refresh(force=force)


def _refresh_holdings(*, force: bool = False) -> dict:
    return portfolio_refresh._refresh_holdings(force=force)


def _price_ttl_ok(*, force: bool = False) -> bool:
    return portfolio_refresh._price_ttl_ok()


def __getattr__(name: str):
    if name == "_lock":
        return portfolio_refresh._lock
    if name in {
        "_home_refresh_running",
        "_active_home_job_id",
        "_refresh_started_at",
        "_last_auto_refresh_at",
        "_last_price_refresh_at",
        "_jobs",
    }:
        return getattr(portfolio_refresh, name)
    if name == "scan_manager":
        return scan_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
