"""Tests for gematria-pattern search integration."""

import pytest

from autogematria.config import DB_PATH
from autogematria.tools.tool_functions import gematria_pattern_search


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_gematria_pattern_search_finds_exact_word_equivalence():
    data = gematria_pattern_search(
        "משה",
        methods=["MISPAR_HECHRACHI"],
        max_results=10,
        max_span_words=3,
    )
    assert data["total_results"] > 0
    assert any(
        row["method"] == "GEMATRIA"
        and (row.get("params") or {}).get("mode") == "exact_word"
        and row.get("verification", {}).get("verified")
        for row in data["results"]
    )


def test_gematria_pattern_search_finds_contiguous_span():
    data = gematria_pattern_search(
        "ברא אלהים",
        methods=["MISPAR_HECHRACHI"],
        max_results=50,
        max_span_words=3,
    )
    assert any(
        (row.get("params") or {}).get("mode") == "contiguous_span"
        and row.get("location", {}).get("book") == "Genesis"
        and row.get("location", {}).get("chapter") == 1
        and row.get("location", {}).get("verse") == 1
        and row.get("verification", {}).get("verified")
        for row in data["results"]
    )
