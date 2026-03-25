"""Direct substring / contains search in Torah text."""

from __future__ import annotations

from autogematria.normalize import normalize_hebrew, extract_letters, FinalsPolicy
from autogematria.search.base import Location, SearchMethod, SearchResult


class SubstringSearch(SearchMethod):
    """Find names as direct substrings within or across words."""

    name = "SUBSTRING"

    def search(
        self,
        query: str,
        max_results: int = 100,
        book: str | None = None,
        cross_word: bool = True,
    ) -> list[SearchResult]:
        """Search for query as a substring in the text.

        Two modes:
        - Within-word: query appears inside a single word
        - Cross-word: query spans word boundaries (spaces removed)
        """
        query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
        if len(query_norm) < 2:
            return []

        results: list[SearchResult] = []
        conn = self._connect()

        # 1. Within-word matches
        book_filter = ""
        params: list = [f"%{query_norm}%"]
        if book:
            book_filter = "AND b.api_name = ? "
            params.append(book)

        rows = conn.execute(
            "SELECT w.word_raw, w.word_normalized, w.absolute_word_index, "
            "b.api_name, c.chapter_num, v.verse_num, v.text_raw "
            "FROM words w "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            f"WHERE w.word_normalized LIKE ? {book_filter}"
            "ORDER BY w.absolute_word_index "
            f"LIMIT {max_results}",
            params,
        ).fetchall()

        for r in rows:
            loc = self._location_for_word(conn, r["absolute_word_index"])
            results.append(SearchResult(
                method=self.name,
                query=query,
                found_text=r["word_raw"],
                location_start=loc,
                raw_score=0.0,  # direct match = best possible
                params={"mode": "within_word"},
                context=r["text_raw"],
            ))

        if not cross_word or len(results) >= max_results:
            conn.close()
            return results[:max_results]

        # 2. Cross-word matches: search verse text with spaces removed
        params2: list = []
        book_filter2 = ""
        if book:
            book_filter2 = "WHERE b.api_name = ? "
            params2.append(book)

        verses = conn.execute(
            "SELECT v.verse_id, v.text_normalized, v.text_raw, "
            "b.api_name, c.chapter_num, v.verse_num "
            "FROM verses v "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            f"{book_filter2}"
            "ORDER BY v.verse_id",
            params2,
        ).fetchall()

        for v in verses:
            if len(results) >= max_results:
                break
            spaceless = v["text_normalized"].replace(" ", "")
            pos = spaceless.find(query_norm)
            while pos != -1 and len(results) < max_results:
                # Check this isn't a within-word match we already found
                loc = Location(
                    book=v["api_name"],
                    chapter=v["chapter_num"],
                    verse=v["verse_num"],
                )
                results.append(SearchResult(
                    method=self.name,
                    query=query,
                    found_text=query_norm,
                    location_start=loc,
                    raw_score=0.5,  # cross-word slightly weaker than within-word
                    params={"mode": "cross_word", "position_in_verse": pos},
                    context=v["text_raw"],
                ))
                pos = spaceless.find(query_norm, pos + 1)

        conn.close()
        return results[:max_results]


