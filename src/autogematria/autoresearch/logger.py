"""Experiment logging for the autoresearch loop."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from autogematria.autoresearch.scorer import ScoreCard


RESULTS_DIR = Path(__file__).resolve().parents[3] / "experiments" / "results"


def log_experiment(
    experiment_name: str,
    config: dict,
    score_card: ScoreCard,
    split: str,
    git_sha: str | None = None,
    notes: str = "",
    log_dir: Path = RESULTS_DIR,
) -> Path:
    """Append an experiment result to the JSONL log."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "experiments.jsonl"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment_name": experiment_name,
        "split": split,
        "config": config,
        "composite_score": score_card.composite,
        "recall": score_card.recall,
        "mrr": score_card.mean_reciprocal_rank,
        "fpr": score_card.false_positive_rate,
        "found_positives": score_card.found_positives,
        "total_positives": score_card.total_positives,
        "found_negatives": score_card.found_negatives,
        "total_negatives": score_card.total_negatives,
        "git_sha": git_sha,
        "notes": notes,
    }

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return log_path


def read_log(log_dir: Path = RESULTS_DIR) -> list[dict]:
    """Read all experiment log entries."""
    log_path = log_dir / "experiments.jsonl"
    if not log_path.exists():
        return []
    entries = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def best_so_far(log_dir: Path = RESULTS_DIR) -> dict | None:
    """Return the experiment entry with the highest composite score."""
    entries = read_log(log_dir)
    if not entries:
        return None
    return max(entries, key=lambda e: e["composite_score"])
