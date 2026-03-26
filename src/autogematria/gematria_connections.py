"""Gematria connection graph and source-backed relationship lookup."""

from __future__ import annotations

import json
import math
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

import networkx as nx
from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import DATA_DIR, DB_PATH
from autogematria.normalize import FinalsPolicy, normalize_hebrew


CONNECTIONS_LIBRARY_PATH = DATA_DIR / "gematria" / "connections.json"


def _resolve_method(method: str) -> tuple[GematriaTypes, str]:
    gtype = getattr(GematriaTypes, method, None)
    if gtype is None:
        gtype = GematriaTypes.MISPAR_HECHRACHI
    return gtype, gtype.name


def _sorted_letters(word: str) -> str:
    return "".join(sorted(normalize_hebrew(word, FinalsPolicy.NORMALIZE)))


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(
                prev[j] + 1,      # delete
                curr[j - 1] + 1,  # insert
                prev[j - 1] + cost,  # replace
            ))
        prev = curr
    return prev[-1]


@lru_cache(maxsize=1)
def load_connections_library(path: str = str(CONNECTIONS_LIBRARY_PATH)) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    payload = json.loads(p.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    return [r for r in records if isinstance(r, dict)]


def _library_matches(
    *,
    value: int,
    method: str,
    query_word: str,
) -> list[dict[str, Any]]:
    query_norm = normalize_hebrew(query_word, FinalsPolicy.PRESERVE)
    matched: list[dict[str, Any]] = []
    for record in load_connections_library():
        rec_method = str(record.get("method", "MISPAR_HECHRACHI"))
        rec_value = int(record.get("value", -1))
        terms = [str(t) for t in record.get("terms", [])]
        if rec_method != method or rec_value != value:
            continue
        if query_norm in terms:
            matched.append(record)
            continue
        if any(normalize_hebrew(t, FinalsPolicy.NORMALIZE) == normalize_hebrew(query_norm, FinalsPolicy.NORMALIZE) for t in terms):
            matched.append(record)
    return matched


def gematria_connections(
    word: str,
    *,
    method: str = "MISPAR_HECHRACHI",
    max_equivalents: int = 120,
    max_related: int = 20,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """Build a connection graph for same-value words and source-backed links."""
    clean = normalize_hebrew(word, FinalsPolicy.PRESERVE)
    gtype, resolved_method = _resolve_method(method)
    value = Hebrew(clean).gematria(gtype)
    norm_word = normalize_hebrew(clean, FinalsPolicy.NORMALIZE)
    lib_matches = _library_matches(value=value, method=resolved_method, query_word=clean)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT wf.form_raw, wf.frequency FROM word_gematria wg "
            "JOIN word_forms wf ON wg.form_id = wf.form_id "
            "JOIN gematria_methods gm ON wg.method_id = gm.method_id "
            "WHERE gm.method_name = ? AND wg.value = ? "
            "ORDER BY wf.frequency DESC LIMIT ?",
            (resolved_method, value, max_equivalents),
        ).fetchall()
    finally:
        conn.close()

    graph = nx.Graph()
    graph.add_node(clean, kind="query")
    query_sorted = _sorted_letters(clean)
    lib_terms_for_value = {
        term
        for record in load_connections_library()
        if str(record.get("method", "")) == resolved_method and int(record.get("value", -1)) == value
        for term in record.get("terms", [])
    }

    related_rows: list[dict[str, Any]] = []
    for row in rows:
        term = str(row["form_raw"])
        freq = int(row["frequency"])
        term_norm = normalize_hebrew(term, FinalsPolicy.NORMALIZE)
        relations: list[str] = ["same_value"]
        source_refs: list[str] = []
        score = 0.2 + min(0.35, math.log10(freq + 1) / 4)

        if term_norm == norm_word:
            relations.append("exact_match")
            score += 0.35
        if _sorted_letters(term) == query_sorted:
            relations.append("anagram")
            score += 0.18
        distance = _levenshtein(norm_word, term_norm)
        if 0 < distance <= 2:
            relations.append("orthographic_neighbor")
            score += 0.08

        if term in lib_terms_for_value:
            relations.append("source_backed")
            score += 0.22
            for rec in load_connections_library():
                if (
                    str(rec.get("method", "")) == resolved_method
                    and int(rec.get("value", -1)) == value
                    and term in rec.get("terms", [])
                ):
                    source_refs.append(str(rec.get("source", "")))
                    if rec.get("relation_type"):
                        relations.append(str(rec["relation_type"]))

        graph.add_node(term, kind="equivalent", frequency=freq)
        graph.add_edge(clean, term, relations=sorted(set(relations)), weight=round(score, 4))

        related_rows.append(
            {
                "word": term,
                "frequency": freq,
                "score": round(min(score, 0.99), 4),
                "relations": sorted(set(relations)),
                "sources": sorted(set(source_refs)),
            }
        )

    related_rows.sort(key=lambda r: (-float(r["score"]), -int(r["frequency"]), r["word"]))
    related_rows = related_rows[:max_related]

    strongest_links = [
        {
            "from": src,
            "to": dst,
            "weight": data.get("weight"),
            "relations": data.get("relations", []),
        }
        for src, dst, data in sorted(
            graph.edges(data=True),
            key=lambda edge: -float(edge[2].get("weight", 0.0)),
        )[:max_related]
    ]

    return {
        "word": word,
        "normalized": clean,
        "method_requested": method,
        "method": resolved_method,
        "value": value,
        "library_matches": [
            {
                "terms": rec.get("terms", []),
                "relation_type": rec.get("relation_type"),
                "source": rec.get("source"),
                "notes": rec.get("notes"),
            }
            for rec in lib_matches
        ],
        "related_words": related_rows,
        "graph": {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "strongest_links": strongest_links,
        },
    }
