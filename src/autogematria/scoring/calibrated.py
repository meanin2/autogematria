"""Deterministic evidence scoring for search candidates."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from autogematria.config import DB_PATH, normalize_corpus_scope
from autogematria.normalize import FinalsPolicy, extract_letters
from autogematria.search.base import SearchResult
from autogematria.stats.null_models import letter_frequency_shuffle, markov_chain_null
from autogematria.stats.significance import empirical_p_value


_LETTERS_IN_HEBREW_ALPHABET = 22
_NULL_PERMUTATIONS = 6
_NULL_WINDOW_RADIUS = 1600


@dataclass(frozen=True)
class CandidateEvidence:
    """A raw candidate and its deterministic verification payload."""

    result: SearchResult
    verification: dict[str, Any] | None


@dataclass(frozen=True)
class ScoredCandidate:
    """A candidate enriched with calibrated evidence features."""

    result: SearchResult
    verification: dict[str, Any] | None
    score: float
    label: str
    rationale: str
    features: dict[str, Any]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _label(score: float, verified: bool) -> str:
    if not verified:
        return "invalid"
    if score >= 0.82:
        return "high"
    if score >= 0.62:
        return "medium"
    if score >= 0.42:
        return "low"
    return "very_low"


@lru_cache(maxsize=8)
def _scope_letter_string(db_path_str: str, corpus_scope: str) -> str:
    conn = sqlite3.connect(db_path_str)
    conn.row_factory = sqlite3.Row
    scope = normalize_corpus_scope(corpus_scope)
    if scope == "torah":
        rows = conn.execute(
            "SELECT l.letter_normalized FROM letters l "
            "JOIN books b ON l.book_id = b.book_id "
            "WHERE b.category = 'Torah' "
            "ORDER BY l.absolute_letter_index"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT letter_normalized FROM letters ORDER BY absolute_letter_index"
        ).fetchall()
    conn.close()
    return "".join(r["letter_normalized"] for r in rows)


def _count_els_hits(text: str, pattern: str, skip: int) -> int:
    if skip <= 0 or len(pattern) < 2:
        return 0
    count = 0
    for offset in range(skip):
        sub = text[offset::skip]
        start = 0
        while True:
            idx = sub.find(pattern, start)
            if idx == -1:
                break
            count += 1
            start = idx + 1
    return count


def _compute_local_null_features(
    *,
    corpus_text: str,
    query_norm: str,
    start_index: int,
    skip: int,
) -> dict[str, float | int]:
    if len(query_norm) < 2 or skip <= 0 or not corpus_text:
        return {
            "null_model_p_shuffle": 1.0,
            "null_model_p_markov": 1.0,
            "null_model_observed_hits": 0,
            "null_model_window_len": 0,
        }

    span = (len(query_norm) - 1) * skip
    low = max(0, start_index - _NULL_WINDOW_RADIUS)
    high = min(len(corpus_text), start_index + span + _NULL_WINDOW_RADIUS + 1)
    window = corpus_text[low:high]
    observed_hits = _count_els_hits(window, query_norm, skip)

    shuffle_counts: list[int] = []
    markov_counts: list[int] = []
    for i in range(_NULL_PERMUTATIONS):
        shuffle_text = letter_frequency_shuffle(window, seed=613 + i)
        markov_text = markov_chain_null(window, order=2, seed=991 + i)
        shuffle_counts.append(_count_els_hits(shuffle_text, query_norm, skip))
        markov_counts.append(_count_els_hits(markov_text, query_norm, skip))

    return {
        "null_model_p_shuffle": round(empirical_p_value(observed_hits, shuffle_counts), 6),
        "null_model_p_markov": round(empirical_p_value(observed_hits, markov_counts), 6),
        "null_model_observed_hits": observed_hits,
        "null_model_window_len": len(window),
    }


def _match_type(result: SearchResult, is_multi_word_query: bool) -> str:
    if result.method == "SUBSTRING":
        mode = str(result.params.get("mode", "within_word"))
        if mode == "within_word" and bool(result.params.get("exact_word_match")):
            return "exact_word"
        if mode == "cross_word" and is_multi_word_query:
            return "exact_phrase"
        if mode == "cross_word":
            return "cross_word"
        return "partial_word"
    if result.method in ("ROSHEI_TEVOT", "SOFEI_TEVOT"):
        return "acrostic"
    if result.method == "ELS":
        return "els"
    if result.method == "GEMATRIA":
        mode = str(result.params.get("mode", "exact_word"))
        if mode == "exact_word":
            return "gematria_exact_word"
        if mode == "contiguous_span":
            return "gematria_span"
        return "gematria"
    if result.method == "ELS_PROXIMITY":
        return "els_proximity"
    return "other"


def _estimate_analytic_els_p(query_len: int, skip: int, scope_letters: int) -> float:
    if query_len < 2 or skip <= 0 or scope_letters <= 0:
        return 1.0
    span = (query_len - 1) * skip
    opportunities = max(scope_letters - span, 1)
    single_prob = _LETTERS_IN_HEBREW_ALPHABET ** (-query_len)
    expected = opportunities * single_prob
    return _clamp(1.0 - math.exp(-expected))


def _verse_distance(
    conn: sqlite3.Connection,
    cache: dict[tuple[str, int, int], int],
    result: SearchResult,
) -> int:
    if result.location_end is None:
        return 1

    def _verse_id(loc_book: str, loc_ch: int, loc_vs: int) -> int | None:
        key = (loc_book, loc_ch, loc_vs)
        if key in cache:
            return cache[key]
        row = conn.execute(
            "SELECT v.verse_id FROM verses v "
            "JOIN chapters c ON v.chapter_id = c.chapter_id "
            "JOIN books b ON c.book_id = b.book_id "
            "WHERE b.api_name=? AND c.chapter_num=? AND v.verse_num=?",
            key,
        ).fetchone()
        if not row:
            cache[key] = -1
            return None
        verse_id = int(row["verse_id"])
        cache[key] = verse_id
        return verse_id

    first = _verse_id(
        result.location_start.book,
        result.location_start.chapter,
        result.location_start.verse,
    )
    last = _verse_id(
        result.location_end.book,
        result.location_end.chapter,
        result.location_end.verse,
    )
    if first is None or last is None:
        return 1
    return abs(last - first) + 1


def score_candidates(
    query: str,
    candidates: list[CandidateEvidence],
    *,
    corpus_scope: str = "torah",
    db_path=DB_PATH,
) -> list[ScoredCandidate]:
    """Score raw search candidates with calibrated transparent features."""
    scope = normalize_corpus_scope(corpus_scope)
    query_norm = extract_letters(query, FinalsPolicy.NORMALIZE)
    query_tokens = [t for t in query.split() if t]
    is_multi_word_query = len(query_tokens) > 1

    exact_direct_exists = any(
        c.result.method == "SUBSTRING"
        and c.result.params.get("mode") == "within_word"
        and bool(c.result.params.get("exact_word_match"))
        for c in candidates
    )

    els_candidates = [c for c in candidates if c.result.method == "ELS"]
    els_null_candidates: set[int] = set()
    els_ranked_for_nulls = sorted(
        enumerate(candidates),
        key=lambda item: abs(int(item[1].result.params.get("skip") or 10_000)),
    )
    for idx, item in els_ranked_for_nulls:
        if item.result.method != "ELS":
            continue
        els_null_candidates.add(idx)
        if len(els_null_candidates) >= 5:
            break

    scope_text = _scope_letter_string(str(db_path), scope)
    scope_letters = len(scope_text)
    verse_cache: dict[tuple[str, int, int], int] = {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        scored: list[ScoredCandidate] = []
        for idx, candidate in enumerate(candidates):
            result = candidate.result
            verification = candidate.verification or {}
            verified = bool(verification.get("verified"))
            match_type = _match_type(result, is_multi_word_query)
            query_len = len(query_norm)

            span = query_len
            if (
                result.location_start.letter_index is not None
                and result.location_end is not None
                and result.location_end.letter_index is not None
            ):
                span = abs(result.location_end.letter_index - result.location_start.letter_index) + 1
            elif (
                result.location_start.word_index is not None
                and result.location_end is not None
                and result.location_end.word_index is not None
            ):
                span = max(
                    query_len,
                    abs(result.location_end.word_index - result.location_start.word_index) + 1,
                )
            span = max(1, span)
            compactness = round(query_len / span, 6)
            verses_crossed = _verse_distance(conn, verse_cache, result)

            skip_size = 0
            if result.method == "ELS":
                skip_size = abs(int(result.params.get("skip") or result.raw_score or 0))

            local_density = 0
            if result.method == "ELS":
                my_skip = skip_size
                my_start = int(result.params.get("start_index") or -1)
                for other in els_candidates:
                    if other is candidate:
                        continue
                    other_skip = abs(int(other.result.params.get("skip") or 0))
                    other_start = int(other.result.params.get("start_index") or -1)
                    if abs(other_skip - my_skip) <= 2 and abs(other_start - my_start) <= 1200:
                        local_density += 1

            analytic_p = 1.0
            null_features: dict[str, float | int] = {
                "null_model_p_shuffle": 1.0,
                "null_model_p_markov": 1.0,
                "null_model_observed_hits": 0,
                "null_model_window_len": 0,
            }
            if result.method == "ELS" and skip_size > 0:
                analytic_p = _estimate_analytic_els_p(query_len, skip_size, scope_letters)
                if idx in els_null_candidates:
                    start_index = int(result.params.get("start_index") or 0)
                    null_features = _compute_local_null_features(
                        corpus_text=scope_text,
                        query_norm=query_norm,
                        start_index=start_index,
                        skip=skip_size,
                    )

            null_rarity_p = max(
                analytic_p,
                float(null_features["null_model_p_shuffle"]),
                float(null_features["null_model_p_markov"]),
            )

            score = 0.0
            rationale = "verification failed"
            if verified:
                if result.method == "SUBSTRING":
                    if match_type == "exact_phrase":
                        score = 0.99
                        rationale = "exact full-phrase substring hit"
                    elif match_type == "exact_word":
                        score = 0.95
                        rationale = "exact single-word direct hit"
                    elif match_type == "cross_word":
                        score = 0.78
                        rationale = "cross-word contiguous substring match"
                    else:
                        if query_len >= 5:
                            score = 0.68
                        elif query_len == 4:
                            score = 0.58
                        else:
                            score = 0.47
                        rationale = "within-word partial substring match"
                    if is_multi_word_query and match_type != "exact_phrase":
                        score -= 0.06

                elif result.method in ("ROSHEI_TEVOT", "SOFEI_TEVOT"):
                    word_span = int(result.params.get("word_span") or max(query_len, 2))
                    score = 0.42 + min(0.16, max(0, query_len - 2) * 0.03)
                    score += min(0.08, max(0, word_span - 3) * 0.02)
                    score -= min(0.12, max(0, verses_crossed - 1) * 0.03)
                    if is_multi_word_query:
                        score -= 0.04
                    rationale = f"acrostic over {word_span} words"

                elif result.method == "ELS":
                    skip_factor = 1.0 - min(skip_size, 400) / 400
                    rarity_bonus = 1.0 - null_rarity_p
                    score = 0.18
                    score += 0.28 * skip_factor
                    score += 0.32 * rarity_bonus
                    score += 0.18 * compactness
                    score -= min(0.2, max(0, verses_crossed - 1) * 0.03)
                    score -= min(0.18, local_density * 0.04)
                    if skip_size > 120:
                        score -= 0.08
                    if is_multi_word_query:
                        score -= 0.05
                    if query_len <= 3:
                        score -= 0.05
                    rationale = (
                        f"ELS skip={skip_size}, compactness={compactness:.4f}, "
                        f"rarity_p={null_rarity_p:.4f}"
                    )
                elif result.method == "ELS_PROXIMITY":
                    distance = int(result.params.get("proximity_distance") or result.raw_score or 10000)
                    surname_skip = abs(int(result.params.get("surname_skip") or 100))
                    firstname_skip = abs(int(result.params.get("firstname_skip") or 0))
                    # Proximity factor: closer = much better
                    if distance <= 50:
                        prox_factor = 1.0
                    elif distance <= 200:
                        prox_factor = 0.85
                    elif distance <= 500:
                        prox_factor = 0.65
                    elif distance <= 2000:
                        prox_factor = 0.40
                    else:
                        prox_factor = 0.15
                    surname_skip_factor = 1.0 - min(surname_skip, 400) / 400
                    firstname_skip_factor = 1.0 - min(firstname_skip, 400) / 400
                    score = (
                        0.30
                        + 0.30 * prox_factor
                        + 0.20 * surname_skip_factor
                        + 0.10 * firstname_skip_factor
                    )
                    # Bonus: if first name is a direct match (skip=0), that's ideal
                    if firstname_skip == 0:
                        score += 0.08
                    rationale = (
                        f"ELS proximity: distance={distance}, "
                        f"surname_skip={surname_skip}, "
                        f"firstname_skip={firstname_skip}"
                    )

                elif result.method == "GEMATRIA":
                    gematria_mode = str(result.params.get("mode", "exact_word"))
                    word_span = int(result.params.get("word_span") or max(query_len, 1))
                    gematria_method = str(result.params.get("gematria_method", "MISPAR_HECHRACHI"))
                    if gematria_mode == "exact_word":
                        score = 0.56
                        if gematria_method == "MISPAR_HECHRACHI":
                            score += 0.06
                        rationale = f"gematria exact-word match via {gematria_method}"
                    else:
                        score = 0.44
                        score += min(0.1, max(0, query_len - 3) * 0.02)
                        score -= min(0.12, max(0, word_span - 2) * 0.03)
                        if gematria_method == "MISPAR_HECHRACHI":
                            score += 0.04
                        rationale = (
                            f"gematria contiguous-span match via {gematria_method} "
                            f"over {word_span} words"
                        )
                    if is_multi_word_query and gematria_mode != "contiguous_span":
                        score -= 0.04
                else:
                    score = 0.2
                    rationale = "unsupported method type"

            score = round(_clamp(score), 4)
            label = _label(score, verified)
            features = {
                "method": result.method,
                "match_type": match_type,
                "query_length": query_len,
                "is_multi_word_query": is_multi_word_query,
                "skip_size": skip_size,
                "total_span": span,
                "verses_crossed": verses_crossed,
                "compactness": compactness,
                "local_density": local_density,
                "null_rarity_p": round(null_rarity_p, 6),
                "analytic_null_p": round(analytic_p, 6),
                "null_model_p_shuffle": null_features["null_model_p_shuffle"],
                "null_model_p_markov": null_features["null_model_p_markov"],
                "null_model_observed_hits": null_features["null_model_observed_hits"],
                "null_model_window_len": null_features["null_model_window_len"],
                "direct_exact_exists_elsewhere": exact_direct_exists,
                "source_backed": None,
                "surname_only_high_skip_els": False,
                "all_tokens_independently_supported": False,
                "corpus_scope": scope,
            }

            scored.append(
                ScoredCandidate(
                    result=result,
                    verification=candidate.verification,
                    score=score,
                    label=label,
                    rationale=rationale,
                    features=features,
                )
            )
    finally:
        conn.close()

    method_priority = {"SUBSTRING": 0, "ELS_PROXIMITY": 1, "ROSHEI_TEVOT": 2, "SOFEI_TEVOT": 3, "ELS": 4}
    scored.sort(
        key=lambda s: (
            -s.score,
            method_priority.get(s.result.method, 9),
            abs(int(s.result.params.get("skip") or 0)),
            s.result.location_start.book,
            s.result.location_start.chapter,
            s.result.location_start.verse,
        )
    )
    return scored
