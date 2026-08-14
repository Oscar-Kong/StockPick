"""Tests for persisted morning-scan email Ops overrides."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.scan_email_overrides_store import (
    ScanEmailOverridesStore,
    cron_from_send_time,
    parse_send_time_et,
    schedule_label_from_time,
    send_time_from_cron,
)
from services.morning_scan_email_templates import build_email_subject, build_morning_scan_email


def test_parse_and_cron_round_trip():
    hour, minute = parse_send_time_et("09:20")
    assert cron_from_send_time(hour, minute) == "20 9 * * 1-5"
    assert send_time_from_cron("20 9 * * 1-5") == "09:20"
    assert schedule_label_from_time("09:20") == "9:20 AM ET"
    assert schedule_label_from_time("14:05") == "2:05 PM ET"


def test_parse_send_time_rejects_invalid():
    with pytest.raises(ValueError):
        parse_send_time_et("9")
    with pytest.raises(ValueError):
        parse_send_time_et("25:00")


def test_overrides_store_persists(tmp_path: Path):
    store = ScanEmailOverridesStore(tmp_path / "scan_email_overrides.json")
    updated = store.update(send_time_et="8:05", stale_after_minutes=90, subject_template="Scan {date}", intro_note="Hello")
    assert updated.send_time_et == "08:05"
    assert updated.stale_after_minutes == 90
    assert updated.subject_template == "Scan {date}"
    assert updated.intro_note == "Hello"

    reloaded = ScanEmailOverridesStore(tmp_path / "scan_email_overrides.json").get()
    assert reloaded.send_time_et == "08:05"
    assert reloaded.stale_after_minutes == 90


def test_subject_template_and_intro_note_in_email():
    subject = build_email_subject(
        market_date_label="Jul 24, 2026",
        is_stale=False,
        unavailable=False,
        subject_template="Custom Morning — {date}",
    )
    assert subject == "Custom Morning — Jul 24, 2026"

    content = build_morning_scan_email(
        market_date_label="Jul 24, 2026",
        generated_at_et="9:20 AM",
        latest_completion_et="8:55 AM",
        freshness_label="Fresh",
        strategy_version="v1",
        sections=[],
        public_url="http://127.0.0.1:18730",
        unavailable=True,
        partial=False,
        global_is_stale=False,
        subject_template="Ops Note — {date}",
        intro_note="Markets are quiet today.",
    )
    assert "Ops Note — Jul 24, 2026" in content.subject
    assert "Markets are quiet today." in content.text
    assert "Operator note" in content.html
    assert "Markets are quiet today." in content.html
