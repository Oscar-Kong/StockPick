"""Active-position quote ingestion, evaluation, and transition persistence."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import threading
from typing import Any

from data.cache import get_active_quote_snapshot, save_active_quote_snapshot
from data.portfolio_store import (
    get_active_position_states,
    get_current_holdings,
    list_active_position_transitions,
    save_active_position_monitor_result,
)
from services.active_position_monitor import ActivePositionMonitor
from services.refresh_orchestrator import refresh_active_quotes


_STATE_SEVERITY = {
    "DATA_STALE": 0,
    "HOLD": 1,
    "WATCH": 2,
    "ADD_CONFIRMED": 3,
    "TRIM": 4,
    "EXIT_WARNING": 5,
    "EXIT": 6,
}
_monitor_lock = threading.Lock()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_now(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = _utcnow()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _select_notifications(
    transitions: list[dict[str, Any]],
    recent_transitions: list[dict[str, Any]],
    *,
    cooldown_seconds: int,
) -> list[dict[str, Any]]:
    """Return change alerts, suppressing churn unless the state becomes more severe."""
    selected: list[dict[str, Any]] = []
    for transition in transitions:
        if not transition.get("actionable"):
            continue
        changed_at = _parse_now(transition.get("changed_at"))
        prior = next(
            (
                row
                for row in recent_transitions
                if str(row.get("symbol") or "").upper()
                == str(transition.get("symbol") or "").upper()
                and row.get("changed_at")
                and row.get("actionable")
            ),
            None,
        )
        if prior is None:
            selected.append(transition)
            continue
        prior_at = _parse_now(prior.get("changed_at"))
        within_cooldown = (changed_at - prior_at).total_seconds() < cooldown_seconds
        escalated = _STATE_SEVERITY.get(str(transition.get("to_state")), 0) > _STATE_SEVERITY.get(
            str(prior.get("to_state")), 0
        )
        if not within_cooldown or escalated:
            selected.append(transition)
    return selected


def refresh_and_store_active_quotes() -> dict[str, Any]:
    """Perform one quote-only refresh and persist a short-lived local snapshot."""
    result = refresh_active_quotes()
    as_of = _utcnow().isoformat()
    quotes = result.get("quotes") or {}
    if isinstance(quotes, dict) and quotes:
        save_active_quote_snapshot(quotes, as_of=as_of)
    return {**result, "as_of": as_of}


def run_active_position_monitor(
    *, refresh_quotes: bool = False, now: str | datetime | None = None
) -> dict[str, Any]:
    """Evaluate current holdings from a local quote snapshot and persist state changes."""
    with _monitor_lock:
        if refresh_quotes:
            refresh_and_store_active_quotes()
        holdings = get_current_holdings()
        quote_snapshot = get_active_quote_snapshot()
        prior_rows = get_active_position_states()
        recent_transitions = list_active_position_transitions(limit=100)
        prior_states = {
            str(row.get("symbol") or "").upper(): str(row.get("state") or "")
            for row in prior_rows
            if row.get("symbol")
        }
        prior_times = {
            str(row.get("symbol") or "").upper(): str(
                row.get("state_changed_at") or row.get("updated_at") or ""
            )
            for row in prior_rows
            if row.get("symbol")
        }
        evaluated = ActivePositionMonitor().evaluate(
            holdings=holdings,
            quotes=dict(quote_snapshot.get("quotes") or {}),
            previous_states=prior_states,
            previous_state_times=prior_times,
            now=_parse_now(now),
        )
        statuses = [asdict(status) for status in evaluated.statuses]
        transitions = [
            {**asdict(transition), "changed_at": evaluated.as_of}
            for transition in evaluated.transitions
        ]
        from config import ACTIVE_POSITION_NOTIFICATION_COOLDOWN_SECONDS

        notifications = _select_notifications(
            transitions,
            recent_transitions,
            cooldown_seconds=ACTIVE_POSITION_NOTIFICATION_COOLDOWN_SECONDS,
        )
        save_active_position_monitor_result(statuses, transitions, as_of=evaluated.as_of)
        return {
            "as_of": evaluated.as_of,
            "quote_as_of": quote_snapshot.get("as_of"),
            "statuses": statuses,
            "transitions": transitions,
            "notifications": notifications,
            "quote_only": True,
            "execution_enabled": False,
        }


def get_active_position_monitor_status(*, transition_limit: int = 30) -> dict[str, Any]:
    states = get_active_position_states()
    transitions = list_active_position_transitions(limit=transition_limit)
    quote_snapshot = get_active_quote_snapshot()
    now = _utcnow()
    for state in states:
        quote_at = _parse_now(state.get("quote_as_of")) if state.get("quote_as_of") else None
        age = (now - quote_at).total_seconds() if quote_at else None
        state["quote_age_seconds"] = max(0.0, age) if age is not None else None
        if age is None or age > 120:
            state["state"] = "DATA_STALE"
            state["data_status"] = "stale_quote" if quote_at else "missing_timestamp"
            state["actionable"] = False
    latest_as_of = max(
        (str(row.get("updated_at")) for row in states if row.get("updated_at")),
        default=None,
    )
    return {
        "as_of": latest_as_of,
        "quote_as_of": quote_snapshot.get("as_of"),
        "statuses": states,
        "transitions": transitions,
        "execution_enabled": False,
    }
