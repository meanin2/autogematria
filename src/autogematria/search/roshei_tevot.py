"""First-, last-, and experimental middle-letter consecutive-word searches."""

from __future__ import annotations

from autogematria.config import DB_PATH, TORAH_BOOKS, normalize_corpus_scope
from autogematria.normalize import FinalsPolicy, extract_letters
from autogematria.search.base import SearchMethod, SearchResult
from autogematria.search.corpus_index import MIDDLE_LETTER_POLICY, load_tevot_index


class _TevotSearch(SearchMethod):
    sequence_name = ""
    acrostic_type = ""
    experimental = False

    def __init__(self, db_path=None):
        super().__init__(db_path=db_path or DB_PATH)

    def _sequence(self) -> str:
        index = load_tevot_index(self.db_path)
        return str(getattr(index, self.sequence_name))

    def search(
        self,
        query: str,
        max_results: int = 100,
        book: str | None = None,
        corpus_scope: str = "tanakh",
    ) -> list[SearchResult]:
        """Find consecutive-word matches under this letter-selection policy."""
        query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
        if len(query_norm) < 2:
            return []
        scope = normalize_corpus_scope(corpus_scope)
        sequence = self._sequence()
        results: list[SearchResult] = []
        conn = self._connect()
        try:
            start = 0
            while len(results) < max_results:
                position = sequence.find(query_norm, start)
                if position == -1:
                    break

                absolute_start = position
                absolute_end = position + len(query_norm) - 1
                location_start = self._location_for_word(conn, absolute_start)
                location_end = self._location_for_word(conn, absolute_end)

                if location_start.book != location_end.book:
                    start = position + 1
                    continue
                if book and location_start.book != book:
                    start = position + 1
                    continue
                if scope == "torah" and location_start.book not in TORAH_BOOKS:
                    start = position + 1
                    continue

                words = conn.execute(
                    "SELECT word_raw FROM words "
                    "WHERE absolute_word_index BETWEEN ? AND ? "
                    "ORDER BY absolute_word_index",
                    (absolute_start, absolute_end),
                ).fetchall()
                params = {
                    "word_span": len(query_norm),
                    "start_word_index": absolute_start,
                    "end_word_index": absolute_end,
                    "acrostic_type": self.acrostic_type,
                }
                if self.experimental:
                    params.update(
                        {
                            "experimental": True,
                            "middle_policy": MIDDLE_LETTER_POLICY,
                        }
                    )

                results.append(
                    SearchResult(
                        method=self.name,
                        query=query,
                        found_text=query_norm,
                        location_start=location_start,
                        location_end=location_end,
                        raw_score=len(query_norm),
                        params=params,
                        context=" ".join(str(row["word_raw"]) for row in words),
                    )
                )
                start = position + 1
        finally:
            conn.close()
        return results


class RosheiTevotSearch(_TevotSearch):
    """Find names spelled by first letters of consecutive words."""

    name = "ROSHEI_TEVOT"
    sequence_name = "first_letters"
    acrostic_type = "first_letters"


class SofeiTevotSearch(_TevotSearch):
    """Find names spelled by last letters of consecutive words."""

    name = "SOFEI_TEVOT"
    sequence_name = "last_letters"
    acrostic_type = "last_letters"


class EmtzaeiTevotSearch(_TevotSearch):
    """Find experimental unique middle letters across consecutive words.

    Only odd-length words of at least three letters have an eligible middle.
    Ineligible words remain in the aligned sequence as hard separators, so a
    reported match can never skip over a one-letter or even-length word.
    """

    name = "EMTZAEI_TEVOT"
    sequence_name = "middle_letters"
    acrostic_type = "middle_letters"
    experimental = True
