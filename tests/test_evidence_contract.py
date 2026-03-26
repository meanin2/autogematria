"""Behavior tests for conservative evidence contract."""

import pytest

from autogematria.autoresearch.ground_truth import load_ground_truth
from autogematria.config import DB_PATH, TORAH_BOOKS
from autogematria.scoring.calibrated import CandidateEvidence, score_candidates
from autogematria.search.base import Location, SearchResult
from autogematria.scoring.verdict import VERDICT_NONE, VERDICT_STRONG, VERDICT_WEAK
from autogematria.tools.tool_functions import find_name_in_torah


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_exact_word_beats_partial_substring():
    exact = SearchResult(
        method="SUBSTRING",
        query="משה",
        found_text="משה",
        location_start=Location("Exodus", 2, 10),
        params={"mode": "within_word", "exact_word_match": True},
    )
    partial = SearchResult(
        method="SUBSTRING",
        query="משה",
        found_text="ומשהו",
        location_start=Location("Exodus", 2, 11),
        params={"mode": "within_word", "exact_word_match": False},
    )
    scored = score_candidates(
        "משה",
        [
            CandidateEvidence(result=exact, verification={"verified": True}),
            CandidateEvidence(result=partial, verification={"verified": True}),
        ],
    )
    scores_by_type = {
        (s.features or {}).get("match_type"): s.score for s in scored
    }
    assert scores_by_type["exact_word"] > scores_by_type["partial_word"]


def test_exact_phrase_gets_strong_full_name_verdict():
    data = find_name_in_torah(
        "מר דרור",
        methods=["substring"],
        max_results=10,
        diversify_methods=False,
    )
    assert data["final_verdict"]["verdict"] == VERDICT_STRONG


def test_common_first_name_plus_weak_surname_does_not_overclaim():
    data = find_name_in_torah(
        "משה גינדי",
        max_results=20,
        diversify_methods=False,
    )
    assert data["final_verdict"]["verdict"] in {VERDICT_WEAK, VERDICT_NONE}


def test_default_scope_is_torah():
    data = find_name_in_torah("דוד", methods=["substring"], max_results=20)
    assert data["corpus_scope"] == "torah"
    for row in data["results"]:
        assert row["location"]["book"] in TORAH_BOOKS


def test_els_payload_contains_significance_features():
    data = find_name_in_torah(
        "משה",
        methods=["els"],
        max_results=3,
        diversify_methods=False,
    )
    assert data["ranked_results"]
    for row in data["ranked_results"]:
        features = (row["confidence"] or {}).get("features") or {}
        assert "null_rarity_p" in features
        assert "null_model_p_shuffle" in features
        assert "null_model_p_markov" in features
        assert 0.0 <= float(features["null_rarity_p"]) <= 1.0


def test_diversified_display_does_not_change_best_evidence():
    diverse = find_name_in_torah("משה", max_results=20, diversify_methods=True)
    ranked = find_name_in_torah("משה", max_results=20, diversify_methods=False)
    assert diverse["best_evidence"]["method"] == ranked["best_evidence"]["method"]
    assert diverse["best_evidence"]["location"] == ranked["best_evidence"]["location"]


def test_hard_negative_remains_non_convincing():
    entries = load_ground_truth()
    candidate = next(e for e in entries if e.track == "hard_negative" and " " in e.name)
    data = find_name_in_torah(candidate.name, max_results=10, diversify_methods=False)
    verdict = data["final_verdict"]["verdict"]
    assert verdict in {VERDICT_WEAK, VERDICT_NONE}
