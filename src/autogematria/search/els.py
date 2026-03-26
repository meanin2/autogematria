"""Equidistant Letter Sequence (ELS) search."""

from __future__ import annotations

from autogematria.normalize import extract_letters, FinalsPolicy
from autogematria.search.base import SearchMethod, SearchResult

# Default skip range bounds
DEFAULT_MIN_SKIP = 1
DEFAULT_MAX_SKIP = 5000
_VALID_DIRECTIONS = {"forward", "backward", "both"}


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

    @staticmethod
    def _validate_search_args(min_skip: int, max_skip: int, direction: str) -> None:
        if min_skip < 1:
            raise ValueError("min_skip must be >= 1")
        if max_skip < min_skip:
            raise ValueError("max_skip must be >= min_skip")
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(f"direction must be one of {_VALID_DIRECTIONS}")

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
        self._validate_search_args(min_skip, max_skip, direction)
        query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
        if len(query_norm) < 2:
            return []

        text = self._letter_string
        text_len = len(text)

        # Determine search region
        start_offset = 0
        end_offset = text_len - 1
        if book:
            if not self._book_offsets or book not in self._book_offsets:
                return []
            start_offset, end_offset = self._book_offsets[book]

        results: list[SearchResult] = []
        conn = self._connect()

        skips_to_check = []
        if direction in ("forward", "both"):
            skips_to_check.extend(range(min_skip, max_skip + 1))
        if direction in ("backward", "both"):
            skips_to_check.extend(range(-min_skip, -max_skip - 1, -1))

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
                search_end = min(end_offset - span, text_len - span - 1)
            else:
                search_start = start_offset + span
                search_end = end_offset

            if search_start > search_end:
                continue

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
                        params={
                            "skip": skip,
                            "start_index": pos,
                            "direction": "forward" if skip > 0 else "backward",
                        },
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
        direction: str = "both",  # "forward", "backward", "both"
    ) -> list[SearchResult]:
        """Optimized ELS using skip-string + str.find().

        For each skip S, builds S sub-strings (every S-th letter from offsets 0..S-1)
        and uses Python's built-in Boyer-Moore str.find() to locate the query.
        Supports forward, backward, or both directions.
        """
        self._load_letters()
        self._validate_search_args(min_skip, max_skip, direction)
        query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
        if len(query_norm) < 2:
            return []

        text = self._letter_string
        text_len = len(text)
        results: list[SearchResult] = []
        conn = self._connect()
        book_bounds = None

        if book:
            if not self._book_offsets or book not in self._book_offsets:
                conn.close()
                return []
            book_bounds = self._book_offsets[book]

        search_specs: list[tuple[str, str, int]] = []
        if direction in ("forward", "both"):
            search_specs.append(("forward", query_norm, 1))
        if direction in ("backward", "both"):
            # Backward match for query Q with skip -S is equivalent to forward
            # match of reversed(Q) with skip +S anchored at the low endpoint.
            search_specs.append(("backward", query_norm[::-1], -1))

        for skip in range(min_skip, max_skip + 1):
            if len(results) >= max_results:
                break
            span = (len(query_norm) - 1) * skip
            if span >= text_len:
                break  # larger skips won't fit either

            for direction_label, pattern, sign in search_specs:
                if len(results) >= max_results:
                    break

                # Build S skip-strings and search each
                for offset in range(skip):
                    if len(results) >= max_results:
                        break
                    sub = text[offset::skip]
                    start = 0
                    while True:
                        idx = sub.find(pattern, start)
                        if idx == -1:
                            break

                        anchor = offset + idx * skip
                        if sign > 0:
                            start_index = anchor
                            end_index = anchor + (len(query_norm) - 1) * skip
                            signed_skip = skip
                        else:
                            start_index = anchor + (len(query_norm) - 1) * skip
                            end_index = anchor
                            signed_skip = -skip

                        span_start = min(start_index, end_index)
                        span_end = max(start_index, end_index)

                        # Book filter
                        if book_bounds:
                            bstart, bend = book_bounds
                            if span_start < bstart or span_end > bend:
                                start = idx + 1
                                continue

                        loc_start = self._location_for_letter(conn, span_start)
                        loc_end = self._location_for_letter(conn, span_end)
                        found = "".join(
                            text[start_index + i * signed_skip] for i in range(len(query_norm))
                        )
                        results.append(SearchResult(
                            method=self.name,
                            query=query,
                            found_text=found,
                            location_start=loc_start,
                            location_end=loc_end,
                            raw_score=skip,
                            params={
                                "skip": signed_skip,
                                "start_index": start_index,
                                "direction": direction_label,
                            },
                            context=f"skip={signed_skip}, span={loc_start.book} "
                                    f"{loc_start.chapter}:{loc_start.verse} → "
                                    f"{loc_end.book} {loc_end.chapter}:{loc_end.verse}",
                        ))
                        if len(results) >= max_results:
                            start = idx + 1
                            break
                        start = idx + 1

        conn.close()
        results.sort(key=lambda r: r.raw_score)
        return results[:max_results]
