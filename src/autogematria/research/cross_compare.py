"""Cross-comparison engine for gematria relationships across name components.

Given a parsed name (first, father, mother, surname), compute gematria via
multiple methods and find surprising matches: same values, known pairs,
Torah word equivalences, and inter-component relationships.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import DB_PATH
from autogematria.normalize import FinalsPolicy, normalize_hebrew


METHODS_FOR_REPORT: list[tuple[str, str]] = [
    ("MISPAR_HECHRACHI", "Standard (Mispar Hechrachi)"),
    ("MISPAR_GADOL", "Full Value (Mispar Gadol)"),
    ("MISPAR_KATAN", "Reduced (Mispar Katan)"),
    ("MISPAR_SIDURI", "Ordinal (Mispar Siduri)"),
    ("ATBASH", "AtBash"),
    ("MISPAR_KOLEL", "Kolel (Standard + # letters)"),
]


def _clean(text: str) -> str:
    return normalize_hebrew(text, FinalsPolicy.PRESERVE).replace(" ", "")


def _gematria(text: str, method_name: str) -> int:
    clean = _clean(text)
    if not clean:
        return 0
    gtype = getattr(GematriaTypes, method_name, GematriaTypes.MISPAR_HECHRACHI)
    return int(Hebrew(clean).gematria(gtype))


def _build_combination_pairs(
    components: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Generate meaningful pair-combinations of components."""
    if len(components) < 2:
        return []
    combos: list[tuple[str, str]] = []
    for i in range(len(components)):
        for j in range(i + 1, len(components)):
            t1, r1 = components[i]
            t2, r2 = components[j]
            combined = _clean(t1) + _clean(t2)
            if combined:
                combos.append((combined, f"{r1}+{r2}"))
    return combos


def compute_gematria_table(
    components: list[tuple[str, str]],
    methods: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Compute gematria values for all components across all methods.

    Args:
        components: list of (hebrew_text, role) pairs
        methods: list of (method_name, display_name) pairs

    Returns:
        A table structure with rows per component and columns per method.
    """
    method_list = methods or METHODS_FOR_REPORT
    rows: list[dict[str, Any]] = []

    for text, role in components:
        clean = _clean(text)
        if not clean:
            continue
        values: dict[str, int] = {}
        for method_name, _ in method_list:
            values[method_name] = _gematria(text, method_name)
        rows.append({
            "text": text,
            "role": role,
            "letter_count": len(clean),
            "values": values,
        })

    combo_pairs = _build_combination_pairs(components)
    for combo_text, combo_role in combo_pairs:
        if not combo_text:
            continue
        values = {}
        for method_name, _ in method_list:
            values[method_name] = _gematria(combo_text, method_name)
        rows.append({
            "text": combo_text,
            "role": combo_role,
            "letter_count": len(combo_text),
            "values": values,
        })

    combined = "".join(_clean(t) for t, _ in components)
    if combined and len(components) > 1:
        combined_values: dict[str, int] = {}
        for method_name, _ in method_list:
            combined_values[method_name] = _gematria(combined, method_name)
        rows.append({
            "text": combined,
            "role": "combined_all",
            "letter_count": len(combined),
            "values": combined_values,
        })

    return {
        "methods": [{"name": n, "display": d} for n, d in method_list],
        "components": rows,
    }


def find_cross_matches(
    components: list[tuple[str, str]],
    methods: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Find pairs of components that share a gematria value under some method.

    This is the core "aha!" finder: when your first name under AtBash equals
    your father's name under standard gematria, that's noteworthy.
    Also checks pair-combinations (e.g., first+surname).
    """
    method_list = methods or METHODS_FOR_REPORT
    matches: list[dict[str, Any]] = []

    extended = list(components) + _build_combination_pairs(components)
    all_entries: list[tuple[str, str, str, int]] = []
    for text, role in extended:
        clean = _clean(text)
        if not clean:
            continue
        for method_name, method_display in method_list:
            val = _gematria(text, method_name)
            all_entries.append((text, role, method_name, val))

    for i in range(len(all_entries)):
        for j in range(i + 1, len(all_entries)):
            t1, r1, m1, v1 = all_entries[i]
            t2, r2, m2, v2 = all_entries[j]
            if v1 != v2 or v1 == 0:
                continue
            if t1 == t2 and m1 == m2:
                continue
            if t1 == t2 and r1 == r2:
                continue

            same_text = _clean(t1) == _clean(t2)
            same_method = m1 == m2
            if same_text and same_method:
                continue

            match_type = "cross_method" if not same_method and not same_text else (
                "same_method_different_name" if same_method else "same_name_different_method"
            )

            matches.append({
                "value": v1,
                "component_a": {"text": t1, "role": r1, "method": m1},
                "component_b": {"text": t2, "role": r2, "method": m2},
                "match_type": match_type,
                "interest_score": _interest_score(r1, r2, m1, m2, v1),
            })

    matches.sort(key=lambda m: -m["interest_score"])
    return matches


def _interest_score(role_a: str, role_b: str, method_a: str, method_b: str, value: int) -> float:
    score = 0.5
    if role_a != role_b:
        score += 0.2
    if method_a == method_b == "MISPAR_HECHRACHI":
        score += 0.15
    elif method_a != method_b:
        score += 0.1
    if value > 10:
        score += 0.05
    if value > 100:
        score += 0.05
    return round(score, 3)


def _fetch_same_value_words(
    conn: sqlite3.Connection,
    *,
    method_name: str,
    value: int,
    exclude_norms: set[str],
    max_per_component: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT wf.form_raw, wf.frequency FROM word_gematria wg "
        "JOIN word_forms wf ON wg.form_id = wf.form_id "
        "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
        "WHERE gm.method_name = ? AND wg.value = ? "
        "ORDER BY wf.frequency DESC LIMIT ?",
        (method_name, value, max_per_component + 10),
    ).fetchall()
    word_matches: list[dict[str, Any]] = []
    for row in rows:
        word = str(row["form_raw"])
        word_clean = normalize_hebrew(word, FinalsPolicy.NORMALIZE)
        if word_clean in exclude_norms:
            continue
        if len(word_clean) < 2:
            continue
        word_matches.append({
            "word": word,
            "frequency": int(row["frequency"]),
            "shared_value": value,
            "method": method_name,
        })
        if len(word_matches) >= max_per_component:
            break
    return word_matches


def find_torah_word_matches(
    components: list[tuple[str, str]],
    db_path=DB_PATH,
    max_per_component: int = 8,
) -> dict[str, list[dict[str, Any]]]:
    """For each component and the full combined name, find Torah words with
    matching gematria across all six report methods.

    Returns notable Torah words that share gematria values with name parts,
    along with their frequency.  A dedicated ``combined_all`` entry is
    always included when there are two or more components so the report
    has first-class Torah-word findings for the user's *full* name, not
    just for its individual components.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    results: dict[str, list[dict[str, Any]]] = {}

    try:
        # Build the exclusion set so we never surface the raw name itself
        # or any of its components as a "Torah word with same gematria"
        # for the full combined name.
        component_norms: set[str] = set()
        for text, _ in components:
            component_norms.add(normalize_hebrew(_clean(text), FinalsPolicy.NORMALIZE))
        combined_clean = "".join(_clean(t) for t, _ in components)
        if combined_clean:
            component_norms.add(normalize_hebrew(combined_clean, FinalsPolicy.NORMALIZE))

        for text, role in components:
            clean = _clean(text)
            if not clean:
                continue
            self_norm = normalize_hebrew(clean, FinalsPolicy.NORMALIZE)
            word_matches: list[dict[str, Any]] = []
            for method_name, _display in METHODS_FOR_REPORT:
                value = _gematria(text, method_name)
                if not value:
                    continue
                word_matches.extend(
                    _fetch_same_value_words(
                        conn,
                        method_name=method_name,
                        value=value,
                        exclude_norms={self_norm},
                        max_per_component=max_per_component,
                    )
                )
                if len(word_matches) >= max_per_component * 2:
                    break
            key = f"{text}|{role}"
            results[key] = word_matches[: max_per_component * 2]

        # Full combined-name entry (the "what about me as a whole" row)
        if combined_clean and len(components) > 1:
            combined_matches: list[dict[str, Any]] = []
            for method_name, _display in METHODS_FOR_REPORT:
                value = _gematria(combined_clean, method_name)
                if not value:
                    continue
                combined_matches.extend(
                    _fetch_same_value_words(
                        conn,
                        method_name=method_name,
                        value=value,
                        exclude_norms=component_norms,
                        max_per_component=max_per_component,
                    )
                )
            key = f"{combined_clean}|combined_all"
            results[key] = combined_matches[: max_per_component * 3]
    finally:
        conn.close()

    return results


def build_cross_comparison_report(
    components: list[tuple[str, str]],
    db_path=DB_PATH,
) -> dict[str, Any]:
    """Build a full cross-comparison report for name components."""
    table = compute_gematria_table(components)
    cross_matches = find_cross_matches(components)
    torah_matches = find_torah_word_matches(components, db_path=db_path)

    noteworthy = [m for m in cross_matches if m["interest_score"] >= 0.7]

    return {
        "gematria_table": table,
        "cross_matches": cross_matches,
        "noteworthy_matches": noteworthy,
        "torah_word_matches": torah_matches,
        "summary": {
            "total_cross_matches": len(cross_matches),
            "noteworthy_count": len(noteworthy),
            "components_analyzed": len(components),
        },
    }
