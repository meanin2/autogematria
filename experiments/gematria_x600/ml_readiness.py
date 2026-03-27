"""Assess whether we have enough verified labels for a stable ML model."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from autogematria.autoresearch.ground_truth import load_ground_truth
from autogematria.gematria_connections import load_connections_library
from autogematria.tools.tool_functions import gematria_lookup

OUT_PATH = Path(__file__).resolve().parent / "ml_readiness.json"


def _connection_positive_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for rec in load_connections_library():
        terms = [str(t) for t in rec.get("terms", []) if str(t).strip()]
        if len(terms) < 2:
            continue
        for q in terms:
            for t in terms:
                if q != t:
                    pairs.add((q, t))
    return pairs


def _discoverable_pair_count(pairs: set[tuple[str, str]]) -> int:
    discoverable = 0
    cache: dict[str, set[str]] = {}
    for q, t in pairs:
        if q not in cache:
            data = gematria_lookup(q, max_equivalents=700)
            cache[q] = {row["word"] for row in data.get("equivalents", [])}
        if t in cache[q]:
            discoverable += 1
    return discoverable


def assess() -> dict:
    gt = load_ground_truth()
    gem_gt = [e for e in gt if e.method == "gematria"]
    gem_pos = [e for e in gem_gt if not e.is_negative]
    gem_neg = [e for e in gem_gt if e.is_negative]

    source_records = load_connections_library()
    pair_labels = _connection_positive_pairs()
    discoverable_pairs = _discoverable_pair_count(pair_labels)

    recommendation = "insufficient_for_stable_ml"
    reasons = []
    if len(gem_pos) < 50:
        reasons.append(f"only {len(gem_pos)} gematria positives in ground truth (recommend >=50)")
    if len(gem_neg) < 50:
        reasons.append(f"only {len(gem_neg)} gematria negatives in ground truth (recommend >=50)")
    if len(pair_labels) < 120:
        reasons.append(f"only {len(pair_labels)} directed source-pair labels (recommend >=120)")
    if discoverable_pairs < 100:
        reasons.append(f"only {discoverable_pairs} discoverable directed source-pairs in corpus (recommend >=100)")
    if not reasons:
        recommendation = "ml_feasible_now"
        reasons.append("label volume passes minimum heuristic thresholds")

    out = {
        "ground_truth": {
            "gematria_total": len(gem_gt),
            "gematria_positive": len(gem_pos),
            "gematria_negative": len(gem_neg),
            "gematria_split_positive": Counter(e.split for e in gem_pos),
            "gematria_split_negative": Counter(e.split for e in gem_neg),
        },
        "connections_library": {
            "records": len(source_records),
            "directed_pair_labels": len(pair_labels),
            "discoverable_directed_pairs": discoverable_pairs,
        },
        "recommendation": recommendation,
        "reasons": reasons,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(assess(), ensure_ascii=False, indent=2))
