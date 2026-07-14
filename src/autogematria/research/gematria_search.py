"""Corpus-wide gematria search primitives."""

from __future__ import annotations

from array import array
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any, Iterable

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import DB_PATH, normalize_corpus_scope
from autogematria.normalize import FinalsPolicy, normalize_hebrew
from autogematria.research.schema import ResearchFinding, ResearchVariant
from autogematria.runtime_data import DataValidationError, connect_corpus
from autogematria.search.corpus_index import load_tevot_index


@dataclass(frozen=True)
class GematriaSignatureMatch:
    """Internal representation of a gematria hit."""

    method: str
    mode: str
    values: list[int]
    start_index: int
    end_index: int
    matched_words: list[dict[str, Any]]
    score: float
    verification: dict[str, Any]
    rationale: str


def _resolve_method(method: str) -> tuple[GematriaTypes, str]:
    gtype = getattr(GematriaTypes, method, None)
    if gtype is None:
        gtype = GematriaTypes.MISPAR_HECHRACHI
    return gtype, gtype.name


def _gematria_value(text: str, method: str) -> int:
    clean = normalize_hebrew(text, FinalsPolicy.PRESERVE).replace(" ", "")
    gtype, _resolved = _resolve_method(method)
    return Hebrew(clean).gematria(gtype)


@lru_cache(maxsize=8)
def _load_method_values(db_path_str: str, method_name: str) -> array:
    """Load one gematria value per corpus word in a compact signed-int array."""
    conn = connect_corpus(db_path_str, row_factory=False)
    try:
        values = array("q")
        expected_index = 0
        cursor = conn.execute(
            "SELECT w.absolute_word_index, wg.value "
            "FROM words w "
            "JOIN word_forms wf ON w.word_normalized = wf.form_text "
            "JOIN word_gematria wg ON wf.form_id = wg.form_id "
            "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
            "WHERE gm.method_name = ? ORDER BY w.absolute_word_index",
            (method_name,),
        )
        while rows := cursor.fetchmany(10_000):
            for absolute_index, value in rows:
                if int(absolute_index) != expected_index:
                    raise DataValidationError(
                        "gematria values must align with gapless absolute_word_index; "
                        f"expected {expected_index}, found {absolute_index}"
                    )
                values.append(int(value))
                expected_index += 1
        if not values:
            raise DataValidationError(f"No corpus values found for gematria method {method_name}")
        return values
    finally:
        conn.close()


def _search_bounds(
    db_path: str,
    corpus_scope: str,
    book: str | None,
) -> tuple[int, int]:
    """Return an absolute-word half-open interval for a scope/book filter."""
    index = load_tevot_index(db_path)
    scope = normalize_corpus_scope(corpus_scope)
    if book:
        bounds = index.book_offsets.get(book)
        if bounds is None:
            return (0, 0)
        if scope == "torah":
            torah_start, torah_end = index.scope_offsets["torah"]
            if bounds[0] < torah_start or bounds[1] > torah_end:
                return (0, 0)
    else:
        bounds = index.scope_offsets[scope]
    return (bounds[0], bounds[1] + 1)


def _load_word_span(
    db_path: str,
    method_name: str,
    start_index: int,
    end_index: int,
) -> list[dict[str, Any]]:
    """Resolve metadata only for a span that has already matched compact values.

    The caller already searched the cached method-value array. Joining the
    894k-row ``word_gematria`` table again for every match made multi-token
    reports spend several seconds per result span. Resolve the handful of
    words by their indexed absolute positions and attach the cached values.
    """
    conn = connect_corpus(db_path)
    try:
        rows = conn.execute(
            "SELECT w.absolute_word_index, w.word_raw, w.word_normalized, "
            "b.api_name, c.chapter_num, v.verse_num "
            "FROM words w "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE w.absolute_word_index BETWEEN ? AND ? "
            "ORDER BY w.absolute_word_index",
            (start_index, end_index),
        ).fetchall()
        method_values = _load_method_values(db_path, method_name)
        resolved: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["value"] = int(method_values[int(item["absolute_word_index"])])
            resolved.append(item)
        return resolved
    finally:
        conn.close()


def _load_exact_rows(
    db_path: str,
    method_name: str,
    expected_value: int,
    corpus_scope: str,
    book: str | None,
    max_results: int,
) -> list[dict[str, Any]]:
    """Use the value index for single-word equivalences without loading the corpus."""
    conn = connect_corpus(db_path)
    try:
        where = ["gm.method_name = ?", "wg.value = ?"]
        params: list[Any] = [method_name, expected_value]
        scope = normalize_corpus_scope(corpus_scope)
        if scope == "torah":
            where.append("b.category = 'Torah'")
        if book:
            where.append("b.api_name = ?")
            params.append(book)
        rows = conn.execute(
            "SELECT w.absolute_word_index, w.word_raw, w.word_normalized, "
            "wg.value, b.api_name, c.chapter_num, v.verse_num "
            "FROM word_gematria wg "
            "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
            "JOIN word_forms wf ON wg.form_id = wf.form_id "
            "JOIN words w ON wf.form_text = w.word_normalized "
            "JOIN verses v ON w.verse_id = v.verse_id "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY w.absolute_word_index LIMIT ?",
            [*params, max_results],
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _span_is_within_one_book(rows: list[dict[str, Any]], expected_length: int) -> bool:
    return (
        len(rows) == expected_length
        and bool(rows)
        and rows[0]["api_name"] == rows[-1]["api_name"]
    )


def _row_location(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "book": row["api_name"],
        "chapter": row["chapter_num"],
        "verse": row["verse_num"],
        "word_index": row["absolute_word_index"],
    }


def _sequence_score(length: int, values: list[int], mode: str) -> float:
    if mode == "exact_sequence":
        return min(0.97, 0.72 + 0.05 * max(0, length - 1))
    if mode == "sum":
        return min(0.88, 0.6 + 0.03 * length)
    return 0.75


def _make_finding(
    *,
    task_id: str,
    query: str,
    variant: ResearchVariant,
    corpus_scope: str,
    book: str | None,
    analysis_method: str,
    match: GematriaSignatureMatch,
    rank: int,
    total_results: int,
) -> ResearchFinding:
    location = match.matched_words[0]["location"]
    location_end = match.matched_words[-1]["location"] if len(match.matched_words) > 1 else None
    return ResearchFinding(
        task_id=task_id,
        query=query,
        variant=variant,
        family="gematria",
        method=match.method,
        analysis_method=analysis_method,
        corpus_scope=corpus_scope,
        book=book,
        rank=rank,
        total_results=total_results,
        location=location,
        location_end=location_end,
        found_text=" ".join(word["word_raw"] for word in match.matched_words),
        params={
            "mode": match.mode,
            "values": match.values,
            "score": match.score,
            "rationale": match.rationale,
        },
        verification=match.verification,
        confidence={
            "score": match.score,
            "label": "exact" if match.verification.get("verified") else "unverified",
            "rationale": match.rationale,
            "features": {
                "gematria_method": analysis_method,
                "mode": match.mode,
                "sequence_length": len(match.values),
            },
        },
        task_params={"analysis_method": analysis_method},
    )


def _search_exact_word(
    *,
    task_id: str,
    query: str,
    variant: ResearchVariant,
    corpus_scope: str,
    book: str | None,
    method_name: str,
    max_results: int,
) -> list[ResearchFinding]:
    expected = _gematria_value(query, method_name)
    rows = _load_exact_rows(
        str(DB_PATH),
        method_name,
        expected,
        corpus_scope,
        book,
        max_results,
    )
    matches: list[ResearchFinding] = []
    for rank, row in enumerate(rows, 1):
        score = 0.85
        match = GematriaSignatureMatch(
            method="GEMATRIA",
            mode="exact_word",
            values=[expected],
            start_index=int(row["absolute_word_index"]),
            end_index=int(row["absolute_word_index"]),
            matched_words=[{
                "location": _row_location(row),
                "word_raw": row["word_raw"],
                "word_normalized": row["word_normalized"],
                "value": int(row["value"]),
            }],
            score=score,
            verification={
                "verified": int(row["value"]) == expected,
                "expected_value": expected,
                "actual_value": int(row["value"]),
                "method": method_name,
                "mode": "exact_word",
            },
            rationale="exact gematria value match for a single word",
        )
        matches.append(
            _make_finding(
                task_id=task_id,
                query=query,
                variant=variant,
                corpus_scope=corpus_scope,
                book=book,
                analysis_method=method_name,
                match=match,
                rank=rank,
                total_results=0,
            )
        )
    return matches


def _search_exact_sequence(
    *,
    task_id: str,
    query: str,
    variant: ResearchVariant,
    corpus_scope: str,
    book: str | None,
    method_name: str,
    max_results: int,
    max_span: int,
) -> list[ResearchFinding]:
    tokens = [token for token in normalize_hebrew(query, FinalsPolicy.PRESERVE).split() if token]
    if len(tokens) < 2:
        return []

    expected = [_gematria_value(token, method_name) for token in tokens]
    db_path = str(DB_PATH)
    values = _load_method_values(db_path, method_name)
    low, high = _search_bounds(db_path, corpus_scope, book)
    high = min(high, len(values))
    matches: list[ResearchFinding] = []
    for idx in range(low, max(low, high - len(expected) + 1)):
        candidate_values = list(values[idx : idx + len(expected)])
        if candidate_values != expected:
            continue
        candidate = _load_word_span(
            db_path,
            method_name,
            idx,
            idx + len(expected) - 1,
        )
        if not _span_is_within_one_book(candidate, len(expected)):
            continue
        words = [
            {
                "location": _row_location(row),
                "word_raw": row["word_raw"],
                "word_normalized": row["word_normalized"],
                "value": int(row["value"]),
            }
            for row in candidate
        ]
        match = GematriaSignatureMatch(
            method="GEMATRIA",
            mode="exact_sequence",
            values=expected,
            start_index=idx,
            end_index=idx + len(expected) - 1,
            matched_words=words,
            score=_sequence_score(len(expected), expected, "exact_sequence"),
            verification={
                "verified": True,
                "expected_values": expected,
                "actual_values": candidate_values,
                "method": method_name,
                "mode": "exact_sequence",
            },
            rationale="contiguous word gematria sequence matched exactly",
        )
        matches.append(
            _make_finding(
                task_id=task_id,
                query=query,
                variant=variant,
                corpus_scope=corpus_scope,
                book=book,
                analysis_method=method_name,
                match=match,
                rank=len(matches) + 1,
                total_results=0,
            )
        )
        if len(matches) >= max_results:
            break
    return matches


def _search_sum_patterns(
    *,
    task_id: str,
    query: str,
    variant: ResearchVariant,
    corpus_scope: str,
    book: str | None,
    method_name: str,
    max_results: int,
    max_span: int,
) -> list[ResearchFinding]:
    tokens = [token for token in normalize_hebrew(query, FinalsPolicy.PRESERVE).split() if token]
    if not tokens:
        return []

    expected_sum = sum(_gematria_value(token, method_name) for token in tokens)
    db_path = str(DB_PATH)
    values = _load_method_values(db_path, method_name)
    low, high = _search_bounds(db_path, corpus_scope, book)
    high = min(high, len(values))
    if low >= high:
        return []

    matches: list[ResearchFinding] = []
    for start in range(low, high):
        total = 0
        for span in range(1, max_span + 1):
            end = start + span
            if end > high:
                break
            total += int(values[end - 1])
            if total > expected_sum:
                break
            if total != expected_sum:
                continue
            candidate = _load_word_span(db_path, method_name, start, end - 1)
            if not _span_is_within_one_book(candidate, span):
                continue
            words = [
                {
                    "location": _row_location(row),
                    "word_raw": row["word_raw"],
                    "word_normalized": row["word_normalized"],
                    "value": int(row["value"]),
                }
                for row in candidate
            ]
            match = GematriaSignatureMatch(
                method="GEMATRIA",
                mode="sum",
                values=[int(row["value"]) for row in candidate],
                start_index=int(candidate[0]["absolute_word_index"]),
                end_index=int(candidate[-1]["absolute_word_index"]),
                matched_words=words,
                score=_sequence_score(span, [expected_sum], "sum"),
                verification={
                    "verified": True,
                    "expected_sum": expected_sum,
                    "actual_sum": total,
                    "method": method_name,
                    "mode": "sum",
                },
                rationale="contiguous word span summed to the expected gematria total",
            )
            matches.append(
                _make_finding(
                    task_id=task_id,
                    query=query,
                    variant=variant,
                    corpus_scope=corpus_scope,
                    book=book,
                    analysis_method=method_name,
                    match=match,
                    rank=len(matches) + 1,
                    total_results=0,
                )
            )
            if len(matches) >= max_results:
                return matches
    return matches


def search_gematria_signatures(
    query: str,
    *,
    methods: Iterable[str] | None = None,
    corpus_scope: str = "tanakh",
    book: str | None = None,
    max_results: int = 20,
    max_sequence_span: int = 4,
    variant: ResearchVariant | None = None,
    task_id: str = "gematria",
) -> list[ResearchFinding]:
    """Search the corpus by gematria signatures across multiple methods."""
    clean = normalize_hebrew(query, FinalsPolicy.PRESERVE)
    chosen_variant = variant or ResearchVariant(
        text=clean,
        source="gematria_search",
        kind="direct",
        token_count=len(clean.split()) if clean else 0,
    )
    analysis_methods = list(methods or ())
    if not analysis_methods:
        analysis_methods = ["MISPAR_HECHRACHI"]

    findings: list[ResearchFinding] = []
    for method_name in analysis_methods:
        exact_hits = _search_exact_word(
            task_id=task_id,
            query=clean,
            variant=chosen_variant,
            corpus_scope=corpus_scope,
            book=book,
            method_name=method_name,
            max_results=max_results,
        )
        findings.extend(exact_hits)
        if len(findings) >= max_results:
            return findings[:max_results]

        seq_hits = _search_exact_sequence(
            task_id=task_id,
            query=clean,
            variant=chosen_variant,
            corpus_scope=corpus_scope,
            book=book,
            method_name=method_name,
            max_results=max_results,
            max_span=max_sequence_span,
        )
        findings.extend(seq_hits)
        if len(findings) >= max_results:
            return findings[:max_results]

        sum_hits = _search_sum_patterns(
            task_id=task_id,
            query=clean,
            variant=chosen_variant,
            corpus_scope=corpus_scope,
            book=book,
            method_name=method_name,
            max_results=max_results,
            max_span=max_sequence_span,
        )
        findings.extend(sum_hits)
        if len(findings) >= max_results:
            return findings[:max_results]

    total = len(findings)
    return [replace(finding, total_results=total) for finding in findings[:max_results]]
