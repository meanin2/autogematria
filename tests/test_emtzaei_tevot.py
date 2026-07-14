"""Tests for experimental Emtzaei Tevot middle-letter search."""

import sqlite3

import pytest
from autogematria.config import DB_PATH
from autogematria.search.corpus_index import (
    MIDDLE_LETTER_POLICY,
    clear_corpus_index_caches,
    load_tevot_index,
)
from autogematria.search.roshei_tevot import EmtzaeiTevotSearch


@pytest.fixture
def emtzaei():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")
    return EmtzaeiTevotSearch()


def test_emtzaei_finds_results(emtzaei):
    results = emtzaei.search("אב", max_results=10, corpus_scope="tanakh")
    assert len(results) > 0
    for r in results:
        assert r.method == "EMTZAEI_TEVOT"
        assert r.params["acrostic_type"] == "middle_letters"
        assert r.params["experimental"] is True
        assert r.params["middle_policy"] == MIDDLE_LETTER_POLICY


def test_emtzaei_single_letter_returns_empty(emtzaei):
    results = emtzaei.search("א", max_results=10)
    assert results == []


def test_even_and_one_letter_words_are_hard_sequence_breaks(tmp_path):
    db_path = tmp_path / "words.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE books (
            book_id INTEGER PRIMARY KEY,
            api_name TEXT,
            category TEXT
        );
        CREATE TABLE chapters (
            chapter_id INTEGER PRIMARY KEY,
            book_id INTEGER,
            chapter_num INTEGER
        );
        CREATE TABLE verses (
            verse_id INTEGER PRIMARY KEY,
            chapter_id INTEGER,
            verse_num INTEGER
        );
        CREATE TABLE words (
            word_id INTEGER PRIMARY KEY,
            verse_id INTEGER,
            absolute_word_index INTEGER,
            word_raw TEXT,
            word_normalized TEXT
        );
        INSERT INTO books VALUES (1, 'Genesis', 'Torah');
        INSERT INTO chapters VALUES (1, 1, 1);
        INSERT INTO verses VALUES (1, 1, 1);
        """
    )
    words = ["אבג", "דהוז", "ח", "טיכלמ", "נסע"]
    conn.executemany(
        "INSERT INTO words VALUES (?, 1, ?, ?, ?)",
        [(index + 1, index, word, word) for index, word in enumerate(words)],
    )
    conn.commit()
    conn.close()

    clear_corpus_index_caches()
    index = load_tevot_index(db_path)
    assert index.middle_letters == "ב\0\0כס"

    searcher = EmtzaeiTevotSearch(db_path=db_path)
    assert searcher.search("בכ", max_results=10) == []
    results = searcher.search("כס", max_results=10)
    assert len(results) == 1
    assert results[0].context == "טיכלמ נסע"
    assert results[0].params["start_word_index"] == 3
    assert results[0].params["end_word_index"] == 4
    clear_corpus_index_caches()
