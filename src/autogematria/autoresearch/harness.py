"""Frozen benchmark harness for the autoresearch loop.

DO NOT MODIFY this file during experiments. Only search configs change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from autogematria.config import DB_PATH, DATA_DIR
from autogematria.autoresearch.ground_truth import load_ground_truth, get_split
from autogematria.autoresearch.scorer import score, ScoreCard
from autogematria.search.unified import UnifiedSearch, UnifiedSearchConfig


DEFAULT_CONFIG = UnifiedSearchConfig(
    enable_substring=True,
    enable_roshei=True,
    enable_sofei=True,
    enable_els=True,
    els_min_skip=1,
    els_max_skip=100,
    els_use_fast=True,
    max_results_per_method=20,
)


def load_config(path: Path) -> UnifiedSearchConfig:
    """Load a search config from a JSON file."""
    data = json.loads(path.read_text())
    return UnifiedSearchConfig(**data)


def run_benchmark(
    config: UnifiedSearchConfig | None = None,
    split: str = "dev",
    db_path: Path = DB_PATH,
) -> ScoreCard:
    """Run the full benchmark on a split and return a ScoreCard.

    Args:
        config: Search configuration. Defaults to DEFAULT_CONFIG.
        split: "train" or "dev". NEVER "holdout" during development.
        db_path: Path to the SQLite database.
    """
    if split == "holdout":
        print("WARNING: Running on holdout split. This should only be done for final evaluation.")

    config = config or DEFAULT_CONFIG
    entries = load_ground_truth()
    split_entries = get_split(entries, split)

    if not split_entries:
        print(f"No entries for split '{split}'")
        return ScoreCard(0, 0, 0, 0, 0, 0, 0, 0)

    searcher = UnifiedSearch(config, db_path=db_path)

    def search_func(name: str, **kwargs) -> list:
        # Temporarily override book filter if provided
        if "book" in kwargs:
            cfg_copy = UnifiedSearchConfig(
                enable_substring=config.enable_substring,
                enable_roshei=config.enable_roshei,
                enable_sofei=config.enable_sofei,
                enable_els=config.enable_els,
                els_min_skip=config.els_min_skip,
                els_max_skip=config.els_max_skip,
                els_use_fast=config.els_use_fast,
                max_results_per_method=config.max_results_per_method,
                book=kwargs["book"],
            )
            s = UnifiedSearch(cfg_copy, db_path=db_path)
            return s.search(name)
        return searcher.search(name)

    return score(split_entries, search_func)


def main():
    """CLI: python -m autogematria.autoresearch.harness [--config FILE] [--split SPLIT]"""
    config = DEFAULT_CONFIG
    split = "dev"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--config" and i + 1 < len(args):
            config = load_config(Path(args[i + 1]))
            i += 2
        elif args[i] == "--split" and i + 1 < len(args):
            split = args[i + 1]
            i += 2
        else:
            i += 1

    print(f"Running benchmark on '{split}' split...")
    sc = run_benchmark(config, split)

    print(f"\n{'='*50}")
    print(f"  BENCHMARK RESULTS ({split} split)")
    print(f"{'='*50}")
    print(f"  Composite Score:     {sc.composite:.4f}")
    print(f"  Recall:              {sc.recall:.4f} ({sc.found_positives}/{sc.total_positives})")
    print(f"  Mean Reciprocal Rank:{sc.mean_reciprocal_rank:.4f}")
    print(f"  False Positive Rate: {sc.false_positive_rate:.4f} ({sc.found_negatives}/{sc.total_negatives})")
    print(f"{'='*50}")

    if sc.details:
        print(f"\n  Details:")
        for d in sc.details:
            status = "FOUND" if d["found"] else "MISS"
            neg = " [NEG CTRL]" if d["is_negative"] else ""
            rank = f" (rank {d['rank']})" if d.get("rank") else ""
            print(f"    {status}{neg} {d['english']} ({d['name']}){rank}")

    return sc


if __name__ == "__main__":
    main()
