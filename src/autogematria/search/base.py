"""Base types for all search methods."""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from autogematria.config import DB_PATH


@dataclass(frozen=True)
class Location:
    """A position in the Tanakh text."""
    book: str
    chapter: int
    verse: int
    word_index: int | None = None       # absolute word index
    letter_index: int | None = None     # absolute letter index


@dataclass
class SearchResult:
    """A single finding from any search method."""
    method: str                         # e.g. "ELS", "ROSHEI_TEVOT", "SUBSTRING"
    query: str                          # the search term
    found_text: str                     # the matched text / letters
    location_start: Location            # where the match begins
    location_end: Location | None = None  # where it ends (for multi-position matches)
    raw_score: float = 0.0             # method-specific score (lower = better for ELS skip)
    params: dict[str, Any] = field(default_factory=dict)  # method-specific params
    context: str = ""                  # surrounding text for display
    p_value: float | None = None       # statistical significance (filled in later)


class SearchMethod(ABC):
    """Abstract base for all search methods."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    @property
    @abstractmethod
    def name(self) -> str:
        """Short method identifier."""

    @abstractmethod
    def search(self, query: str, **kwargs) -> list[SearchResult]:
        """Run this search method and return results."""

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _location_for_letter(self, conn: sqlite3.Connection, abs_idx: int) -> Location:
        """Resolve an absolute letter index to a full Location."""
        row = conn.execute(
            "SELECT b.api_name, c.chapter_num, v.verse_num, "
            "w.absolute_word_index, l.absolute_letter_index "
            "FROM letters l "
            "JOIN words w ON l.word_id = w.word_id "
            "JOIN verses v ON l.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE l.absolute_letter_index = ?",
            (abs_idx,),
        ).fetchone()
        if not row:
            return Location("?", 0, 0, letter_index=abs_idx)
        return Location(
            book=row["api_name"],
            chapter=row["chapter_num"],
            verse=row["verse_num"],
            word_index=row["absolute_word_index"],
            letter_index=abs_idx,
        )

    def _location_for_word(self, conn: sqlite3.Connection, abs_idx: int) -> Location:
        """Resolve an absolute word index to a full Location."""
        row = conn.execute(
            "SELECT b.api_name, c.chapter_num, v.verse_num, w.absolute_word_index "
            "FROM words w "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE w.absolute_word_index = ?",
            (abs_idx,),
        ).fetchone()
        if not row:
            return Location("?", 0, 0, word_index=abs_idx)
        return Location(
            book=row["api_name"],
            chapter=row["chapter_num"],
            verse=row["verse_num"],
            word_index=abs_idx,
        )

    def _get_verse_text(self, conn: sqlite3.Connection, book: str, ch: int, vs: int) -> str:
        """Fetch the raw text of a verse."""
        row = conn.execute(
            "SELECT v.text_raw FROM verses v "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE b.api_name=? AND c.chapter_num=? AND v.verse_num=?",
            (book, ch, vs),
        ).fetchone()
        return row["text_raw"] if row else ""
