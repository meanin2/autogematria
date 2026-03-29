"""Tests for corpus-wide gematria search."""

from __future__ import annotations

import pytest

from autogematria.config import DB_PATH
from autogematria.research.gematria_search import search_gematria_signatures
from autogematria.research.schema import ResearchVariant


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_gematria_search_finds_exact_word_matches():
    results = search_gematria_signatures(
        "משה",
        methods=["MISPAR_HECHRACHI"],
        corpus_scope="torah",
        max_results=5,
    )

    assert results
    assert results[0].analysis_method == "MISPAR_HECHRACHI"
    assert results[0].params["mode"] == "exact_word"
    assert results[0].verification["verified"] is True


def test_gematria_search_finds_exact_sequence_and_sum_patterns(monkeypatch):
    rows = (
        {
            "absolute_word_index": 0,
            "word_raw": "א",
            "word_normalized": "א",
            "value": 10,
            "api_name": "Genesis",
            "chapter_num": 1,
            "verse_num": 1,
        },
        {
            "absolute_word_index": 1,
            "word_raw": "ב",
            "word_normalized": "ב",
            "value": 20,
            "api_name": "Genesis",
            "chapter_num": 1,
            "verse_num": 1,
        },
        {
            "absolute_word_index": 2,
            "word_raw": "ג",
            "word_normalized": "ג",
            "value": 30,
            "api_name": "Genesis",
            "chapter_num": 1,
            "verse_num": 1,
        },
    )

    monkeypatch.setattr(
        "autogematria.research.gematria_search._load_method_rows",
        lambda *_args, **_kwargs: rows,
    )
    monkeypatch.setattr(
        "autogematria.research.gematria_search._gematria_value",
        lambda text, method: {"א ב": 999, "א": 10, "ב": 20, "ג": 30}.get(text, 999),
    )

    variant = ResearchVariant(text="א ב", source="test", kind="direct", token_count=2)
    results = search_gematria_signatures(
        "א ב",
        methods=["MISPAR_HECHRACHI"],
        corpus_scope="torah",
        max_results=10,
        max_sequence_span=3,
        variant=variant,
        task_id="task-1",
    )

    modes = [result.params["mode"] for result in results]
    assert "exact_sequence" in modes
    assert "sum" in modes
    assert all(result.verification["verified"] for result in results)
