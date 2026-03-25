"""Statistical significance testing for Torah code findings."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import false_discovery_control

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
    arr = np.array(p_values)
    adjusted = false_discovery_control(arr, method="bh")
    return adjusted.tolist()


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

    null_arr = np.array(null_counts, dtype=float)
    p = empirical_p_value(observed, null_counts)

    return SignificanceResult(
        method=null_model,
        query=query,
        observed_count=observed,
        null_mean=float(null_arr.mean()),
        null_std=float(null_arr.std()),
        p_value=p,
    )
