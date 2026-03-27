"""Tests for query variant resolution behavior in verify_cli."""

from __future__ import annotations

from autogematria.tools import verify_cli


def _fake_payload(*, labels: list[str], verified: int, query: str) -> dict:
    results = []
    for idx, label in enumerate(labels):
        results.append(
            {
                "method": "SUBSTRING",
                "confidence": {"label": label, "score": 0.65},
                "verification": {"verified": idx < verified},
            }
        )
    verdict = "moderate_evidence" if any(label in {"high", "medium"} for label in labels) else "no_convincing_evidence"
    return {
        "query": query,
        "query_normalized": query,
        "book_filter": None,
        "corpus_scope": "torah",
        "total_results": len(results),
        "results": results,
        "final_verdict": {"verdict": verdict, "confidence_score": 0.7 if verdict != "no_convincing_evidence" else 0.0},
    }


def test_resolve_variants_prefers_verified_alternate_over_empty_first(monkeypatch):
    payloads = {
        "משה גינדי": _fake_payload(labels=[], verified=0, query="משה גינדי"),
        "משה גנדי": _fake_payload(labels=["medium"], verified=1, query="משה גנדי"),
        "מוש גינדי": _fake_payload(labels=[], verified=0, query="מוש גינדי"),
        "מוש גנדי": _fake_payload(labels=[], verified=0, query="מוש גנדי"),
    }

    def fake_find_name_in_torah(name: str, **_kwargs):
        return payloads.get(name, _fake_payload(labels=[], verified=0, query=name))

    monkeypatch.setattr(verify_cli, "find_name_in_torah", fake_find_name_in_torah)

    resolved, data, _rows = verify_cli._resolve_query_with_variants(
        "moshe gindi",
        auto_hebrew=True,
        book=None,
        max_results=20,
        els_max_skip=500,
        corpus_scope="torah",
    )

    assert resolved == "משה גנדי"
    assert data["final_verdict"]["verdict"] == "moderate_evidence"


def test_resolve_variants_keeps_curated_first_when_alternate_unverified(monkeypatch):
    payloads = {
        "משה גינדי": _fake_payload(labels=["low"], verified=0, query="משה גינדי"),
        "משה גנדי": _fake_payload(labels=["medium"], verified=0, query="משה גנדי"),
        "מוש גינדי": _fake_payload(labels=[], verified=0, query="מוש גינדי"),
        "מוש גנדי": _fake_payload(labels=[], verified=0, query="מוש גנדי"),
    }

    def fake_find_name_in_torah(name: str, **_kwargs):
        return payloads.get(name, _fake_payload(labels=[], verified=0, query=name))

    monkeypatch.setattr(verify_cli, "find_name_in_torah", fake_find_name_in_torah)

    resolved, data, _rows = verify_cli._resolve_query_with_variants(
        "moshe gindi",
        auto_hebrew=True,
        book=None,
        max_results=20,
        els_max_skip=500,
        corpus_scope="torah",
    )

    assert resolved == "משה גינדי"
    assert data["final_verdict"]["verdict"] == "no_convincing_evidence"
