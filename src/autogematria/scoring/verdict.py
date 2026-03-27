"""Full-query evidence aggregation and abstention logic."""

from __future__ import annotations

from typing import Any


VERDICT_STRONG = "strong_evidence"
VERDICT_MODERATE = "moderate_evidence"
VERDICT_WEAK = "weak_evidence"
VERDICT_NONE = "no_convincing_evidence"
TOKEN_FALLBACK_CONFIDENCE_PENALTY = 0.12

COMMON_FIRST_NAMES = {
    "אברהם",
    "אהרן",
    "אליהו",
    "בנימין",
    "דוד",
    "חיים",
    "יוסף",
    "יהושע",
    "יעקב",
    "יצחק",
    "מאיר",
    "משה",
    "מרים",
    "נח",
    "רחל",
    "שרה",
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _empty_token_support(tokens: list[str]) -> dict[str, dict[str, Any]]:
    return {
        token: {
            "best_score": 0.0,
            "best_label": "invalid",
            "best_method": None,
            "best_skip": None,
            "has_any_support": False,
            "has_direct_exact": False,
        }
        for token in tokens
    }


def build_token_support(token_results: dict[str, dict[str, Any]], tokens: list[str]) -> dict[str, dict[str, Any]]:
    """Summarize per-token evidence for full-name aggregation."""
    support = _empty_token_support(tokens)
    for token in tokens:
        rows = token_results.get(token, {}).get("results", [])
        if not rows:
            continue
        best = rows[0]
        conf = best.get("confidence") or {}
        score = float(conf.get("score", 0.0) or 0.0)
        features = conf.get("features") or {}
        method = best.get("method")
        skip = (best.get("params") or {}).get("skip")

        support[token] = {
            "best_score": score,
            "best_label": str(conf.get("label", "invalid")),
            "best_method": method,
            "best_skip": abs(int(skip)) if skip is not None else None,
            "has_any_support": any(
                float((r.get("confidence") or {}).get("score", 0.0) or 0.0) >= 0.35
                and bool((r.get("verification") or {}).get("verified"))
                for r in rows
            ),
            "has_direct_exact": any(
                r.get("method") == "SUBSTRING"
                and ((r.get("confidence") or {}).get("features") or {}).get("match_type")
                == "exact_word"
                and bool((r.get("verification") or {}).get("verified"))
                for r in rows
            ),
            "match_type": features.get("match_type"),
        }
    return support


def aggregate_full_name_verdict(
    *,
    query: str,
    ranked_results: list[dict[str, Any]],
    token_support: dict[str, dict[str, Any]] | None,
    corpus_scope: str,
) -> dict[str, Any]:
    """Combine all evidence rows into one conservative verdict."""
    tokens = [t for t in query.split() if t]
    strongest = ranked_results[0] if ranked_results else None
    strongest_conf = (strongest or {}).get("confidence") or {}
    strongest_score = float(strongest_conf.get("score", 0.0) or 0.0)

    rationale: list[str] = []
    discounted: list[str] = []
    verdict = VERDICT_NONE
    confidence = 0.0

    if strongest is None:
        return {
            "verdict": VERDICT_NONE,
            "confidence_score": 0.0,
            "abstain": True,
            "corpus_scope": corpus_scope,
            "strongest_evidence": None,
            "token_support": token_support or {},
            "rationale": ["no verified findings were produced"],
            "discounted_findings": [],
        }

    if len(tokens) <= 1:
        confidence = strongest_score
        if strongest_score >= 0.84:
            verdict = VERDICT_STRONG
            rationale.append("strong single-token evidence")
        elif strongest_score >= 0.64:
            verdict = VERDICT_MODERATE
            rationale.append("moderate single-token evidence")
        elif strongest_score >= 0.42:
            verdict = VERDICT_WEAK
            rationale.append("weak but non-zero single-token evidence")
        else:
            verdict = VERDICT_NONE
            rationale.append("single-token signal is not convincing")
    else:
        support = token_support or _empty_token_support(tokens)
        first = tokens[0]
        surname = tokens[-1]
        first_support = support.get(first, {})
        surname_support = support.get(surname, {})

        full_phrase_hit = any(
            row.get("method") == "SUBSTRING"
            and (((row.get("confidence") or {}).get("features") or {}).get("match_type") == "exact_phrase")
            and bool((row.get("verification") or {}).get("verified"))
            for row in ranked_results
        )
        token_fallback_used = any(
            bool((((row.get("confidence") or {}).get("features") or {}).get("token_fallback")))
            for row in ranked_results
        )
        all_tokens_supported = all(support.get(t, {}).get("has_any_support") for t in tokens)
        all_tokens_direct = all(support.get(t, {}).get("has_direct_exact") for t in tokens)
        all_tokens_only_weak_els = all(
            support.get(t, {}).get("best_method") == "ELS"
            and float(support.get(t, {}).get("best_score", 0.0) or 0.0) < 0.5
            for t in tokens
        )
        surname_only_high_skip_els = (
            surname_support.get("best_method") == "ELS"
            and not surname_support.get("has_direct_exact")
            and int(surname_support.get("best_skip") or 0) >= 80
        )
        first_is_common = first in COMMON_FIRST_NAMES

        supported_ratio = sum(1 for t in tokens if support.get(t, {}).get("has_any_support")) / len(tokens)
        confidence = 0.7 * strongest_score + 0.3 * supported_ratio
        if full_phrase_hit:
            confidence += 0.2
        if token_fallback_used and not full_phrase_hit:
            confidence -= TOKEN_FALLBACK_CONFIDENCE_PENALTY
            discounted.append("token-level fallback evidence is conservatively discounted")
        if surname_only_high_skip_els:
            confidence -= 0.22
            discounted.append("surname evidence appears only via high-skip ELS")
        if all_tokens_only_weak_els:
            confidence -= 0.2
            discounted.append("all tokens are supported only by weak ELS-style hits")
        if first_is_common and not surname_support.get("has_direct_exact"):
            confidence -= 0.1
            discounted.append("common first-name evidence receives a conservative penalty")
        confidence = _clamp(confidence)

        if full_phrase_hit:
            verdict = VERDICT_STRONG
            rationale.append("exact full-name phrase evidence was found")
        elif all_tokens_direct and confidence >= 0.62:
            verdict = VERDICT_MODERATE
            rationale.append("all name tokens have direct support")
        elif all_tokens_supported and not all_tokens_only_weak_els and confidence >= 0.58:
            verdict = VERDICT_MODERATE
            rationale.append("all tokens are independently supported")
        elif first_support.get("has_any_support") and not surname_support.get("has_any_support"):
            verdict = VERDICT_NONE if first_is_common else VERDICT_WEAK
            discounted.append("only one token has support")
        elif surname_only_high_skip_els and first_is_common:
            verdict = VERDICT_WEAK if confidence >= 0.42 else VERDICT_NONE
        elif confidence >= 0.42:
            verdict = VERDICT_WEAK
            rationale.append("mixed evidence exists but is not strong")
        else:
            verdict = VERDICT_NONE
            rationale.append("evidence does not exceed random-like baseline")

    strongest_ref = (
        f"{strongest['location']['book']} "
        f"{strongest['location']['chapter']}:{strongest['location']['verse']}"
    )
    return {
        "verdict": verdict,
        "confidence_score": round(confidence, 4),
        "abstain": verdict == VERDICT_NONE,
        "corpus_scope": corpus_scope,
        "strongest_evidence": {
            "method": strongest.get("method"),
            "ref": strongest_ref,
            "score": strongest_score,
            "label": strongest_conf.get("label"),
            "match_type": ((strongest_conf.get("features") or {}).get("match_type")),
        },
        "token_support": token_support or {},
        "rationale": rationale,
        "discounted_findings": discounted,
    }
