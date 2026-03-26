"""Ground truth dataset loader with train/dev/holdout splitting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autogematria.config import DATA_DIR

GROUND_TRUTH_PATH = DATA_DIR / "ground_truth" / "known_findings_v2.jsonl"
LEGACY_GROUND_TRUTH_PATH = DATA_DIR / "ground_truth" / "known_findings.jsonl"


@dataclass
class GroundTruthEntry:
    name: str
    english: str
    method: str                          # "els", "substring", "roshei_tevot", "sofei_tevot", "gematria"
    book: str | None
    chapter: int | None
    verse: int | None
    params: dict[str, Any]
    source: str
    difficulty: str                      # "easy", "medium", "hard"
    split: str                           # "train", "dev", "holdout"
    entry_id: str = ""
    track: str = "source_backed_positive"  # source-backed, expected, hard-negative, trivial-negative, holdout
    task: str = "unknown"  # direct_substring, hint_substring, acrostic, els, gematria, full_name
    corpus_scope: str | None = None  # "torah", "tanakh", or None (infer from book)
    notes: str = ""
    is_negative: bool = False            # True for negative controls


def load_ground_truth(path: Path = GROUND_TRUTH_PATH) -> list[GroundTruthEntry]:
    """Load all entries from the JSONL file."""
    if not path.exists():
        path = LEGACY_GROUND_TRUTH_PATH

    entries = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            entry = GroundTruthEntry(
                entry_id=str(d.get("entry_id") or d.get("id") or ""),
                name=d["name"],
                english=d["english"],
                method=d["method"],
                book=d.get("book"),
                chapter=d.get("chapter"),
                verse=d.get("verse"),
                params=d.get("params", {}),
                source=d.get("source", ""),
                difficulty=d.get("difficulty", "medium"),
                split=d.get("split", "train"),
                track=d.get("track", "source_backed_positive"),
                task=d.get("task", d.get("method", "unknown")),
                corpus_scope=d.get("corpus_scope"),
                notes=d.get("notes", ""),
                is_negative=bool(d.get("is_negative", False)),
            )
            entries.append(entry)
    return entries


def get_split(
    entries: list[GroundTruthEntry], split: str
) -> list[GroundTruthEntry]:
    """Filter entries by split name."""
    return [e for e in entries if e.split == split]


def get_positives(entries: list[GroundTruthEntry]) -> list[GroundTruthEntry]:
    """Get only positive (non-control) entries."""
    return [e for e in entries if not e.is_negative]


def get_negatives(entries: list[GroundTruthEntry]) -> list[GroundTruthEntry]:
    """Get only negative control entries."""
    return [e for e in entries if e.is_negative]
