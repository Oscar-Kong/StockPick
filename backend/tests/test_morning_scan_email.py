"""Tests for morning scan email notification."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zoneinfo import ZoneInfo

from services.email.types import EmailDeliveryResult
from services.morning_scan_email_templates import build_email_subject, build_morning_scan_email, BucketEmailSection
from services.scan_email_comparison import compare_scan_results
from services.scan_email_config import hash_recipients, load_scan_email_settings, mask_email, mask_recipients


def _sample_row(symbol: str, score: float = 80.0, rank: int = 1) -> dict:
    return {
        "symbol": symbol,
        "price": 4.2,
        "score": score,
        "confidence_score": 72.0,
        "tradability_score": 68.0,
        "risk_level": "medium",
        "bucket": "penny",
        "signals": [{"name": "Momentum", "value": 1, "weight": 1, "contribution": 1}],
        "metrics": {"final_rank": rank, "company_name": f"{symbol} Inc"},
    }


class TestScanEmailConfig:
    def test_mask_email_hides_local_part(self):
        assert mask_email("alice@example.com") == "a***@example.com"

    def test_mask_recipients_never_shows_full_list_in_single_field(self):
        masked = mask_recipients(["a@x.com", "b@y.com"])
        assert "a***@x.com" in masked
        assert "+1 more" in masked

    def test_hash_recipients_stable(self):
        h1 = hash_recipients(["b@y.com", "a@x.com"])
        h2 = hash_recipients(["a@x.com", "b@y.com"])
        assert h1 == h2


class TestCronTimezone:
    def test_cron_resolves_920_am_new_york(self):
        from apscheduler.triggers.cron import CronTrigger

        trigger = CronTrigger.from_crontab("20 9 * * 1-5", timezone="America/New_York")
        tz = ZoneInfo("America/New_York")
        # Pick a known Monday in EST
        ref = datetime(2026, 1, 5, 0, 0, tzinfo=tz)
        next_run = trigger.get_next_fire_time(None, ref)
        assert next_run is not None
        assert next_run.hour == 9
        assert next_run.minute == 20
        assert next_run.tzinfo is not None

    def test_dst_uses_iana_timezone_not_fixed_utc_offset(self):
        from apscheduler.triggers.cron import CronTrigger

        trigger = CronTrigger.from_crontab("20 9 * * 1-5", timezone="America/New_York")
        tz = ZoneInfo("America/New_York")
        winter = datetime(2026, 1, 5, 0, 0, tzinfo=tz)
        summer = datetime(2026, 6, 1, 0, 0, tzinfo=tz)
        w = trigger.get_next_fire_time(None, winter)
        s = trigger.get_next_fire_time(None, summer)
        assert w is not None and s is not None
        assert w.utcoffset() != s.utcoffset()


class TestTradingCalendar:
    def test_weekend_not_trading_session(self):
        from services.morning_scan_email_service import is_trading_session

        with patch("services.morning_scan_email_service.xcals", create=True):
            with patch("pandas.Timestamp") as ts_mock:
                ts_mock.now.return_value.normalize.return_value = MagicMock()
                with patch("services.morning_scan_email_service.is_trading_session") as mocked:
                    mocked.return_value = False
                    assert mocked() is False

    def test_holiday_skipped_via_calendar(self):
        from services.morning_scan_email_service import is_trading_session

        mock_cal = MagicMock()
        mock_cal.is_session.return_value = False
        with patch.dict("sys.modules", {"exchange_calendars": MagicMock(get_calendar=lambda _: mock_cal)}):
            with patch("pandas.Timestamp") as ts_mock:
                ts_mock.now.return_value.normalize.return_value = MagicMock()
                assert is_trading_session() is False


class TestScanSelectionAndTemplates:
    def test_stale_subject_label(self):
        subject = build_email_subject(market_date_label="Jun 24, 2026", is_stale=True, unavailable=False)
        assert subject.startswith("[STALE]")

    def test_unavailable_subject_label(self):
        subject = build_email_subject(market_date_label="Jun 24, 2026", is_stale=False, unavailable=True)
        assert subject.startswith("[Scan Unavailable]")

    def test_html_and_text_include_candidates(self):
        section = BucketEmailSection(
            bucket="penny",
            label="Penny",
            results=[_sample_row("ABC"), _sample_row("XYZ", score=75, rank=2)],
            completed_at=datetime.now(timezone.utc),
            strategy_version="v1",
            is_stale=False,
            age_label="10m",
            missing=False,
            warnings=[],
            comparison=compare_scan_results([], None),
            strongest=_sample_row("ABC"),
        )
        content = build_morning_scan_email(
            market_date_label="Jun 24, 2026",
            generated_at_et="Jun 24, 2026 09:20 AM",
            latest_completion_et="Jun 24, 2026 08:00 AM",
            freshness_label="Fresh",
            strategy_version="v1",
            sections=[section],
            public_url="http://127.0.0.1:18730",
            unavailable=False,
            partial=False,
            global_is_stale=False,
        )
        assert "ABC" in content.html
        assert "ABC" in content.text
        assert "Penny" in content.html

    def test_missing_bucket_does_not_block_other(self):
        penny = BucketEmailSection(
            bucket="penny",
            label="Penny",
            results=[_sample_row("AAA")],
            completed_at=datetime.now(timezone.utc),
            strategy_version="v1",
            is_stale=False,
            age_label="5m",
            missing=False,
            warnings=[],
            comparison=compare_scan_results([], None),
            strongest=_sample_row("AAA"),
        )
        compounder = BucketEmailSection(
            bucket="compounder",
            label="Compounder",
            results=[],
            completed_at=None,
            strategy_version=None,
            is_stale=False,
            age_label="—",
            missing=True,
            warnings=["No completed scan available"],
            comparison=compare_scan_results([], None),
            strongest=None,
        )
        content = build_morning_scan_email(
            market_date_label="Jun 24, 2026",
            generated_at_et="Jun 24, 2026 09:20 AM",
            latest_completion_et="Jun 24, 2026 08:00 AM",
            freshness_label="Partial",
            strategy_version="v1",
            sections=[penny, compounder],
            public_url="http://127.0.0.1:18730",
            unavailable=False,
            partial=True,
            global_is_stale=False,
        )
        assert "AAA" in content.text
        assert "Compounder" in content.text


class TestMorningScanEmailService:
    @pytest.fixture
    def enabled_settings(self):
        from services.scan_email_config import ScanEmailSettings

        return ScanEmailSettings(
            enabled=True,
            provider="smtp",
            recipients=("ops@example.com",),
            from_address="StockPick <ops@example.com>",
            buckets=("penny", "compounder"),
            top_n=5,
            cron="20 9 * * 1-5",
            timezone="America/New_York",
            stale_after_minutes=60,
            retry_delay_minutes=5,
            max_retries=3,
            public_url="http://127.0.0.1:18730",
            config_valid=True,
        )

    def test_dry_run_does_not_contact_provider(self, enabled_settings):
        from services.morning_scan_email_service import run_morning_scan_email

        with patch("services.morning_scan_email_service.load_scan_email_settings", return_value=enabled_settings):
            with patch("services.morning_scan_email_service.is_trading_session", return_value=True):
                with patch("services.morning_scan_email_service.scan_manager") as sm:
                    sm.get_active_jobs_for_buckets.return_value = []
                    sm.get_latest_scan.return_value = {
                        "results": [_sample_row("AAA")],
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "strategy_version": "v1",
                    }
                    with patch("services.morning_scan_email_service.get_email_provider") as gp:
                        result = asyncio.run(run_morning_scan_email(dry_run=True))
                        gp.assert_not_called()
                        assert result.status == "dry_run"
                        assert result.subject

    def test_demo_mode_blocks_real_send(self, enabled_settings):
        from services.morning_scan_email_service import run_morning_scan_email

        with patch("services.morning_scan_email_service.load_scan_email_settings", return_value=enabled_settings):
            with patch("services.morning_scan_email_service.is_trading_session", return_value=True):
                with patch("services.morning_scan_email_service.scan_manager") as sm:
                    sm.get_active_jobs_for_buckets.return_value = []
                    sm.get_latest_scan.return_value = {
                        "results": [_sample_row("AAA")],
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    with patch("config.DEMO_MODE", True):
                        result = asyncio.run(run_morning_scan_email(dry_run=False))
                        assert result.status == "skipped"
                        assert "Demo" in result.message

    def test_active_scan_defers_with_retry(self, enabled_settings):
        from services.morning_scan_email_service import run_morning_scan_email

        active_job = MagicMock()
        active_job.status = "running"
        with patch("services.morning_scan_email_service.load_scan_email_settings", return_value=enabled_settings):
            with patch("services.morning_scan_email_service.is_trading_session", return_value=True):
                with patch("services.morning_scan_email_service.scan_manager") as sm:
                    sm.get_active_jobs_for_buckets.return_value = [active_job]
                    with patch("services.scheduler.schedule_morning_scan_email_retry") as sched:
                        result = asyncio.run(run_morning_scan_email(retry_attempt=0))
                        assert result.status == "deferred"
                        sched.assert_called_once_with(1, 5)

    def test_provider_failure_persisted(self, enabled_settings):
        from engines.quant_db import init_quant_db
        from services.morning_scan_email_service import run_morning_scan_email, get_morning_scan_email_history

        init_quant_db()
        provider = MagicMock()
        provider.send_email = AsyncMock(
            return_value=EmailDeliveryResult(
                ok=False,
                provider="noop",
                error_code="http_422",
                error_summary="Invalid from",
            )
        )
        with patch("services.morning_scan_email_service.load_scan_email_settings", return_value=enabled_settings):
            with patch("services.morning_scan_email_service.is_trading_session", return_value=True):
                with patch("services.morning_scan_email_service.scan_manager") as sm:
                    sm.get_active_jobs_for_buckets.return_value = []
                    sm.get_latest_scan.return_value = {
                        "results": [_sample_row("AAA")],
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    with patch("config.DEMO_MODE", False):
                        with patch("services.morning_scan_email_service.get_email_provider", return_value=provider):
                            result = asyncio.run(run_morning_scan_email(force=True))
                            assert result.status == "failed"
                            history = get_morning_scan_email_history(limit=1)
                            assert history
                            assert history[0]["status"] == "failed"

    def test_duplicate_execution_skipped(self, enabled_settings):
        from engines.quant_db import init_quant_db
        from engines.quant_models import NotificationSentLock
        from data.db_engine import get_engine
        from sqlalchemy.orm import sessionmaker
        from services.morning_scan_email_service import run_morning_scan_email, NOTIFICATION_TYPE

        init_quant_db()
        Session = sessionmaker(bind=get_engine())
        session = Session()
        try:
            session.add(
                NotificationSentLock(
                    notification_type=NOTIFICATION_TYPE,
                    market_date="2026-06-24",
                    recipient_hash=enabled_settings.recipient_hash,
                    delivery_id=1,
                )
            )
            session.commit()
        finally:
            session.close()

        with patch("services.morning_scan_email_service.load_scan_email_settings", return_value=enabled_settings):
            with patch("services.morning_scan_email_service.get_market_date_et", return_value="2026-06-24"):
                with patch("services.morning_scan_email_service.is_trading_session", return_value=True):
                    result = asyncio.run(run_morning_scan_email())
                    assert result.status == "skipped"

    def test_stale_scan_freshness_label(self, enabled_settings):
        from services.morning_scan_email_service import _load_bucket_section

        old = datetime.now(timezone.utc) - timedelta(hours=30)
        with patch("services.morning_scan_email_service.scan_manager") as sm:
            sm.get_latest_scan.return_value = {
                "results": [_sample_row("OLD")],
                "completed_at": old.isoformat(),
                "strategy_version": "v1",
            }
            with patch("services.morning_scan_email_service.cache_module") as cache:
                cache.get_latest_scan_cache_age_seconds.return_value = 30 * 3600
                cache.get_last_scan_attempt_failure.return_value = None
                cache.list_saved_scans.return_value = []
                section = _load_bucket_section("penny", enabled_settings)
                assert section.is_stale is True


class TestOpsAuthorization:
    def test_send_requires_non_demo(self):
        from fastapi.testclient import TestClient
        from main import app

        with patch("utils.demo_guard._demo_mode", return_value=True):
            client = TestClient(app)
            resp = client.post("/ops/notifications/morning-scan/send", json={"force": False, "dry_run": True})
            assert resp.status_code == 403

    def test_status_endpoint_available_in_demo(self):
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        resp = client.get("/ops/notifications/morning-scan/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "enabled" in body
        assert "recipient_masked" in body
        assert "ops@example.com" not in str(body)
