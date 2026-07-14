"""Compact, shared, read-only corpus indexes for text search methods."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from autogematria.config import DB_PATH
from autogematria.runtime_data import DataValidationError, connect_corpus

_CHUNK_SIZE = 10_000
_NO_LETTER = "\0"
MIDDLE_LETTER_POLICY = "odd_length_unique_interior_center"


@dataclass(frozen=True)
class LetterCorpusIndex:
    text: str
    book_offsets: dict[str, tuple[int, int]]
    scope_offsets: dict[str, tuple[int, int]]

    def text_for_scope(self, corpus_scope: str) -> str:
        start, end = self.scope_offsets[corpus_scope]
        return self.text[start : end + 1]


@dataclass(frozen=True)
class TevotCorpusIndex:
    first_letters: str
    last_letters: str
    middle_letters: str
    book_offsets: dict[str, tuple[int, int]]
    scope_offsets: dict[str, tuple[int, int]]

    @property
    def word_count(self) -> int:
        return len(self.first_letters)


def _path_key(db_path: str | Path | None) -> str:
    return str(Path(db_path or DB_PATH).resolve())


@lru_cache(maxsize=4)
def _load_letter_index(db_path: str) -> LetterCorpusIndex:
    conn = connect_corpus(db_path, row_factory=False)
    try:
        chunks: list[str] = []
        cursor = conn.execute(
            "SELECT letter_normalized FROM letters ORDER BY absolute_letter_index"
        )
        while rows := cursor.fetchmany(_CHUNK_SIZE):
            chunks.append("".join(str(row[0]) for row in rows))
        text = "".join(chunks)
        if not text:
            raise DataValidationError("Corpus letter index is empty")

        book_offsets = {
            str(row[0]): (int(row[1]), int(row[2]))
            for row in conn.execute(
                "SELECT b.api_name, MIN(l.absolute_letter_index), MAX(l.absolute_letter_index) "
                "FROM letters l JOIN books b ON l.book_id = b.book_id "
                "GROUP BY b.book_id ORDER BY MIN(l.absolute_letter_index)"
            )
        }
        torah_row = conn.execute(
            "SELECT MIN(l.absolute_letter_index), MAX(l.absolute_letter_index) "
            "FROM letters l JOIN books b ON l.book_id = b.book_id "
            "WHERE b.category = 'Torah'"
        ).fetchone()
        if torah_row is None or torah_row[0] is None or torah_row[1] is None:
            raise DataValidationError("Corpus contains no Torah letter range")
        scope_offsets = {
            "torah": (int(torah_row[0]), int(torah_row[1])),
            "tanakh": (0, len(text) - 1),
        }
        return LetterCorpusIndex(
            text=text,
            book_offsets=book_offsets,
            scope_offsets=scope_offsets,
        )
    finally:
        conn.close()


@lru_cache(maxsize=4)
def _load_tevot_index(db_path: str) -> TevotCorpusIndex:
    conn = connect_corpus(db_path, row_factory=False)
    try:
        first_chunks: list[str] = []
        last_chunks: list[str] = []
        middle_chunks: list[str] = []
        expected_index = 0
        cursor = conn.execute(
            "SELECT word_normalized, absolute_word_index FROM words "
            "ORDER BY absolute_word_index"
        )
        while rows := cursor.fetchmany(_CHUNK_SIZE):
            first: list[str] = []
            last: list[str] = []
            middle: list[str] = []
            for word_value, absolute_index in rows:
                if int(absolute_index) != expected_index:
                    raise DataValidationError(
                        "absolute_word_index must be gapless and start at zero; "
                        f"expected {expected_index}, found {absolute_index}"
                    )
                expected_index += 1
                word = str(word_value or "")
                first.append(word[0] if word else _NO_LETTER)
                last.append(word[-1] if word else _NO_LETTER)
                if len(word) >= 3 and len(word) % 2 == 1:
                    middle.append(word[len(word) // 2])
                else:
                    middle.append(_NO_LETTER)
            first_chunks.append("".join(first))
            last_chunks.append("".join(last))
            middle_chunks.append("".join(middle))

        first_letters = "".join(first_chunks)
        last_letters = "".join(last_chunks)
        middle_letters = "".join(middle_chunks)
        if not first_letters:
            raise DataValidationError("Corpus word index is empty")
        book_offsets = {
            str(row[0]): (int(row[1]), int(row[2]))
            for row in conn.execute(
                "SELECT b.api_name, MIN(w.absolute_word_index), MAX(w.absolute_word_index) "
                "FROM words w "
                "JOIN verses v ON w.verse_id = v.verse_id "
                "JOIN chapters c ON v.chapter_id = c.chapter_id "
                "JOIN books b ON c.book_id = b.book_id "
                "GROUP BY b.book_id ORDER BY MIN(w.absolute_word_index)"
            )
        }
        torah_row = conn.execute(
            "SELECT MIN(w.absolute_word_index), MAX(w.absolute_word_index) "
            "FROM words w "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE b.category = 'Torah'"
        ).fetchone()
        if torah_row is None or torah_row[0] is None or torah_row[1] is None:
            raise DataValidationError("Corpus contains no Torah word range")
        return TevotCorpusIndex(
            first_letters=first_letters,
            last_letters=last_letters,
            middle_letters=middle_letters,
            book_offsets=book_offsets,
            scope_offsets={
                "torah": (int(torah_row[0]), int(torah_row[1])),
                "tanakh": (0, len(first_letters) - 1),
            },
        )
    finally:
        conn.close()


def load_letter_index(db_path: str | Path | None = None) -> LetterCorpusIndex:
    return _load_letter_index(_path_key(db_path))


def load_tevot_index(db_path: str | Path | None = None) -> TevotCorpusIndex:
    return _load_tevot_index(_path_key(db_path))


def clear_corpus_index_caches() -> None:
    """Clear process caches, primarily for fixture-backed tests and data replacement."""
    _load_letter_index.cache_clear()
    _load_tevot_index.cache_clear()
