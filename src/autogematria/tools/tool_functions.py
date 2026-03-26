"""Typed Python tool functions for LLM consumption.

These are the primary interface for AI agents to interact with the
AutoGematria system. Each function returns a structured dict.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import DB_PATH
from autogematria.normalize import normalize_hebrew, extract_letters, FinalsPolicy
from autogematria.stats.reliability import score_search_result
from autogematria.search.unified import UnifiedSearch, UnifiedSearchConfig
from autogematria.tools.verification import build_verification_payload


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_gematria_method(method: str) -> tuple[GematriaTypes, str]:
    gtype = getattr(GematriaTypes, method, None)
    if gtype is None:
        gtype = GematriaTypes.MISPAR_HECHRACHI
    return gtype, gtype.name


def _diversify_results(results, max_results: int):
    """Select a balanced top-N across methods in round-robin order."""
    if not results:
        return []

    method_order = ["SUBSTRING", "ROSHEI_TEVOT", "SOFEI_TEVOT", "ELS"]
    buckets: dict[str, list] = {m: [] for m in method_order}
    extras: list = []
    for result in results:
        if result.method in buckets:
            buckets[result.method].append(result)
        else:
            extras.append(result)

    selected = []
    while len(selected) < max_results:
        advanced = False
        for method in method_order:
            bucket = buckets[method]
            if bucket and len(selected) < max_results:
                selected.append(bucket.pop(0))
                advanced = True
        if not advanced:
            break

    # Fill any remaining slots with non-standard methods (if present)
    while len(selected) < max_results and extras:
        selected.append(extras.pop(0))

    return selected[:max_results]


def find_name_in_torah(
    name: str,
    methods: list[str] | None = None,
    book: str | None = None,
    max_results: int = 20,
    els_max_skip: int = 500,
    include_verification: bool = True,
    diversify_methods: bool = True,
) -> dict[str, Any]:
    """Search for a Hebrew name across the Tanakh using all available methods.

    Args:
        name: Hebrew name to search for (e.g. "משה", "אברהם")
        methods: Subset of ["substring", "roshei_tevot", "sofei_tevot", "els"].
                 None = all methods.
        book: Restrict search to a specific book (e.g. "Genesis", "Exodus")
        max_results: Maximum total results to return
        els_max_skip: Maximum ELS skip distance to search
        include_verification: Include deterministic verification payload per result
        diversify_methods: Round-robin across methods to avoid one-method saturation

    Returns:
        Dict with query info and ranked results list.
    """
    cfg = UnifiedSearchConfig(
        enable_substring=methods is None or "substring" in methods,
        enable_roshei=methods is None or "roshei_tevot" in methods,
        enable_sofei=methods is None or "sofei_tevot" in methods,
        enable_els=methods is None or "els" in methods,
        els_max_skip=els_max_skip,
        els_direction="both",
        els_use_fast=True,
        max_results_per_method=max_results,
        book=book,
    )
    searcher = UnifiedSearch(cfg)
    raw_results = searcher.search(name)
    results = (
        _diversify_results(raw_results, max_results)
        if diversify_methods
        else raw_results[:max_results]
    )

    verify_conn = _conn() if include_verification else None
    packed_results = []
    try:
        for r in results:
            verification_payload = None
            if verify_conn is not None:
                verification_payload = build_verification_payload(verify_conn, r)

            result_payload = {
                "method": r.method,
                "location": {
                    "book": r.location_start.book,
                    "chapter": r.location_start.chapter,
                    "verse": r.location_start.verse,
                },
                "location_end": {
                    "book": r.location_end.book,
                    "chapter": r.location_end.chapter,
                    "verse": r.location_end.verse,
                } if r.location_end else None,
                "found_text": r.found_text,
                "score": r.raw_score,
                "params": r.params,
                "context": r.context,
            }
            if verification_payload is not None:
                result_payload["verification"] = verification_payload
                verified = bool(verification_payload.get("verified"))
            else:
                verified = False
            result_payload["confidence"] = score_search_result(r, verified=verified)
            packed_results.append(result_payload)
    finally:
        if verify_conn is not None:
            verify_conn.close()

    return {
        "query": name,
        "query_normalized": extract_letters(name, FinalsPolicy.NORMALIZE),
        "book_filter": book,
        "total_results": len(results),
        "results": packed_results,
    }


def gematria_lookup(
    word: str,
    method: str = "MISPAR_HECHRACHI",
    max_equivalents: int = 20,
) -> dict[str, Any]:
    """Compute gematria value and find all Tanakh words with the same value.

    Args:
        word: Hebrew word to compute gematria for
        method: Gematria method name (e.g. "MISPAR_HECHRACHI", "MISPAR_GADOL", "ATBASH")
        max_equivalents: Max equivalent words to return

    Returns:
        Dict with the word's value and all equivalent words found in Tanakh.
    """
    # Compute gematria
    clean = normalize_hebrew(word, FinalsPolicy.PRESERVE)
    h = Hebrew(clean)
    gtype, resolved_method = _resolve_gematria_method(method)
    value = h.gematria(gtype)

    # Find equivalents in the corpus
    conn = _conn()
    rows = conn.execute(
        "SELECT wf.form_raw, wf.frequency FROM word_gematria wg "
        "JOIN word_forms wf ON wg.form_id = wf.form_id "
        "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
        "WHERE gm.method_name = ? AND wg.value = ? "
        "ORDER BY wf.frequency DESC LIMIT ?",
        (resolved_method, value, max_equivalents),
    ).fetchall()

    equivalents = []
    for r in rows:
        # Get a sample location for each word
        loc_row = conn.execute(
            "SELECT b.api_name, c.chapter_num, v.verse_num FROM words w "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE w.word_raw = ? LIMIT 1",
            (r["form_raw"],),
        ).fetchone()

        equivalents.append({
            "word": r["form_raw"],
            "frequency": r["frequency"],
            "sample_location": {
                "book": loc_row["api_name"],
                "chapter": loc_row["chapter_num"],
                "verse": loc_row["verse_num"],
            } if loc_row else None,
        })

    conn.close()

    return {
        "word": word,
        "normalized": clean,
        "method_requested": method,
        "method": resolved_method,
        "value": value,
        "total_equivalents": len(equivalents),
        "equivalents": equivalents,
    }


def get_verse(
    book: str,
    chapter: int,
    verse: int,
) -> dict[str, Any]:
    """Retrieve a specific verse with its words, gematria, and letter indices.

    Args:
        book: Book name (e.g. "Genesis", "Exodus")
        chapter: Chapter number
        verse: Verse number

    Returns:
        Dict with verse text, words with gematria, and letter index range.
    """
    conn = _conn()

    # Get verse
    v_row = conn.execute(
        "SELECT v.verse_id, v.text_raw, v.text_normalized FROM verses v "
        "JOIN chapters c ON v.chapter_id = c.chapter_id "
        "JOIN books b ON c.book_id = b.book_id "
        "WHERE b.api_name = ? AND c.chapter_num = ? AND v.verse_num = ?",
        (book, chapter, verse),
    ).fetchone()

    if not v_row:
        conn.close()
        return {"error": f"Verse not found: {book} {chapter}:{verse}"}

    # Get words with gematria
    words = conn.execute(
        "SELECT w.word_raw, w.word_normalized, w.absolute_word_index "
        "FROM words w WHERE w.verse_id = ? ORDER BY w.word_index_in_verse",
        (v_row["verse_id"],),
    ).fetchall()

    word_list = []
    for w in words:
        try:
            gem_val = Hebrew(w["word_raw"]).gematria(GematriaTypes.MISPAR_HECHRACHI)
        except Exception:
            gem_val = None
        word_list.append({
            "word": w["word_raw"],
            "gematria": gem_val,
            "absolute_word_index": w["absolute_word_index"],
        })

    # Get letter index range
    letter_range = conn.execute(
        "SELECT MIN(absolute_letter_index), MAX(absolute_letter_index) "
        "FROM letters WHERE verse_id = ?",
        (v_row["verse_id"],),
    ).fetchone()

    conn.close()

    verse_gematria = sum(w["gematria"] for w in word_list if w["gematria"])

    return {
        "ref": f"{book} {chapter}:{verse}",
        "text": v_row["text_raw"],
        "text_normalized": v_row["text_normalized"],
        "words": word_list,
        "word_count": len(word_list),
        "verse_gematria": verse_gematria,
        "letter_index_start": letter_range[0] if letter_range else None,
        "letter_index_end": letter_range[1] if letter_range else None,
    }


def els_detail(
    query: str,
    skip: int,
    start_index: int,
) -> dict[str, Any]:
    """Get detailed info about a specific ELS occurrence.

    Args:
        query: The Hebrew text found
        skip: The skip distance
        start_index: Absolute letter index where the ELS starts

    Returns:
        Dict with letter-by-letter breakdown and spanning verses.
    """
    query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
    conn = _conn()

    letters_detail = []
    verse_ids = set()

    for i, ch in enumerate(query_norm):
        abs_idx = start_index + i * skip
        row = conn.execute(
            "SELECT l.letter_raw, l.letter_normalized, "
            "b.api_name, c.chapter_num, v.verse_num, v.verse_id "
            "FROM letters l "
            "JOIN words w ON l.word_id = w.word_id "
            "JOIN verses v ON l.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE l.absolute_letter_index = ?",
            (abs_idx,),
        ).fetchone()

        if row:
            letters_detail.append({
                "letter": row["letter_raw"],
                "absolute_index": abs_idx,
                "book": row["api_name"],
                "chapter": row["chapter_num"],
                "verse": row["verse_num"],
            })
            verse_ids.add(row["verse_id"])

    # Get the full text of spanning verses
    spanning_verses = []
    for vid in sorted(verse_ids):
        v_row = conn.execute(
            "SELECT v.text_raw, b.api_name, c.chapter_num, v.verse_num "
            "FROM verses v "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE v.verse_id = ?",
            (vid,),
        ).fetchone()
        if v_row:
            spanning_verses.append({
                "ref": f"{v_row['api_name']} {v_row['chapter_num']}:{v_row['verse_num']}",
                "text": v_row["text_raw"],
            })

    conn.close()

    return {
        "query": query,
        "skip": skip,
        "start_index": start_index,
        "end_index": start_index + (len(query_norm) - 1) * skip,
        "letters": letters_detail,
        "spanning_verses": spanning_verses,
        "num_verses_spanned": len(spanning_verses),
    }


def corpus_stats() -> dict[str, Any]:
    """Return summary statistics about the Tanakh corpus."""
    conn = _conn()

    stats = {}
    for table, label in [
        ("books", "total_books"),
        ("chapters", "total_chapters"),
        ("verses", "total_verses"),
        ("words", "total_words"),
        ("letters", "total_letters"),
        ("word_forms", "unique_word_forms"),
        ("gematria_methods", "gematria_methods"),
        ("word_gematria", "total_gematria_values"),
    ]:
        stats[label] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    # Per-book breakdown
    books = conn.execute(
        "SELECT b.api_name, b.hebrew_name, b.category, b.num_chapters, "
        "(SELECT COUNT(*) FROM words w "
        " JOIN verses v ON w.verse_id = v.verse_id "
        " JOIN chapters c ON v.chapter_id = c.chapter_id "
        " WHERE c.book_id = b.book_id) as word_count "
        "FROM books b ORDER BY b.sort_order"
    ).fetchall()

    stats["books"] = [
        {
            "name": b["api_name"],
            "hebrew": b["hebrew_name"],
            "category": b["category"],
            "chapters": b["num_chapters"],
            "words": b["word_count"],
        }
        for b in books
    ]

    conn.close()
    return stats
