"""Fixed benchmark for large-scale Moshe Gindi strategy sweeps.

This benchmark is deterministic and intentionally focused on usability + safety:
- positives: Hebrew and Latin query forms for Moshe Gindi,
- negatives: hard-negative multi-word names that should abstain.
"""

from __future__ import annotations

from functools import lru_cache
import json
from typing import Any

from autogematria.search.els import ELSSearch
from autogematria.tools.name_variants import generate_hebrew_variants
from autogematria.tools.tool_functions import find_name_in_torah

POSITIVE_HEBREW_CASES = [
    {"id": "he_torah_gandi", "query": "משה גנדי", "scope": "torah"},
    {"id": "he_tanakh_gandi", "query": "משה גנדי", "scope": "tanakh"},
    {"id": "he_tanakh_gindi", "query": "משה גינדי", "scope": "tanakh"},
]

POSITIVE_LATIN_CASES = [
    {"id": "latin_gindi", "query": "moshe gindi", "scope": "torah"},
    {"id": "latin_gandi", "query": "moshe gandi", "scope": "torah"},
    {"id": "latin_gandy", "query": "moshe gandy", "scope": "torah"},
]

NEGATIVE_HEBREW_QUERIES = [
    "קפאנק צשכאמע",
    "רפדון קליינסקי",
    "יצחק שמאגעגקן",
    "זדקיה ארגלר",
    "לאזו דוכהצח",
    "אליהו יוברמן",
    "טדמת אירקנו",
]

NEGATIVE_LATIN_QUERIES = [
    "yitzchak shamagegken",
    "raphdon kleinski",
    "lahzo dukhatzach",
]

GOOD_VERDICTS = {"weak_evidence", "moderate_evidence", "strong_evidence"}
NONE_VERDICT = "no_convincing_evidence"

DEFAULT_STRATEGY: dict[str, Any] = {
    "surname_score_min": 0.58,
    "surname_skip_max": 12,
    "confidence_penalty": 0.12,
    "weak_min": 0.42,
    "moderate_min": 0.58,
    "confidence_band_low": 0.45,
    "confidence_band_high": 0.80,
    "require_first_direct_exact": True,
    "require_all_tokens_supported": True,
    "min_verified_rows": 1,
    "require_same_book": False,
    "require_same_chapter": False,
    "require_same_verse": False,
    "require_joined_els_gate": False,
    "joined_els_skip_cap": 40,
    "latin_policy": "best_verified",  # curated_first | best_verified | weighted
    "scope_policy": "torah_to_tanakh",  # none | torah_to_tanakh | best_of_both
    "max_variants": 8,
    "weighted_good_bonus": 4.0,
    "weighted_verified_bonus": 1.2,
    "weighted_total_bonus": 0.3,
    "weighted_index_penalty": 0.25,
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_good(verdict: str) -> bool:
    return verdict in GOOD_VERDICTS


@lru_cache(maxsize=512)
def _payload(query: str, scope: str) -> dict[str, Any]:
    return find_name_in_torah(
        query,
        max_results=20,
        diversify_methods=False,
        corpus_scope=scope,
    )


@lru_cache(maxsize=64)
def _joined_min_skip(joined_query: str, scope: str) -> int | None:
    els = ELSSearch()
    rows = els.search_fast(
        joined_query,
        min_skip=1,
        max_skip=120,
        max_results=50,
        direction="both",
        corpus_scope=scope,
    )
    if not rows:
        return None
    return min(abs(int(r.params.get("skip") or 10_000)) for r in rows)


def _best_verified_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    verified = [row for row in rows if bool((row.get("verification") or {}).get("verified"))]
    pool = verified or rows
    if not pool:
        return None
    return max(pool, key=lambda row: _as_float((row.get("confidence") or {}).get("score")))


def _support_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    best = _best_verified_row(rows)
    if not best:
        return {
            "best_score": 0.0,
            "best_method": None,
            "best_skip": None,
            "has_any_support": False,
            "has_direct_exact": False,
        }

    score = _as_float((best.get("confidence") or {}).get("score"))
    method = best.get("method")
    skip = (best.get("params") or {}).get("skip")
    has_any = any(
        _as_float((row.get("confidence") or {}).get("score")) >= 0.35
        and bool((row.get("verification") or {}).get("verified"))
        for row in rows
    )
    has_direct = any(
        row.get("method") == "SUBSTRING"
        and (((row.get("confidence") or {}).get("features") or {}).get("match_type") == "exact_word")
        and bool((row.get("verification") or {}).get("verified"))
        for row in rows
    )
    return {
        "best_score": score,
        "best_method": method,
        "best_skip": abs(int(skip)) if skip is not None else None,
        "has_any_support": has_any,
        "has_direct_exact": has_direct,
    }


def _location_tuple(row: dict[str, Any] | None) -> tuple[str | None, int | None, int | None]:
    if not row:
        return None, None, None
    loc = row.get("location") or {}
    return loc.get("book"), loc.get("chapter"), loc.get("verse")


def _normalize_strategy(strategy: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_STRATEGY)
    if strategy:
        merged.update(strategy)
    if merged["require_same_verse"]:
        merged["require_same_chapter"] = True
        merged["require_same_book"] = True
    if merged["require_same_chapter"]:
        merged["require_same_book"] = True
    return merged


def _evaluate_hebrew_case(query: str, scope: str, strategy: dict[str, Any]) -> dict[str, Any]:
    payload = _payload(query, scope)
    tokens = [t for t in query.split() if t]
    ranked = payload.get("ranked_results") or []
    verified_rows = sum(1 for row in ranked if bool((row.get("verification") or {}).get("verified")))

    if len(tokens) < 2:
        final = payload.get("final_verdict") or {}
        verdict = str(final.get("verdict") or NONE_VERDICT)
        confidence = _as_float(final.get("confidence_score"))
        return {
            "query": query,
            "scope": scope,
            "verdict": verdict,
            "confidence": confidence,
            "total_results": int(payload.get("total_results") or 0),
            "verified_rows": verified_rows,
            "surname_quality_signal": False,
            "first_ref": None,
            "surname_ref": None,
            "same_book": False,
            "same_chapter": False,
            "same_verse": False,
            "joined_els_min_skip": None,
        }

    first = tokens[0]
    surname = tokens[-1]
    word_results = payload.get("word_results") or {}
    first_rows = (word_results.get(first) or {}).get("results") or []
    surname_rows = (word_results.get(surname) or {}).get("results") or []
    token_support = ((payload.get("final_verdict") or {}).get("token_support")) or {}

    first_support = token_support.get(first) or _support_from_rows(first_rows)
    surname_support = token_support.get(surname) or _support_from_rows(surname_rows)
    all_tokens_supported = all(
        bool((token_support.get(token) or _support_from_rows((word_results.get(token) or {}).get("results") or [])).get("has_any_support"))
        for token in tokens
    )

    first_row = _best_verified_row(first_rows)
    surname_row = _best_verified_row(surname_rows)
    first_loc = _location_tuple(first_row)
    surname_loc = _location_tuple(surname_row)

    same_book = bool(first_loc[0] and first_loc[0] == surname_loc[0])
    same_chapter = same_book and first_loc[1] == surname_loc[1]
    same_verse = same_chapter and first_loc[2] == surname_loc[2]

    first_score = _as_float(first_support.get("best_score"))
    surname_score = _as_float(surname_support.get("best_score"))
    surname_skip = int(surname_support.get("best_skip") or 10_000)
    surname_method = str(surname_support.get("best_method") or "")
    surname_quality_signal = bool(surname_support.get("has_direct_exact")) or (
        surname_method == "ELS"
        and bool(surname_support.get("has_any_support"))
        and surname_score >= _as_float(strategy["surname_score_min"])
        and surname_skip <= int(strategy["surname_skip_max"])
    )

    passes = True
    if strategy["require_first_direct_exact"] and not bool(first_support.get("has_direct_exact")):
        passes = False
    if strategy["require_all_tokens_supported"] and not all_tokens_supported:
        passes = False
    if strategy["min_verified_rows"] > int(verified_rows):
        passes = False
    if not surname_quality_signal:
        passes = False
    if strategy["require_same_book"] and not same_book:
        passes = False
    if strategy["require_same_chapter"] and not same_chapter:
        passes = False
    if strategy["require_same_verse"] and not same_verse:
        passes = False

    joined_min_skip = None
    if strategy["require_joined_els_gate"]:
        joined_query = "".join(tokens)
        joined_min_skip = _joined_min_skip(joined_query, scope)
        if joined_min_skip is None or joined_min_skip > int(strategy["joined_els_skip_cap"]):
            passes = False

    supported_ratio = sum(1 for token in tokens if bool((token_support.get(token) or {}).get("has_any_support")) or bool(_support_from_rows((word_results.get(token) or {}).get("results") or []).get("has_any_support"))) / len(tokens)
    confidence = 0.68 * max(first_score, surname_score) + 0.32 * supported_ratio
    if same_book:
        confidence += 0.03
    if same_chapter:
        confidence += 0.03
    if same_verse:
        confidence += 0.04
    if strategy["require_joined_els_gate"] and joined_min_skip is not None:
        confidence += 0.04
    confidence -= _as_float(strategy["confidence_penalty"])
    confidence = _clamp(confidence)

    if not passes:
        verdict = NONE_VERDICT
        confidence = 0.0
        total_results = 0
    elif confidence >= _as_float(strategy["moderate_min"]):
        verdict = "moderate_evidence"
        total_results = max(2, int(payload.get("total_results") or 0))
    elif confidence >= _as_float(strategy["weak_min"]):
        verdict = "weak_evidence"
        total_results = max(1, int(payload.get("total_results") or 0))
    else:
        verdict = NONE_VERDICT
        confidence = 0.0
        total_results = 0

    return {
        "query": query,
        "scope": scope,
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "total_results": total_results,
        "verified_rows": verified_rows,
        "surname_quality_signal": surname_quality_signal,
        "surname_score": round(surname_score, 4),
        "surname_skip": None if surname_skip >= 10_000 else surname_skip,
        "first_ref": None if not first_row else f"{first_loc[0]} {first_loc[1]}:{first_loc[2]}",
        "surname_ref": None if not surname_row else f"{surname_loc[0]} {surname_loc[1]}:{surname_loc[2]}",
        "same_book": same_book,
        "same_chapter": same_chapter,
        "same_verse": same_verse,
        "joined_els_min_skip": joined_min_skip,
    }


def _apply_scope_policy(
    query: str,
    initial_scope: str,
    strategy: dict[str, Any],
    base: dict[str, Any],
) -> dict[str, Any]:
    policy = strategy["scope_policy"]
    if initial_scope != "torah" or policy == "none":
        return base

    tanakh = _evaluate_hebrew_case(query, "tanakh", strategy)
    if policy == "torah_to_tanakh":
        if base["verdict"] == NONE_VERDICT and _is_good(tanakh["verdict"]):
            return tanakh
        return base

    if policy == "best_of_both":
        base_key = (_is_good(base["verdict"]), base["confidence"], base["total_results"], base["verified_rows"])
        tanakh_key = (_is_good(tanakh["verdict"]), tanakh["confidence"], tanakh["total_results"], tanakh["verified_rows"])
        return tanakh if tanakh_key > base_key else base

    return base


def _weighted_variant_score(row: dict[str, Any], idx: int, strategy: dict[str, Any]) -> float:
    score = 0.0
    if _is_good(row["verdict"]):
        score += _as_float(strategy["weighted_good_bonus"])
    score += _as_float(strategy["weighted_verified_bonus"]) * int(row["verified_rows"])
    score += _as_float(strategy["weighted_total_bonus"]) * int(row["total_results"])
    score += _as_float(row["confidence"]) * 1.5
    score -= _as_float(strategy["weighted_index_penalty"]) * idx
    return score


def _evaluate_latin_case(query: str, scope: str, strategy: dict[str, Any]) -> dict[str, Any]:
    variants = generate_hebrew_variants(query, max_variants=int(strategy["max_variants"]))
    if not variants:
        variants = [query]

    rows: list[dict[str, Any]] = []
    for idx, variant in enumerate(variants):
        base = _evaluate_hebrew_case(variant, scope, strategy)
        final = _apply_scope_policy(variant, scope, strategy, base)
        row = dict(final)
        row["variant"] = variant
        row["index"] = idx
        rows.append(row)

    policy = strategy["latin_policy"]
    chosen = rows[0]
    if policy == "best_verified":
        chosen = max(
            rows,
            key=lambda row: (
                _is_good(row["verdict"]),
                int(row["verified_rows"]),
                _as_float(row["confidence"]),
                int(row["total_results"]),
                -int(row["index"]),
            ),
        )
    elif policy == "weighted":
        chosen = max(rows, key=lambda row: _weighted_variant_score(row, int(row["index"]), strategy))

    output = dict(chosen)
    output["query_input"] = query
    output["resolved_query"] = chosen["variant"]
    output["variants_considered"] = len(rows)
    return output


def _positive_points(case_result: dict[str, Any], strategy: dict[str, Any], *, is_latin: bool) -> int:
    points = 0
    verdict = str(case_result["verdict"])
    confidence = _as_float(case_result["confidence"])
    total_results = int(case_result["total_results"])
    if _is_good(verdict):
        points += 15
    if total_results >= 2:
        points += 8
    elif total_results >= 1:
        points += 4
    if _as_float(strategy["confidence_band_low"]) <= confidence <= _as_float(strategy["confidence_band_high"]):
        points += 4
    if bool(case_result.get("surname_quality_signal")):
        points += 3
    if is_latin and case_result.get("resolved_query") in {"משה גנדי", "משה גינדי"}:
        points += 2
    return points


def _negative_penalty(case_result: dict[str, Any]) -> int:
    verdict = str(case_result["verdict"])
    if verdict == NONE_VERDICT:
        return 0
    penalty = 15
    if int(case_result["total_results"]) > 0:
        penalty += 5
    if _as_float(case_result["confidence"]) >= 0.5:
        penalty += 5
    return penalty


def evaluate_strategy(strategy: dict[str, Any] | None = None, *, include_rows: bool = True) -> tuple[float, dict[str, Any]]:
    strategy_norm = _normalize_strategy(strategy)

    positives: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []
    positive_points = 0
    total_penalty = 0

    for case in POSITIVE_HEBREW_CASES:
        result = _evaluate_hebrew_case(case["query"], case["scope"], strategy_norm)
        result["case_id"] = case["id"]
        points = _positive_points(result, strategy_norm, is_latin=False)
        result["points"] = points
        positive_points += points
        positives.append(result)

    for case in POSITIVE_LATIN_CASES:
        result = _evaluate_latin_case(case["query"], case["scope"], strategy_norm)
        result["case_id"] = case["id"]
        points = _positive_points(result, strategy_norm, is_latin=True)
        result["points"] = points
        positive_points += points
        positives.append(result)

    for query in NEGATIVE_HEBREW_QUERIES:
        result = _evaluate_hebrew_case(query, "torah", strategy_norm)
        result["query_input"] = query
        result["negative_type"] = "hebrew"
        penalty = _negative_penalty(result)
        result["penalty"] = penalty
        total_penalty += penalty
        negatives.append(result)

    for query in NEGATIVE_LATIN_QUERIES:
        result = _evaluate_latin_case(query, "torah", strategy_norm)
        result["negative_type"] = "latin"
        penalty = _negative_penalty(result)
        result["penalty"] = penalty
        total_penalty += penalty
        negatives.append(result)

    score = max(0.0, float(positive_points - total_penalty))
    details: dict[str, Any] = {
        "score": score,
        "positive_points": positive_points,
        "negative_penalty": total_penalty,
        "positives_total": len(positives),
        "negatives_total": len(negatives),
        "positives_good": sum(1 for row in positives if _is_good(str(row["verdict"]))),
        "negatives_flagged": sum(1 for row in negatives if str(row["verdict"]) != NONE_VERDICT),
        "strategy": strategy_norm,
    }
    if include_rows:
        details["positives"] = positives
        details["negatives"] = negatives
    return score, details


def main() -> None:
    score, details = evaluate_strategy(DEFAULT_STRATEGY, include_rows=True)
    print(json.dumps(details, ensure_ascii=False, indent=2))
    print(f"SCORE: {score:.2f}")


if __name__ == "__main__":
    main()
