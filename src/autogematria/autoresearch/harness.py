"""Frozen benchmark harness for the autoresearch loop.

DO NOT MODIFY this file during experiments. Only search configs change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from autogematria.config import DB_PATH
from autogematria.autoresearch.ground_truth import load_ground_truth, get_split
from autogematria.autoresearch.scorer import score, ScoreCard
from autogematria.search.unified import UnifiedSearch, UnifiedSearchConfig
from autogematria.tools.tool_functions import gematria_lookup


DEFAULT_CONFIG = UnifiedSearchConfig(
    enable_substring=True,
    enable_roshei=True,
    enable_sofei=True,
    enable_els=True,
    els_min_skip=1,
    els_max_skip=100,
    els_direction="both",
    els_use_fast=True,
    max_results_per_method=20,
    corpus_scope="torah",
)


def load_config(path: Path) -> UnifiedSearchConfig:
    """Load a search config from a JSON file."""
    data = json.loads(path.read_text())
    return UnifiedSearchConfig(**data)


def run_benchmark(
    config: UnifiedSearchConfig | None = None,
    split: str = "dev",
    db_path: Path = DB_PATH,
    top_k: int = 20,
) -> ScoreCard:
    """Run the full benchmark on a split and return a ScoreCard.

    Args:
        config: Search configuration. Defaults to DEFAULT_CONFIG.
        split: "train" or "dev". NEVER "holdout" during development.
        db_path: Path to the SQLite database.
        top_k: Number of results considered by scorer per entry/method.
    """
    if split == "holdout":
        print("WARNING: Running on holdout split. This should only be done for final evaluation.")

    config = config or DEFAULT_CONFIG
    entries = load_ground_truth()
    split_entries = get_split(entries, split)

    if not split_entries:
        print(f"No entries for split '{split}'")
        return ScoreCard(0, 0, 0, 0, 0, 0, 0, 0)

    def search_func(name: str, **kwargs) -> list:
        cfg_copy = UnifiedSearchConfig(
            enable_substring=config.enable_substring,
            enable_roshei=config.enable_roshei,
            enable_sofei=config.enable_sofei,
            enable_els=config.enable_els,
            els_min_skip=kwargs.get("els_min_skip", config.els_min_skip),
            els_max_skip=kwargs.get("els_max_skip", config.els_max_skip),
            els_direction=kwargs.get("els_direction", config.els_direction),
            els_use_fast=config.els_use_fast,
            max_results_per_method=kwargs.get("max_results_per_method", config.max_results_per_method),
            book=kwargs.get("book", config.book),
            corpus_scope=kwargs.get("corpus_scope", config.corpus_scope),
        )

        only_method = kwargs.get("only_method")
        if only_method:
            cfg_copy.enable_substring = only_method == "substring"
            cfg_copy.enable_roshei = only_method == "roshei_tevot"
            cfg_copy.enable_sofei = only_method == "sofei_tevot"
            cfg_copy.enable_els = only_method == "els"

        s = UnifiedSearch(cfg_copy, db_path=db_path)
        cross_word = kwargs.get("cross_word", True)
        if cfg_copy.enable_substring and not (cfg_copy.enable_roshei or cfg_copy.enable_sofei or cfg_copy.enable_els):
            # Preserve the scoring-time within-word/cross-word control.
            return s.search(name, substring_cross_word=cross_word)
        return s.search(name)

    return score(split_entries, search_func, gematria_func=gematria_lookup, top_k=top_k)


def main():
    """CLI: python -m autogematria.autoresearch.harness [--config FILE] [--split SPLIT] [--top-k N]"""
    config = DEFAULT_CONFIG
    split = "dev"
    top_k = 20

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--config" and i + 1 < len(args):
            config = load_config(Path(args[i + 1]))
            i += 2
        elif args[i] == "--split" and i + 1 < len(args):
            split = args[i + 1]
            i += 2
        elif args[i] == "--top-k" and i + 1 < len(args):
            top_k = int(args[i + 1])
            i += 2
        else:
            i += 1

    print(f"Running benchmark on '{split}' split...")
    sc = run_benchmark(config, split, top_k=top_k)

    print(f"\n{'='*50}")
    print(f"  BENCHMARK RESULTS ({split} split)")
    print(f"{'='*50}")
    print(f"  Composite Score:     {sc.composite:.4f}")
    print(f"  Recall:              {sc.recall:.4f} ({sc.found_positives}/{sc.total_positives})")
    print(f"  Mean Reciprocal Rank:{sc.mean_reciprocal_rank:.4f}")
    print(f"  False Positive Rate: {sc.false_positive_rate:.4f} ({sc.found_negatives}/{sc.total_negatives})")
    print(f"{'='*50}")

    if sc.details:
        print("\n  Details:")
        for d in sc.details:
            status = "FOUND" if d["found"] else "MISS"
            neg = " [NEG CTRL]" if d["is_negative"] else ""
            rank = f" (rank {d['rank']})" if d.get("rank") else ""
            print(f"    {status}{neg} {d['english']} ({d['name']}){rank}")
    if sc.task_metrics:
        print("\n  By task:")
        for task, metrics in sorted(sc.task_metrics.items()):
            print(
                f"    {task}: recall={metrics['recall']:.4f} "
                f"mrr={metrics['mrr']:.4f} fpr={metrics['fpr']:.4f} "
                f"composite={metrics['composite']:.4f}"
            )

    return sc


if __name__ == "__main__":
    main()
