"""Background job worker thread.

The API process spawns one worker on startup. It polls jobs.db for queued jobs,
claims one atomically, runs the matching handler, and writes the result.
"""

from __future__ import annotations

import os
import socket
import threading
import time
import traceback
from typing import Any, Callable

from autogematria import jobs

_started = False
_started_lock = threading.Lock()

POLL_INTERVAL_SECONDS = 0.5
CLEANUP_INTERVAL_SECONDS = 600.0


def _run_full_report(payload: dict[str, Any]) -> dict[str, Any]:
    from autogematria.report_service import build_full_report_payload

    return build_full_report_payload(payload["query"])


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "full_report": _run_full_report,
}


def _worker_loop(worker_id: str) -> None:
    last_cleanup = 0.0
    while True:
        try:
            now = time.time()
            if now - last_cleanup > CLEANUP_INTERVAL_SECONDS:
                try:
                    jobs.cleanup_old_jobs()
                except Exception:
                    pass
                last_cleanup = now

            job = jobs.claim_next_job(worker_id)
            if job is None:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            handler = _HANDLERS.get(job["operation"])
            if handler is None:
                jobs.fail_job(job["id"], f"unknown operation: {job['operation']}")
                continue

            try:
                result = handler(job["payload"])
                jobs.complete_job(job["id"], result)
            except Exception as exc:
                jobs.fail_job(job["id"], f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        except Exception:
            time.sleep(POLL_INTERVAL_SECONDS * 4)


def start_worker() -> None:
    global _started
    with _started_lock:
        if _started:
            return
        jobs.init_db()
        jobs.recover_stale_jobs(stale_after_seconds=0)
        _started = True
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    t = threading.Thread(target=_worker_loop, args=(worker_id,), name="ag-job-worker", daemon=True)
    t.start()
