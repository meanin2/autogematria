"""Corpus-wide gematria search over indexed Tanakh word forms.

This module reuses the precomputed `word_gematria` table to search the corpus by:

* exact word-value equivalence
* bounded contiguous token-signature matches
* bounded contiguous phrase-total matches

Every returned hit includes provenance back to the exact source span and a
deterministic verification payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import sqlite3
from typing import Any, Iterable

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import DB_PATH, normalize_corpus_scope
from autogematria.normalize import FinalsPolicy, normalize_hebrew, validate_normalized
from autogematria.search.base import Location, SearchResult


SEARCH_KIND_WORD_EQUIVALENCE = "word_equivalence"
SEARCH_KIND_TOKEN_SEQUENCE = "token_sequence"
SEARCH_KIND_PHRASE_TOTAL = "phrase_total"

DEFAULT_SEARCH_KINDS = (
    SEARCH_KIND_WORD_EQUIVALENCE,
    SEARCH_KIND_TOKEN_SEQUENCE,
    SEARCH_KIND_PHRASE_TOTAL,
)


@dataclass(frozen=True)
class GematriaWordRow:
    """A single corpus word annotated with one gematria method."""

    absolute_word_index: int
    word_raw: str
    word_normalized: str
    book: str
    chapter: int
    verse: int
    value: int


@dataclass(frozen=True)
class GematriaSearchHit:
    """A deterministic gematria finding with provenance and verification."""

    query: str
    query_normalized: str
    gematria_method: str
    search_kind: str
    query_tokens: tuple[str, ...]
    query_values: tuple[int, ...]
    query_total: int
    match_values: tuple[int, ...]
    match_total: int
    result: SearchResult
    verification: dict[str, Any]
    token_index: int | None = None
    token_query: str | None = None

    def to_dict(self) -> dict[str, Any]:
        loc = self.result.location_start
        end = self.result.location_end
        return {
            "query": self.query,
            "query_normalized": self.query_normalized,
            "gematria_method": self.gematria_method,
            "search_kind": self.search_kind,
            "query_tokens": list(self.query_tokens),
            "query_values": list(self.query_values),
            "query_total": self.query_total,
            "match_values": list(self.match_values),
            "match_total": self.match_total,
            "token_index": self.token_index,
            "token_query": self.token_query,
            "method": self.result.method,
            "location": {
                "book": loc.book,
                "chapter": loc.chapter,
                "verse": loc.verse,
                "word_index": loc.word_index,
                "letter_index": loc.letter_index,
            },
            "location_end": {
                "book": end.book,
                "chapter": end.chapter,
                "verse": end.verse,
                "word_index": end.word_index,
                "letter_index": end.letter_index,
            } if end else None,
            "found_text": self.result.found_text,
            "context": self.result.context,
            "raw_score": self.result.raw_score,
            "params": self.result.params,
            "verification": self.verification,
        }


def _resolve_gematria_method(method: str) -> tuple[GematriaTypes, str]:
    gtype = getattr(GematriaTypes, method, None)
    if gtype is None:
        gtype = GematriaTypes.MISPAR_HECHRACHI
    return gtype, gtype.name


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _location_from_row(row: GematriaWordRow) -> Location:
    return Location(
        book=row.book,
        chapter=row.chapter,
        verse=row.verse,
        word_index=row.absolute_word_index,
    )


def _location_for_word(conn: sqlite3.Connection, abs_word_idx: int) -> Location:
    row = conn.execute(
        "SELECT b.api_name, c.chapter_num, v.verse_num, w.absolute_word_index "
        "FROM words w "
        "JOIN verses v ON w.verse_id = v.verse_id "
        "JOIN chapters c ON v.chapter_id = c.chapter_id "
        "JOIN books b ON c.book_id = b.book_id "
        "WHERE w.absolute_word_index = ?",
        (abs_word_idx,),
    ).fetchone()
    if not row:
        return Location("?", 0, 0, word_index=abs_word_idx)
    return Location(
        book=row["api_name"],
        chapter=row["chapter_num"],
        verse=row["verse_num"],
        word_index=abs_word_idx,
    )


def _span_payload(rows: list[GematriaWordRow]) -> list[dict[str, Any]]:
    return [
        {
            "absolute_word_index": row.absolute_word_index,
            "word_raw": row.word_raw,
            "word_normalized": row.word_normalized,
            "book": row.book,
            "chapter": row.chapter,
            "verse": row.verse,
            "value": row.value,
        }
        for row in rows
    ]


def _query_total(values: Iterable[int]) -> int:
    return sum(int(v) for v in values)


def _build_hit(
    *,
    query: str,
    query_normalized: str,
    gematria_method: str,
    search_kind: str,
    query_tokens: tuple[str, ...],
    query_values: tuple[int, ...],
    match_rows: list[GematriaWordRow],
    token_index: int | None = None,
    token_query: str | None = None,
    exact_word_match: bool = False,
) -> GematriaSearchHit:
    start_row = match_rows[0]
    end_row = match_rows[-1]
    match_values = tuple(row.value for row in match_rows)
    match_total = _query_total(match_values)
    query_total = _query_total(query_values)
    found_text = " ".join(row.word_raw for row in match_rows)
    location_start = _location_from_row(start_row)
    location_end = _location_from_row(end_row) if len(match_rows) > 1 else location_start
    verification: dict[str, Any]
    if search_kind == SEARCH_KIND_WORD_EQUIVALENCE:
        verification = {
            "verified": start_row.value == query_values[0],
            "expected_value": query_values[0],
            "actual_value": start_row.value,
            "exact_word_match": exact_word_match,
            "span": _span_payload(match_rows),
        }
        raw_score = 0.0 if exact_word_match else 0.2
    elif search_kind == SEARCH_KIND_TOKEN_SEQUENCE:
        verification = {
            "verified": list(match_values) == list(query_values),
            "expected_signature": list(query_values),
            "actual_signature": list(match_values),
            "expected_total": query_total,
            "actual_total": match_total,
            "span": _span_payload(match_rows),
        }
        raw_score = float(len(match_rows))
    else:
        verification = {
            "verified": match_total == query_total,
            "expected_total": query_total,
            "actual_total": match_total,
            "expected_signature": list(query_values),
            "actual_signature": list(match_values),
            "span": _span_payload(match_rows),
        }
        raw_score = float(len(match_rows))
    result = SearchResult(
        method="GEMATRIA",
        query=query,
        found_text=found_text,
        location_start=location_start,
        location_end=location_end,
        raw_score=raw_score,
        params={
            "gematria_method": gematria_method,
            "search_kind": search_kind,
            "query_tokens": list(query_tokens),
            "query_values": list(query_values),
            "query_total": query_total,
            "match_values": list(match_values),
            "match_total": match_total,
            "token_index": token_index,
            "token_query": token_query,
            "span_word_count": len(match_rows),
            "start_word_index": start_row.absolute_word_index,
            "end_word_index": end_row.absolute_word_index,
            "start_ref": f"{location_start.book} {location_start.chapter}:{location_start.verse}",
            "end_ref": f"{location_end.book} {location_end.chapter}:{location_end.verse}",
            "exact_word_match": exact_word_match,
        },
        context=(
            f"{location_start.book} {location_start.chapter}:{location_start.verse}"
            if location_start == location_end
            else f"{location_start.book} {location_start.chapter}:{location_start.verse}"
            f" -> {location_end.book} {location_end.chapter}:{location_end.verse}"
        ),
    )

    return GematriaSearchHit(
        query=query,
        query_normalized=query_normalized,
        gematria_method=gematria_method,
        search_kind=search_kind,
        query_tokens=query_tokens,
        query_values=query_values,
        query_total=query_total,
        match_values=match_values,
        match_total=match_total,
        result=result,
        verification=verification,
        token_index=token_index,
        token_query=token_query,
    )


@lru_cache(maxsize=32)
def _load_method_rows(
    db_path_str: str,
    gematria_method: str,
    corpus_scope: str,
    book: str | None,
) -> tuple[GematriaWordRow, ...]:
    conn = sqlite3.connect(db_path_str)
    conn.row_factory = sqlite3.Row
    try:
        scope = normalize_corpus_scope(corpus_scope)
        where_parts = ["gm.method_name = ?"]
        params: list[Any] = [gematria_method]
        if scope == "torah":
            where_parts.append("b.category = 'Torah'")
        if book:
            where_parts.append("b.api_name = ?")
            params.append(book)
        where_sql = " AND ".join(where_parts)
        rows = conn.execute(
            "SELECT w.absolute_word_index, w.word_raw, w.word_normalized, "
            "b.api_name, c.chapter_num, v.verse_num, wg.value "
            "FROM words w "
            "JOIN word_forms wf ON w.word_normalized = wf.form_text "
            "JOIN word_gematria wg ON wf.form_id = wg.form_id "
            "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            f"WHERE {where_sql} "
            "ORDER BY w.absolute_word_index",
            params,
        ).fetchall()
        return tuple(
            GematriaWordRow(
                absolute_word_index=int(r["absolute_word_index"]),
                word_raw=str(r["word_raw"]),
                word_normalized=str(r["word_normalized"]),
                book=str(r["api_name"]),
                chapter=int(r["chapter_num"]),
                verse=int(r["verse_num"]),
                value=int(r["value"]),
            )
            for r in rows
        )
    finally:
        conn.close()


def available_gematria_methods(db_path=DB_PATH) -> list[str]:
    """Return registered gematria methods in deterministic order."""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT method_name FROM gematria_methods ORDER BY method_id"
        ).fetchall()
        methods = [str(r[0]) for r in rows]
    finally:
        conn.close()
    return methods


def _resolve_methods(methods: Iterable[str] | None, db_path=DB_PATH) -> list[str]:
    if methods is None:
        resolved = available_gematria_methods(db_path=db_path)
    else:
        resolved = []
        for method in methods:
            _, method_name = _resolve_gematria_method(str(method))
            if method_name not in resolved:
                resolved.append(method_name)
    if not resolved:
        raise ValueError("No supported gematria methods available")
    return resolved


def _search_word_equivalences(
    *,
    query: str,
    query_normalized: str,
    query_tokens: tuple[str, ...],
    query_values: tuple[int, ...],
    gematria_method: str,
    corpus_scope: str,
    book: str | None,
    max_results_per_method: int,
) -> list[GematriaSearchHit]:
    rows = _load_method_rows(str(DB_PATH), gematria_method, corpus_scope, book)
    if not rows:
        return []

    hits: list[GematriaSearchHit] = []
    token_count = len(query_tokens)
    for token_index, token in enumerate(query_tokens):
        token_value = query_values[token_index]
        token_rows = [row for row in rows if row.value == token_value]
        for row in token_rows[:max_results_per_method]:
            exact_word_match = row.word_normalized == token
            hit = _build_hit(
                query=query,
                query_normalized=query_normalized,
                gematria_method=gematria_method,
                search_kind=SEARCH_KIND_WORD_EQUIVALENCE,
                query_tokens=query_tokens,
                query_values=(token_value,),
                match_rows=[row],
                token_index=token_index if token_count > 1 else None,
                token_query=token if token_count > 1 else None,
                exact_word_match=exact_word_match,
            )
            hits.append(hit)
    return hits


def _search_token_sequences(
    *,
    query: str,
    query_normalized: str,
    query_tokens: tuple[str, ...],
    query_values: tuple[int, ...],
    gematria_method: str,
    corpus_scope: str,
    book: str | None,
    max_results_per_method: int,
) -> list[GematriaSearchHit]:
    if len(query_values) < 2:
        return []

    rows = _load_method_rows(str(DB_PATH), gematria_method, corpus_scope, book)
    if len(rows) < len(query_values):
        return []

    values = [row.value for row in rows]
    needle = list(query_values)
    hits: list[GematriaSearchHit] = []
    needle_len = len(needle)
    limit = len(values) - needle_len + 1
    for start in range(limit):
        if values[start : start + needle_len] != needle:
            continue
        match_rows = list(rows[start : start + needle_len])
        hit = _build_hit(
            query=query,
            query_normalized=query_normalized,
            gematria_method=gematria_method,
            search_kind=SEARCH_KIND_TOKEN_SEQUENCE,
            query_tokens=query_tokens,
            query_values=query_values,
            match_rows=match_rows,
        )
        hits.append(hit)
        if len(hits) >= max_results_per_method:
            break
    return hits


def _search_phrase_totals(
    *,
    query: str,
    query_normalized: str,
    query_tokens: tuple[str, ...],
    query_values: tuple[int, ...],
    gematria_method: str,
    corpus_scope: str,
    book: str | None,
    max_span_words: int,
    max_results_per_method: int,
) -> list[GematriaSearchHit]:
    rows = _load_method_rows(str(DB_PATH), gematria_method, corpus_scope, book)
    if not rows or max_span_words < 1:
        return []

    target_total = _query_total(query_values)
    values = [row.value for row in rows]
    hits: list[GematriaSearchHit] = []

    for start in range(len(values)):
        total = 0
        for span_len in range(1, min(max_span_words, len(values) - start) + 1):
            total += values[start + span_len - 1]
            if total > target_total:
                break
            if total != target_total:
                continue
            match_rows = list(rows[start : start + span_len])
            hit = _build_hit(
                query=query,
                query_normalized=query_normalized,
                gematria_method=gematria_method,
                search_kind=SEARCH_KIND_PHRASE_TOTAL,
                query_tokens=query_tokens,
                query_values=query_values,
                match_rows=match_rows,
            )
            hits.append(hit)
            if len(hits) >= max_results_per_method:
                return hits
    return hits


def search_gematria_corpus(
    query: str,
    *,
    methods: Iterable[str] | None = None,
    search_kinds: Iterable[str] | None = None,
    corpus_scope: str = "torah",
    book: str | None = None,
    max_span_words: int = 6,
    max_results_per_method: int = 20,
) -> dict[str, Any]:
    """Search the corpus by gematria value/signature across multiple methods."""
    scope = normalize_corpus_scope(corpus_scope)
    normalized_query = normalize_hebrew(query, FinalsPolicy.PRESERVE)
    query_tokens = tuple(token for token in normalized_query.split() if token)
    if not query_tokens:
        return {
            "query": query,
            "query_normalized": normalized_query,
            "query_tokens": [],
            "methods": [],
            "search_kinds": [],
            "corpus_scope": scope,
            "book_filter": book,
            "results": [],
            "by_method": {},
            "summary": {
                "total_results": 0,
                "methods_with_hits": {},
            },
        }

    for token in query_tokens:
        if not validate_normalized(token):
            raise ValueError(f"Query contains unsupported characters for gematria: {query!r}")

    selected_methods = _resolve_methods(methods)
    selected_kinds = list(search_kinds or DEFAULT_SEARCH_KINDS)
    if len(query_tokens) <= 1:
        selected_kinds = [
            kind
            for kind in selected_kinds
            if kind == SEARCH_KIND_WORD_EQUIVALENCE
        ]
    results: list[GematriaSearchHit] = []

    query_values_by_method: dict[str, tuple[int, ...]] = {}
    query_totals_by_method: dict[str, int] = {}
    for method in selected_methods:
        gtype, resolved = _resolve_gematria_method(method)
        values = tuple(Hebrew(token).gematria(gtype) for token in query_tokens)
        query_values_by_method[resolved] = values
        query_totals_by_method[resolved] = _query_total(values)

        if SEARCH_KIND_WORD_EQUIVALENCE in selected_kinds:
            results.extend(
                _search_word_equivalences(
                    query=query,
                    query_normalized=normalized_query,
                    query_tokens=query_tokens,
                    query_values=values,
                    gematria_method=resolved,
                    corpus_scope=scope,
                    book=book,
                    max_results_per_method=max_results_per_method,
                )
            )
        if SEARCH_KIND_TOKEN_SEQUENCE in selected_kinds:
            results.extend(
                _search_token_sequences(
                    query=query,
                    query_normalized=normalized_query,
                    query_tokens=query_tokens,
                    query_values=values,
                    gematria_method=resolved,
                    corpus_scope=scope,
                    book=book,
                    max_results_per_method=max_results_per_method,
                )
            )
        if SEARCH_KIND_PHRASE_TOTAL in selected_kinds:
            results.extend(
                _search_phrase_totals(
                    query=query,
                    query_normalized=normalized_query,
                    query_tokens=query_tokens,
                    query_values=values,
                    gematria_method=resolved,
                    corpus_scope=scope,
                    book=book,
                    max_span_words=max_span_words,
                    max_results_per_method=max_results_per_method,
                )
            )

    # Deterministic ordering: method, kind, position, then span length.
    kind_priority = {
        SEARCH_KIND_WORD_EQUIVALENCE: 0,
        SEARCH_KIND_TOKEN_SEQUENCE: 1,
        SEARCH_KIND_PHRASE_TOTAL: 2,
    }
    results.sort(
        key=lambda hit: (
            hit.gematria_method,
            kind_priority.get(hit.search_kind, 99),
            hit.result.location_start.book,
            hit.result.location_start.chapter,
            hit.result.location_start.verse,
            hit.result.location_start.word_index or -1,
            hit.result.location_end.word_index if hit.result.location_end else -1,
            hit.token_index if hit.token_index is not None else -1,
        )
    )

    payloads = [hit.to_dict() for hit in results]
    by_method: dict[str, list[dict[str, Any]]] = {}
    by_kind: dict[str, int] = {}
    for payload in payloads:
        by_method.setdefault(str(payload["gematria_method"]), []).append(payload)
        kind = str(payload["search_kind"])
        by_kind[kind] = by_kind.get(kind, 0) + 1

    methods_with_hits = {
        method: len(rows)
        for method, rows in by_method.items()
        if rows
    }

    return {
        "query": query,
        "query_normalized": normalized_query,
        "query_tokens": list(query_tokens),
        "methods": selected_methods,
        "search_kinds": selected_kinds,
        "corpus_scope": scope,
        "book_filter": book,
        "max_span_words": max_span_words,
        "query_values_by_method": {
            method: list(values) for method, values in query_values_by_method.items()
        },
        "query_totals_by_method": query_totals_by_method,
        "results": payloads,
        "by_method": by_method,
        "summary": {
            "total_results": len(payloads),
            "methods_with_hits": methods_with_hits,
            "by_kind": by_kind,
        },
    }
