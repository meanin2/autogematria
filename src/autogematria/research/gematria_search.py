"""Corpus-wide gematria search primitives."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from dataclasses import replace
from typing import Any, Iterable

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import DB_PATH, normalize_corpus_scope
from autogematria.normalize import FinalsPolicy, normalize_hebrew
from autogematria.research.schema import ResearchFinding, ResearchVariant


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


@lru_cache(maxsize=12)
def _load_method_rows(
    db_path_str: str,
    method_name: str,
    corpus_scope: str,
    book: str | None,
) -> tuple[dict[str, Any], ...]:
    conn = sqlite3.connect(db_path_str)
    conn.row_factory = sqlite3.Row
    try:
        params: list[Any] = [method_name]
        where = ["gm.method_name = ?"]
        scope = normalize_corpus_scope(corpus_scope)
        if scope == "torah":
            where.append("b.category = 'Torah'")
        if book:
            where.append("b.api_name = ?")
            params.append(book)

        sql = (
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
            "ORDER BY w.absolute_word_index"
        )
        rows = conn.execute(sql, params).fetchall()
        return tuple(dict(row) for row in rows)
    finally:
        conn.close()


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
    rows = _load_method_rows(str(DB_PATH), method_name, corpus_scope, book)
    expected = _gematria_value(query, method_name)
    matches: list[ResearchFinding] = []
    for rank, row in enumerate((row for row in rows if int(row["value"]) == expected), 1):
        if len(matches) >= max_results:
            break
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


def _window_rows(rows: tuple[dict[str, Any], ...], start: int, span: int) -> list[dict[str, Any]]:
    return list(rows[start : start + span])


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
    rows = _load_method_rows(str(DB_PATH), method_name, corpus_scope, book)
    matches: list[ResearchFinding] = []
    for idx in range(0, max(0, len(rows) - len(expected) + 1)):
        candidate = rows[idx : idx + len(expected)]
        candidate_values = [int(row["value"]) for row in candidate]
        if candidate_values != expected:
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
            start_index=int(candidate[0]["absolute_word_index"]),
            end_index=int(candidate[-1]["absolute_word_index"]),
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
    rows = _load_method_rows(str(DB_PATH), method_name, corpus_scope, book)
    if not rows:
        return []

    prefix: list[int] = [0]
    for row in rows:
        prefix.append(prefix[-1] + int(row["value"]))

    matches: list[ResearchFinding] = []
    for start in range(0, len(rows)):
        for span in range(1, max_span + 1):
            end = start + span
            if end > len(rows):
                break
            total = prefix[end] - prefix[start]
            if total != expected_sum:
                continue
            candidate = _window_rows(rows, start, span)
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
