"""Persistent mailing list for scan email and other notifications."""
from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.datetime_util import utc_iso_z

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class MailingListSubscriber:
    id: str
    email: str
    label: str
    enabled: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "label": self.label,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class MailingListStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._subscribers: list[dict[str, Any]] = []
        self._load()

    def list_subscribers(self) -> list[MailingListSubscriber]:
        with self._lock:
            return [self._row_to_subscriber(row) for row in self._sorted_rows()]

    def active_emails(self) -> list[str]:
        with self._lock:
            return [
                str(row["email"]).strip().lower()
                for row in self._sorted_rows()
                if row.get("enabled", True) and str(row.get("email", "")).strip()
            ]

    def add_subscriber(self, email: str, *, label: str = "") -> MailingListSubscriber:
        normalized = _normalize_email(email)
        if not _EMAIL_RE.match(normalized):
            raise ValueError(f"Invalid email address: {email.strip()}")

        now = utc_iso_z(datetime.now(timezone.utc))
        with self._lock:
            for row in self._subscribers:
                if str(row.get("email", "")).strip().lower() == normalized:
                    raise ValueError(f"Email already on the mailing list: {normalized}")

            subscriber = {
                "id": uuid.uuid4().hex[:12],
                "email": normalized,
                "label": (label or "").strip(),
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }
            self._subscribers.append(subscriber)
            self._save()
            return self._row_to_subscriber(subscriber)

    def update_subscriber(
        self,
        subscriber_id: str,
        *,
        enabled: bool | None = None,
        label: str | None = None,
    ) -> MailingListSubscriber:
        with self._lock:
            row = self._find_row(subscriber_id)
            if row is None:
                raise ValueError(f"Subscriber not found: {subscriber_id}")

            if enabled is not None:
                row["enabled"] = bool(enabled)
            if label is not None:
                row["label"] = label.strip()
            row["updated_at"] = utc_iso_z(datetime.now(timezone.utc))
            self._save()
            return self._row_to_subscriber(row)

    def remove_subscriber(self, subscriber_id: str) -> None:
        with self._lock:
            before = len(self._subscribers)
            self._subscribers = [row for row in self._subscribers if row.get("id") != subscriber_id]
            if len(self._subscribers) == before:
                raise ValueError(f"Subscriber not found: {subscriber_id}")
            self._save()

    def import_from_env(self, emails: list[str]) -> int:
        """Add env recipients that are not already present. Returns count added."""
        added = 0
        for raw in emails:
            email = raw.strip()
            if not email:
                continue
            try:
                self.add_subscriber(email)
                added += 1
            except ValueError as exc:
                if "already on the mailing list" not in str(exc):
                    raise
        return added

    def _find_row(self, subscriber_id: str) -> dict[str, Any] | None:
        for row in self._subscribers:
            if row.get("id") == subscriber_id:
                return row
        return None

    def _sorted_rows(self) -> list[dict[str, Any]]:
        return sorted(
            self._subscribers,
            key=lambda row: (
                str(row.get("email", "")).lower(),
                str(row.get("created_at", "")),
            ),
        )

    @staticmethod
    def _row_to_subscriber(row: dict[str, Any]) -> MailingListSubscriber:
        return MailingListSubscriber(
            id=str(row["id"]),
            email=str(row["email"]),
            label=str(row.get("label") or ""),
            enabled=bool(row.get("enabled", True)),
            created_at=str(row.get("created_at") or ""),
            updated_at=str(row.get("updated_at") or ""),
        )

    def _load(self) -> None:
        if not self._path.exists():
            self._subscribers = []
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            rows = raw.get("subscribers") if isinstance(raw, dict) else None
            if isinstance(rows, list):
                self._subscribers = [row for row in rows if isinstance(row, dict) and row.get("id")]
            else:
                self._subscribers = []
        except Exception:
            self._subscribers = []

    def reload_from_disk(self) -> None:
        with self._lock:
            self._load()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"subscribers": self._sorted_rows()}
        self._path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


_store: MailingListStore | None = None


def get_mailing_list_store(data_dir: Path | None = None) -> MailingListStore:
    global _store
    if _store is None:
        base = data_dir or Path(__file__).resolve().parent.parent / "data_store"
        _store = MailingListStore(base / "mailing_list.json")
    return _store


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def resolve_scan_email_recipients() -> tuple[list[str], str]:
    """Return (recipients, source) where source is settings | env | none."""
    from config import SCAN_EMAIL_TO

    store = get_mailing_list_store()
    store.reload_from_disk()
    managed = store.active_emails()
    if managed:
        return managed, "settings"

    env_parts = [p.strip() for p in (SCAN_EMAIL_TO or "").split(",") if p.strip()]
    if env_parts:
        return env_parts, "env"
    return [], "none"


def get_mailing_list_summary() -> dict[str, Any]:
    store = get_mailing_list_store()
    subscribers = store.list_subscribers()
    active = [s for s in subscribers if s.enabled]
    recipients, source = resolve_scan_email_recipients()
    return {
        "subscribers": [s.to_dict() for s in subscribers],
        "active_count": len(active),
        "recipient_source": source,
        "recipient_count": len(recipients),
    }
