"""Tests for gematria connection graph and source-backed links."""

import pytest

from autogematria.config import DB_PATH
from autogematria.gematria_connections import load_connections_library
from autogematria.tools.tool_functions import gematria_connections, gematria_lookup


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_connections_library_loads():
    records = load_connections_library()
    assert records
    assert any(int(r.get("value", -1)) == 345 for r in records)


def test_gematria_connections_for_moshe():
    data = gematria_connections("משה")
    assert data["value"] == 345
    related_words = [r["word"] for r in data["related_words"]]
    assert "משה" in related_words
    assert data["graph"]["nodes"] >= 2


def test_gematria_lookup_includes_connections_payload():
    data = gematria_lookup("משה")
    assert data["value"] == 345
    assert data["connections"] is not None
    assert "related_words" in data["connections"]
