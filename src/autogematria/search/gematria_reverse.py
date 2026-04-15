"""Fast reverse gematria lookup: given a number, find all matching words.

Uses the existing precomputed word_gematria table (built by ag-index) which
already covers all 22 methods for all 40,664 unique word forms in Tanakh.

The ag-index-report-methods CLI adds a covering index for the 6 report
methods to make lookups even faster.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from typing import Any

from autogematria.config import DB_PATH

REPORT_METHODS = [
    "MISPAR_HECHRACHI",
    "MISPAR_GADOL",
    "MISPAR_KATAN",
    "MISPAR_SIDURI",
    "ATBASH",
    "MISPAR_KOLEL",
]

REPORT_METHOD_DISPLAY = {
    "MISPAR_HECHRACHI": "Standard",
    "MISPAR_GADOL": "Full Value",
    "MISPAR_KATAN": "Reduced",
    "MISPAR_SIDURI": "Ordinal",
    "ATBASH": "AtBash",
    "MISPAR_KOLEL": "Kolel",
}


def _conn(db_path=DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def reverse_lookup(
    value: int,
    *,
    method: str = "MISPAR_HECHRACHI",
    max_results: int = 50,
    db_path=DB_PATH,
) -> list[dict[str, Any]]:
    """Find all Tanakh word forms with the given gematria value under one method."""
    max_results = max(1, min(max_results, 500))
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT wf.form_raw, wf.form_text, wf.frequency "
            "FROM word_gematria wg "
            "JOIN word_forms wf ON wg.form_id = wf.form_id "
            "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
            "WHERE gm.method_name = ? AND wg.value = ? "
            "ORDER BY wf.frequency DESC LIMIT ?",
            (method, value, max_results),
        ).fetchall()
        return [
            {
                "word": row["form_raw"],
                "normalized": row["form_text"],
                "frequency": row["frequency"],
                "method": method,
                "value": value,
            }
            for row in rows
        ]
    finally:
        conn.close()


def reverse_lookup_all_methods(
    value: int,
    *,
    methods: list[str] | None = None,
    max_per_method: int = 20,
    db_path=DB_PATH,
) -> dict[str, list[dict[str, Any]]]:
    """Find matching words across multiple methods for a single value."""
    method_list = methods or REPORT_METHODS
    results: dict[str, list[dict[str, Any]]] = {}
    for method in method_list:
        results[method] = reverse_lookup(
            value, method=method, max_results=max_per_method, db_path=db_path,
        )
    return results


def word_gematria_profile(
    word: str,
    *,
    methods: list[str] | None = None,
    db_path=DB_PATH,
) -> dict[str, Any]:
    """Compute gematria values for a word across all report methods."""
    from hebrew import Hebrew
    from hebrew.gematria import GematriaTypes
    from autogematria.normalize import FinalsPolicy, normalize_hebrew

    clean = normalize_hebrew(word, FinalsPolicy.PRESERVE).replace(" ", "")
    if not clean:
        return {"word": word, "values": {}}

    method_list = methods or REPORT_METHODS
    h = Hebrew(clean)
    values: dict[str, int] = {}
    for method_name in method_list:
        gtype = getattr(GematriaTypes, method_name, None)
        if gtype is not None:
            try:
                values[method_name] = int(h.gematria(gtype))
            except Exception:
                pass
    return {"word": word, "normalized": clean, "values": values}


def build_name_gematria_graph(
    components: list[tuple[str, str]],
    *,
    methods: list[str] | None = None,
    max_shared_words: int = 10,
    db_path=DB_PATH,
) -> dict[str, Any]:
    """Build a comprehensive gematria relationship graph for name components.

    For each component, across each method:
      1. Compute the value
      2. Find all Torah words with the same value
      3. Find cross-component matches (same value, different method or component)

    Returns a structure suitable for rendering as a visual graph or table.
    """
    method_list = methods or REPORT_METHODS

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_id_map: dict[str, int] = {}
    next_id = 0

    for text, role in components:
        profile = word_gematria_profile(text, methods=method_list, db_path=db_path)
        node_id = next_id
        next_id += 1
        node_id_map[f"{text}|{role}"] = node_id
        nodes.append({
            "id": node_id,
            "type": "name_component",
            "text": text,
            "role": role,
            "values": profile.get("values", {}),
        })

    value_to_nodes: dict[tuple[str, int], list[int]] = {}
    for node in nodes:
        for method, val in node["values"].items():
            key = (method, val)
            value_to_nodes.setdefault(key, []).append(node["id"])

    for (method, val), nids in value_to_nodes.items():
        if len(nids) < 2:
            continue
        for i in range(len(nids)):
            for j in range(i + 1, len(nids)):
                edges.append({
                    "source": nids[i],
                    "target": nids[j],
                    "type": "same_value",
                    "method": method,
                    "value": val,
                })

    for method, val in value_to_nodes:
        shared = reverse_lookup(
            val, method=method, max_results=max_shared_words, db_path=db_path,
        )
        component_norms = {
            n["text"].replace(" ", "")
            for n in nodes
            if n["type"] == "name_component"
        }
        for sw in shared:
            if sw["normalized"] in component_norms:
                continue
            torah_id = next_id
            next_id += 1
            nodes.append({
                "id": torah_id,
                "type": "torah_word",
                "text": sw["word"],
                "frequency": sw["frequency"],
                "method": method,
                "value": val,
            })
            for nid in value_to_nodes[(method, val)]:
                edges.append({
                    "source": nid,
                    "target": torah_id,
                    "type": "shared_value",
                    "method": method,
                    "value": val,
                })

    cross_method_edges: list[dict[str, Any]] = []
    for node in nodes:
        if node["type"] != "name_component":
            continue
        for method_a, val_a in node["values"].items():
            for other in nodes:
                if other["id"] == node["id"] or other["type"] != "name_component":
                    continue
                for method_b, val_b in other["values"].items():
                    if val_a == val_b and method_a != method_b:
                        edge_key = tuple(sorted([
                            (node["id"], method_a),
                            (other["id"], method_b),
                        ]))
                        if edge_key not in {
                            tuple(sorted([
                                (e["source"], e.get("source_method", "")),
                                (e["target"], e.get("target_method", "")),
                            ]))
                            for e in cross_method_edges
                        }:
                            cross_method_edges.append({
                                "source": node["id"],
                                "target": other["id"],
                                "type": "cross_method_match",
                                "source_method": method_a,
                                "target_method": method_b,
                                "value": val_a,
                            })
    edges.extend(cross_method_edges)

    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "name_components": sum(1 for n in nodes if n["type"] == "name_component"),
            "torah_words": sum(1 for n in nodes if n["type"] == "torah_word"),
            "same_value_edges": sum(1 for e in edges if e["type"] == "same_value"),
            "shared_value_edges": sum(1 for e in edges if e["type"] == "shared_value"),
            "cross_method_edges": sum(1 for e in edges if e["type"] == "cross_method_match"),
        },
    }


def ensure_report_indexes(db_path=DB_PATH) -> None:
    """Add covering indexes optimized for the 6 report methods.

    This is safe to call repeatedly (CREATE INDEX IF NOT EXISTS).
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_gematria_value_method "
        "ON word_gematria(value, method_id)"
    )
    conn.commit()
    conn.close()
