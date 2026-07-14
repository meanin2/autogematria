"""Tests for the bounded, single-replica SQLite job lifecycle."""

from __future__ import annotations

import sqlite3

import pytest

from autogematria import jobs


@pytest.fixture
def isolated_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "VAR_DIR", tmp_path)
    monkeypatch.setattr(jobs, "JOBS_DB_PATH", tmp_path / "jobs.db")
    jobs.init_db()
    return jobs


def test_job_lifecycle_round_trips_json(isolated_jobs):
    job_id = isolated_jobs.create_job("full_report", {"query": "משה"})
    queued = isolated_jobs.get_job(job_id)
    assert queued is not None
    assert queued["status"] == jobs.STATUS_QUEUED
    assert queued["queue_position"] == 1

    claimed = isolated_jobs.claim_next_job("test-worker")
    assert claimed is not None
    assert claimed["id"] == job_id
    assert claimed["status"] == jobs.STATUS_RUNNING
    assert claimed["attempts"] == 1
    assert claimed["payload"] == {"query": "משה"}

    isolated_jobs.complete_job(job_id, {"ok": True})
    completed = isolated_jobs.get_job(job_id)
    assert completed is not None
    assert completed["status"] == jobs.STATUS_DONE
    assert completed["result"] == {"ok": True}


def test_stale_job_is_retried_once_then_failed(isolated_jobs):
    job_id = isolated_jobs.create_job("full_report", {"query": "רות"})
    first = isolated_jobs.claim_next_job("worker-before-restart")
    assert first is not None

    with isolated_jobs._conn() as conn:
        conn.execute("UPDATE jobs SET started_at = ? WHERE id = ?", (100.0, job_id))

    recovery = isolated_jobs.recover_stale_jobs(
        stale_after_seconds=10,
        max_attempts=2,
        now=200.0,
    )
    assert recovery == {"requeued": 1, "failed": 0}
    assert isolated_jobs.get_job(job_id)["status"] == jobs.STATUS_QUEUED

    second = isolated_jobs.claim_next_job("worker-after-restart")
    assert second is not None
    assert second["attempts"] == 2
    with isolated_jobs._conn() as conn:
        conn.execute("UPDATE jobs SET started_at = ? WHERE id = ?", (200.0, job_id))

    recovery = isolated_jobs.recover_stale_jobs(
        stale_after_seconds=10,
        max_attempts=2,
        now=300.0,
    )
    assert recovery == {"requeued": 0, "failed": 1}
    failed = isolated_jobs.get_job(job_id)
    assert failed is not None
    assert failed["status"] == jobs.STATUS_ERROR
    assert "2 attempts" in failed["error"]


def test_zero_staleness_recovers_a_just_started_job(isolated_jobs):
    job_id = isolated_jobs.create_job("full_report", {"query": "משה"})
    claimed = isolated_jobs.claim_next_job("worker-before-restart")
    assert claimed is not None

    recovery = isolated_jobs.recover_stale_jobs(
        stale_after_seconds=0,
        max_attempts=2,
        now=claimed["started_at"],
    )

    assert recovery == {"requeued": 1, "failed": 0}
    assert isolated_jobs.get_job(job_id)["status"] == jobs.STATUS_QUEUED


def test_init_db_migrates_pre_attempts_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            payload TEXT NOT NULL,
            result TEXT,
            error TEXT,
            created_at REAL NOT NULL,
            started_at REAL,
            completed_at REAL,
            claimed_by TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(jobs, "VAR_DIR", tmp_path)
    monkeypatch.setattr(jobs, "JOBS_DB_PATH", db_path)
    jobs.init_db()

    with jobs._conn() as migrated:
        columns = {row[1] for row in migrated.execute("PRAGMA table_info(jobs)")}
    assert "attempts" in columns
