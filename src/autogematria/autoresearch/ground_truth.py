"""Ground truth dataset loader with train/dev/holdout splitting."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autogematria.config import DATA_DIR

GROUND_TRUTH_PATH = DATA_DIR / "ground_truth" / "known_findings.jsonl"


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
    notes: str = ""
    is_negative: bool = False            # True for negative controls


def load_ground_truth(path: Path = GROUND_TRUTH_PATH) -> list[GroundTruthEntry]:
    """Load all entries from the JSONL file."""
    entries = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            entry = GroundTruthEntry(
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
                notes=d.get("notes", ""),
                is_negative="negative" in d.get("source", "").lower()
                            or "negative" in d.get("notes", "").lower(),
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
