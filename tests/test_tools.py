"""Tests for tool functions and pipeline."""

import pytest
from autogematria.config import DB_PATH
from autogematria.tools.tool_functions import (
    find_name_in_torah,
    gematria_lookup,
    get_verse,
    els_detail,
    corpus_stats,
)
from autogematria.tools.pipeline import find_name_full_report


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_find_name_moshe():
    result = find_name_in_torah("משה", max_results=5)
    assert result["total_results"] > 0
    assert result["query"] == "משה"


def test_find_name_with_book_filter():
    result = find_name_in_torah("אברהם", book="Genesis", max_results=5)
    for r in result["results"]:
        assert r["location"]["book"] == "Genesis"


def test_gematria_lookup_moshe():
    result = gematria_lookup("משה")
    assert result["value"] == 345
    assert result["method"] == "MISPAR_HECHRACHI"
    words = [e["word"] for e in result["equivalents"]]
    assert "משה" in words
    assert "השם" in words  # Famous equivalence


def test_gematria_lookup_elohim():
    result = gematria_lookup("אלהים")
    assert result["value"] == 86


def test_get_verse_genesis_1_1():
    result = get_verse("Genesis", 1, 1)
    assert result["text"] == "בראשית ברא אלהים את השמים ואת הארץ"
    assert result["word_count"] == 7
    assert result["verse_gematria"] > 0


def test_els_detail():
    # Torah at skip 50, start 5 in Genesis
    result = els_detail("תורה", 50, 5)
    assert len(result["letters"]) == 4
    assert result["skip"] == 50
    assert result["letters"][0]["letter"] in ("ת", "ט")  # normalized


def test_corpus_stats():
    result = corpus_stats()
    assert result["total_books"] == 39
    assert result["total_letters"] > 1_000_000
    assert len(result["books"]) == 39


def test_full_report_moshe():
    report = find_name_full_report("משה", els_max_skip=50, max_results=5)
    assert report["summary"]["standard_gematria"] == 345
    assert report["summary"]["total_findings"] > 0
    assert "MISPAR_HECHRACHI" in report["gematria"]


def test_full_report_multiword():
    report = find_name_full_report("בני ישראל", els_max_skip=10, max_results=5)
    assert report["word_results"] is not None
    assert len(report["word_results"]) == 2  # two words searched separately
