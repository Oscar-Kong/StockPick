"""Phase 7 unit tests — dialect, audit log, DB job queue."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_database_dialect_sqlite():
    from data.db_engine import database_dialect, is_sqlite

    assert is_sqlite()
    assert database_dialect() == "sqlite"


def test_audit_and_job_queue():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_url = f"sqlite:///{path}"
    os.environ["DATABASE_URL"] = db_url
    os.environ["AUDIT_LOG_ENABLED"] = "true"
    os.environ["JOB_QUEUE_BACKEND"] = "db"

    import importlib
    import config

    importlib.reload(config)

    from data import db_engine
    from engines.quant_models import QuantBase

    db_engine.reset_engine()
    QuantBase.metadata.create_all(bind=db_engine.get_engine())

    import engines.audit.logger as al

    importlib.reload(al)
    from engines.audit.logger import audit_log, list_audit_logs

    audit_log("test_event", symbol="AAPL", sleeve="penny", payload={"x": 1})
    events = list_audit_logs(limit=5, event_type="test_event")
    assert len(events) == 1
    assert events[0]["strategy_version"]

    import engines.jobs.queue as jq

    importlib.reload(jq)
    from engines.jobs.queue import enqueue_job, list_queued_jobs

    jid = enqueue_job("quant_daily_jobs", {"force_rebalance": False})
    rows = list_queued_jobs()
    assert any(r["job_id"] == jid for r in rows)

    from services.version_pin import pinned_versions

    v = pinned_versions()
    assert "strategy_version" in v
    assert v["database_dialect"] == "sqlite"

    os.unlink(path)


if __name__ == "__main__":
    test_database_dialect_sqlite()
    test_audit_and_job_queue()
    print("quant v2 phase7 tests passed")
