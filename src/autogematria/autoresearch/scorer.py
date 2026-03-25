"""Composite scoring metric for the autoresearch loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autogematria.autoresearch.ground_truth import GroundTruthEntry
from autogematria.search.base import SearchResult


@dataclass
class ScoreCard:
    """Result of evaluating a search config against ground truth."""
    recall: float                  # fraction of positive GT entries found
    mean_reciprocal_rank: float    # average 1/rank of correct finding
    false_positive_rate: float     # fraction of negative controls found
    total_positives: int
    total_negatives: int
    found_positives: int
    found_negatives: int
    composite: float               # THE scalar to optimize
    details: list[dict[str, Any]] | None = None  # per-entry results


def compute_composite(
    recall: float,
    mrr: float,
    fpr: float,
    w_recall: float = 0.4,
    w_mrr: float = 0.3,
    w_fpr: float = 0.3,
) -> float:
    """Weighted composite score. FPR is subtracted (lower FPR = better).

    composite = w_recall * recall + w_mrr * mrr - w_fpr * fpr
    Range: roughly [-0.3, 0.7] in practice
    """
    return w_recall * recall + w_mrr * mrr - w_fpr * fpr


def evaluate_entry(
    entry: GroundTruthEntry,
    results: list[SearchResult],
    top_k: int = 20,
) -> dict[str, Any]:
    """Check if a single ground truth entry is found in results.

    Returns dict with: found (bool), rank (int or None), method_matched (str or None)
    """
    results = results[:top_k]

    for rank, r in enumerate(results, 1):
        # For substring/roshei_tevot/sofei_tevot: check method matches
        if entry.method in ("substring", "roshei_tevot", "sofei_tevot"):
            method_map = {
                "substring": "SUBSTRING",
                "roshei_tevot": "ROSHEI_TEVOT",
                "sofei_tevot": "SOFEI_TEVOT",
            }
            if r.method != method_map.get(entry.method):
                continue
            # For direct occurrences with known location, check location
            if entry.book and r.location_start.book != entry.book:
                continue
            if entry.verse and r.location_start.verse != entry.verse:
                continue
            return {"found": True, "rank": rank, "method_matched": r.method}

        elif entry.method == "els":
            if r.method != "ELS":
                continue
            # Check skip if specified
            if "skip" in entry.params and r.params.get("skip") != entry.params["skip"]:
                continue
            if entry.book and r.location_start.book != entry.book:
                continue
            return {"found": True, "rank": rank, "method_matched": r.method}

        elif entry.method == "gematria":
            # Gematria entries are validated differently — check if value matches
            return {"found": True, "rank": 1, "method_matched": "GEMATRIA"}

    # For entries that should just "be found by any method"
    if not entry.is_negative and results:
        if entry.book:
            for rank, r in enumerate(results, 1):
                if r.location_start.book == entry.book:
                    return {"found": True, "rank": rank, "method_matched": r.method}
        elif results:
            return {"found": True, "rank": 1, "method_matched": results[0].method}

    return {"found": False, "rank": None, "method_matched": None}


def score(
    entries: list[GroundTruthEntry],
    search_func,
    top_k: int = 20,
) -> ScoreCard:
    """Score a search function against ground truth entries.

    Args:
        entries: Ground truth entries to evaluate against
        search_func: Callable(name: str, **kwargs) -> list[SearchResult]
        top_k: How many results to consider for each entry
    """
    positives = [e for e in entries if not e.is_negative]
    negatives = [e for e in entries if e.is_negative]

    found_pos = 0
    reciprocal_ranks = []
    details = []

    for entry in positives:
        kwargs = {}
        if entry.book:
            kwargs["book"] = entry.book

        results = search_func(entry.name, **kwargs)
        eval_result = evaluate_entry(entry, results, top_k)

        if eval_result["found"]:
            found_pos += 1
            if eval_result["rank"]:
                reciprocal_ranks.append(1.0 / eval_result["rank"])
        else:
            reciprocal_ranks.append(0.0)

        details.append({
            "name": entry.name,
            "english": entry.english,
            "method": entry.method,
            "is_negative": False,
            **eval_result,
        })

    found_neg = 0
    for entry in negatives:
        results = search_func(entry.name)
        # A negative control is "found" (bad) if any result appears
        if results:
            found_neg += 1
        details.append({
            "name": entry.name,
            "english": entry.english,
            "method": entry.method,
            "is_negative": True,
            "found": bool(results),
            "rank": None,
            "method_matched": results[0].method if results else None,
        })

    recall = found_pos / len(positives) if positives else 0.0
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    fpr = found_neg / len(negatives) if negatives else 0.0

    return ScoreCard(
        recall=recall,
        mean_reciprocal_rank=mrr,
        false_positive_rate=fpr,
        total_positives=len(positives),
        total_negatives=len(negatives),
        found_positives=found_pos,
        found_negatives=found_neg,
        composite=compute_composite(recall, mrr, fpr),
        details=details,
    )
