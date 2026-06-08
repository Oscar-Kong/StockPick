#!/usr/bin/env python3
"""Poll DB or Redis job queue and execute registered handlers."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import JOB_QUEUE_POLL_SEC
from data.cache import init_db
from engines.jobs.queue import dequeue_one, effective_backend, process_job


def main() -> None:
    init_db()
    backend = effective_backend()
    if backend == "sync":
        print("JOB_QUEUE_BACKEND=sync — worker not needed (jobs run inline)")
        return

    print(f"Job worker started (backend={backend}, poll={JOB_QUEUE_POLL_SEC}s)")
    while True:
        item = dequeue_one()
        if not item:
            time.sleep(JOB_QUEUE_POLL_SEC)
            continue
        job_id = item["job_id"]
        job_name = item["job_name"]
        payload = item.get("payload") or {}
        print(f"Running {job_name} ({job_id})")
        try:
            process_job(job_id, job_name, payload, backend=backend)
            print(f"Finished {job_name}")
        except Exception as exc:
            print(f"Failed {job_name}: {exc}")


if __name__ == "__main__":
    main()
