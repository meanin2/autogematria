"""Manual verification helpers for search findings."""

from __future__ import annotations

import sqlite3
from typing import Any

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

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
    if result.method == "GEMATRIA":
        return _verify_gematria(conn, result)
    if result.method == "ELS_PROXIMITY":
        return _verify_els_proximity(conn, result)
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


def _verify_els_proximity(conn: sqlite3.Connection, result: SearchResult) -> dict[str, Any]:
    """Verify both ELS components of a proximity pair."""
    surname_token = result.params.get("surname_token", "")
    surname_skip = result.params.get("surname_skip")
    surname_start = result.params.get("surname_start_index")
    firstname_token = result.params.get("firstname_token", "")
    firstname_skip = result.params.get("firstname_skip")
    firstname_start = result.params.get("firstname_start_index")
    firstname_method = result.params.get("firstname_method", "ELS")

    # Verify surname ELS
    surname_norm = extract_letters(surname_token, FinalsPolicy.NORMALIZE)
    surname_verified = False
    surname_letters: list[dict[str, Any]] = []
    if isinstance(surname_skip, int) and isinstance(surname_start, int) and surname_norm:
        for i in range(len(surname_norm)):
            abs_idx = surname_start + i * surname_skip
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
                break
            surname_letters.append({
                "index": abs_idx,
                "letter_normalized": row["letter_normalized"],
                "ref": f"{row['api_name']} {row['chapter_num']}:{row['verse_num']}",
            })
        actual_surname = "".join(d["letter_normalized"] for d in surname_letters)
        surname_verified = actual_surname == surname_norm

    # Verify firstname
    firstname_norm = extract_letters(firstname_token, FinalsPolicy.NORMALIZE)
    firstname_verified = False
    firstname_letters: list[dict[str, Any]] = []
    if isinstance(firstname_start, int) and firstname_norm:
        if firstname_method == "SUBSTRING" or firstname_skip == 0:
            # Direct word match -- just check the word exists at this position
            row = conn.execute(
                "SELECT w.word_normalized FROM words w "
                "JOIN letters l ON w.word_id = l.word_id "
                "WHERE l.absolute_letter_index = ?",
                (firstname_start,),
            ).fetchone()
            firstname_verified = row is not None and firstname_norm in row["word_normalized"]
        elif isinstance(firstname_skip, int):
            for i in range(len(firstname_norm)):
                abs_idx = firstname_start + i * firstname_skip
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
                    break
                firstname_letters.append({
                    "index": abs_idx,
                    "letter_normalized": row["letter_normalized"],
                    "ref": f"{row['api_name']} {row['chapter_num']}:{row['verse_num']}",
                })
            actual_fn = "".join(d["letter_normalized"] for d in firstname_letters)
            firstname_verified = actual_fn == firstname_norm

    return {
        "verified": surname_verified and firstname_verified,
        "method": "ELS_PROXIMITY",
        "proximity_distance": result.params.get("proximity_distance"),
        "surname": {
            "token": surname_token,
            "verified": surname_verified,
            "skip": surname_skip,
            "start_index": surname_start,
            "letters": surname_letters,
        },
        "firstname": {
            "token": firstname_token,
            "verified": firstname_verified,
            "method": firstname_method,
            "skip": firstname_skip,
            "start_index": firstname_start,
            "letters": firstname_letters,
        },
    }


def _verify_gematria(conn: sqlite3.Connection, result: SearchResult) -> dict[str, Any]:
    mode = str(result.params.get("mode", ""))
    method_name = str(result.params.get("gematria_method", "MISPAR_HECHRACHI"))
    gtype = getattr(GematriaTypes, method_name, GematriaTypes.MISPAR_HECHRACHI)
    query_value = int(result.params.get("query_value") or 0)
    if mode == "exact_word":
        return _verify_gematria_exact_word(conn, result, gtype, method_name, query_value)
    if mode == "contiguous_span":
        return _verify_gematria_span(conn, result, gtype, method_name, query_value)
    return {"verified": False, "reason": f"Unsupported gematria mode {mode}"}


def _verify_gematria_exact_word(
    conn: sqlite3.Connection,
    result: SearchResult,
    gtype,
    method_name: str,
    query_value: int,
) -> dict[str, Any]:
    abs_word_idx = result.params.get("start_word_index") or result.location_start.word_index
    if not isinstance(abs_word_idx, int):
        return {"verified": False, "reason": "Missing word index for gematria exact-word match"}

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

    value = int(Hebrew(str(row["word_raw"])).gematria(gtype))
    return {
        "verified": value == query_value,
        "method": "GEMATRIA",
        "mode": "exact_word",
        "gematria_method": method_name,
        "query_value": query_value,
        "matched_value": value,
        "word": {
            "absolute_word_index": row["absolute_word_index"],
            "raw": row["word_raw"],
            "normalized": row["word_normalized"],
            "ref": f"{row['api_name']} {row['chapter_num']}:{row['verse_num']}",
        },
    }


def _verify_gematria_span(
    conn: sqlite3.Connection,
    result: SearchResult,
    gtype,
    method_name: str,
    query_value: int,
) -> dict[str, Any]:
    start_word_idx = result.params.get("start_word_index") or result.location_start.word_index
    end_word_idx = result.params.get("end_word_index")
    if result.location_end is not None and result.location_end.word_index is not None:
        end_word_idx = result.location_end.word_index
    if not isinstance(start_word_idx, int) or not isinstance(end_word_idx, int):
        return {"verified": False, "reason": "Missing word span for gematria contiguous-span match"}

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
        return {"verified": False, "reason": "No words found for gematria span"}

    words = []
    total = 0
    for row in rows:
        value = int(Hebrew(str(row["word_raw"])).gematria(gtype))
        total += value
        words.append(
            {
                "absolute_word_index": row["absolute_word_index"],
                "word_raw": row["word_raw"],
                "word_normalized": row["word_normalized"],
                "value": value,
                "ref": f"{row['api_name']} {row['chapter_num']}:{row['verse_num']}",
            }
        )

    return {
        "verified": total == query_value,
        "method": "GEMATRIA",
        "mode": "contiguous_span",
        "gematria_method": method_name,
        "query_value": query_value,
        "matched_value": total,
        "start_word_index": lo,
        "end_word_index": hi,
        "words": words,
    }
