"""Heuristic reliability scoring for search findings."""

from __future__ import annotations

from autogematria.normalize import FinalsPolicy, extract_letters
from autogematria.search.base import SearchResult

# Full Tanakh letters (approx) used for coarse ELS chance estimates.
_CORPUS_LETTERS_APPROX = 1_200_000


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _label(score: float, verified: bool) -> str:
    if not verified:
        return "invalid"
    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    if score >= 0.40:
        return "low"
    return "very_low"


def _els_expected_per_skip(query_len: int) -> float:
    if query_len <= 0:
        return float("inf")
    return _CORPUS_LETTERS_APPROX * (22 ** (-query_len))


def score_search_result(result: SearchResult, verified: bool) -> dict[str, float | str]:
    """Return a confidence score and label for a single finding."""
    qlen = len(extract_letters(result.query, FinalsPolicy.NORMALIZE))
    method = result.method
    rationale = ""

    if method == "SUBSTRING":
        mode = str(result.params.get("mode", "within_word"))
        if mode == "within_word":
            is_exact = bool(result.params.get("exact_word_match"))
            if is_exact:
                score = 0.98
                rationale = "exact word match"
            elif qlen >= 5:
                score = 0.72
                rationale = "within-word partial embedding (length>=5)"
            elif qlen == 4:
                score = 0.60
                rationale = "within-word partial embedding (length=4)"
            else:
                score = 0.45
                rationale = "within-word partial embedding (short query)"
        else:
            if qlen >= 5:
                score = 0.70
                rationale = "cross-word match (length>=5)"
            elif qlen == 4:
                score = 0.50
                rationale = "cross-word match (length=4)"
            else:
                score = 0.35
                rationale = "cross-word match (short query)"

    elif method in ("ROSHEI_TEVOT", "SOFEI_TEVOT"):
        span = int(result.params.get("word_span") or max(qlen, 2))
        score = 0.55 + min(0.25, max(0, span - 3) * 0.05)
        rationale = f"acrostic over {span} words"

    elif method == "ELS":
        skip = abs(int(result.params.get("skip") or int(result.raw_score or 0)))
        if skip <= 2:
            score = 0.55
        elif skip <= 10:
            score = 0.40
        elif skip <= 50:
            score = 0.28
        elif skip <= 100:
            score = 0.20
        elif skip <= 300:
            score = 0.13
        elif skip <= 800:
            score = 0.09
        else:
            score = 0.05

        score += min(0.25, max(0, qlen - 4) * 0.04)
        expected = _els_expected_per_skip(qlen)
        if expected > 0.5:
            score -= 0.12
        elif expected > 0.1:
            score -= 0.08
        elif expected > 0.03:
            score -= 0.04

        rationale = f"ELS skip={skip}, query_len={qlen}, expected_per_skip≈{expected:.4f}"
    else:
        score = 0.2
        rationale = "unknown method"

    if not verified:
        score = 0.0

    score = _clamp(score)
    return {
        "score": round(score, 4),
        "label": _label(score, verified),
        "rationale": rationale,
    }
