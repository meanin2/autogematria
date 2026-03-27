"""Fixed benchmark for gematria pair-quality optimization."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from autogematria.gematria_connections import (
    DEFAULT_GEMATRIA_SCORE_PARAMS,
    gematria_connections,
)


POSITIVE_CASES = [
    {"query": "משה", "target": "השם", "label": "moshe_hashem"},
    {"query": "משה", "target": "שמה", "label": "moshe_shmah"},
    {"query": "השם", "target": "משה", "label": "hashem_moshe"},
    {"query": "נחש", "target": "משיח", "label": "nachash_mashiach"},
    {"query": "משיח", "target": "נחש", "label": "mashiach_nachash"},
    {"query": "יין", "target": "סוד", "label": "yayin_sod"},
    {"query": "סוד", "target": "יין", "label": "sod_yayin"},
    {"query": "נח", "target": "חן", "label": "noach_chen"},
    {"query": "אהבה", "target": "אחד", "label": "ahava_echad"},
    {"query": "עמלק", "target": "ספק", "label": "amalek_safek"},
    {"query": "ילד", "target": "דם", "label": "yeled_dam"},
    {"query": "אברהם", "target": "רמח", "label": "avraham_rmach"},
    {"query": "אלהים", "target": "אלהים", "label": "elohim_self"},
    {"query": "יהוה", "target": "יהוה", "label": "yhvh_self"},
]

NEGATIVE_CASES = [
    {"query": "משה", "target": "נחש", "label": "neg_moshe_nachash"},
    {"query": "אהבה", "target": "ספק", "label": "neg_ahava_safek"},
    {"query": "עמלק", "target": "אחד", "label": "neg_amalek_echad"},
    {"query": "יין", "target": "משיח", "label": "neg_yayin_mashiach"},
    {"query": "נח", "target": "רמח", "label": "neg_noach_rmach"},
    {"query": "ילד", "target": "אחד", "label": "neg_yeled_echad"},
    {"query": "אברהם", "target": "דם", "label": "neg_avraham_dam"},
    {"query": "נחש", "target": "סוד", "label": "neg_nachash_sod"},
    {"query": "השם", "target": "עמלק", "label": "neg_hashem_amalek"},
    {"query": "סוד", "target": "רמח", "label": "neg_sod_rmach"},
]


def _normalize_params(score_params: dict[str, float] | None) -> dict[str, float]:
    merged = dict(DEFAULT_GEMATRIA_SCORE_PARAMS)
    if score_params:
        for key, value in score_params.items():
            if key in merged:
                merged[key] = float(value)
    return merged


def _find_target_row(query: str, target: str, params: dict[str, float]) -> tuple[int | None, dict[str, Any] | None]:
    payload = gematria_connections(
        query,
        method="MISPAR_HECHRACHI",
        max_equivalents=200,
        max_related=80,
        score_params=params,
    )
    for rank, row in enumerate(payload.get("related_words", []), start=1):
        if row.get("word") == target:
            return rank, row
    return None, None


def _positive_points(rank: int | None, row: dict[str, Any] | None) -> int:
    if rank is None or row is None:
        return 0
    points = 0
    if rank <= 3:
        points += 14
    elif rank <= 10:
        points += 10
    elif rank <= 20:
        points += 6
    elif rank <= 40:
        points += 3

    relations = set(row.get("relations") or [])
    if "source_backed" in relations:
        points += 3
    if "source_pair" in relations:
        points += 4

    score = float(row.get("score") or 0.0)
    if score >= 0.85:
        points += 2
    elif score >= 0.65:
        points += 1
    return points


def _negative_penalty(rank: int | None, row: dict[str, Any] | None) -> int:
    if rank is None:
        return 0
    penalty = 0
    if rank <= 3:
        penalty += 14
    elif rank <= 10:
        penalty += 10
    elif rank <= 20:
        penalty += 6
    elif rank <= 40:
        penalty += 3

    if row is not None:
        relations = set(row.get("relations") or [])
        if "source_backed" in relations:
            penalty += 4
        if "source_pair" in relations:
            penalty += 5
    return penalty


def evaluate_strategy(
    score_params: dict[str, float] | None = None,
    *,
    include_rows: bool = True,
) -> tuple[float, dict[str, Any]]:
    params = _normalize_params(score_params)
    positives_rows: list[dict[str, Any]] = []
    negatives_rows: list[dict[str, Any]] = []

    positive_points = 0
    for case in POSITIVE_CASES:
        rank, row = _find_target_row(case["query"], case["target"], params)
        points = _positive_points(rank, row)
        positive_points += points
        positives_rows.append(
            {
                **case,
                "rank": rank,
                "points": points,
                "relations": [] if row is None else row.get("relations", []),
                "score": None if row is None else row.get("score"),
            }
        )

    negative_penalty = 0
    for case in NEGATIVE_CASES:
        rank, row = _find_target_row(case["query"], case["target"], params)
        penalty = _negative_penalty(rank, row)
        negative_penalty += penalty
        negatives_rows.append(
            {
                **case,
                "rank": rank,
                "penalty": penalty,
                "relations": [] if row is None else row.get("relations", []),
                "score": None if row is None else row.get("score"),
            }
        )

    score = max(0.0, float(positive_points - negative_penalty))
    details: dict[str, Any] = {
        "score": score,
        "positive_points": positive_points,
        "negative_penalty": negative_penalty,
        "positive_cases": len(POSITIVE_CASES),
        "negative_cases": len(NEGATIVE_CASES),
        "positive_hit_rate": round(sum(1 for row in positives_rows if row["rank"] is not None) / len(POSITIVE_CASES), 4),
        "negative_flag_rate": round(sum(1 for row in negatives_rows if row["rank"] is not None) / len(NEGATIVE_CASES), 4),
        "score_params": deepcopy(params),
    }
    if include_rows:
        details["positives"] = positives_rows
        details["negatives"] = negatives_rows
    return score, details


def main() -> None:
    score, details = evaluate_strategy(include_rows=True)
    print(json.dumps(details, ensure_ascii=False, indent=2))
    print(f"SCORE: {score:.2f}")


if __name__ == "__main__":
    main()
