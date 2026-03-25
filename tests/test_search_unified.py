"""Tests for unified search."""

import pytest
from autogematria.config import DB_PATH
from autogematria.search.unified import UnifiedSearch, UnifiedSearchConfig


@pytest.fixture
def searcher():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")
    cfg = UnifiedSearchConfig(els_max_skip=100, max_results_per_method=10)
    return UnifiedSearch(cfg)


def test_unified_moshe(searcher):
    """'משה' should be found by multiple methods."""
    results = searcher.search("משה")
    methods = {r.method for r in results}
    assert "SUBSTRING" in methods  # משה appears directly in text
    assert len(results) > 0


def test_unified_avraham(searcher):
    """'אברהם' should be found by at least substring."""
    results = searcher.search("אברהם")
    assert any(r.method == "SUBSTRING" for r in results)


def test_unified_sorted(searcher):
    """Results should be sorted: substring first, then roshei/sofei, then ELS."""
    results = searcher.search("משה")
    if len(results) >= 2:
        methods_order = [r.method for r in results]
        # Find first ELS result
        for i, m in enumerate(methods_order):
            if m == "ELS":
                # All substring/roshei/sofei should come before
                for j in range(i):
                    assert methods_order[j] in ("SUBSTRING", "ROSHEI_TEVOT", "SOFEI_TEVOT")
                break


def test_unified_book_filter():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")
    cfg = UnifiedSearchConfig(book="Genesis", els_max_skip=50, max_results_per_method=5)
    searcher = UnifiedSearch(cfg)
    results = searcher.search("אברהם")
    # Substring and roshei results should be in Genesis
    for r in results:
        if r.method in ("SUBSTRING", "ROSHEI_TEVOT", "SOFEI_TEVOT"):
            assert r.location_start.book == "Genesis"
