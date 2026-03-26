"""Direct substring / contains search in Torah text."""

from __future__ import annotations

from autogematria.normalize import extract_letters, FinalsPolicy
from autogematria.search.base import SearchMethod, SearchResult


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

        # 1. Within-word matches (exact word matches first, then partial embeddings)
        book_filter = ""
        exact_params: list = [query_norm]
        partial_params: list = [f"%{query_norm}%", query_norm]
        if book:
            book_filter = "AND b.api_name = ? "
            exact_params.append(book)
            partial_params.append(book)

        exact_rows = conn.execute(
            "SELECT w.word_raw, w.word_normalized, w.absolute_word_index, "
            "b.api_name, c.chapter_num, v.verse_num, v.text_raw "
            "FROM words w "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            f"WHERE w.word_normalized = ? {book_filter}"
            "ORDER BY w.absolute_word_index "
            "LIMIT ?",
            exact_params + [max_results],
        ).fetchall()

        remaining = max_results - len(exact_rows)
        partial_rows = []
        if remaining > 0:
            partial_rows = conn.execute(
                "SELECT w.word_raw, w.word_normalized, w.absolute_word_index, "
                "b.api_name, c.chapter_num, v.verse_num, v.text_raw "
                "FROM words w "
                "JOIN verses v ON w.verse_id = v.verse_id "
                "JOIN chapters c ON v.chapter_id = c.chapter_id "
                "JOIN books b ON c.book_id = b.book_id "
                f"WHERE w.word_normalized LIKE ? AND w.word_normalized != ? {book_filter}"
                "ORDER BY w.absolute_word_index "
                "LIMIT ?",
                partial_params + [remaining],
            ).fetchall()

        rows = list(exact_rows) + list(partial_rows)

        for r in rows:
            loc = self._location_for_word(conn, r["absolute_word_index"])
            is_exact = r["word_normalized"] == query_norm
            if is_exact:
                match_positions = [0]
            else:
                match_positions = []
                start = 0
                while True:
                    idx = r["word_normalized"].find(query_norm, start)
                    if idx == -1:
                        break
                    match_positions.append(idx)
                    start = idx + 1
            results.append(SearchResult(
                method=self.name,
                query=query,
                found_text=r["word_raw"],
                location_start=loc,
                raw_score=0.0 if is_exact else 0.2,  # exact words outrank partial embeddings
                params={
                    "mode": "within_word",
                    "match_positions": match_positions,
                    "exact_word_match": is_exact,
                },
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
            word_rows = conn.execute(
                "SELECT absolute_word_index, word_normalized "
                "FROM words WHERE verse_id = ? ORDER BY word_index_in_verse",
                (v["verse_id"],),
            ).fetchall()
            char_to_word_idx: list[int] = []
            for w in word_rows:
                char_to_word_idx.extend([w["absolute_word_index"]] * len(w["word_normalized"]))

            spaceless = v["text_normalized"].replace(" ", "")
            pos = spaceless.find(query_norm)
            while pos != -1 and len(results) < max_results:
                end_pos = pos + len(query_norm) - 1
                if end_pos >= len(char_to_word_idx):
                    pos = spaceless.find(query_norm, pos + 1)
                    continue

                start_abs_word_idx = char_to_word_idx[pos]
                end_abs_word_idx = char_to_word_idx[end_pos]
                # Skip within-word spans; those are handled in mode=within_word.
                if start_abs_word_idx == end_abs_word_idx:
                    pos = spaceless.find(query_norm, pos + 1)
                    continue

                loc_start = self._location_for_word(conn, start_abs_word_idx)
                loc_end = self._location_for_word(conn, end_abs_word_idx)
                results.append(SearchResult(
                    method=self.name,
                    query=query,
                    found_text=query_norm,
                    location_start=loc_start,
                    location_end=loc_end,
                    raw_score=0.5,  # cross-word slightly weaker than within-word
                    params={
                        "mode": "cross_word",
                        "position_in_verse": pos,
                        "end_position_in_verse": end_pos,
                        "start_word_index": start_abs_word_idx,
                        "end_word_index": end_abs_word_idx,
                    },
                    context=v["text_raw"],
                ))
                pos = spaceless.find(query_norm, pos + 1)

        conn.close()
        return results[:max_results]


