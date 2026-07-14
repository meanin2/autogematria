"""Statistical significance testing for Torah code findings."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, pstdev

from autogematria.stats.null_models import letter_frequency_shuffle, markov_chain_null


@dataclass
class SignificanceResult:
    """Significance assessment for a single finding."""
    method: str
    query: str
    observed_count: int
    null_mean: float
    null_std: float
    p_value: float
    adjusted_p_value: float | None = None  # after BH correction


def empirical_p_value(observed: int, null_counts: list[int]) -> float:
    """Conservative empirical p-value: (r + 1) / (n + 1).

    Where r = number of null runs with count >= observed.
    """
    n = len(null_counts)
    r = sum(1 for c in null_counts if c >= observed)
    return (r + 1) / (n + 1)


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Apply Benjamini-Hochberg FDR correction to a list of p-values."""
    if not p_values:
        return []
    for value in p_values:
        if value < 0.0 or value > 1.0:
            raise ValueError("p-values must be between 0 and 1")

    count = len(p_values)
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * count
    running_min = 1.0
    for rank_index in range(count - 1, -1, -1):
        original_index, value = ordered[rank_index]
        rank = rank_index + 1
        running_min = min(running_min, value * count / rank)
        adjusted[original_index] = min(1.0, running_min)
    return adjusted


def compute_significance(
    search_func,
    query: str,
    letter_string: str,
    n_permutations: int = 100,
    null_model: str = "shuffle",
) -> SignificanceResult:
    """Compute empirical significance for a search finding.

    Args:
        search_func: Callable(text, query) -> int (count of matches)
        query: The search term
        letter_string: The full corpus as a letter string
        n_permutations: Number of null corpus runs
        null_model: "shuffle" or "markov"
    """
    # Observed count on real text
    observed = search_func(letter_string, query)

    # Null distribution
    null_counts = []
    for i in range(n_permutations):
        if null_model == "markov":
            null_text = markov_chain_null(letter_string, order=2, seed=i)
        else:
            null_text = letter_frequency_shuffle(letter_string, seed=i)
        null_counts.append(search_func(null_text, query))

    p = empirical_p_value(observed, null_counts)

    return SignificanceResult(
        method=null_model,
        query=query,
        observed_count=observed,
        null_mean=fmean(null_counts) if null_counts else 0.0,
        null_std=pstdev(null_counts) if null_counts else 0.0,
        p_value=p,
    )
