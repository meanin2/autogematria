"""Curation helpers for presentable, party-trick style outputs."""

from __future__ import annotations

from typing import Any

from autogematria.research.namesakes import is_biblical_namesake


def _variant(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("variant") or {}


def _is_namesake_only_hit(row: dict[str, Any], *, multi_token_query: bool) -> bool:
    """True when this row is a raw match for a biblical namesake token.

    Used to suppress meaningless ``משה``-in-Exodus-2 style hits when the
    user's query is a full multi-token name.  We only suppress
    *token*-level variants (not full-name variants), so a verified
    full-name phrase match is never demoted.
    """
    if not multi_token_query:
        return False
    variant = _variant(row)
    kind = str(variant.get("kind") or "")
    text = str(variant.get("text") or "")
    if kind != "token":
        return False
    if not is_biblical_namesake(text):
        return False
    method = str(row.get("method") or "")
    family = str(row.get("family") or "")
    # Text-layer hits on a bare biblical name are what we suppress --
    # they are just "the Torah talks about the biblical figure".
    if method in {"SUBSTRING", "ROSHEI_TEVOT", "SOFEI_TEVOT", "ELS"}:
        return True
    if family == "gematria":
        # A Torah word whose gematria equals the biblical name is still
        # mostly about the biblical figure, not about the modern person.
        return True
    return False


def _is_full_name_variant(row: dict[str, Any]) -> bool:
    variant = _variant(row)
    return str(variant.get("kind") or "") == "full_name" and int(variant.get("token_count") or 1) > 1


def _feature(row: dict[str, Any], key: str, default=None):
    return (((row.get("confidence") or {}).get("features") or {}).get(key, default))


def _verified(row: dict[str, Any]) -> bool:
    return bool((row.get("verification") or {}).get("verified"))


def _confidence(row: dict[str, Any]) -> float:
    return float(((row.get("confidence") or {}).get("score") or 0.0))


def _presentation_score(row: dict[str, Any], *, has_direct_exact: bool) -> float:
    method = str(row.get("method"))
    family = str(row.get("family") or "")
    score = _confidence(row)
    match_type = str(_feature(row, "match_type", ""))
    mode = str((row.get("params") or {}).get("mode") or (row.get("params") or {}).get("search_kind") or "")

    if not _verified(row):
        return -1.0

    bonus = 0.0
    if method == "SUBSTRING":
        if match_type in {"exact_word", "exact_phrase"}:
            bonus += 2.0
        elif match_type == "cross_word":
            bonus += 0.7
        else:
            bonus += 0.5
    elif family == "gematria":
        if mode in {"exact_sequence", "token_sequence", "exact_word", "word_equivalence"}:
            bonus += 1.0
        elif mode in {"sum", "phrase_total", "contiguous_span"}:
            bonus += 0.6
    elif method in {"ROSHEI_TEVOT", "SOFEI_TEVOT"}:
        bonus += 0.7
    elif method == "ELS":
        skip = abs(int((row.get("params") or {}).get("skip") or _feature(row, "skip_size", 9999) or 9999))
        if skip <= 20:
            bonus += 0.5
        elif skip <= 60:
            bonus += 0.2

    if has_direct_exact and method == "SUBSTRING" and match_type == "cross_word":
        bonus -= 0.4
    if has_direct_exact and method == "ELS":
        bonus -= 0.5

    return round(score + bonus, 4)


def _tier(row: dict[str, Any], *, has_direct_exact: bool) -> str | None:
    method = str(row.get("method"))
    family = str(row.get("family") or "")
    match_type = str(_feature(row, "match_type", ""))
    mode = str((row.get("params") or {}).get("mode") or (row.get("params") or {}).get("search_kind") or "")

    if not _verified(row):
        return None
    if method == "SUBSTRING" and match_type in {"exact_word", "exact_phrase"}:
        return "headline"
    if family == "gematria" and mode in {"exact_sequence", "token_sequence", "exact_word", "word_equivalence"}:
        return "supporting"
    if method in {"ROSHEI_TEVOT", "SOFEI_TEVOT"}:
        return "supporting" if not has_direct_exact else "interesting"
    if method == "SUBSTRING" and match_type == "cross_word":
        return "interesting"
    if family == "gematria":
        return "interesting"
    if method == "ELS":
        skip = abs(int((row.get("params") or {}).get("skip") or _feature(row, "skip_size", 9999) or 9999))
        return "interesting" if skip <= 60 else None
    return None


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (
            row.get("method"),
            row.get("analysis_method"),
            (row.get("location") or {}).get("book"),
            (row.get("location") or {}).get("chapter"),
            (row.get("location") or {}).get("verse"),
            row.get("found_text"),
            (row.get("params") or {}).get("mode"),
            (row.get("params") or {}).get("search_kind"),
        )
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def build_showcase(payload: dict[str, Any], *, limit_per_tier: int = 5) -> dict[str, Any]:
    """Turn the raw research ledger into a presentable summary."""
    rows = [
        row
        for grouped in (payload.get("findings_by_method") or {}).values()
        for row in grouped
    ]
    rows = _dedupe(rows)

    query = str(payload.get("query") or "")
    multi_token_query = len([t for t in query.split() if t]) > 1

    has_direct_exact = any(
        row.get("method") == "SUBSTRING"
        and str(_feature(row, "match_type", "")) in {"exact_word", "exact_phrase"}
        and _verified(row)
        and not _is_namesake_only_hit(row, multi_token_query=multi_token_query)
        for row in rows
    )

    scored_rows = []
    namesake_rows: list[dict[str, Any]] = []
    for row in rows:
        if _is_namesake_only_hit(row, multi_token_query=multi_token_query):
            # Keep a copy visible, but in a clearly labeled separate bin
            # so it never pollutes headline/supporting findings about the
            # user's actual combined name.
            if _verified(row):
                enriched_ns = dict(row)
                enriched_ns["presentation_tier"] = "biblical_namesake"
                enriched_ns["presentation_score"] = round(_confidence(row), 4)
                namesake_rows.append(enriched_ns)
            continue
        tier = _tier(row, has_direct_exact=has_direct_exact)
        if not tier:
            continue
        enriched = dict(row)
        base_score = _presentation_score(row, has_direct_exact=has_direct_exact)
        # Boost findings about the full combined name so they rank above
        # individual-token matches whenever they exist.
        if _is_full_name_variant(row):
            base_score += 1.5
        enriched["presentation_score"] = base_score
        enriched["presentation_tier"] = tier
        scored_rows.append(enriched)

    scored_rows.sort(key=lambda row: (-float(row["presentation_score"]), row.get("method", "")))

    tiers = {"headline": [], "supporting": [], "interesting": []}
    for row in scored_rows:
        tier = str(row["presentation_tier"])
        if len(tiers[tier]) < limit_per_tier:
            tiers[tier].append(row)

    namesake_rows.sort(key=lambda row: -float(row.get("presentation_score") or 0.0))
    namesake_rows = namesake_rows[: limit_per_tier]

    if tiers["headline"]:
        verdict = "presentable_direct_hit"
    elif tiers["supporting"]:
        verdict = "presentable_indirect_hit"
    elif tiers["interesting"]:
        verdict = "interesting_but_weak"
    else:
        verdict = "no_presentable_hit"

    verdict_labels = {
        "presentable_direct_hit": "Direct textual hit",
        "presentable_indirect_hit": "Indirect but solid hit",
        "interesting_but_weak": "Interesting but weak",
        "no_presentable_hit": "No presentable hit",
    }
    verdict_notes = {
        "presentable_direct_hit": "A verified direct-text match was found and promoted to the top.",
        "presentable_indirect_hit": "No strong direct-text match was found, but there are verified supporting findings.",
        "interesting_but_weak": "Only weaker methods produced verified findings, so the result should be treated as exploratory.",
        "no_presentable_hit": "Nothing met the presentation threshold under the current rules.",
    }
    headline = tiers["headline"][0] if tiers["headline"] else None
    summary_line = verdict_notes[verdict]
    if headline:
        loc = headline.get("location") or {}
        summary_line = (
            f"Best match: {headline.get('found_text')} at "
            f"{loc.get('book')} {loc.get('chapter')}:{loc.get('verse')} "
            f"via {headline.get('method')}."
        )

    return {
        "query": payload.get("query"),
        "verdict": verdict,
        "verdict_label": verdict_labels[verdict],
        "summary_line": summary_line,
        "headline": headline,
        "headline_findings": tiers["headline"],
        "supporting_findings": tiers["supporting"],
        "interesting_findings": tiers["interesting"],
        "biblical_namesake_findings": namesake_rows,
        "hidden_findings": max(
            0,
            len(rows) - sum(len(v) for v in tiers.values()) - len(namesake_rows),
        ),
        "has_direct_exact": has_direct_exact,
    }
