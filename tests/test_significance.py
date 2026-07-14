"""Pure-Python statistical helper tests."""

from __future__ import annotations

import pytest

from autogematria.stats.significance import benjamini_hochberg, compute_significance


def test_benjamini_hochberg_preserves_order_and_monotonic_adjustment():
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03])
    assert adjusted == pytest.approx([0.03, 0.04, 0.04])


def test_benjamini_hochberg_rejects_invalid_probability():
    with pytest.raises(ValueError, match="between 0 and 1"):
        benjamini_hochberg([0.5, 1.1])


def test_compute_significance_uses_population_statistics():
    result = compute_significance(
        lambda text, query: text.count(query),
        "א",
        "אבבא",
        n_permutations=4,
        null_model="shuffle",
    )
    assert result.observed_count == 2
    assert result.null_mean == pytest.approx(2.0)
    assert result.null_std == pytest.approx(0.0)
