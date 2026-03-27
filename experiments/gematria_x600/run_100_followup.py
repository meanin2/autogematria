"""Run 100 focused experiments in the best direction from broad sweep."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import random
from typing import Any

from bench import evaluate_strategy

BASE_DIR = Path(__file__).resolve().parent
SUMMARY_500_PATH = BASE_DIR / "summary_500.json"
RESULTS_100_PATH = BASE_DIR / "results_100_followup.jsonl"
SUMMARY_FINAL_PATH = BASE_DIR / "summary_final.json"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


BOUNDS = {
    "base_score": (0.02, 0.4),
    "freq_scale": (1.8, 7.0),
    "freq_cap": (0.08, 0.6),
    "exact_bonus": (0.05, 0.6),
    "anagram_bonus": (0.0, 0.5),
    "edit_bonus": (0.0, 0.4),
    "source_backed_bonus": (0.0, 0.6),
    "source_pair_bonus": (0.0, 0.8),
}


def _strategy_key(params: dict[str, float]) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((k, round(float(v), 6)) for k, v in params.items()))


def _directional_mutation(
    base: dict[str, float],
    *,
    direction: str,
    rng: random.Random,
) -> dict[str, float]:
    params = dict(base)

    def nudge(name: str, deltas: list[float]) -> None:
        lo, hi = BOUNDS[name]
        params[name] = _clamp(params[name] + rng.choice(deltas), lo, hi)

    if direction == "source_weighted":
        nudge("source_backed_bonus", [-0.08, -0.04, -0.02, 0.02, 0.04, 0.08])
        nudge("source_pair_bonus", [-0.1, -0.05, -0.02, 0.02, 0.05, 0.1])
        nudge("freq_cap", [-0.04, -0.02, 0.0, 0.02, 0.04])
        nudge("freq_scale", [-0.6, -0.3, 0.0, 0.3, 0.6])
        nudge("exact_bonus", [-0.06, -0.03, 0.0, 0.03, 0.06])
    elif direction == "frequency_constrained":
        nudge("freq_scale", [-0.9, -0.5, -0.2, 0.2, 0.5, 0.9])
        nudge("freq_cap", [-0.08, -0.04, -0.02, 0.02, 0.04, 0.08])
        nudge("base_score", [-0.06, -0.03, 0.0, 0.03, 0.06])
        nudge("source_backed_bonus", [-0.05, -0.02, 0.0, 0.02, 0.05])
    elif direction == "lexical_boosted":
        nudge("anagram_bonus", [-0.08, -0.04, -0.02, 0.02, 0.04, 0.08])
        nudge("edit_bonus", [-0.05, -0.02, 0.0, 0.02, 0.05])
        nudge("exact_bonus", [-0.06, -0.03, 0.0, 0.03, 0.06])
        nudge("source_pair_bonus", [-0.06, -0.03, 0.0, 0.03, 0.06])
    else:
        for name in (
            "base_score",
            "freq_scale",
            "freq_cap",
            "exact_bonus",
            "anagram_bonus",
            "edit_bonus",
            "source_backed_bonus",
            "source_pair_bonus",
        ):
            span = 0.05 if name not in {"freq_scale"} else 0.5
            nudge(name, [-span, -span / 2, 0.0, span / 2, span])

    return params


def run(limit: int = 100, reset: bool = False) -> dict[str, Any]:
    if not SUMMARY_500_PATH.exists():
        raise FileNotFoundError("summary_500.json not found; run run_500.py first.")

    if reset and RESULTS_100_PATH.exists():
        RESULTS_100_PATH.unlink()

    summary_500 = json.loads(SUMMARY_500_PATH.read_text(encoding="utf-8"))
    baseline_score = float(summary_500["baseline_score"])
    best_500_score = float(summary_500["best_score"])
    direction = str(summary_500.get("next_direction") or "balanced")
    base_params = {k: float(v) for k, v in dict(summary_500["best_params"]).items()}

    best_score = best_500_score
    best_params = dict(base_params)
    best_details = summary_500.get("best_details", {})

    _append_jsonl(
        RESULTS_100_PATH,
        {
            "experiment": 0,
            "phase": "followup_seed",
            "direction": direction,
            "score": best_500_score,
            "delta_from_baseline": round(best_500_score - baseline_score, 4),
            "kept": True,
            "params": base_params,
            "timestamp": _now_iso(),
            "notes": "seed from best broad strategy",
        },
    )

    rng = random.Random(7717)
    seen = {_strategy_key(base_params)}
    for idx in range(1, limit + 1):
        candidate = _directional_mutation(base_params, direction=direction, rng=rng)
        key = _strategy_key(candidate)
        if key in seen:
            # keep deterministic progress by adding tiny drift on base score
            candidate["base_score"] = _clamp(
                candidate["base_score"] + (0.001 * idx),
                *BOUNDS["base_score"],
            )
            key = _strategy_key(candidate)
        seen.add(key)

        score, details = evaluate_strategy(candidate, include_rows=False)
        kept = score > best_score
        if kept:
            best_score = score
            best_params = dict(candidate)
            best_details = details
            base_params = dict(candidate)  # hill-climb around improvements

        _append_jsonl(
            RESULTS_100_PATH,
            {
                "experiment": idx,
                "phase": "followup_100",
                "direction": direction,
                "score": score,
                "delta_from_baseline": round(score - baseline_score, 4),
                "kept": kept,
                "params": candidate,
                "timestamp": _now_iso(),
                "notes": (
                    f"pos_hit={details['positive_hit_rate']} "
                    f"neg_flag={details['negative_flag_rate']}"
                ),
            },
        )
        if idx % 20 == 0:
            print(f"Progress: {idx}/{limit}")

    summary = {
        "baseline_score": baseline_score,
        "best_500_score": best_500_score,
        "best_final_score": best_score,
        "improvement_vs_baseline": round(best_score - baseline_score, 4),
        "improvement_vs_best_500": round(best_score - best_500_score, 4),
        "next_direction": direction,
        "experiments_run_followup": limit + 1,
        "best_params": best_params,
        "best_details": best_details,
        "generated_at": _now_iso(),
    }
    SUMMARY_FINAL_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 100 focused follow-up experiments.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    summary = run(limit=args.limit, reset=args.reset)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
