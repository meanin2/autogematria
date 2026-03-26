"""Roshei Tevot (first letters of consecutive words) search."""

from __future__ import annotations

from autogematria.normalize import extract_letters, FinalsPolicy
from autogematria.search.base import SearchMethod, SearchResult


class RosheiTevotSearch(SearchMethod):
    """Find names spelled by first letters of consecutive words."""

    name = "ROSHEI_TEVOT"

    def __init__(self, db_path=None):
        from autogematria.config import DB_PATH as _DB_PATH
        super().__init__(db_path=db_path or _DB_PATH)
        self._word_data: list[tuple[str, str, int]] | None = None  # (first_letter, last_letter, abs_word_idx)

    def _load_words(self):
        if self._word_data is not None:
            return
        conn = self._connect()
        rows = conn.execute(
            "SELECT word_normalized, absolute_word_index FROM words "
            "ORDER BY absolute_word_index"
        ).fetchall()
        self._word_data = []
        for r in rows:
            word = r["word_normalized"]
            if word:
                self._word_data.append((word[0], word[-1], r["absolute_word_index"]))
        conn.close()

    def search(
        self,
        query: str,
        max_results: int = 100,
        book: str | None = None,
    ) -> list[SearchResult]:
        """Find all roshei tevot occurrences of query."""
        self._load_words()
        query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
        if len(query_norm) < 2:
            return []

        # Build string of first letters
        first_letters = "".join(w[0] for w in self._word_data)
        results: list[SearchResult] = []
        conn = self._connect()

        start = 0
        while len(results) < max_results:
            idx = first_letters.find(query_norm, start)
            if idx == -1:
                break

            abs_word_start = self._word_data[idx][2]
            abs_word_end = self._word_data[idx + len(query_norm) - 1][2]

            loc_start = self._location_for_word(conn, abs_word_start)
            loc_end = self._location_for_word(conn, abs_word_end)

            # Disallow cross-book spans and enforce optional book filter.
            if loc_start.book != loc_end.book:
                start = idx + 1
                continue
            if book and (loc_start.book != book or loc_end.book != book):
                start = idx + 1
                continue

            # Collect the actual words for context
            words_in_match = []
            for i in range(len(query_norm)):
                w_idx = self._word_data[idx + i][2]
                row = conn.execute(
                    "SELECT word_raw FROM words WHERE absolute_word_index=?", (w_idx,)
                ).fetchone()
                if row:
                    words_in_match.append(row["word_raw"])

            results.append(SearchResult(
                method=self.name,
                query=query,
                found_text=query_norm,
                location_start=loc_start,
                location_end=loc_end,
                raw_score=len(query_norm),  # longer matches = better
                params={
                    "word_span": len(query_norm),
                    "start_word_index": abs_word_start,
                    "end_word_index": abs_word_end,
                    "acrostic_type": "first_letters",
                },
                context=" ".join(words_in_match),
            ))
            start = idx + 1

        conn.close()
        return results


class SofeiTevotSearch(SearchMethod):
    """Find names spelled by last letters of consecutive words."""

    name = "SOFEI_TEVOT"

    def __init__(self, db_path=None):
        from autogematria.config import DB_PATH as _DB_PATH
        super().__init__(db_path=db_path or _DB_PATH)
        self._word_data: list[tuple[str, str, int]] | None = None

    def _load_words(self):
        if self._word_data is not None:
            return
        conn = self._connect()
        rows = conn.execute(
            "SELECT word_normalized, absolute_word_index FROM words "
            "ORDER BY absolute_word_index"
        ).fetchall()
        self._word_data = []
        for r in rows:
            word = r["word_normalized"]
            if word:
                self._word_data.append((word[0], word[-1], r["absolute_word_index"]))
        conn.close()

    def search(
        self,
        query: str,
        max_results: int = 100,
        book: str | None = None,
    ) -> list[SearchResult]:
        """Find all sofei tevot occurrences of query."""
        self._load_words()
        query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
        if len(query_norm) < 2:
            return []

        # Build string of last letters
        last_letters = "".join(w[1] for w in self._word_data)
        results: list[SearchResult] = []
        conn = self._connect()

        start = 0
        while len(results) < max_results:
            idx = last_letters.find(query_norm, start)
            if idx == -1:
                break

            abs_word_start = self._word_data[idx][2]
            abs_word_end = self._word_data[idx + len(query_norm) - 1][2]

            loc_start = self._location_for_word(conn, abs_word_start)
            loc_end = self._location_for_word(conn, abs_word_end)

            if loc_start.book != loc_end.book:
                start = idx + 1
                continue
            if book and (loc_start.book != book or loc_end.book != book):
                start = idx + 1
                continue

            words_in_match = []
            for i in range(len(query_norm)):
                w_idx = self._word_data[idx + i][2]
                row = conn.execute(
                    "SELECT word_raw FROM words WHERE absolute_word_index=?", (w_idx,)
                ).fetchone()
                if row:
                    words_in_match.append(row["word_raw"])

            results.append(SearchResult(
                method=self.name,
                query=query,
                found_text=query_norm,
                location_start=loc_start,
                location_end=loc_end,
                raw_score=len(query_norm),
                params={
                    "word_span": len(query_norm),
                    "start_word_index": abs_word_start,
                    "end_word_index": abs_word_end,
                    "acrostic_type": "last_letters",
                },
                context=" ".join(words_in_match),
            ))
            start = idx + 1

        conn.close()
        return results
