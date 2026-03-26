"""Composite scoring metric for the autoresearch loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autogematria.autoresearch.ground_truth import GroundTruthEntry
from autogematria.search.base import SearchResult

METHOD_MAP = {
    "substring": "SUBSTRING",
    "roshei_tevot": "ROSHEI_TEVOT",
    "sofei_tevot": "SOFEI_TEVOT",
}


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
    task_metrics: dict[str, dict[str, float | int]] | None = None


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
    def _match_loc(strict_result: SearchResult) -> bool:
        if entry.book and strict_result.location_start.book != entry.book:
            return False
        if entry.chapter and strict_result.location_start.chapter != entry.chapter:
            return False
        if entry.verse and strict_result.location_start.verse != entry.verse:
            return False
        return True

    def _match_els_loc(strict_result: SearchResult) -> bool:
        candidates = [strict_result.location_start]
        if strict_result.location_end:
            candidates.append(strict_result.location_end)
        for loc in candidates:
            if entry.book and loc.book != entry.book:
                continue
            if entry.chapter and loc.chapter != entry.chapter:
                continue
            if entry.verse and loc.verse != entry.verse:
                continue
            return True
        return not any((entry.book, entry.chapter, entry.verse))

    if entry.method in METHOD_MAP:
        method_results = [r for r in results if r.method == METHOD_MAP[entry.method]]
        for rank, result in enumerate(method_results[:top_k], 1):
            if not _match_loc(result):
                continue
            expected_mode = entry.params.get("mode")
            if expected_mode:
                result_mode = result.params.get("mode")
                if expected_mode == "phrase":
                    if result_mode not in ("cross_word", "within_word"):
                        continue
                elif result_mode != expected_mode:
                    continue
            return {"found": True, "rank": rank, "method_matched": result.method}
        return {"found": False, "rank": None, "method_matched": None}

    if entry.method == "els":
        method_results = [r for r in results if r.method == "ELS"]
        for rank, result in enumerate(method_results[:top_k], 1):
            if not _match_els_loc(result):
                continue

            skip = result.params.get("skip")
            if skip is None:
                continue
            if "skip" in entry.params and abs(int(skip)) != abs(int(entry.params["skip"])):
                continue
            if "start_index" in entry.params and result.params.get("start_index") != entry.params["start_index"]:
                continue
            if "skip_range" in entry.params:
                lo, hi = entry.params["skip_range"]
                if not (int(lo) <= abs(int(skip)) <= int(hi)):
                    continue

            expected_direction = entry.params.get("direction")
            if expected_direction == "forward" and int(skip) < 0:
                continue
            if expected_direction in ("backward", "forward_reversed") and int(skip) > 0:
                continue

            return {"found": True, "rank": rank, "method_matched": result.method}
        return {"found": False, "rank": None, "method_matched": None}

    return {"found": False, "rank": None, "method_matched": None}


def _evaluate_gematria_entry(
    entry: GroundTruthEntry,
    gematria_func,
) -> dict[str, Any]:
    if gematria_func is None:
        return {"found": False, "rank": None, "method_matched": None}

    method = entry.params.get("method", "MISPAR_HECHRACHI")
    try:
        data = gematria_func(entry.name, method=method, max_equivalents=500)
    except Exception:
        return {"found": False, "rank": None, "method_matched": None}

    expected_value = entry.params.get("value")
    if expected_value is not None and data.get("value") != expected_value:
        return {"found": False, "rank": None, "method_matched": None}

    expected_equivs = entry.params.get("equivalents") or []
    if expected_equivs:
        actual_equivs = {e["word"] for e in data.get("equivalents", [])}
        if not any(eq in actual_equivs for eq in expected_equivs):
            return {"found": False, "rank": None, "method_matched": None}

    return {"found": True, "rank": 1, "method_matched": "GEMATRIA"}


def _build_search_kwargs(entry: GroundTruthEntry, top_k: int) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"max_results_per_method": max(top_k, 100)}
    if entry.book:
        kwargs["book"] = entry.book
    if entry.corpus_scope:
        kwargs["corpus_scope"] = entry.corpus_scope

    if entry.method in METHOD_MAP:
        kwargs["only_method"] = entry.method
        if entry.method == "substring":
            mode = entry.params.get("mode")
            if mode == "within_word":
                kwargs["cross_word"] = False
            elif mode == "cross_word":
                kwargs["cross_word"] = True
            elif mode == "phrase":
                # Phrase matching is implemented via spaceless cross-word scans.
                kwargs["cross_word"] = True
        return kwargs

    if entry.method == "els":
        kwargs["only_method"] = "els"
        if "skip" in entry.params:
            skip = abs(int(entry.params["skip"]))
            kwargs["els_min_skip"] = skip
            kwargs["els_max_skip"] = skip
        elif "skip_range" in entry.params:
            lo, hi = entry.params["skip_range"]
            kwargs["els_min_skip"] = int(lo)
            kwargs["els_max_skip"] = int(hi)

        expected_direction = entry.params.get("direction")
        if expected_direction == "forward":
            kwargs["els_direction"] = "forward"
        elif expected_direction in ("backward", "forward_reversed"):
            kwargs["els_direction"] = "backward"
        else:
            kwargs["els_direction"] = "both"
        return kwargs

    return kwargs


def score(
    entries: list[GroundTruthEntry],
    search_func,
    gematria_func=None,
    top_k: int = 20,
) -> ScoreCard:
    """Score a search function against ground truth entries.

    Args:
        entries: Ground truth entries to evaluate against
        search_func: Callable(name: str, **kwargs) -> list[SearchResult]
        gematria_func: Optional callable(name, method, max_equivalents) -> dict
        top_k: How many results to consider for each entry
    """
    positives = [e for e in entries if not e.is_negative]
    negatives = [e for e in entries if e.is_negative]

    found_pos = 0
    reciprocal_ranks = []
    details = []
    task_stats: dict[str, dict[str, float]] = {}

    def _task_bucket(task: str) -> dict[str, float]:
        if task not in task_stats:
            task_stats[task] = {
                "positives": 0.0,
                "negatives": 0.0,
                "found_positives": 0.0,
                "found_negatives": 0.0,
                "rr_sum": 0.0,
            }
        return task_stats[task]

    for entry in positives:
        bucket = _task_bucket(entry.task)
        bucket["positives"] += 1
        if entry.method == "gematria":
            eval_result = _evaluate_gematria_entry(entry, gematria_func)
        else:
            kwargs = _build_search_kwargs(entry, top_k)
            results = search_func(entry.name, **kwargs)
            eval_result = evaluate_entry(entry, results, top_k)

        if eval_result["found"]:
            found_pos += 1
            bucket["found_positives"] += 1
            if eval_result["rank"]:
                reciprocal_ranks.append(1.0 / eval_result["rank"])
                bucket["rr_sum"] += 1.0 / eval_result["rank"]
        else:
            reciprocal_ranks.append(0.0)

        details.append({
            "name": entry.name,
            "english": entry.english,
            "method": entry.method,
            "task": entry.task,
            "track": entry.track,
            "is_negative": False,
            **eval_result,
        })

    found_neg = 0
    for entry in negatives:
        bucket = _task_bucket(entry.task)
        bucket["negatives"] += 1
        if entry.method == "gematria":
            eval_result = _evaluate_gematria_entry(entry, gematria_func)
        else:
            kwargs = _build_search_kwargs(entry, top_k)
            results = search_func(entry.name, **kwargs)
            eval_result = evaluate_entry(entry, results, top_k)

        if eval_result["found"]:
            found_neg += 1
            bucket["found_negatives"] += 1
        details.append({
            "name": entry.name,
            "english": entry.english,
            "method": entry.method,
            "task": entry.task,
            "track": entry.track,
            "is_negative": True,
            **eval_result,
        })

    recall = found_pos / len(positives) if positives else 0.0
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    fpr = found_neg / len(negatives) if negatives else 0.0

    per_task: dict[str, dict[str, float | int]] = {}
    for task, data in task_stats.items():
        pos = int(data["positives"])
        neg = int(data["negatives"])
        found_task_pos = int(data["found_positives"])
        found_task_neg = int(data["found_negatives"])
        recall_task = found_task_pos / pos if pos else 0.0
        mrr_task = data["rr_sum"] / pos if pos else 0.0
        fpr_task = found_task_neg / neg if neg else 0.0
        per_task[task] = {
            "total_positives": pos,
            "total_negatives": neg,
            "found_positives": found_task_pos,
            "found_negatives": found_task_neg,
            "recall": round(recall_task, 4),
            "mrr": round(mrr_task, 4),
            "fpr": round(fpr_task, 4),
            "composite": round(compute_composite(recall_task, mrr_task, fpr_task), 4),
        }

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
        task_metrics=per_task,
    )
