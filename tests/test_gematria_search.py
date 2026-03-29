"""Tests for the corpus-wide gematria search layer."""

from __future__ import annotations

import pytest

from autogematria.config import DB_PATH
from autogematria.search.gematria_search import (
    available_gematria_methods,
    search_gematria_corpus,
)


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_available_gematria_methods_registers_full_set():
    methods = available_gematria_methods()
    assert len(methods) >= 20
    assert "MISPAR_HECHRACHI" in methods


def test_word_equivalence_returns_verified_results():
    data = search_gematria_corpus(
        "משה",
        methods=["MISPAR_HECHRACHI"],
        search_kinds=["word_equivalence"],
        max_results_per_method=5,
    )

    assert data["summary"]["total_results"] == 5
    assert data["query_tokens"] == ["משה"]
    assert "MISPAR_HECHRACHI" in data["by_method"]

    first = data["by_method"]["MISPAR_HECHRACHI"][0]
    assert first["search_kind"] == "word_equivalence"
    assert first["verification"]["verified"] is True
    assert first["location"]["book"] != "?"
    assert first["found_text"]


def test_token_sequence_finds_known_genesis_span():
    data = search_gematria_corpus(
        "בראשית ברא",
        methods=["MISPAR_HECHRACHI"],
        search_kinds=["token_sequence"],
        max_span_words=2,
        max_results_per_method=5,
    )

    assert data["summary"]["total_results"] == 1
    hit = data["results"][0]
    assert hit["search_kind"] == "token_sequence"
    assert hit["verification"]["verified"] is True
    assert hit["location"]["book"] == "Genesis"
    assert hit["location"]["chapter"] == 1
    assert hit["location"]["verse"] == 1
    assert hit["location_end"]["book"] == "Genesis"
    assert hit["location_end"]["chapter"] == 1
    assert hit["location_end"]["verse"] == 1
    assert hit["params"]["span_word_count"] == 2
    assert hit["found_text"] == "בראשית ברא"


def test_phrase_total_finds_known_genesis_span():
    data = search_gematria_corpus(
        "בראשית ברא",
        methods=["MISPAR_HECHRACHI"],
        search_kinds=["phrase_total"],
        max_span_words=2,
        max_results_per_method=10,
    )

    assert data["summary"]["total_results"] >= 1
    assert any(
        row["location"]["book"] == "Genesis"
        and row["location"]["chapter"] == 1
        and row["location"]["verse"] == 1
        and row["verification"]["verified"] is True
        for row in data["results"]
    )


def test_multiple_methods_stay_separate():
    data = search_gematria_corpus(
        "משה",
        methods=["MISPAR_HECHRACHI", "MISPAR_GADOL"],
        search_kinds=["word_equivalence"],
        max_results_per_method=3,
    )

    assert set(data["by_method"]) == {"MISPAR_HECHRACHI", "MISPAR_GADOL"}
    assert all(rows for rows in data["by_method"].values())
    for method, rows in data["by_method"].items():
        assert all(row["gematria_method"] == method for row in rows)
        assert all(row["verification"]["verified"] is True for row in rows)
