"""Tests for ELS search."""

import pytest
from autogematria.config import DB_PATH
from autogematria.search.els import ELSSearch


@pytest.fixture
def els():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")
    return ELSSearch()


def test_els_finds_moshe_small_skip(els):
    """משה should appear at small skip distances in the Torah."""
    results = els.search_fast("משה", min_skip=1, max_skip=50, max_results=10)
    assert len(results) > 0
    assert all(r.method == "ELS" for r in results)


def test_els_skip_1_is_direct(els):
    """Skip 1 = consecutive letters = same as substring within the letter stream."""
    results = els.search_fast("משה", min_skip=1, max_skip=1, max_results=5)
    # משה appears directly in the Torah text
    assert len(results) > 0
    assert results[0].raw_score == 1


def test_els_result_has_location(els):
    results = els.search_fast("תורה", min_skip=1, max_skip=100, max_results=1)
    if results:
        r = results[0]
        assert r.location_start.book != "?"
        assert r.location_start.chapter > 0
        assert r.location_start.verse > 0


def test_els_book_filter(els):
    """Book filter should restrict results to that book."""
    results = els.search_fast("משה", min_skip=1, max_skip=50, book="Genesis", max_results=50)
    for r in results:
        assert r.location_start.book == "Genesis"


def test_els_query_normalization(els):
    """Query with nikkud should still work."""
    results_clean = els.search_fast("משה", min_skip=1, max_skip=10, max_results=5)
    results_nikkud = els.search_fast("מֹשֶׁה", min_skip=1, max_skip=10, max_results=5)
    assert len(results_clean) == len(results_nikkud)
