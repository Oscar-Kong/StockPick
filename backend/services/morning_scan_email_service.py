"""Morning scan email orchestration — scheduler, ops API, and delivery persistence."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from data import cache as cache_module
from data.db_engine import get_engine
from engines.quant_models import NotificationDelivery, NotificationSentLock, QuantAuditLog
from models.schemas import Bucket
from services.email import get_email_provider
from services.morning_scan_email_templates import BucketEmailSection, build_morning_scan_email
from services.scan_email_comparison import compare_scan_results
from services.scan_email_config import (
    ScanEmailSettings,
    format_recipient_list,
    load_scan_email_settings,
    mask_recipients,
)
from services.scan_manager import scan_manager
from sqlalchemy.orm import Session, sessionmaker
from utils.datetime_util import utc_now

logger = logging.getLogger(__name__)

NOTIFICATION_TYPE = "morning_scan_email"
DELIVERY_KIND_PRIMARY = "primary"


def _recipient_source() -> str:
    from services.mailing_list_store import resolve_scan_email_recipients

    _recipients, source = resolve_scan_email_recipients()
    return source


@dataclass
class MorningScanEmailResult:
    status: str
    message: str
    delivery_id: int | None = None
    dry_run: bool = False
    subject: str | None = None
    html_preview: str | None = None
    text_preview: str | None = None
    deferred: bool = False
    retry_scheduled: bool = False
    recipients: tuple[str, ...] = ()


def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def _parse_completed_at(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_et(dt: datetime | None, tz: ZoneInfo) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%b %d, %Y %I:%M %p")


def _age_label(age_seconds: float | None) -> str:
    if age_seconds is None:
        return "unknown"
    minutes = int(age_seconds // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem = minutes % 60
    if hours < 48:
        return f"{hours}h {rem}m" if rem else f"{hours}h"
    days = hours // 24
    return f"{days}d"


def is_trading_session(settings: ScanEmailSettings | None = None) -> bool:
    from config import SCHEDULER_MARKET_CALENDAR

    settings = settings or load_scan_email_settings()
    try:
        import exchange_calendars as xcals
        import pandas as pd

        cal = xcals.get_calendar(SCHEDULER_MARKET_CALENDAR)
        today = pd.Timestamp.now(tz=settings.timezone).normalize()
        return bool(cal.is_session(today))
    except ImportError:
        return True
    except Exception as exc:
        logger.debug("Market calendar check skipped: %s", exc)
        return True


def get_market_date_et(settings: ScanEmailSettings | None = None) -> str:
    settings = settings or load_scan_email_settings()
    tz = ZoneInfo(settings.timezone)
    return datetime.now(tz).strftime("%Y-%m-%d")


def get_market_date_label(settings: ScanEmailSettings | None = None) -> str:
    settings = settings or load_scan_email_settings()
    tz = ZoneInfo(settings.timezone)
    return datetime.now(tz).strftime("%b %d, %Y")


def _bucket_label(bucket: str) -> str:
    return {"penny": "Penny", "compounder": "Compounder"}.get(bucket, bucket.title())


def _load_previous_scan(bucket: str) -> list[dict[str, Any]] | None:
    saved = cache_module.list_saved_scans(bucket=bucket, limit=2)
    if len(saved) >= 2:
        return saved[1].get("results") or []
    return None


def _collect_warnings(results: list[dict[str, Any]], metadata: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if any((r.get("metrics") or {}).get("provider_limited_partial_data") for r in results):
        warnings.append("Some candidates have provider-limited partial data")
    parity = metadata.get("parity_summary") or {}
    if parity.get("symbol_count"):
        warnings.append(f"Parity sample active ({parity.get('symbol_count')} symbols)")
    failed = cache_module.get_last_scan_attempt_failure(bucket=metadata.get("_bucket", ""))
    if failed:
        warnings.append("Last scan attempt failed; showing prior cached results")
    return warnings


def _load_bucket_section(
    bucket: str,
    settings: ScanEmailSettings,
) -> BucketEmailSection:
    data = scan_manager.get_latest_scan(Bucket(bucket))
    age_seconds = cache_module.get_latest_scan_cache_age_seconds(bucket)
    is_stale = age_seconds is not None and age_seconds > settings.stale_after_minutes * 60

    if not data or not data.get("results"):
        return BucketEmailSection(
            bucket=bucket,
            label=_bucket_label(bucket),
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

    results = list(data.get("results") or [])
    top = results[: settings.top_n]
    completed = _parse_completed_at(data.get("completed_at"))
    metadata = {**data, "_bucket": bucket}
    warnings = _collect_warnings(results, metadata)
    previous = _load_previous_scan(bucket)
    comparison = compare_scan_results(results, previous, top_n=settings.top_n)

    return BucketEmailSection(
        bucket=bucket,
        label=_bucket_label(bucket),
        results=top,
        completed_at=completed,
        strategy_version=data.get("strategy_version"),
        is_stale=is_stale,
        age_label=_age_label(age_seconds),
        missing=False,
        warnings=warnings,
        comparison=comparison,
        strongest=results[0] if results else None,
    )


def has_active_scans(buckets: tuple[str, ...]) -> bool:
    active = scan_manager.get_active_jobs_for_buckets(buckets)
    return len(active) > 0


def _has_sent_lock(
    session: Session,
    *,
    market_date: str,
    recipient_hash: str,
) -> NotificationSentLock | None:
    return (
        session.query(NotificationSentLock)
        .filter_by(
            notification_type=NOTIFICATION_TYPE,
            market_date=market_date,
            recipient_hash=recipient_hash,
        )
        .first()
    )


def _claim_sent_lock(
    session: Session,
    *,
    market_date: str,
    recipient_hash: str,
    delivery_id: int,
) -> bool:
    """Return True if lock acquired; False if already sent today."""
    if _has_sent_lock(session, market_date=market_date, recipient_hash=recipient_hash):
        return False
    try:
        session.add(
            NotificationSentLock(
                notification_type=NOTIFICATION_TYPE,
                market_date=market_date,
                recipient_hash=recipient_hash,
                delivery_id=delivery_id,
            )
        )
        session.flush()
        return True
    except Exception:
        session.rollback()
        return False


def _find_sent_delivery(
    session: Session,
    *,
    market_date: str,
    recipient_hash: str,
    delivery_kind: str = DELIVERY_KIND_PRIMARY,
) -> NotificationDelivery | None:
    return (
        session.query(NotificationDelivery)
        .filter_by(
            notification_type=NOTIFICATION_TYPE,
            market_date=market_date,
            recipient_hash=recipient_hash,
            delivery_kind=delivery_kind,
            status="sent",
        )
        .order_by(NotificationDelivery.sent_at.desc())
        .first()
    )


def _audit(event_type: str, payload: dict[str, Any]) -> None:
    from config import AUDIT_LOG_ENABLED, FACTOR_MODEL_VERSION, STRATEGY_VERSION

    if not AUDIT_LOG_ENABLED:
        return
    session = _session_factory()()
    try:
        session.add(
            QuantAuditLog(
                event_type=event_type,
                strategy_version=STRATEGY_VERSION,
                factor_model_version=FACTOR_MODEL_VERSION,
                payload_json=json.dumps(payload, default=str)[:4000],
            )
        )
        session.commit()
    except Exception as exc:
        logger.warning("Audit log write failed: %s", exc)
        session.rollback()
    finally:
        session.close()


async def run_morning_scan_email(
    *,
    force: bool = False,
    dry_run: bool = False,
    retry_attempt: int = 0,
    source: str = "scheduler",
) -> MorningScanEmailResult:
    """Internal entry point for scheduler and ops API."""
    settings = load_scan_email_settings()

    if not settings.enabled and not dry_run and not force:
        return MorningScanEmailResult(status="skipped", message="Morning scan email is disabled")

    if not settings.config_valid and not dry_run:
        return MorningScanEmailResult(
            status="skipped",
            message="Invalid email configuration: " + "; ".join(settings.config_errors),
        )

    market_date = get_market_date_et(settings)
    market_date_label = get_market_date_label(settings)
    recipient_hash = settings.recipient_hash
    delivery_kind = DELIVERY_KIND_PRIMARY if not force else f"resend-{uuid.uuid4().hex[:8]}"

    if not dry_run and not force and not is_trading_session(settings):
        return MorningScanEmailResult(status="skipped", message="Not an XNYS trading session")

    session = _session_factory()()
    try:
        if not force and not dry_run:
            if _has_sent_lock(session, market_date=market_date, recipient_hash=recipient_hash):
                sent_row = _find_sent_delivery(
                    session,
                    market_date=market_date,
                    recipient_hash=recipient_hash,
                )
                return MorningScanEmailResult(
                    status="skipped",
                    message="Email already sent for this market date",
                    delivery_id=sent_row.id if sent_row else None,
                )

        if has_active_scans(settings.buckets) and retry_attempt < settings.max_retries and not force:
            from services.scheduler import schedule_morning_scan_email_retry

            schedule_morning_scan_email_retry(retry_attempt + 1, settings.retry_delay_minutes)
            return MorningScanEmailResult(
                status="deferred",
                message="Scan in progress — retry scheduled",
                deferred=True,
                retry_scheduled=True,
            )

        sections = [_load_bucket_section(b, settings) for b in settings.buckets]
        available = [s for s in sections if not s.missing]
        unavailable = len(available) == 0
        partial = len(available) < len(sections) and not unavailable
        global_stale = any(s.is_stale for s in available) if available else False

        tz = ZoneInfo(settings.timezone)
        generated_et = _format_et(datetime.now(timezone.utc), tz) or "—"
        latest_completion = None
        for sec in available:
            if sec.completed_at and (latest_completion is None or sec.completed_at > latest_completion):
                latest_completion = sec.completed_at
        latest_completion_et = _format_et(latest_completion, tz)

        if global_stale and latest_completion:
            freshness = f"STALE SCAN — Last completed: {latest_completion_et} · Age: {_age_label((datetime.now(timezone.utc) - latest_completion).total_seconds())}"
        elif unavailable:
            freshness = "Unavailable"
        else:
            freshness = "Fresh"

        strategy_version = next((s.strategy_version for s in available if s.strategy_version), "—") or "—"

        content = build_morning_scan_email(
            market_date_label=market_date_label,
            generated_at_et=generated_et or "—",
            latest_completion_et=latest_completion_et,
            freshness_label=freshness,
            strategy_version=str(strategy_version),
            sections=sections,
            public_url=settings.public_url,
            unavailable=unavailable,
            partial=partial,
            global_is_stale=global_stale,
        )

        if dry_run:
            return MorningScanEmailResult(
                status="dry_run",
                message=f"Email built successfully (dry run) — would send to {format_recipient_list(settings.recipients)}",
                dry_run=True,
                subject=content.subject,
                html_preview=content.html[:2000],
                text_preview=content.text[:2000],
                recipients=settings.recipients,
            )

        from config import DEMO_MODE

        if DEMO_MODE:
            return MorningScanEmailResult(status="skipped", message="Demo mode — real email blocked")

        if not force:
            if _has_sent_lock(session, market_date=market_date, recipient_hash=recipient_hash):
                sent_row = _find_sent_delivery(
                    session,
                    market_date=market_date,
                    recipient_hash=recipient_hash,
                )
                return MorningScanEmailResult(
                    status="skipped",
                    message="Email already sent for this market date",
                    delivery_id=sent_row.id if sent_row else None,
                )

        delivery = NotificationDelivery(
            notification_type=NOTIFICATION_TYPE,
            market_date=market_date,
            scheduled_for=utc_now(),
            recipient_hash=recipient_hash,
            delivery_kind=delivery_kind,
            status="sending",
            provider=settings.provider,
            attempt_count=retry_attempt + 1,
            scan_ids_json=json.dumps({s.bucket: len(s.results) for s in sections}),
            is_resend=force,
            is_dry_run=False,
        )
        session.add(delivery)
        session.commit()
        session.refresh(delivery)

        if not force:
            if not _claim_sent_lock(
                session,
                market_date=market_date,
                recipient_hash=recipient_hash,
                delivery_id=delivery.id,
            ):
                delivery.status = "skipped"
                delivery.error_summary = "Duplicate delivery suppressed by idempotency lock"
                session.commit()
                return MorningScanEmailResult(
                    status="skipped",
                    message="Email already sent for this market date",
                    delivery_id=delivery.id,
                )

        provider = get_email_provider(dry_run=False)
        result = await provider.send_email(
            to=list(settings.recipients),
            subject=content.subject,
            html=content.html,
            text=content.text,
            from_address=settings.from_address,
        )

        if result.ok:
            delivery.status = "sent"
            delivery.sent_at = utc_now()
            delivery.provider_message_id = result.message_id
            session.commit()
            _audit(
                "morning_scan_email_sent",
                {
                    "delivery_id": delivery.id,
                    "market_date": market_date,
                    "source": source,
                    "recipient_masked": mask_recipients(settings.recipients),
                    "is_resend": force,
                },
            )
            logger.info(
                "Morning scan email sent delivery_id=%s market_date=%s source=%s",
                delivery.id,
                market_date,
                source,
            )
            return MorningScanEmailResult(
                status="sent",
                message=f"Email sent to {format_recipient_list(settings.recipients)}",
                delivery_id=delivery.id,
                subject=content.subject,
                recipients=settings.recipients,
            )

        delivery.status = "failed"
        delivery.error_code = result.error_code
        delivery.error_summary = (result.error_summary or "")[:500]
        if not force:
            try:
                lock = _has_sent_lock(session, market_date=market_date, recipient_hash=recipient_hash)
                if lock and lock.delivery_id == delivery.id:
                    session.delete(lock)
            except Exception:
                pass
        session.commit()
        _audit(
            "morning_scan_email_failed",
            {
                "delivery_id": delivery.id,
                "error_code": result.error_code,
                "source": source,
            },
        )
        return MorningScanEmailResult(
            status="failed",
            message=result.error_summary or "Email delivery failed",
            delivery_id=delivery.id,
        )
    except Exception as exc:
        session.rollback()
        logger.exception("Morning scan email job failed")
        return MorningScanEmailResult(status="failed", message=str(exc)[:200])
    finally:
        session.close()


def run_morning_scan_email_sync(**kwargs: Any) -> dict[str, Any]:
    """Sync wrapper for scheduler and job queue."""
    result = asyncio.run(run_morning_scan_email(**kwargs))
    return {
        "status": result.status,
        "message": result.message,
        "delivery_id": result.delivery_id,
        "dry_run": result.dry_run,
        "deferred": result.deferred,
        "retry_scheduled": result.retry_scheduled,
        "subject": result.subject,
        "html_preview": result.html_preview,
        "text_preview": result.text_preview,
        "recipients": list(result.recipients),
    }


def get_morning_scan_email_status() -> dict[str, Any]:
    settings = load_scan_email_settings()
    from services.scheduler import get_morning_scan_email_scheduler_info

    sched = get_morning_scan_email_scheduler_info()
    session = _session_factory()()
    try:
        last_sent = (
            session.query(NotificationDelivery)
            .filter_by(notification_type=NOTIFICATION_TYPE, status="sent")
            .order_by(NotificationDelivery.sent_at.desc())
            .first()
        )
        last_attempt = (
            session.query(NotificationDelivery)
            .filter_by(notification_type=NOTIFICATION_TYPE)
            .order_by(NotificationDelivery.created_at.desc())
            .first()
        )
    finally:
        session.close()

    freshness: dict[str, Any] = {}
    for bucket in settings.buckets:
        age = cache_module.get_latest_scan_cache_age_seconds(bucket)
        freshness[bucket] = {
            "cache_age_seconds": age,
            "stale": age is not None and age > settings.stale_after_minutes * 60,
        }

    return {
        "enabled": settings.enabled,
        "configured": settings.config_valid,
        "config_errors": list(settings.config_errors),
        "provider": settings.provider,
        "recipient_masked": mask_recipients(settings.recipients),
        "recipients": list(settings.recipients),
        "recipient_count": len(settings.recipients),
        "recipient_source": _recipient_source(),
        "schedule_label": "9:20 AM ET",
        "cron": settings.cron,
        "timezone": settings.timezone,
        "buckets": list(settings.buckets),
        "top_n": settings.top_n,
        "scheduler_active": sched.get("active", False),
        "next_run_at": sched.get("next_run_at"),
        "last_successful_delivery": _delivery_to_dict(last_sent),
        "last_attempted_delivery": _delivery_to_dict(last_attempt),
        "scan_freshness": freshness,
    }


def get_morning_scan_email_history(limit: int = 20) -> list[dict[str, Any]]:
    session = _session_factory()()
    try:
        rows = (
            session.query(NotificationDelivery)
            .filter_by(notification_type=NOTIFICATION_TYPE)
            .order_by(NotificationDelivery.created_at.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        return [_delivery_to_dict(r) for r in rows]
    finally:
        session.close()


def _delivery_to_dict(row: NotificationDelivery | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": row.id,
        "notification_type": row.notification_type,
        "market_date": row.market_date,
        "status": row.status,
        "provider": row.provider,
        "attempt_count": row.attempt_count,
        "error_code": row.error_code,
        "error_summary": row.error_summary,
        "is_resend": row.is_resend,
        "is_dry_run": row.is_dry_run,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        "sent_at": row.sent_at.isoformat() + "Z" if row.sent_at else None,
    }
