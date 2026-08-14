"""Persisted morning-scan email overrides (schedule, freshness, preview copy).

Env vars remain defaults. Settings → Ops writes win when set.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.datetime_util import utc_iso_z

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


@dataclass(frozen=True)
class ScanEmailOverrides:
    send_time_et: str | None = None  # "HH:MM" America/New_York
    stale_after_minutes: int | None = None
    subject_template: str | None = None  # may include {date}
    intro_note: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "send_time_et": self.send_time_et,
            "stale_after_minutes": self.stale_after_minutes,
            "subject_template": self.subject_template,
            "intro_note": self.intro_note,
            "updated_at": self.updated_at,
        }


def parse_send_time_et(value: str) -> tuple[int, int]:
    text = (value or "").strip()
    match = _TIME_RE.match(text)
    if not match:
        raise ValueError("Send time must be HH:MM (24-hour), e.g. 09:20")
    hour = int(match.group(1))
    minute = int(match.group(2))
    return hour, minute


def cron_from_send_time(hour: int, minute: int) -> str:
    """Weekday-only cron in SCAN_EMAIL_TIMEZONE (default America/New_York)."""
    return f"{minute} {hour} * * 1-5"


def send_time_from_cron(cron: str) -> str | None:
    parts = (cron or "").strip().split()
    if len(parts) < 2:
        return None
    try:
        minute = int(parts[0])
        hour = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def schedule_label_from_time(send_time_et: str, *, timezone_name: str = "America/New_York") -> str:
    hour, minute = parse_send_time_et(send_time_et)
    suffix = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    tz_short = "ET" if "New_York" in timezone_name or "Detroit" in timezone_name else timezone_name
    return f"{hour12}:{minute:02d} {suffix} {tz_short}"


class ScanEmailOverridesStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()

    def get(self) -> ScanEmailOverrides:
        with self._lock:
            return self._row_to_overrides(self._data)

    def update(
        self,
        *,
        send_time_et: str | None = None,
        stale_after_minutes: int | None = None,
        subject_template: str | None = None,
        intro_note: str | None = None,
        clear_subject_template: bool = False,
        clear_intro_note: bool = False,
    ) -> ScanEmailOverrides:
        with self._lock:
            if send_time_et is not None:
                text = send_time_et.strip()
                if text == "":
                    self._data.pop("send_time_et", None)
                else:
                    parse_send_time_et(text)  # validate
                    self._data["send_time_et"] = f"{parse_send_time_et(text)[0]:02d}:{parse_send_time_et(text)[1]:02d}"

            if stale_after_minutes is not None:
                mins = int(stale_after_minutes)
                if mins < 1:
                    raise ValueError("stale_after_minutes must be >= 1")
                if mins > 10080:
                    raise ValueError("stale_after_minutes must be <= 10080 (7 days)")
                self._data["stale_after_minutes"] = mins

            if clear_subject_template:
                self._data.pop("subject_template", None)
            elif subject_template is not None:
                cleaned = subject_template.strip()
                if not cleaned:
                    self._data.pop("subject_template", None)
                else:
                    if len(cleaned) > 200:
                        raise ValueError("subject_template must be <= 200 characters")
                    self._data["subject_template"] = cleaned

            if clear_intro_note:
                self._data.pop("intro_note", None)
            elif intro_note is not None:
                cleaned = intro_note.strip()
                if not cleaned:
                    self._data.pop("intro_note", None)
                else:
                    if len(cleaned) > 2000:
                        raise ValueError("intro_note must be <= 2000 characters")
                    self._data["intro_note"] = cleaned

            self._data["updated_at"] = utc_iso_z(datetime.now(timezone.utc))
            self._save()
            return self._row_to_overrides(self._data)

    @staticmethod
    def _row_to_overrides(row: dict[str, Any]) -> ScanEmailOverrides:
        stale = row.get("stale_after_minutes")
        try:
            stale_int = int(stale) if stale is not None else None
        except (TypeError, ValueError):
            stale_int = None
        return ScanEmailOverrides(
            send_time_et=str(row["send_time_et"]) if row.get("send_time_et") else None,
            stale_after_minutes=stale_int,
            subject_template=str(row["subject_template"]) if row.get("subject_template") else None,
            intro_note=str(row["intro_note"]) if row.get("intro_note") else None,
            updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
        )

    def _load(self) -> None:
        if not self._path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._data = raw if isinstance(raw, dict) else {}
        except Exception:
            self._data = {}

    def reload_from_disk(self) -> None:
        with self._lock:
            self._load()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2) + "\n", encoding="utf-8")


_store: ScanEmailOverridesStore | None = None


def get_scan_email_overrides_store(data_dir: Path | None = None) -> ScanEmailOverridesStore:
    global _store
    if _store is None:
        base = data_dir or Path(__file__).resolve().parent.parent / "data_store"
        _store = ScanEmailOverridesStore(base / "scan_email_overrides.json")
    return _store


def reset_scan_email_overrides_store_for_tests() -> None:
    global _store
    _store = None
