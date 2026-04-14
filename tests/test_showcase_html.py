"""Tests for showcase HTML export."""

import json

import pytest

from autogematria.config import DB_PATH
import autogematria.research.html_export as html_export
from autogematria.research.html_export import render_showcase_html, write_showcase_site_bundle
from autogematria.tools import cli_entrypoints


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


@pytest.fixture
def enriched_payload():
    return {
        "query": "משה",
        "showcase": {
            "summary_line": "Found a clean direct textual hit.",
            "verdict_label": "Direct textual hit",
            "main_finding_explanation": "The name appears directly in the verse as an exact word.",
            "headline": {
                "found_text": "משה",
                "method": "SUBSTRING",
                "location": {"book": "Exodus", "chapter": 2, "verse": 10},
                "confidence": {"score": 0.98},
                "verse_context": {
                    "ref": "Exodus 2:10",
                    "hebrew": "וַתִּקְרָא שְׁמוֹ מֹשֶׁה",
                    "english": "She named him Moses.",
                },
                "explanation": "The name appears directly in the verse as an exact word.",
            },
            "headline_findings": [
                {
                    "found_text": "משה",
                    "method": "SUBSTRING",
                    "location": {"book": "Exodus", "chapter": 2, "verse": 10},
                    "confidence": {"score": 0.98},
                    "params": {"mode": "within_word", "exact_word_match": True},
                    "verse_context": {
                        "ref": "Exodus 2:10",
                        "hebrew": "וַתִּקְרָא שְׁמוֹ מֹשֶׁה",
                        "english": "She named him Moses.",
                    },
                    "explanation": "The name appears directly in the verse as an exact word.",
                }
            ],
            "supporting_findings": [],
            "interesting_findings": [],
            "hidden_findings": 0,
        },
    }


def test_render_showcase_html_contains_brand_and_query(enriched_payload):
    payload = enriched_payload
    html = render_showcase_html(payload)
    assert "AutoGematria Showcase" in html
    assert "משה" in html
    assert "Exodus 2:10" in html
    assert "She named him Moses." in html
    assert "The name appears directly in the verse as an exact word." in html


def test_show_name_cli_writes_html(monkeypatch, capsys, tmp_path):
    html_out = tmp_path / "moshe-showcase.html"
    monkeypatch.setattr(html_export, "_lookup_verse_context", lambda *args, **kwargs: {
        "ref": "Exodus 2:10",
        "hebrew": "וַתִּקְרָא שְׁמוֹ מֹשֶׁה",
        "english": "She named him Moses.",
    })
    monkeypatch.setattr(
        "sys.argv",
        ["ag-show-name", "משה", "--html-out", str(html_out), "--json"],
    )
    cli_entrypoints.show_name_main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["html_output"] == str(html_out)
    assert html_out.exists()
    html = html_out.read_text(encoding="utf-8")
    assert "AutoGematria Showcase" in html
    assert "משה" in html
    assert "She named him Moses." in html


def test_write_showcase_site_bundle_writes_html_and_json(tmp_path, enriched_payload):
    payload = enriched_payload
    bundle = write_showcase_site_bundle(payload, tmp_path / "site")
    assert bundle["index_html"].exists()
    assert bundle["result_json"].exists()
    assert "AutoGematria Showcase" in bundle["index_html"].read_text(encoding="utf-8")
    saved = json.loads(bundle["result_json"].read_text(encoding="utf-8"))
    assert saved["query"] == "משה"
    assert saved["showcase"]["headline"]["verse_context"]["english"] == "She named him Moses."


def test_show_name_cli_can_publish_here_now(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(html_export, "_lookup_verse_context", lambda *args, **kwargs: {
        "ref": "Exodus 2:10",
        "hebrew": "וַתִּקְרָא שְׁמוֹ מֹשֶׁה",
        "english": "She named him Moses.",
    })

    def fake_publish_directory(site_dir, **kwargs):
        site_root = tmp_path / "published"
        assert str(site_dir)
        return {
            "slug": "demo-slug",
            "site_url": "https://demo-slug.here.now/",
            "claimUrl": "https://here.now/claim?slug=demo-slug&token=abc",
            "expiresAt": "2026-03-30T00:00:00.000Z",
            "anonymous": True,
        }

    monkeypatch.setattr(cli_entrypoints, "publish_directory", fake_publish_directory)
    monkeypatch.setattr(
        "sys.argv",
        ["ag-show-name", "משה", "--publish-here-now", "--json"],
    )
    cli_entrypoints.show_name_main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["here_now"]["site_url"] == "https://demo-slug.here.now/"
    bundle = payload["site_bundle"]
    assert bundle["directory"]
    assert bundle["index_html"].endswith("index.html")
    assert bundle["result_json"].endswith("result.json")
