"""Tests for the run logger and ETA estimator."""

import json
import tempfile
from pathlib import Path

from autogematria.run_logger import RunTimer, estimate_seconds, get_run_stats


class TestRunTimer:
    def test_timer_measures_time(self):
        timer = RunTimer(operation="test_op", input_text="hello")
        with timer:
            pass
        assert timer.elapsed_seconds > 0
        assert timer.elapsed_seconds < 2

    def test_timer_logs_to_file(self, tmp_path):
        import autogematria.run_logger as rl
        original = rl.LOG_PATH
        rl.LOG_PATH = tmp_path / "test_log.jsonl"
        try:
            with RunTimer(operation="test_log", input_text="test"):
                pass
            assert rl.LOG_PATH.exists()
            lines = rl.LOG_PATH.read_text().strip().split("\n")
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["operation"] == "test_log"
            assert record["input_text"] == "test"
            assert record["elapsed_seconds"] >= 0
            assert "timestamp" in record
        finally:
            rl.LOG_PATH = original

    def test_timer_metadata(self, tmp_path):
        import autogematria.run_logger as rl
        original = rl.LOG_PATH
        rl.LOG_PATH = tmp_path / "test_log.jsonl"
        try:
            timer = RunTimer(operation="test_meta", letter_count=10, word_count=3)
            with timer:
                timer.set_result_metadata(verdict="strong")
            lines = rl.LOG_PATH.read_text().strip().split("\n")
            record = json.loads(lines[0])
            assert record["letter_count"] == 10
            assert record["word_count"] == 3
            assert record["metadata"]["verdict"] == "strong"
        finally:
            rl.LOG_PATH = original


class TestEstimate:
    def test_default_estimate(self):
        est = estimate_seconds("full_report", letter_count=5)
        assert est > 0

    def test_unknown_operation(self):
        est = estimate_seconds("unknown_op")
        assert est > 0


class TestRunStats:
    def test_empty_stats(self, tmp_path):
        import autogematria.run_logger as rl
        original = rl.LOG_PATH
        rl.LOG_PATH = tmp_path / "nonexistent.jsonl"
        try:
            stats = get_run_stats()
            assert stats["total_runs"] == 0
        finally:
            rl.LOG_PATH = original

    def test_stats_with_data(self, tmp_path):
        import autogematria.run_logger as rl
        original = rl.LOG_PATH
        rl.LOG_PATH = tmp_path / "test_stats.jsonl"
        try:
            with RunTimer(operation="op_a"):
                pass
            with RunTimer(operation="op_b"):
                pass
            stats = get_run_stats()
            assert stats["total_runs"] == 2
            assert "op_a" in stats["operations"]
            assert "op_b" in stats["operations"]
        finally:
            rl.LOG_PATH = original
