"""Run 500 broad gematria scoring experiments."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import random
from typing import Any

from bench import evaluate_strategy
from autogematria.gematria_connections import DEFAULT_GEMATRIA_SCORE_PARAMS

BASE_DIR = Path(__file__).resolve().parent
RESULTS_PATH = BASE_DIR / "results_500.jsonl"
SUMMARY_PATH = BASE_DIR / "summary_500.json"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _direction(params: dict[str, float]) -> str:
    if params["source_pair_bonus"] >= 0.32 or params["source_backed_bonus"] >= 0.3:
        return "source_weighted"
    if params["freq_cap"] <= 0.24 or params["freq_scale"] >= 5.2:
        return "frequency_constrained"
    if params["anagram_bonus"] >= 0.2 or params["edit_bonus"] >= 0.1:
        return "lexical_boosted"
    return "balanced"


def _strategy_key(params: dict[str, float]) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((k, round(float(v), 6)) for k, v in params.items()))


def _generate_strategies(count: int = 500, seed: int = 613) -> list[dict[str, float]]:
    rng = random.Random(seed)
    base = dict(DEFAULT_GEMATRIA_SCORE_PARAMS)
    candidates = {
        "base_score": [0.08, 0.14, 0.2, 0.26],
        "freq_scale": [2.6, 3.2, 4.0, 4.8, 5.6],
        "freq_cap": [0.18, 0.24, 0.3, 0.36, 0.42],
        "exact_bonus": [0.18, 0.26, 0.34, 0.42],
        "anagram_bonus": [0.06, 0.12, 0.18, 0.24],
        "edit_bonus": [0.02, 0.06, 0.1, 0.14],
        "source_backed_bonus": [0.1, 0.16, 0.22, 0.28, 0.34],
        "source_pair_bonus": [0.1, 0.18, 0.26, 0.34, 0.42],
    }

    seen = {_strategy_key(base)}
    out: list[dict[str, float]] = []
    while len(out) < count:
        params = {
            name: float(rng.choice(values))
            for name, values in candidates.items()
        }
        key = _strategy_key(params)
        if key in seen:
            continue
        seen.add(key)
        out.append(params)
    return out


def run(limit: int = 500, reset: bool = False) -> dict[str, Any]:
    if reset:
        for path in (RESULTS_PATH, SUMMARY_PATH):
            if path.exists():
                path.unlink()

    baseline_score, baseline_details = evaluate_strategy(
        dict(DEFAULT_GEMATRIA_SCORE_PARAMS),
        include_rows=False,
    )
    best_score = baseline_score
    best_params = dict(DEFAULT_GEMATRIA_SCORE_PARAMS)
    best_details = baseline_details
    top_rows: list[dict[str, Any]] = []
    direction_scores: dict[str, list[float]] = defaultdict(list)
    direction_top_hits: Counter[str] = Counter()

    _append_jsonl(
        RESULTS_PATH,
        {
            "experiment": 0,
            "phase": "baseline",
            "direction": _direction(best_params),
            "score": baseline_score,
            "delta": 0.0,
            "kept": True,
            "params": best_params,
            "timestamp": _now_iso(),
        },
    )

    strategies = _generate_strategies(count=limit, seed=613)
    for idx, params in enumerate(strategies, start=1):
        score, details = evaluate_strategy(params, include_rows=False)
        direction = _direction(params)
        direction_scores[direction].append(score)
        kept = score > best_score
        if kept:
            best_score = score
            best_params = params
            best_details = details
            direction_top_hits[direction] += 1

        row = {
            "experiment": idx,
            "phase": "broad_500",
            "direction": direction,
            "score": score,
            "delta": round(score - baseline_score, 4),
            "kept": kept,
            "params": params,
            "timestamp": _now_iso(),
            "notes": (
                f"pos_hit={details['positive_hit_rate']} "
                f"neg_flag={details['negative_flag_rate']}"
            ),
        }
        _append_jsonl(RESULTS_PATH, row)
        top_rows.append(row)
        if idx % 50 == 0:
            print(f"Progress: {idx}/{limit}")

    top_rows.sort(key=lambda r: (-float(r["score"]), int(r["experiment"])))
    top_50 = top_rows[:50]
    top_50_direction_avg: dict[str, float] = {}
    if top_50:
        by_direction: dict[str, list[float]] = defaultdict(list)
        for row in top_50:
            by_direction[str(row["direction"])].append(float(row["score"]))
        for direction, scores in by_direction.items():
            top_50_direction_avg[direction] = round(sum(scores) / len(scores), 4)

    next_direction = (
        max(top_50_direction_avg.items(), key=lambda kv: kv[1])[0]
        if top_50_direction_avg
        else _direction(best_params)
    )

    summary = {
        "baseline_score": baseline_score,
        "best_score": best_score,
        "improvement": round(best_score - baseline_score, 4),
        "experiments_run": limit + 1,
        "best_params": best_params,
        "best_details": best_details,
        "direction_avg_score": {
            direction: round(sum(scores) / len(scores), 4)
            for direction, scores in sorted(direction_scores.items())
        },
        "top_50_direction_avg": top_50_direction_avg,
        "next_direction": next_direction,
        "kept_count": sum(1 for row in top_rows if row["kept"]) + 1,
        "generated_at": _now_iso(),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run 500 broad gematria experiments.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    summary = run(limit=args.limit, reset=args.reset)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
