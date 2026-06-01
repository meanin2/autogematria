"""Tests for gematria connection graph and source-backed links."""

import json

import pytest
from hebrew import Hebrew
from hebrew.gematria import GematriaTypes

from autogematria.config import DB_PATH, PROJECT_ROOT
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


def test_source_pair_relation_for_ahava_echad():
    data = gematria_connections("אהבה", max_related=40)
    target = next((row for row in data["related_words"] if row["word"] == "אחד"), None)
    assert target is not None
    relations = set(target.get("relations") or [])
    assert "source_backed" in relations
    assert "source_pair" in relations


_GEMATRIA_TYPE_MAP = {
    "MISPAR_HECHRACHI": GematriaTypes.MISPAR_HECHRACHI,
    "MISPAR_KATAN": GematriaTypes.MISPAR_KATAN,
    "MISPAR_GADOL": GematriaTypes.MISPAR_GADOL,
    "MISPAR_SIDURI": GematriaTypes.MISPAR_SIDURI,
    "ATBASH": GematriaTypes.ATBASH,
    "MISPAR_KOLEL": GematriaTypes.MISPAR_KOLEL,
}


class TestConnectionsDataIntegrity:
    """Verify that every record in connections.json has correct gematria values."""

    @pytest.fixture()
    def connection_records(self):
        path = PROJECT_ROOT / "data" / "gematria" / "connections.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)["records"]

    def test_all_terms_match_stated_value(self, connection_records):
        errors = []
        for i, record in enumerate(connection_records):
            value = record["value"]
            method_name = record["method"]
            gtype = _GEMATRIA_TYPE_MAP.get(method_name)
            if gtype is None:
                continue
            for term in record["terms"]:
                computed = int(Hebrew(term).gematria(gtype))
                if computed != value:
                    errors.append(
                        f"Record {i}: term '{term}' has {method_name}={computed}, "
                        f"but record claims {value}"
                    )
        assert not errors, "Connections data errors:\n" + "\n".join(errors)

    def test_no_duplicate_records(self, connection_records):
        seen = set()
        dupes = []
        for i, record in enumerate(connection_records):
            key = (record["value"], record["method"], tuple(sorted(record["terms"])))
            if key in seen:
                dupes.append(f"Record {i}: duplicate {key}")
            seen.add(key)
        assert not dupes, "Duplicate records:\n" + "\n".join(dupes)
