"""Quick ablations for benchmark sensitivity checks."""

from __future__ import annotations

import json

from autogematria.autoresearch.harness import DEFAULT_CONFIG, run_benchmark
from autogematria.search.unified import UnifiedSearchConfig


def run_ablations(split: str = "dev") -> list[dict]:
    configs = [
        ("baseline_torah", DEFAULT_CONFIG),
        ("baseline_tanakh", UnifiedSearchConfig(**{**DEFAULT_CONFIG.__dict__, "corpus_scope": "tanakh"})),
        ("no_els", UnifiedSearchConfig(**{**DEFAULT_CONFIG.__dict__, "enable_els": False})),
        ("substring_only", UnifiedSearchConfig(
            enable_substring=True,
            enable_roshei=False,
            enable_sofei=False,
            enable_els=False,
            els_min_skip=DEFAULT_CONFIG.els_min_skip,
            els_max_skip=DEFAULT_CONFIG.els_max_skip,
            els_direction=DEFAULT_CONFIG.els_direction,
            els_use_fast=DEFAULT_CONFIG.els_use_fast,
            max_results_per_method=DEFAULT_CONFIG.max_results_per_method,
            book=DEFAULT_CONFIG.book,
            corpus_scope=DEFAULT_CONFIG.corpus_scope,
        )),
    ]

    rows = []
    for name, cfg in configs:
        score = run_benchmark(cfg, split=split)
        rows.append(
            {
                "name": name,
                "split": split,
                "composite": round(score.composite, 4),
                "recall": round(score.recall, 4),
                "mrr": round(score.mean_reciprocal_rank, 4),
                "fpr": round(score.false_positive_rate, 4),
            }
        )
    return rows


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run simple benchmark ablations.")
    parser.add_argument("--split", default="dev", choices=("train", "dev", "holdout"))
    args = parser.parse_args()

    rows = run_ablations(split=args.split)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
