"""ELS Proximity search: find co-located ELS pairs for multi-word names.

For a query like "משה גינדי", finds regions where both tokens appear
as ELS (or direct text) near each other.  A co-located pair is
exponentially more significant than two independent findings.
"""

from __future__ import annotations

from autogematria.config import DB_PATH, normalize_corpus_scope
from autogematria.normalize import extract_letters, FinalsPolicy
from autogematria.search.base import Location, SearchResult
from autogematria.search.els import ELSSearch


def _letter_span(result: SearchResult) -> tuple[int, int]:
    """Return (min_letter_index, max_letter_index) for a search result."""
    start = result.params.get("start_index")
    if start is None:
        start = result.location_start.letter_index or 0
    skip = result.params.get("skip", 1)
    query_len = len(extract_letters(result.query, FinalsPolicy.NORMALIZE))
    end = start + (query_len - 1) * skip
    return (min(start, end), max(start, end))


def find_proximity_pairs(
    query: str,
    token_a: str,
    token_b: str,
    *,
    els_max_skip: int = 500,
    max_distance: int = 5000,
    max_results: int = 20,
    corpus_scope: str = "torah",
    db_path=None,
) -> list[SearchResult]:
    """Find co-located ELS pairs between two tokens.

    Searches for ELS of both tokens independently, then pairs them
    by proximity.  Returns SearchResult objects with method='ELS_PROXIMITY'.

    Args:
        query: Full original query (e.g. "משה גינדי")
        token_a: First token (e.g. "משה") -- typically the common first name
        token_b: Second token (e.g. "גינדי") -- typically the surname
        els_max_skip: Max skip distance to search for each token
        max_distance: Max letter distance to consider a co-location
        max_results: Cap on returned proximity pairs
        corpus_scope: "torah" or "tanakh"
        db_path: Optional DB path override

    Returns:
        List of SearchResult with method='ELS_PROXIMITY', sorted by
        combined quality (distance + skip sizes).
    """
    from autogematria.config import DB_PATH as DEFAULT_DB
    _db = db_path or DEFAULT_DB
    scope = normalize_corpus_scope(corpus_scope)

    els = ELSSearch(_db)

    # Search token_b (surname, the rarer one) with broader skip range
    b_results = els.search_fast(
        token_b,
        min_skip=1,
        max_skip=els_max_skip,
        max_results=200,
        direction="both",
        corpus_scope=scope,
    )
    if not b_results:
        return []

    # Search token_a (first name, more common) -- use smaller max_skip
    # since we expect many hits at low skips
    a_max_skip = min(els_max_skip, 200)
    a_results = els.search_fast(
        token_a,
        min_skip=1,
        max_skip=a_max_skip,
        max_results=500,
        direction="both",
        corpus_scope=scope,
    )

    # Also add direct substring matches of token_a as "skip=0" equivalents
    from autogematria.search.substring import SubstringSearch
    sub = SubstringSearch(_db)
    sub_results = sub.search(
        token_a, max_results=200, cross_word=False, corpus_scope=scope,
    )
    # Convert substring word indices to approximate letter indices for proximity
    conn = els._connect() if sub_results else None
    for sr in sub_results:
        if sr.location_start.word_index is not None and sr.location_start.letter_index is None:
            # Look up first letter index of this word
            if conn is not None:
                row = conn.execute(
                    "SELECT MIN(absolute_letter_index) as li FROM letters "
                    "WHERE word_id = (SELECT word_id FROM words WHERE absolute_word_index = ?)",
                    (sr.location_start.word_index,),
                ).fetchone()
                if row and row["li"] is not None:
                    sr.location_start = Location(
                        book=sr.location_start.book,
                        chapter=sr.location_start.chapter,
                        verse=sr.location_start.verse,
                        word_index=sr.location_start.word_index,
                        letter_index=row["li"],
                    )
                    sr.params["start_index"] = row["li"]
                    sr.params["skip"] = 0  # direct match
    if conn is not None:
        conn.close()

    a_all = a_results + [sr for sr in sub_results if sr.params.get("start_index") is not None]

    if not a_all:
        return []

    # Build index of token_a positions for fast proximity lookup
    a_positions: list[tuple[int, int, SearchResult]] = []  # (min_idx, max_idx, result)
    for r in a_all:
        lo, hi = _letter_span(r)
        a_positions.append((lo, hi, r))
    a_positions.sort(key=lambda x: x[0])

    pairs: list[tuple[float, SearchResult]] = []

    for b_result in b_results:
        b_lo, b_hi = _letter_span(b_result)
        b_center = (b_lo + b_hi) // 2
        b_skip = abs(b_result.params.get("skip", 1))

        best_a: tuple[int, SearchResult] | None = None
        for a_lo, a_hi, a_result in a_positions:
            a_center = (a_lo + a_hi) // 2
            distance = abs(b_center - a_center)
            if distance > max_distance:
                # If sorted positions are already past our window, check if
                # we've gone too far ahead
                if a_lo > b_hi + max_distance:
                    break
                continue
            if best_a is None or distance < best_a[0]:
                best_a = (distance, a_result)

        if best_a is None:
            continue

        distance, a_result = best_a
        a_skip = abs(a_result.params.get("skip", 0))

        # Combined quality score (lower = better):
        # - distance is the primary factor
        # - skip sizes are secondary
        quality = distance + b_skip * 5 + a_skip * 2

        a_loc = a_result.location_start
        b_loc_start = b_result.location_start
        b_loc_end = b_result.location_end

        pairs.append((quality, SearchResult(
            method="ELS_PROXIMITY",
            query=query,
            found_text=f"{a_result.found_text} + {b_result.found_text}",
            location_start=b_loc_start,
            location_end=b_loc_end,
            raw_score=distance,
            params={
                "proximity_distance": distance,
                "surname_token": token_b,
                "surname_skip": b_result.params.get("skip"),
                "surname_start_index": b_result.params.get("start_index"),
                "surname_direction": b_result.params.get("direction"),
                "firstname_token": token_a,
                "firstname_method": "SUBSTRING" if a_skip == 0 else "ELS",
                "firstname_skip": a_result.params.get("skip"),
                "firstname_start_index": a_result.params.get("start_index"),
                "firstname_location": {
                    "book": a_loc.book,
                    "chapter": a_loc.chapter,
                    "verse": a_loc.verse,
                },
            },
            context=(
                f"proximity={distance} letters, "
                f"{token_a}(skip={a_skip}) near "
                f"{token_b}(skip={abs(b_result.params.get('skip', 0))}), "
                f"region={b_loc_start.book} {b_loc_start.chapter}:{b_loc_start.verse}"
            ),
        )))

    # Deduplicate: keep best pair per unique (b_start_index, a_start_index)
    seen: set[tuple[int, int]] = set()
    deduped: list[tuple[float, SearchResult]] = []
    pairs.sort(key=lambda x: x[0])
    for quality, result in pairs:
        key = (
            result.params.get("surname_start_index", 0),
            result.params.get("firstname_start_index", 0),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append((quality, result))

    deduped.sort(key=lambda x: x[0])
    return [r for _, r in deduped[:max_results]]
