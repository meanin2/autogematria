"""Single-replica job queue backed by SQLite (WAL).

The API process runs one worker thread. Running jobs are recovered after a
process restart, with a bounded number of attempts.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from typing import Any

from autogematria.config import VAR_DIR

JOBS_DB_PATH = VAR_DIR / "jobs.db"

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _conn() -> sqlite3.Connection:
    VAR_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(JOBS_DB_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                completed_at REAL,
                claimed_by TEXT,
                attempts INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        columns = {row[1] for row in c.execute("PRAGMA table_info(jobs)")}
        if "attempts" not in columns:
            c.execute("ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at)")


def create_job(operation: str, payload: dict[str, Any]) -> str:
    job_id = secrets.token_urlsafe(12)
    now = time.time()
    with _conn() as c:
        c.execute(
            "INSERT INTO jobs (id, operation, status, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, operation, STATUS_QUEUED, json.dumps(payload), now),
        )
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    out = dict(row)
    if out.get("result"):
        try:
            out["result"] = json.loads(out["result"])
        except json.JSONDecodeError:
            pass
    if out.get("payload"):
        try:
            out["payload"] = json.loads(out["payload"])
        except json.JSONDecodeError:
            pass
    if out["status"] == STATUS_QUEUED:
        with _conn() as c:
            ahead = c.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = ? AND created_at < ?",
                (STATUS_QUEUED, out["created_at"]),
            ).fetchone()[0]
        out["queue_position"] = ahead + 1
    return out


def claim_next_job(worker_id: str) -> dict[str, Any] | None:
    """Atomically claim the oldest queued job. Returns the claimed row or None."""
    now = time.time()
    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            row = c.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1",
                (STATUS_QUEUED,),
            ).fetchone()
            if row is None:
                c.execute("COMMIT")
                return None
            c.execute(
                "UPDATE jobs SET status = ?, started_at = ?, claimed_by = ?, "
                "attempts = attempts + 1 WHERE id = ? AND status = ?",
                (STATUS_RUNNING, now, worker_id, row["id"], STATUS_QUEUED),
            )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
    out = dict(row)
    out["status"] = STATUS_RUNNING
    out["started_at"] = now
    out["claimed_by"] = worker_id
    out["attempts"] = int(out.get("attempts", 0)) + 1
    if out.get("payload"):
        try:
            out["payload"] = json.loads(out["payload"])
        except json.JSONDecodeError:
            pass
    return out


def recover_stale_jobs(
    *,
    stale_after_seconds: float | None = None,
    max_attempts: int | None = None,
    now: float | None = None,
) -> dict[str, int]:
    """Requeue abandoned work, failing jobs past the retry cap.

    A zero staleness threshold is used at process startup because this queue is
    intentionally single-replica: every pre-existing running row belonged to
    the worker process that just stopped and can be recovered immediately.
    """
    stale_after = max(
        0.0,
        stale_after_seconds
        if stale_after_seconds is not None
        else _env_float("AUTOGEMATRIA_JOB_STALE_SECONDS", 1800.0),
    )
    attempt_limit = max(
        1,
        max_attempts
        if max_attempts is not None
        else _env_int("AUTOGEMATRIA_JOB_MAX_ATTEMPTS", 2),
    )
    current_time = time.time() if now is None else now
    cutoff = current_time - stale_after
    requeued = 0
    failed = 0

    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            rows = c.execute(
                "SELECT id, attempts FROM jobs "
                "WHERE status = ? AND started_at IS NOT NULL AND started_at <= ?",
                (STATUS_RUNNING, cutoff),
            ).fetchall()
            for row in rows:
                if int(row["attempts"]) >= attempt_limit:
                    c.execute(
                        "UPDATE jobs SET status = ?, error = ?, completed_at = ?, "
                        "claimed_by = NULL WHERE id = ? AND status = ?",
                        (
                            STATUS_ERROR,
                            f"job abandoned after {int(row['attempts'])} attempts",
                            current_time,
                            row["id"],
                            STATUS_RUNNING,
                        ),
                    )
                    failed += 1
                else:
                    c.execute(
                        "UPDATE jobs SET status = ?, started_at = NULL, claimed_by = NULL, "
                        "error = NULL WHERE id = ? AND status = ?",
                        (STATUS_QUEUED, row["id"], STATUS_RUNNING),
                    )
                    requeued += 1
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
    return {"requeued": requeued, "failed": failed}


def complete_job(job_id: str, result: dict[str, Any]) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE jobs SET status = ?, result = ?, completed_at = ? WHERE id = ?",
            (STATUS_DONE, json.dumps(result, ensure_ascii=False, default=str), time.time(), job_id),
        )


def fail_job(job_id: str, error: str) -> None:
    with _conn() as c:
        c.execute(
            "UPDATE jobs SET status = ?, error = ?, completed_at = ? WHERE id = ?",
            (STATUS_ERROR, error, time.time(), job_id),
        )


def cleanup_old_jobs(max_age_seconds: float = 3600.0) -> int:
    cutoff = time.time() - max_age_seconds
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM jobs WHERE status IN (?, ?) AND completed_at IS NOT NULL AND completed_at < ?",
            (STATUS_DONE, STATUS_ERROR, cutoff),
        )
        return cur.rowcount


def queue_depth() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM jobs WHERE status = ?", (STATUS_QUEUED,)).fetchone()[0]
