"""Tests for the autoresearch harness and scoring."""

import pytest
from autogematria.config import DB_PATH
from autogematria.autoresearch.ground_truth import load_ground_truth, get_split
from autogematria.autoresearch.harness import run_benchmark, DEFAULT_CONFIG
from autogematria.autoresearch.scorer import compute_composite


@pytest.fixture
def gt():
    return load_ground_truth()


def test_ground_truth_loads(gt):
    assert len(gt) > 20


def test_splits_exist(gt):
    train = get_split(gt, "train")
    dev = get_split(gt, "dev")
    holdout = get_split(gt, "holdout")
    assert len(train) > 0
    assert len(dev) > 0
    assert len(holdout) > 0


def test_negatives_exist(gt):
    negatives = [e for e in gt if e.is_negative]
    assert len(negatives) >= 4


def test_composite_score_range():
    assert compute_composite(1.0, 1.0, 0.0) == pytest.approx(0.7)
    assert compute_composite(0.0, 0.0, 1.0) == pytest.approx(-0.3)
    assert compute_composite(0.5, 0.5, 0.5) == pytest.approx(0.2)


def test_baseline_runs():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")
    sc = run_benchmark(DEFAULT_CONFIG, "train")
    assert sc.composite > 0
    assert sc.recall > 0
