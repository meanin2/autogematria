"""Typed Python tool functions for LLM consumption.

These are the primary interface for AI agents to interact with the
AutoGematria system. Each function returns a structured dict.
"""

from __future__ import annotations

from copy import deepcopy
import sqlite3
from typing import Any

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import DB_PATH, normalize_corpus_scope
from autogematria.gematria_connections import gematria_connections as build_gematria_connections
from autogematria.normalize import normalize_hebrew, extract_letters, FinalsPolicy
from autogematria.research import ResearchConfig, run_name_research as run_bounded_name_research
from autogematria.research.presentation import build_showcase
from autogematria.scoring.calibrated import CandidateEvidence, score_candidates
from autogematria.scoring.verdict import aggregate_full_name_verdict, build_token_support
from autogematria.search.gematria import GematriaSearch
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


def _result_method(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("method", "?"))
    return str(getattr(row, "method", "?"))


def _diversify_results(results, max_results: int):
    """Select a balanced top-N across methods in round-robin order."""
    if not results:
        return []

    method_order = ["SUBSTRING", "ROSHEI_TEVOT", "SOFEI_TEVOT", "ELS"]
    buckets: dict[str, list] = {m: [] for m in method_order}
    extras: list = []
    for result in results:
        method = _result_method(result)
        if method in buckets:
            buckets[method].append(result)
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


def _pack_scored_candidate(scored) -> dict[str, Any]:
    r = scored.result
    payload = {
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
        "confidence": {
            "score": scored.score,
            "label": scored.label,
            "rationale": scored.rationale,
            "features": scored.features,
        },
    }
    if scored.verification is not None:
        payload["verification"] = scored.verification
    return payload


def _build_token_fallback_rows(
    *,
    tokens: list[str],
    token_results: dict[str, dict[str, Any]],
    token_support: dict[str, dict[str, Any]],
    max_results: int,
) -> list[dict[str, Any]]:
    """Build conservative multi-word fallback rows from per-token evidence."""
    if len(tokens) < 2:
        return []

    first = tokens[0]
    surname = tokens[-1]
    first_support = token_support.get(first) or {}
    surname_support = token_support.get(surname) or {}

    # Guardrail: only allow fallback when first-name evidence is direct exact.
    if not bool(first_support.get("has_direct_exact")):
        return []

    surname_skip = int(surname_support.get("best_skip") or 10_000)
    surname_score = float(surname_support.get("best_score") or 0.0)
    surname_quality_signal = bool(surname_support.get("has_direct_exact")) or (
        surname_support.get("best_method") == "ELS"
        and bool(surname_support.get("has_any_support"))
        and surname_score >= 0.58
        and surname_skip <= 10
    )
    if not surname_quality_signal:
        return []

    if not all(bool(token_support.get(token, {}).get("has_any_support")) for token in tokens):
        return []

    rows: list[dict[str, Any]] = []
    for token in tokens:
        candidates = (token_results.get(token) or {}).get("results") or []
        if not candidates:
            return []
        chosen = next(
            (
                row
                for row in candidates
                if bool((row.get("verification") or {}).get("verified"))
            ),
            candidates[0],
        )
        row = deepcopy(chosen)
        params = row.get("params") or {}
        params["derived_from_token"] = token
        params["fallback_mode"] = "token_support"
        row["params"] = params

        confidence = row.get("confidence") or {}
        features = confidence.get("features") or {}
        features["token_fallback"] = True
        features["fallback_token"] = token
        confidence["features"] = features
        row["confidence"] = confidence
        rows.append(row)

    rows.sort(
        key=lambda row: float(((row.get("confidence") or {}).get("score") or 0.0)),
        reverse=True,
    )
    return rows[:max_results]


def _run_search_pipeline(
    name: str,
    methods: list[str] | None = None,
    book: str | None = None,
    max_results: int = 20,
    els_max_skip: int = 500,
    include_verification: bool = True,
    diversify_methods: bool = True,
    corpus_scope: str = "torah",
) -> dict[str, Any]:
    scope = normalize_corpus_scope(corpus_scope)
    cfg = UnifiedSearchConfig(
        enable_substring=methods is None or "substring" in methods,
        enable_roshei=methods is None or "roshei_tevot" in methods,
        enable_sofei=methods is None or "sofei_tevot" in methods,
        enable_els=methods is None or "els" in methods,
        els_max_skip=els_max_skip,
        els_direction="both",
        els_use_fast=True,
        max_results_per_method=max(max_results, 20),
        book=book,
        corpus_scope=scope,
    )
    searcher = UnifiedSearch(cfg)
    raw_results = searcher.search(name)

    verify_conn = _conn() if include_verification else None
    candidates: list[CandidateEvidence] = []
    try:
        for row in raw_results:
            verification_payload = None
            if verify_conn is not None:
                verification_payload = build_verification_payload(verify_conn, row)
            candidates.append(CandidateEvidence(result=row, verification=verification_payload))
    finally:
        if verify_conn is not None:
            verify_conn.close()

    scored = score_candidates(name, candidates, corpus_scope=scope)
    ranked_payloads = [_pack_scored_candidate(s) for s in scored[:max_results]]
    display_payloads = (
        _diversify_results(ranked_payloads, max_results) if diversify_methods else ranked_payloads
    )
    return {
        "raw_results": raw_results,
        "ranked_results": ranked_payloads,
        "display_results": display_payloads,
        "corpus_scope": scope,
    }


def find_name_in_torah(
    name: str,
    methods: list[str] | None = None,
    book: str | None = None,
    max_results: int = 20,
    els_max_skip: int = 500,
    include_verification: bool = True,
    diversify_methods: bool = True,
    corpus_scope: str = "torah",
) -> dict[str, Any]:
    """Search for a Hebrew name with conservative evidence aggregation.

    Args:
        name: Hebrew name to search for (e.g. "משה", "אברהם")
        methods: Subset of ["substring", "roshei_tevot", "sofei_tevot", "els"].
                 None = all methods.
        book: Restrict search to a specific book
        max_results: Maximum total results to return
        els_max_skip: Maximum ELS skip distance to search
        include_verification: Include deterministic verification payload per result
        diversify_methods: Apply round-robin for display-only results
        corpus_scope: "torah" (default) or "tanakh"

    Returns:
        Dict with deterministic ranked evidence + final verdict.
    """
    pipeline = _run_search_pipeline(
        name=name,
        methods=methods,
        book=book,
        max_results=max_results,
        els_max_skip=els_max_skip,
        include_verification=include_verification,
        diversify_methods=diversify_methods,
        corpus_scope=corpus_scope,
    )
    ranked_results = pipeline["ranked_results"]
    display_results = pipeline["display_results"]
    scope = pipeline["corpus_scope"]

    tokens = [t for t in name.split() if t]
    token_results: dict[str, dict[str, Any]] = {}
    token_support: dict[str, dict[str, Any]] = {}
    if len(tokens) > 1:
        for token in tokens:
            token_result = _run_search_pipeline(
                name=token,
                methods=methods,
                book=book,
                max_results=min(10, max_results),
                els_max_skip=els_max_skip,
                include_verification=include_verification,
                diversify_methods=False,
                corpus_scope=scope,
            )
            token_results[token] = {
                "total_results": len(token_result["ranked_results"]),
                "results": token_result["ranked_results"],
            }
        token_support = build_token_support(token_results, tokens)

        all_tokens_supported = all(v.get("has_any_support") for v in token_support.values())
        surname = tokens[-1]
        surname_support = token_support.get(surname, {})
        surname_only_high_skip_els = (
            surname_support.get("best_method") == "ELS"
            and not surname_support.get("has_direct_exact")
            and int(surname_support.get("best_skip") or 0) >= 80
        )
        for row in ranked_results:
            features = ((row.get("confidence") or {}).get("features") or {})
            features["all_tokens_independently_supported"] = all_tokens_supported
            features["surname_only_high_skip_els"] = surname_only_high_skip_els

        if not ranked_results:
            fallback_rows = _build_token_fallback_rows(
                tokens=tokens,
                token_results=token_results,
                token_support=token_support,
                max_results=max_results,
            )
            if fallback_rows:
                ranked_results = fallback_rows
                display_results = (
                    _diversify_results(ranked_results, max_results)
                    if diversify_methods
                    else ranked_results
                )

    final_verdict = aggregate_full_name_verdict(
        query=name,
        ranked_results=ranked_results,
        token_support=token_support if token_support else None,
        corpus_scope=scope,
    )

    return {
        "query": name,
        "query_normalized": extract_letters(name, FinalsPolicy.NORMALIZE),
        "book_filter": book,
        "corpus_scope": scope,
        "total_results": len(display_results),
        "results": display_results,
        "ranked_results": ranked_results,
        "best_evidence": ranked_results[0] if ranked_results else None,
        "word_results": token_results if token_results else None,
        "final_verdict": final_verdict,
    }


def gematria_pattern_search(
    query: str,
    methods: list[str] | None = None,
    book: str | None = None,
    max_results: int = 20,
    max_span_words: int = 4,
    include_verification: bool = True,
    corpus_scope: str = "torah",
) -> dict[str, Any]:
    """Search the corpus by gematria value/signature using bounded, traceable methods."""
    scope = normalize_corpus_scope(corpus_scope)
    searcher = GematriaSearch(DB_PATH)
    raw_results = searcher.search(
        query,
        methods=methods,
        book=book,
        max_results=max_results,
        max_span_words=max_span_words,
        corpus_scope=scope,
    )

    verify_conn = _conn() if include_verification else None
    candidates: list[CandidateEvidence] = []
    try:
        for row in raw_results:
            verification_payload = None
            if verify_conn is not None:
                verification_payload = build_verification_payload(verify_conn, row)
            candidates.append(CandidateEvidence(result=row, verification=verification_payload))
    finally:
        if verify_conn is not None:
            verify_conn.close()

    scored = score_candidates(query, candidates, corpus_scope=scope)
    results = [_pack_scored_candidate(item) for item in scored[:max_results]]
    return {
        "query": query,
        "query_normalized": extract_letters(query, FinalsPolicy.NORMALIZE),
        "book_filter": book,
        "corpus_scope": scope,
        "methods_requested": methods or ["MISPAR_HECHRACHI"],
        "max_span_words": max_span_words,
        "total_results": len(results),
        "results": results,
        "best_evidence": results[0] if results else None,
    }


def run_name_research(
    query: str,
    *,
    corpus_scope: str = "torah",
    include_tanakh_expansion: bool = True,
    methods: list[str] | None = None,
    max_variants: int = 16,
    max_tasks: int = 80,
    max_results_per_task: int = 12,
    els_max_skip: int = 120,
    gematria_methods: list[str] | None = None,
    max_gematria_span_words: int = 4,
) -> dict[str, Any]:
    """Run the bounded multi-method research workflow."""
    text_methods = tuple(method for method in (methods or ("substring", "roshei_tevot", "sofei_tevot", "els", "gematria")) if method != "gematria")
    corpus_scopes = (corpus_scope, "tanakh") if include_tanakh_expansion and corpus_scope == "torah" else (corpus_scope,)
    config = ResearchConfig(
        text_methods=text_methods or ResearchConfig().text_methods,
        max_variants=max_variants,
        max_tasks=max_tasks,
        corpus_scopes=corpus_scopes,
        max_text_results_per_task=max_results_per_task,
        max_gematria_results_per_task=max_results_per_task,
        els_max_skip=els_max_skip,
        gematria_methods=tuple(gematria_methods or ResearchConfig().gematria_methods),
        max_gematria_span_words=max_gematria_span_words,
    )
    return run_bounded_name_research(query, config=config)


def showcase_name(
    query: str,
    *,
    corpus_scope: str = "torah",
    include_tanakh_expansion: bool = True,
    methods: list[str] | None = None,
    max_variants: int = 12,
    max_tasks: int = 60,
    max_results_per_task: int = 8,
    els_max_skip: int = 80,
    gematria_methods: list[str] | None = None,
    max_gematria_span_words: int = 3,
) -> dict[str, Any]:
    """Return a curated, presentable view over the full research ledger."""
    research = run_name_research(
        query,
        corpus_scope=corpus_scope,
        include_tanakh_expansion=include_tanakh_expansion,
        methods=methods,
        max_variants=max_variants,
        max_tasks=max_tasks,
        max_results_per_task=max_results_per_task,
        els_max_skip=els_max_skip,
        gematria_methods=gematria_methods,
        max_gematria_span_words=max_gematria_span_words,
    )
    return {
        "query": query,
        "showcase": build_showcase(research),
        "research": research,
    }


def gematria_lookup(
    word: str,
    method: str = "MISPAR_HECHRACHI",
    max_equivalents: int = 20,
    include_connections: bool = True,
) -> dict[str, Any]:
    """Compute gematria value and find all Tanakh words with the same value.

    Args:
        word: Hebrew word to compute gematria for
        method: Gematria method name (e.g. "MISPAR_HECHRACHI", "MISPAR_GADOL", "ATBASH")
        max_equivalents: Max equivalent words to return
        include_connections: Include source-backed connection graph payload

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

    connections = None
    if include_connections:
        connections = build_gematria_connections(
            word,
            method=resolved_method,
            max_equivalents=max(80, max_equivalents),
            max_related=15,
            db_path=DB_PATH,
        )

    return {
        "word": word,
        "normalized": clean,
        "method_requested": method,
        "method": resolved_method,
        "value": value,
        "total_equivalents": len(equivalents),
        "equivalents": equivalents,
        "connections": connections,
    }


def gematria_connections(
    word: str,
    method: str = "MISPAR_HECHRACHI",
    max_related: int = 20,
) -> dict[str, Any]:
    """Return source-backed and graph-ranked gematria connections for a word."""
    return build_gematria_connections(
        word,
        method=method,
        max_equivalents=max(120, max_related * 3),
        max_related=max_related,
        db_path=DB_PATH,
    )


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
