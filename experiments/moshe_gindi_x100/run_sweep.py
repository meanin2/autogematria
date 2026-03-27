"""Run 100+ strategy experiments against the fixed Moshe Gindi benchmark."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from bench import DEFAULT_STRATEGY, evaluate_strategy

BASE_DIR = Path(__file__).resolve().parent
RESULTS_PATH = BASE_DIR / "results.jsonl"
BEST_PATH = BASE_DIR / "best_strategy.json"
SUMMARY_PATH = BASE_DIR / "sweep_summary.json"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _build_experiments() -> list[dict[str, Any]]:
    experiments: list[dict[str, Any]] = []

    # Track A: threshold sweeps (96 experiments)
    for surname_score_min in (0.50, 0.56, 0.62, 0.68):
        for surname_skip_max in (8, 12, 20):
            for confidence_penalty in (0.08, 0.12, 0.16, 0.20):
                for min_verified_rows in (1, 2):
                    experiments.append(
                        {
                            "track": "threshold_sweep",
                            "hypothesis": "tune token-fallback quality thresholds",
                            "overrides": {
                                "surname_score_min": surname_score_min,
                                "surname_skip_max": surname_skip_max,
                                "confidence_penalty": confidence_penalty,
                                "min_verified_rows": min_verified_rows,
                                "latin_policy": "best_verified",
                                "scope_policy": "torah_to_tanakh",
                                "require_same_book": False,
                                "require_same_chapter": False,
                                "require_same_verse": False,
                                "require_joined_els_gate": False,
                            },
                        }
                    )

    # Track B: Bible-code proximity gates (48 experiments)
    proximity_modes = (
        ("book", {"require_same_book": True, "require_same_chapter": False, "require_same_verse": False}),
        ("chapter", {"require_same_book": True, "require_same_chapter": True, "require_same_verse": False}),
        ("verse", {"require_same_book": True, "require_same_chapter": True, "require_same_verse": True}),
    )
    for mode_name, mode_flags in proximity_modes:
        for confidence_penalty in (0.10, 0.14):
            for surname_score_min in (0.56, 0.62):
                for surname_skip_max in (10, 20):
                    for min_verified_rows in (1, 2):
                        overrides = {
                            "surname_score_min": surname_score_min,
                            "surname_skip_max": surname_skip_max,
                            "confidence_penalty": confidence_penalty,
                            "min_verified_rows": min_verified_rows,
                            "latin_policy": "best_verified",
                            "scope_policy": "torah_to_tanakh",
                            "require_joined_els_gate": False,
                        }
                        overrides.update(mode_flags)
                        experiments.append(
                            {
                                "track": "bible_proximity",
                                "hypothesis": f"Bible-code proximity gate ({mode_name})",
                                "overrides": overrides,
                            }
                        )

    # Track C: transliteration + scope + joined-ELS directions (36 experiments)
    for latin_policy in ("curated_first", "best_verified", "weighted"):
        for scope_policy in ("none", "torah_to_tanakh", "best_of_both"):
            for require_joined in (False, True):
                for surname_score_min in (0.56, 0.62):
                    experiments.append(
                        {
                            "track": "resolver_scope_joined",
                            "hypothesis": "resolver policy + Torah/Tanakh escalation + joined-name ELS",
                            "overrides": {
                                "latin_policy": latin_policy,
                                "scope_policy": scope_policy,
                                "require_joined_els_gate": require_joined,
                                "joined_els_skip_cap": 40,
                                "surname_score_min": surname_score_min,
                                "surname_skip_max": 12,
                                "confidence_penalty": 0.12,
                                "min_verified_rows": 1,
                                "require_same_book": False,
                                "require_same_chapter": False,
                                "require_same_verse": False,
                            },
                        }
                    )

    return experiments


def run_sweep(limit: int | None = None, reset: bool = False) -> dict[str, Any]:
    if reset:
        for path in (RESULTS_PATH, BEST_PATH, SUMMARY_PATH):
            if path.exists():
                path.unlink()

    experiments = _build_experiments()
    if limit is not None:
        experiments = experiments[:limit]

    baseline_score, baseline_details = evaluate_strategy(DEFAULT_STRATEGY, include_rows=False)
    best_score = baseline_score
    best_strategy = dict(DEFAULT_STRATEGY)
    best_details = baseline_details

    _append_jsonl(
        RESULTS_PATH,
        {
            "experiment": 0,
            "track": "baseline",
            "hypothesis": "default strategy",
            "score": baseline_score,
            "delta_from_baseline": 0.0,
            "kept": True,
            "timestamp": _now_iso(),
            "overrides": {},
            "notes": "baseline measurement",
        },
    )

    total = len(experiments)
    for idx, exp in enumerate(experiments, start=1):
        strategy = dict(DEFAULT_STRATEGY)
        strategy.update(exp["overrides"])
        score, details = evaluate_strategy(strategy, include_rows=False)
        kept = score > best_score
        if kept:
            best_score = score
            best_strategy = strategy
            best_details = details

        _append_jsonl(
            RESULTS_PATH,
            {
                "experiment": idx,
                "track": exp["track"],
                "hypothesis": exp["hypothesis"],
                "score": score,
                "delta_from_baseline": round(score - baseline_score, 4),
                "kept": kept,
                "timestamp": _now_iso(),
                "overrides": exp["overrides"],
                "notes": f"positives_good={details['positives_good']} negatives_flagged={details['negatives_flagged']}",
            },
        )

        if idx % 20 == 0 or idx == total:
            print(f"Progress: {idx}/{total} experiments")

    summary = {
        "baseline_score": baseline_score,
        "best_score": best_score,
        "improvement": round(best_score - baseline_score, 4),
        "experiments_run": total + 1,
        "best_strategy": best_strategy,
        "best_details": best_details,
        "generated_at": _now_iso(),
    }
    BEST_PATH.write_text(json.dumps({"best_strategy": best_strategy}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run high-volume Moshe Gindi strategy sweep.")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on number of experiments")
    parser.add_argument("--reset", action="store_true", help="Delete previous sweep artifacts before running")
    args = parser.parse_args()

    summary = run_sweep(limit=args.limit, reset=args.reset)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
