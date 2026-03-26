"""Migrate legacy ground truth to v2 tracks/tasks with explicit negatives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autogematria.autoresearch.hard_negatives import generate_hard_negative_entries
from autogematria.config import DATA_DIR, TORAH_BOOKS


LEGACY_PATH = DATA_DIR / "ground_truth" / "known_findings.jsonl"
V2_PATH = DATA_DIR / "ground_truth" / "known_findings_v2.jsonl"


def _legacy_is_negative(row: dict) -> bool:
    source = str(row.get("source", "")).lower()
    notes = str(row.get("notes", "")).lower()
    english = str(row.get("english", "")).lower()
    return any("negative" in text for text in (source, notes, english))


def _track_for_row(row: dict, is_negative: bool) -> str:
    split = str(row.get("split", "train")).lower()
    source = str(row.get("source", "")).lower()
    if split == "holdout":
        return "holdout"
    if is_negative:
        name = str(row.get("name", ""))
        return "hard_negative" if len(name.replace(" ", "")) >= 8 else "trivial_negative"
    if "expected" in source:
        return "expected_but_unverified"
    return "source_backed_positive"


def _task_for_row(row: dict) -> str:
    method = str(row.get("method", "")).lower()
    params = row.get("params", {}) or {}
    source = str(row.get("source", "")).lower()
    notes = str(row.get("notes", "")).lower()
    english = str(row.get("english", "")).lower()
    name = str(row.get("name", ""))

    if method == "substring":
        if "hint" in source or "hint" in notes or "hint" in english:
            return "hint_substring"
        if params.get("mode") == "phrase" or " " in name:
            return "multi_word_full_name"
        return "direct_substring"
    if method in {"roshei_tevot", "sofei_tevot"}:
        return "acrostic"
    if method == "els":
        return "els"
    if method == "gematria":
        return "gematria"
    return "unknown"


def _corpus_scope_for_row(row: dict) -> str:
    book = row.get("book")
    if not book:
        return "torah"
    return "torah" if str(book) in TORAH_BOOKS else "tanakh"


def migrate_dataset(
    *,
    source_path: Path = LEGACY_PATH,
    dest_path: Path = V2_PATH,
    hard_negative_count: int = 36,
    hard_negative_seed: int = 613,
) -> dict[str, int]:
    legacy_rows = [
        json.loads(line)
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    converted: list[dict] = []
    for idx, row in enumerate(legacy_rows):
        is_negative = _legacy_is_negative(row)
        converted.append(
            {
                "entry_id": f"gt_{idx:04d}",
                "name": row["name"],
                "english": row["english"],
                "method": row["method"],
                "book": row.get("book"),
                "chapter": row.get("chapter"),
                "verse": row.get("verse"),
                "params": row.get("params", {}),
                "source": row.get("source", ""),
                "difficulty": row.get("difficulty", "medium"),
                "split": row.get("split", "train"),
                "track": _track_for_row(row, is_negative),
                "task": _task_for_row(row),
                "corpus_scope": _corpus_scope_for_row(row),
                "notes": row.get("notes", ""),
                "is_negative": is_negative,
            }
        )

    existing_names = {str(row.get("name")) for row in converted}
    hard_rows = generate_hard_negative_entries(
        existing_names=existing_names,
        count=hard_negative_count,
        seed=hard_negative_seed,
    )
    for idx, row in enumerate(hard_rows):
        row["entry_id"] = f"hardneg_{idx:04d}"
    converted.extend(hard_rows)

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in converted),
        encoding="utf-8",
    )

    by_track: dict[str, int] = {}
    by_task: dict[str, int] = {}
    for row in converted:
        track = str(row.get("track", "unknown"))
        task = str(row.get("task", "unknown"))
        by_track[track] = by_track.get(track, 0) + 1
        by_task[task] = by_task.get(task, 0) + 1

    summary = {
        "total": len(converted),
        "source_rows": len(legacy_rows),
        "hard_negatives_added": len(hard_rows),
    }
    for k, v in by_track.items():
        summary[f"track:{k}"] = v
    for k, v in by_task.items():
        summary[f"task:{k}"] = v
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build v2 benchmark dataset with explicit tracks/tasks.")
    parser.add_argument("--source", type=Path, default=LEGACY_PATH)
    parser.add_argument("--dest", type=Path, default=V2_PATH)
    parser.add_argument("--hard-negatives", type=int, default=36)
    parser.add_argument("--seed", type=int, default=613)
    args = parser.parse_args()

    summary = migrate_dataset(
        source_path=args.source,
        dest_path=args.dest,
        hard_negative_count=args.hard_negatives,
        hard_negative_seed=args.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
