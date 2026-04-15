"""Run logger and ETA estimator for AutoGematria operations.

Logs each run (timing, input metadata, results summary) to a JSONL file.
Uses historical data to estimate completion time for new runs based on
input complexity (letter count, word count, component count).
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autogematria.config import DATA_DIR

_write_lock = threading.Lock()
_cache_lock = threading.Lock()
_records_cache: list[dict[str, Any]] = []
_records_cache_mtime: float = -1.0

LOG_PATH = DATA_DIR / "run_log.jsonl"


def _all_records() -> list[dict[str, Any]]:
    """Return all log records, cached and invalidated on file mtime change."""
    global _records_cache, _records_cache_mtime
    if not LOG_PATH.exists():
        return []
    try:
        mtime = LOG_PATH.stat().st_mtime
    except OSError:
        return []
    with _cache_lock:
        if mtime == _records_cache_mtime and _records_cache:
            return _records_cache
        records: list[dict[str, Any]] = []
        try:
            with open(LOG_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return _records_cache
        _records_cache = records
        _records_cache_mtime = mtime
        return records

_DEFAULT_ESTIMATES = {
    "name_report": 0.8,
    "full_report": 15.0,
    "reverse_lookup": 0.05,
    "showcase": 12.0,
    "search": 3.0,
}


@dataclass
class RunTimer:
    """Context manager that times an operation and logs it."""

    operation: str
    input_text: str = ""
    letter_count: int = 0
    word_count: int = 0
    component_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    _start: float = 0.0
    _elapsed: float = 0.0

    def __enter__(self) -> "RunTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._elapsed = time.monotonic() - self._start
        self._log()

    @property
    def elapsed_seconds(self) -> float:
        if self._elapsed > 0:
            return self._elapsed
        return time.monotonic() - self._start

    def set_result_metadata(self, **kwargs: Any) -> None:
        self.metadata.update(kwargs)

    def _log(self) -> None:
        record = {
            "timestamp": time.time(),
            "operation": self.operation,
            "input_text": self.input_text[:200],
            "letter_count": self.letter_count,
            "word_count": self.word_count,
            "component_count": self.component_count,
            "elapsed_seconds": round(self._elapsed, 3),
            "metadata": self.metadata,
        }
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
            with _write_lock:
                with open(LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(line)
        except Exception:
            pass


def estimate_seconds(
    operation: str,
    letter_count: int = 0,
    word_count: int = 0,
    component_count: int = 0,
) -> float:
    """Estimate how long an operation will take based on historical runs.

    Uses a simple linear model: base + per_letter * letters + per_word * words.
    Falls back to hardcoded defaults if no history exists.
    """
    history = _load_history(operation)

    if len(history) < 3:
        base = _DEFAULT_ESTIMATES.get(operation, 5.0)
        return base * max(1, component_count, word_count / 3)

    total_time = sum(h["elapsed_seconds"] for h in history)
    total_letters = sum(h.get("letter_count", 1) or 1 for h in history)
    total_words = sum(h.get("word_count", 1) or 1 for h in history)
    avg_time = total_time / len(history)

    per_letter = total_time / max(total_letters, 1)
    per_word = total_time / max(total_words, 1)

    if letter_count > 0:
        estimate = per_letter * letter_count
    elif word_count > 0:
        estimate = per_word * word_count
    else:
        estimate = avg_time

    return max(0.5, round(estimate, 1))


def get_run_stats() -> dict[str, Any]:
    """Return aggregate statistics about all logged runs."""
    records = _all_records()
    if not records:
        return {"total_runs": 0, "operations": {}}

    ops: dict[str, list[float]] = {}
    for record in records:
        op = record.get("operation", "unknown")
        elapsed = record.get("elapsed_seconds", 0)
        ops.setdefault(op, []).append(elapsed)

    summary: dict[str, Any] = {}
    for op, times in ops.items():
        summary[op] = {
            "count": len(times),
            "avg_seconds": round(sum(times) / len(times), 2),
            "min_seconds": round(min(times), 2),
            "max_seconds": round(max(times), 2),
            "total_seconds": round(sum(times), 2),
        }

    return {"total_runs": len(records), "operations": summary}


def _load_history(operation: str, max_records: int = 50) -> list[dict[str, Any]]:
    matched = [r for r in _all_records() if r.get("operation") == operation]
    return matched[-max_records:]
