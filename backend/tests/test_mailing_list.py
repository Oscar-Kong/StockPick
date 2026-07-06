"""Tests for mailing list store and recipient resolution."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.mailing_list_store import MailingListStore, get_mailing_list_store, resolve_scan_email_recipients
from services.scan_email_config import load_scan_email_settings


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    path = tmp_path / "mailing_list.json"
    store = MailingListStore(path)
    monkeypatch.setattr("services.mailing_list_store._store", store)
    return store


class TestMailingListStore:
    def test_add_and_list_subscriber(self, isolated_store):
        sub = isolated_store.add_subscriber("Alice@Example.com", label="Alice")
        assert sub.email == "alice@example.com"
        assert sub.enabled is True
        rows = isolated_store.list_subscribers()
        assert len(rows) == 1
        assert rows[0].label == "Alice"

    def test_duplicate_email_rejected(self, isolated_store):
        isolated_store.add_subscriber("a@x.com")
        with pytest.raises(ValueError, match="already on the mailing list"):
            isolated_store.add_subscriber("A@x.com")

    def test_invalid_email_rejected(self, isolated_store):
        with pytest.raises(ValueError, match="Invalid email"):
            isolated_store.add_subscriber("not-an-email")

    def test_toggle_and_remove(self, isolated_store):
        sub = isolated_store.add_subscriber("a@x.com")
        updated = isolated_store.update_subscriber(sub.id, enabled=False)
        assert updated.enabled is False
        assert isolated_store.active_emails() == []
        isolated_store.remove_subscriber(sub.id)
        assert isolated_store.list_subscribers() == []

    def test_import_from_env_skips_duplicates(self, isolated_store):
        isolated_store.add_subscriber("a@x.com")
        imported = isolated_store.import_from_env(["a@x.com", "b@y.com"])
        assert imported == 1
        assert {s.email for s in isolated_store.list_subscribers()} == {"a@x.com", "b@y.com"}


class TestRecipientResolution:
    def test_settings_list_takes_priority_over_env(self, isolated_store, monkeypatch):
        isolated_store.add_subscriber("managed@x.com")
        monkeypatch.setattr("config.SCAN_EMAIL_TO", "env@x.com")
        recipients, source = resolve_scan_email_recipients()
        assert recipients == ["managed@x.com"]
        assert source == "settings"

    def test_env_fallback_when_store_empty(self, isolated_store, monkeypatch):
        monkeypatch.setattr("config.SCAN_EMAIL_TO", "env@x.com, other@y.com")
        recipients, source = resolve_scan_email_recipients()
        assert recipients == ["env@x.com", "other@y.com"]
        assert source == "env"

    def test_none_when_empty(self, isolated_store, monkeypatch):
        monkeypatch.setattr("config.SCAN_EMAIL_TO", "")
        recipients, source = resolve_scan_email_recipients()
        assert recipients == []
        assert source == "none"

    def test_load_scan_email_settings_uses_managed_list(self, isolated_store, monkeypatch):
        isolated_store.add_subscriber("managed@x.com")
        monkeypatch.setenv("SCAN_EMAIL_ENABLED", "true")
        monkeypatch.setattr("config.SCAN_EMAIL_TO", "")
        monkeypatch.setenv("SCAN_EMAIL_FROM", "StockPick <sender@example.com>")
        monkeypatch.setenv("SMTP_USER", "sender@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        settings = load_scan_email_settings()
        assert settings.recipients == ("managed@x.com",)
        assert settings.config_valid is True
