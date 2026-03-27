"""Fixed benchmark for improving `משה גנדי` query behavior.

This benchmark is intentionally narrow: it scores whether the system returns
useful-but-conservative evidence for the target query while avoiding overclaims
on nearby hard-negative multi-word names.
"""

from __future__ import annotations

import json

from autogematria.tools.tool_functions import find_name_in_torah

TARGET_QUERY = "משה גנדי"
TARGET_FIRST = "משה"
TARGET_SURNAME = "גנדי"

# Multi-word hard negatives from the ground-truth file (dev split).
NEGATIVE_QUERIES = [
    "קפאנק צשכאמע",
    "רפדון קליינסקי",
    "יצחק שמאגעגקן",
    "זדקיה ארגלר",
    "לאזו דוכהצח",
    "אליהו יוברמן",
    "טדמת אירקנו",
]

GOOD_VERDICTS = {"weak_evidence", "moderate_evidence"}
NONE_VERDICT = "no_convincing_evidence"


def _target_points(payload: dict) -> tuple[int, dict]:
    final = payload.get("final_verdict") or {}
    support = final.get("token_support") or {}
    first = support.get(TARGET_FIRST) or {}
    surname = support.get(TARGET_SURNAME) or {}
    verdict = str(final.get("verdict") or "")
    confidence = float(final.get("confidence_score") or 0.0)

    surname_skip = int(surname.get("best_skip") or 10_000)
    surname_score = float(surname.get("best_score") or 0.0)
    surname_supported = bool(surname.get("has_any_support"))
    surname_has_quality_signal = (
        surname_supported
        and surname_score >= 0.58
        and surname_skip <= 10
    )

    points = 0
    if verdict in GOOD_VERDICTS:
        points += 25
    if payload.get("total_results", 0) > 0:
        points += 25
    if bool(first.get("has_direct_exact")):
        points += 20
    if surname_has_quality_signal:
        points += 20
    # Reward conservative confidence range for this query type.
    if 0.42 <= confidence <= 0.78:
        points += 10

    details = {
        "verdict": verdict,
        "confidence": confidence,
        "total_results": payload.get("total_results", 0),
        "first_has_direct_exact": bool(first.get("has_direct_exact")),
        "surname_supported": surname_supported,
        "surname_score": surname_score,
        "surname_skip": surname_skip if surname_skip < 10_000 else None,
    }
    return points, details


def _negative_penalty(payload: dict) -> int:
    final = payload.get("final_verdict") or {}
    verdict = str(final.get("verdict") or "")
    return 0 if verdict == NONE_VERDICT else 15


def run_bench() -> tuple[float, dict]:
    target_payload = find_name_in_torah(
        TARGET_QUERY,
        max_results=20,
        diversify_methods=False,
    )
    target_score, target_details = _target_points(target_payload)

    penalties = []
    total_penalty = 0
    for query in NEGATIVE_QUERIES:
        payload = find_name_in_torah(query, max_results=10, diversify_methods=False)
        penalty = _negative_penalty(payload)
        penalties.append(
            {
                "query": query,
                "verdict": (payload.get("final_verdict") or {}).get("verdict"),
                "penalty": penalty,
            }
        )
        total_penalty += penalty

    score = max(0.0, float(target_score - total_penalty))
    details = {
        "target_query": TARGET_QUERY,
        "target_points": target_score,
        "target": target_details,
        "negative_penalty": total_penalty,
        "negative_cases": penalties,
        "score": score,
    }
    return score, details


def main() -> None:
    score, details = run_bench()
    print(json.dumps(details, ensure_ascii=False, indent=2))
    print(f"SCORE: {score:.2f}")


if __name__ == "__main__":
    main()
