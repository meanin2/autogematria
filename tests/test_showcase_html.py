"""Tests for showcase HTML export."""

import json

import pytest

from autogematria.config import DB_PATH
from autogematria.research.html_export import render_showcase_html, write_showcase_site_bundle
from autogematria.tools import cli_entrypoints


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


def test_render_showcase_html_contains_brand_and_query():
    payload = {
        "query": "משה",
        "showcase": {
            "summary_line": "Found a clean direct textual hit.",
            "verdict_label": "Direct textual hit",
            "headline": {
                "found_text": "משה",
                "method": "SUBSTRING",
                "location": {"book": "Exodus", "chapter": 2, "verse": 10},
                "confidence": {"score": 0.98},
            },
            "headline_findings": [],
            "supporting_findings": [],
            "interesting_findings": [],
            "hidden_findings": 0,
        },
    }
    html = render_showcase_html(payload)
    assert "AutoGematria Showcase" in html
    assert "משה" in html
    assert "Exodus 2:10" in html


def test_show_name_cli_writes_html(monkeypatch, capsys, tmp_path):
    html_out = tmp_path / "moshe-showcase.html"
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


def test_write_showcase_site_bundle_writes_html_and_json(tmp_path):
    payload = {
        "query": "משה",
        "showcase": {
            "summary_line": "Found a clean direct textual hit.",
            "verdict_label": "Direct textual hit",
            "headline": {
                "found_text": "משה",
                "method": "SUBSTRING",
                "location": {"book": "Exodus", "chapter": 2, "verse": 10},
                "confidence": {"score": 0.98},
            },
            "headline_findings": [],
            "supporting_findings": [],
            "interesting_findings": [],
            "hidden_findings": 0,
        },
    }
    bundle = write_showcase_site_bundle(payload, tmp_path / "site")
    assert bundle["index_html"].exists()
    assert bundle["result_json"].exists()
    assert "AutoGematria Showcase" in bundle["index_html"].read_text(encoding="utf-8")
    saved = json.loads(bundle["result_json"].read_text(encoding="utf-8"))
    assert saved["query"] == "משה"


def test_show_name_cli_can_publish_here_now(monkeypatch, capsys, tmp_path):
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
