"""Persist pairs-research runs for Quant Lab evidence (bounded retention)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from data.db_engine import get_engine
from engines.quant_models import PairsResearchRun
from sqlalchemy.orm import Session
from utils.pydantic_util import json_safe

MAX_PAIRS_STORED = 50
MAX_RUNS_RETAINED = 20


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def persist_pairs_run(
    result: dict[str, Any],
    *,
    status: str = "completed",
    error_message: str | None = None,
    started_at: datetime | None = None,
) -> str:
    """Save a pairs research summary and bounded pair rows."""
    run_id = f"pairs_{uuid.uuid4().hex[:12]}"
    pairs = list(result.get("pairs") or [])[:MAX_PAIRS_STORED]
    summary = {
        k: v
        for k, v in result.items()
        if k != "pairs"
    }
    config = {
        "symbols_requested": summary.get("symbols_requested") or [],
        "symbols_used": summary.get("symbols_used") or [],
        "lookback_period": summary.get("lookback_period"),
        "excluded": summary.get("excluded") or [],
    }

    engine = get_engine()
    with Session(engine) as session:
        session.add(
            PairsResearchRun(
                run_id=run_id,
                status=status,
                config_json=json.dumps(json_safe(config)),
                summary_json=json.dumps(json_safe(summary)),
                pairs_json=json.dumps(json_safe(pairs)),
                error_message=error_message,
                started_at=started_at or _utcnow(),
                finished_at=_utcnow(),
            )
        )
        _prune_old_runs(session)
        session.commit()
    from services.research_run_service import notify_run_persisted

    notify_run_persisted(run_id, store="pairs_research_runs")
    return run_id


def _prune_old_runs(session: Session) -> None:
    rows = (
        session.query(PairsResearchRun)
        .order_by(PairsResearchRun.finished_at.desc())
        .offset(MAX_RUNS_RETAINED)
        .all()
    )
    for row in rows:
        session.delete(row)


def load_latest_pairs_run() -> dict[str, Any] | None:
    engine = get_engine()
    with Session(engine) as session:
        row = (
            session.query(PairsResearchRun)
            .filter(PairsResearchRun.status == "completed")
            .order_by(PairsResearchRun.finished_at.desc())
            .first()
        )
        if not row:
            return None
        summary = json.loads(row.summary_json or "{}")
        return {
            "run_id": row.run_id,
            "status": row.status,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "error_message": row.error_message,
            "config": json.loads(row.config_json or "{}"),
            **summary,
            "pairs": json.loads(row.pairs_json or "[]"),
        }


def load_pairs_run(run_id: str) -> dict[str, Any] | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(PairsResearchRun, run_id)
        if not row:
            return None
        return {
            "run_id": row.run_id,
            "status": row.status,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "error_message": row.error_message,
            "config": json.loads(row.config_json or "{}"),
            "summary": json.loads(row.summary_json or "{}"),
            "pairs": json.loads(row.pairs_json or "[]"),
        }
