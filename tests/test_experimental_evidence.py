"""Experimental findings stay visible without changing conservative verdicts."""

from __future__ import annotations

import sqlite3

from autogematria.scoring.calibrated import CandidateEvidence, score_candidates
from autogematria.scoring.verdict import (
    VERDICT_NONE,
    aggregate_full_name_verdict,
    build_token_support,
)
from autogematria.search.base import Location, SearchResult


def _experimental_candidate() -> CandidateEvidence:
    return CandidateEvidence(
        result=SearchResult(
            method="EMTZAEI_TEVOT",
            query="בס",
            found_text="בס",
            location_start=Location("Genesis", 1, 1),
            location_end=Location("Genesis", 1, 1),
            raw_score=2,
            params={
                "experimental": True,
                "middle_policy": "odd_length_unique_interior_center",
            },
        ),
        verification={"verified": True},
    )


def _build_location_database(path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE books (book_id INTEGER PRIMARY KEY, api_name TEXT);
        CREATE TABLE chapters (
            chapter_id INTEGER PRIMARY KEY,
            book_id INTEGER,
            chapter_num INTEGER
        );
        CREATE TABLE verses (
            verse_id INTEGER PRIMARY KEY,
            chapter_id INTEGER,
            verse_num INTEGER
        );
        INSERT INTO books VALUES (1, 'Genesis');
        INSERT INTO chapters VALUES (1, 1, 1);
        INSERT INTO verses VALUES (1, 1, 1);
        """
    )
    conn.commit()
    conn.close()


def test_emtzaei_score_is_marked_ineligible_for_verdict(tmp_path):
    db_path = tmp_path / "locations.db"
    _build_location_database(db_path)
    scored = score_candidates("בס", [_experimental_candidate()], db_path=db_path)
    assert len(scored) == 1
    features = scored[0].features
    assert features["experimental"] is True
    assert features["eligible_for_verdict"] is False
    assert scored[0].label == "experimental"


def test_experimental_only_result_cannot_create_a_verdict(tmp_path):
    db_path = tmp_path / "locations.db"
    _build_location_database(db_path)
    scored = score_candidates("בס", [_experimental_candidate()], db_path=db_path)[0]
    row = {
        "method": scored.result.method,
        "location": {"book": "Genesis", "chapter": 1, "verse": 1},
        "verification": {"verified": True},
        "confidence": {
            "score": scored.score,
            "label": scored.label,
            "features": scored.features,
        },
    }

    token_support = build_token_support({"בס": {"results": [row]}}, ["בס"])
    assert token_support["בס"]["has_any_support"] is False

    verdict = aggregate_full_name_verdict(
        query="בס",
        ranked_results=[row],
        token_support=token_support,
        corpus_scope="torah",
    )
    assert verdict["verdict"] == VERDICT_NONE
    assert verdict["abstain"] is True
    assert verdict["strongest_evidence"] is None
