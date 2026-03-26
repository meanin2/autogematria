"""Manual verification helpers for search findings."""

from __future__ import annotations

import sqlite3
from typing import Any

from autogematria.normalize import FinalsPolicy, extract_letters
from autogematria.search.base import SearchResult


def build_verification_payload(conn: sqlite3.Connection, result: SearchResult) -> dict[str, Any]:
    """Build a deterministic verification payload for a single search finding."""
    if result.method == "ELS":
        return _verify_els(conn, result)
    if result.method in ("ROSHEI_TEVOT", "SOFEI_TEVOT"):
        return _verify_acrostic(conn, result)
    if result.method == "SUBSTRING":
        mode = str(result.params.get("mode", "within_word"))
        if mode == "cross_word":
            return _verify_substring_cross_word(conn, result)
        return _verify_substring_within_word(conn, result)
    return {"verified": False, "reason": f"Unsupported method {result.method}"}


def _verify_els(conn: sqlite3.Connection, result: SearchResult) -> dict[str, Any]:
    query_norm = extract_letters(result.query, FinalsPolicy.NORMALIZE)
    if not query_norm:
        return {"verified": False, "reason": "Query has no letters after normalization"}

    skip = result.params.get("skip")
    start_index = result.params.get("start_index")
    if not isinstance(skip, int) or not isinstance(start_index, int):
        return {"verified": False, "reason": "ELS result missing integer skip/start_index"}

    letters = []
    actual = []
    for i in range(len(query_norm)):
        abs_idx = start_index + i * skip
        row = conn.execute(
            "SELECT l.letter_raw, l.letter_normalized, "
            "b.api_name, c.chapter_num, v.verse_num "
            "FROM letters l "
            "JOIN verses v ON l.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE l.absolute_letter_index = ?",
            (abs_idx,),
        ).fetchone()
        if row is None:
            return {"verified": False, "reason": f"Letter index not found: {abs_idx}"}
        letters.append(
            {
                "index": abs_idx,
                "letter_raw": row["letter_raw"],
                "letter_normalized": row["letter_normalized"],
                "ref": f"{row['api_name']} {row['chapter_num']}:{row['verse_num']}",
            }
        )
        actual.append(row["letter_normalized"])

    actual_seq = "".join(actual)
    return {
        "verified": actual_seq == query_norm,
        "method": "ELS",
        "expected_sequence": query_norm,
        "actual_sequence": actual_seq,
        "skip": skip,
        "start_index": start_index,
        "letters": letters,
    }


def _verify_acrostic(conn: sqlite3.Connection, result: SearchResult) -> dict[str, Any]:
    query_norm = extract_letters(result.query, FinalsPolicy.NORMALIZE)
    start_word_idx = result.location_start.word_index
    end_word_idx = result.location_end.word_index if result.location_end else None
    if start_word_idx is None:
        start_word_idx = result.params.get("start_word_index")
    if end_word_idx is None:
        end_word_idx = result.params.get("end_word_index")

    if not isinstance(start_word_idx, int) or not isinstance(end_word_idx, int):
        return {"verified": False, "reason": "Missing absolute word indices for acrostic"}

    lo = min(start_word_idx, end_word_idx)
    hi = max(start_word_idx, end_word_idx)
    rows = conn.execute(
        "SELECT w.absolute_word_index, w.word_raw, w.word_normalized, "
        "b.api_name, c.chapter_num, v.verse_num "
        "FROM words w "
        "JOIN verses v ON w.verse_id = v.verse_id "
        "JOIN chapters c ON v.chapter_id = c.chapter_id "
        "JOIN books b ON c.book_id = b.book_id "
        "WHERE w.absolute_word_index BETWEEN ? AND ? "
        "ORDER BY w.absolute_word_index",
        (lo, hi),
    ).fetchall()

    if not rows:
        return {"verified": False, "reason": "No words found for acrostic span"}

    words = []
    extracted = []
    for row in rows:
        normalized_word = row["word_normalized"]
        if not normalized_word:
            continue
        letter = normalized_word[0] if result.method == "ROSHEI_TEVOT" else normalized_word[-1]
        extracted.append(letter)
        words.append(
            {
                "absolute_word_index": row["absolute_word_index"],
                "word_raw": row["word_raw"],
                "word_normalized": normalized_word,
                "picked_letter": letter,
                "ref": f"{row['api_name']} {row['chapter_num']}:{row['verse_num']}",
            }
        )

    actual_seq = "".join(extracted)
    return {
        "verified": actual_seq == query_norm,
        "method": result.method,
        "expected_sequence": query_norm,
        "actual_sequence": actual_seq,
        "start_word_index": lo,
        "end_word_index": hi,
        "words": words,
    }


def _verify_substring_within_word(conn: sqlite3.Connection, result: SearchResult) -> dict[str, Any]:
    query_norm = extract_letters(result.query, FinalsPolicy.NORMALIZE)
    abs_word_idx = result.location_start.word_index
    if abs_word_idx is None:
        abs_word_idx = result.params.get("start_word_index")
    if not isinstance(abs_word_idx, int):
        return {"verified": False, "reason": "Missing absolute word index for within-word match"}

    row = conn.execute(
        "SELECT w.word_raw, w.word_normalized, w.absolute_word_index, "
        "b.api_name, c.chapter_num, v.verse_num "
        "FROM words w "
        "JOIN verses v ON w.verse_id = v.verse_id "
        "JOIN chapters c ON v.chapter_id = c.chapter_id "
        "JOIN books b ON c.book_id = b.book_id "
        "WHERE w.absolute_word_index = ?",
        (abs_word_idx,),
    ).fetchone()

    if row is None:
        return {"verified": False, "reason": f"Word index not found: {abs_word_idx}"}

    positions = []
    start = 0
    word_norm = row["word_normalized"]
    while True:
        idx = word_norm.find(query_norm, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1

    return {
        "verified": bool(positions),
        "method": "SUBSTRING",
        "mode": "within_word",
        "expected_sequence": query_norm,
        "positions_in_word": positions,
        "word": {
            "absolute_word_index": row["absolute_word_index"],
            "raw": row["word_raw"],
            "normalized": row["word_normalized"],
            "ref": f"{row['api_name']} {row['chapter_num']}:{row['verse_num']}",
        },
    }


def _verify_substring_cross_word(conn: sqlite3.Connection, result: SearchResult) -> dict[str, Any]:
    query_norm = extract_letters(result.query, FinalsPolicy.NORMALIZE)
    loc = result.location_start
    verse_row = conn.execute(
        "SELECT v.verse_id, v.text_raw, v.text_normalized "
        "FROM verses v "
        "JOIN chapters c ON v.chapter_id = c.chapter_id "
        "JOIN books b ON c.book_id = b.book_id "
        "WHERE b.api_name = ? AND c.chapter_num = ? AND v.verse_num = ?",
        (loc.book, loc.chapter, loc.verse),
    ).fetchone()

    if verse_row is None:
        return {"verified": False, "reason": f"Verse not found: {loc.book} {loc.chapter}:{loc.verse}"}

    words = conn.execute(
        "SELECT absolute_word_index, word_raw, word_normalized "
        "FROM words WHERE verse_id = ? ORDER BY word_index_in_verse",
        (verse_row["verse_id"],),
    ).fetchall()
    if not words:
        return {"verified": False, "reason": "Verse has no words"}

    char_map: list[tuple[int, str]] = []
    for word in words:
        for ch in word["word_normalized"]:
            char_map.append((word["absolute_word_index"], ch))

    spaceless = verse_row["text_normalized"].replace(" ", "")
    start_pos = result.params.get("position_in_verse")
    if not isinstance(start_pos, int):
        start_pos = spaceless.find(query_norm)
    if start_pos < 0:
        return {"verified": False, "reason": "Query not found in spaceless verse"}

    end_pos = start_pos + len(query_norm) - 1
    if end_pos >= len(char_map):
        return {"verified": False, "reason": "Cross-word match extends beyond verse bounds"}

    observed = spaceless[start_pos : start_pos + len(query_norm)]
    start_word = char_map[start_pos][0]
    end_word = char_map[end_pos][0]

    span_words = [
        {
            "absolute_word_index": w["absolute_word_index"],
            "word_raw": w["word_raw"],
            "word_normalized": w["word_normalized"],
        }
        for w in words
        if start_word <= w["absolute_word_index"] <= end_word
    ]

    return {
        "verified": observed == query_norm and start_word != end_word,
        "method": "SUBSTRING",
        "mode": "cross_word",
        "expected_sequence": query_norm,
        "actual_sequence": observed,
        "position_in_verse": start_pos,
        "end_position_in_verse": end_pos,
        "start_word_index": start_word,
        "end_word_index": end_word,
        "verse_text_raw": verse_row["text_raw"],
        "verse_text_normalized": verse_row["text_normalized"],
        "span_words": span_words,
    }
