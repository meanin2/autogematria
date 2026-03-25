"""Tests for roshei/sofei tevot search."""

import pytest
from autogematria.config import DB_PATH
from autogematria.search.roshei_tevot import RosheiTevotSearch, SofeiTevotSearch


@pytest.fixture
def roshei():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")
    return RosheiTevotSearch()


@pytest.fixture
def sofei():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")
    return SofeiTevotSearch()


def test_roshei_finds_results(roshei):
    """A 3-letter name should have many roshei tevot hits in the Tanakh."""
    results = roshei.search("אבר", max_results=10)
    assert len(results) > 0


def test_roshei_has_context(roshei):
    """Each result should have the source words as context."""
    results = roshei.search("אבר", max_results=1)
    if results:
        assert len(results[0].context) > 0
        # Context should contain multiple words (space-separated)
        assert " " in results[0].context


def test_sofei_finds_results(sofei):
    results = sofei.search("אבר", max_results=10)
    assert len(results) > 0


def test_roshei_book_filter(roshei):
    results = roshei.search("אבר", max_results=20, book="Genesis")
    for r in results:
        assert r.location_start.book == "Genesis"
