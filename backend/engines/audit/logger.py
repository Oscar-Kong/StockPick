"""Immutable quant audit trail with pinned strategy / factor model versions."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config import AUDIT_LOG_ENABLED, FACTOR_MODEL_VERSION, STRATEGY_VERSION
from data.db_engine import get_engine
from engines.quant_models import QuantAuditLog
from utils.datetime_util import utc_iso_z

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def audit_log(
    event_type: str,
    *,
    symbol: str | None = None,
    sleeve: str | None = None,
    payload: dict[str, Any] | None = None,
    strategy_version: str | None = None,
    factor_model_version: str | None = None,
) -> int | None:
    if not AUDIT_LOG_ENABLED:
        return None
    try:
        from sqlalchemy.orm import Session

        engine = get_engine()
        with Session(engine) as session:
            row = QuantAuditLog(
                event_type=event_type,
                symbol=symbol.upper() if symbol else None,
                sleeve=sleeve,
                strategy_version=strategy_version or STRATEGY_VERSION,
                factor_model_version=factor_model_version or FACTOR_MODEL_VERSION,
                payload_json=json.dumps(payload or {}, default=str),
                created_at=_utcnow(),
            )
            session.add(row)
            session.commit()
            return int(row.id)
    except Exception as exc:
        logger.warning("Audit log failed (%s): %s", event_type, exc)
        return None


def list_audit_logs(
    *,
    limit: int = 50,
    event_type: str | None = None,
    symbol: str | None = None,
    sleeve: str | None = None,
    since: str | None = None,
    until: str | None = None,
    run_id: str | None = None,
    experiment_id: str | None = None,
    proposal_id: str | None = None,
    strategy_version: str | None = None,
) -> list[dict[str, Any]]:
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        q = session.query(QuantAuditLog).order_by(QuantAuditLog.created_at.desc())
        if event_type:
            q = q.filter(QuantAuditLog.event_type == event_type)
        if symbol:
            q = q.filter(QuantAuditLog.symbol == symbol.upper())
        if sleeve:
            q = q.filter(QuantAuditLog.sleeve == sleeve)
        if strategy_version:
            q = q.filter(QuantAuditLog.strategy_version == strategy_version)
        if since:
            q = q.filter(QuantAuditLog.created_at >= datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None))
        if until:
            q = q.filter(QuantAuditLog.created_at <= datetime.fromisoformat(until.replace("Z", "+00:00")).replace(tzinfo=None))
        rows = q.limit(max(limit, 1) * 3 if run_id or experiment_id or proposal_id else limit).all()
        out: list[dict[str, Any]] = []
        for r in rows:
            payload = json.loads(r.payload_json or "{}")
            if run_id and run_id not in json.dumps(payload):
                if payload.get("run_id") != run_id and run_id not in (payload.get("run_ids") or []):
                    continue
            if experiment_id and payload.get("experiment_id") != experiment_id:
                continue
            if proposal_id and payload.get("proposal_id") != proposal_id:
                continue
            out.append(
                {
                    "id": r.id,
                    "event_type": r.event_type,
                    "symbol": r.symbol,
                    "sleeve": r.sleeve,
                    "strategy_version": r.strategy_version,
                    "factor_model_version": r.factor_model_version,
                    "payload": payload,
                    "created_at": utc_iso_z(r.created_at),
                }
            )
            if len(out) >= limit:
                break
        return out
