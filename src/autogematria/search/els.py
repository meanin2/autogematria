"""Equidistant Letter Sequence (ELS) search."""

from __future__ import annotations

from autogematria.normalize import extract_letters, FinalsPolicy
from autogematria.search.base import SearchMethod, SearchResult

# Default skip range bounds
DEFAULT_MIN_SKIP = 1
DEFAULT_MAX_SKIP = 5000


class ELSSearch(SearchMethod):
    """Find names encoded at equidistant letter intervals in the text."""

    name = "ELS"

    def __init__(self, db_path=None, **kwargs):
        from autogematria.config import DB_PATH
        super().__init__(db_path=db_path or DB_PATH)
        self._letter_string: str | None = None
        self._book_offsets: dict[str, tuple[int, int]] | None = None

    def _load_letters(self):
        """Load the entire letter array as a single string. ~1.2MB in memory."""
        if self._letter_string is not None:
            return
        conn = self._connect()
        rows = conn.execute(
            "SELECT letter_normalized FROM letters ORDER BY absolute_letter_index"
        ).fetchall()
        self._letter_string = "".join(r["letter_normalized"] for r in rows)

        # Build book offset map for book-filtered searches
        book_ranges = conn.execute(
            "SELECT b.api_name, MIN(l.absolute_letter_index), MAX(l.absolute_letter_index) "
            "FROM letters l JOIN books b ON l.book_id = b.book_id "
            "GROUP BY b.book_id ORDER BY MIN(l.absolute_letter_index)"
        ).fetchall()
        self._book_offsets = {
            r["api_name"]: (r[1], r[2]) for r in book_ranges
        }
        conn.close()

    def search(
        self,
        query: str,
        min_skip: int = DEFAULT_MIN_SKIP,
        max_skip: int = DEFAULT_MAX_SKIP,
        book: str | None = None,
        max_results: int = 100,
        direction: str = "both",  # "forward", "backward", "both"
    ) -> list[SearchResult]:
        """Find all ELS occurrences of query within the skip range.

        Args:
            query: Hebrew name/word to search for (will be normalized)
            min_skip: Minimum skip distance (inclusive)
            max_skip: Maximum skip distance (inclusive)
            book: Optional book name to restrict search
            max_results: Cap on returned results
            direction: "forward" (positive skip), "backward" (negative), or "both"
        """
        self._load_letters()
        query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
        if len(query_norm) < 2:
            return []

        text = self._letter_string
        text_len = len(text)

        # Determine search region
        start_offset = 0
        end_offset = text_len
        if book and self._book_offsets and book in self._book_offsets:
            start_offset, end_offset = self._book_offsets[book]

        results: list[SearchResult] = []
        conn = self._connect()

        skips_to_check = []
        if direction in ("forward", "both"):
            skips_to_check.extend(range(min_skip, max_skip + 1))
        if direction in ("backward", "both"):
            skips_to_check.extend(range(-max_skip, -min_skip + 1))

        for skip in skips_to_check:
            if len(results) >= max_results:
                break
            abs_skip = abs(skip)
            # For a query of length N at skip S, the span is (N-1)*S letters
            span = (len(query_norm) - 1) * abs_skip
            if span >= text_len:
                continue

            # Build the skip-string and search it
            # For forward skip: try each offset in [start_offset, end_offset - span]
            if skip > 0:
                search_start = start_offset
                search_end = min(end_offset, text_len - span)
            else:
                search_start = start_offset + span
                search_end = end_offset

            for pos in range(search_start, search_end + 1):
                if len(results) >= max_results:
                    break
                # Check if letters at pos, pos+skip, pos+2*skip... spell the query
                match = True
                for i, ch in enumerate(query_norm):
                    idx = pos + i * skip
                    if idx < 0 or idx >= text_len or text[idx] != ch:
                        match = False
                        break
                if match:
                    end_idx = pos + (len(query_norm) - 1) * skip
                    first_idx = min(pos, end_idx)
                    last_idx = max(pos, end_idx)
                    loc_start = self._location_for_letter(conn, first_idx)
                    loc_end = self._location_for_letter(conn, last_idx)
                    # Collect the actual letters for display
                    found = "".join(text[pos + i * skip] for i in range(len(query_norm)))
                    results.append(SearchResult(
                        method=self.name,
                        query=query,
                        found_text=found,
                        location_start=loc_start,
                        location_end=loc_end,
                        raw_score=abs_skip,  # lower skip = "stronger" finding
                        params={"skip": skip, "start_index": pos},
                        context=f"skip={skip}, span={loc_start.book} "
                                f"{loc_start.chapter}:{loc_start.verse} → "
                                f"{loc_end.book} {loc_end.chapter}:{loc_end.verse}",
                    ))

        conn.close()
        # Sort by absolute skip distance (lower = more notable)
        results.sort(key=lambda r: r.raw_score)
        return results[:max_results]

    def search_fast(
        self,
        query: str,
        min_skip: int = DEFAULT_MIN_SKIP,
        max_skip: int = DEFAULT_MAX_SKIP,
        book: str | None = None,
        max_results: int = 100,
    ) -> list[SearchResult]:
        """Optimized forward-only ELS using skip-string + str.find().

        For each skip S, builds S sub-strings (every S-th letter from offsets 0..S-1)
        and uses Python's built-in Boyer-Moore str.find() to locate the query.
        Much faster than brute-force for large skip ranges.
        """
        self._load_letters()
        query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
        if len(query_norm) < 2:
            return []

        text = self._letter_string
        text_len = len(text)
        results: list[SearchResult] = []
        conn = self._connect()

        for skip in range(min_skip, max_skip + 1):
            if len(results) >= max_results:
                break
            span = (len(query_norm) - 1) * skip
            if span >= text_len:
                break  # larger skips won't fit either

            # Build S skip-strings and search each
            for offset in range(skip):
                sub = text[offset::skip]
                start = 0
                while True:
                    idx = sub.find(query_norm, start)
                    if idx == -1:
                        break
                    # Convert back to absolute letter index
                    abs_pos = offset + idx * skip
                    abs_end = abs_pos + (len(query_norm) - 1) * skip

                    # Book filter
                    if book and self._book_offsets and book in self._book_offsets:
                        bstart, bend = self._book_offsets[book]
                        if abs_pos < bstart or abs_end > bend:
                            start = idx + 1
                            continue

                    loc_start = self._location_for_letter(conn, abs_pos)
                    loc_end = self._location_for_letter(conn, abs_end)
                    results.append(SearchResult(
                        method=self.name,
                        query=query,
                        found_text=query_norm,
                        location_start=loc_start,
                        location_end=loc_end,
                        raw_score=skip,
                        params={"skip": skip, "start_index": abs_pos},
                        context=f"skip={skip}, span={loc_start.book} "
                                f"{loc_start.chapter}:{loc_start.verse} → "
                                f"{loc_end.book} {loc_end.chapter}:{loc_end.verse}",
                    ))
                    if len(results) >= max_results:
                        break
                    start = idx + 1

        conn.close()
        results.sort(key=lambda r: r.raw_score)
        return results[:max_results]
