"""Tests for the API server routes and web UI."""

import json

import pytest

from autogematria.tools.api_server import AutoGematriaHandler, _build_routes


class TestRoutes:
    def test_routes_have_all_endpoints(self):
        routes = _build_routes()
        assert "/health" in routes
        assert "/api/showcase-name" in routes
        assert "/api/search-name" in routes
        assert "/api/full-report" in routes
        assert "/api/reverse-lookup" in routes

    def test_health_check(self):
        routes = _build_routes()
        result = routes["/health"]["GET"](None)
        assert result == {"status": "ok"}


class TestReverseLookupHandler:
    def test_reverse_lookup_basic(self):
        routes = _build_routes()
        handler = routes["/api/reverse-lookup"]["POST"]
        result = handler({"value": 345, "method": "MISPAR_HECHRACHI"})
        assert result["value"] == 345
        assert result["method"] == "MISPAR_HECHRACHI"
        words = [w["word"] for w in result["words"]]
        assert "משה" in words

    def test_reverse_lookup_default_method(self):
        routes = _build_routes()
        handler = routes["/api/reverse-lookup"]["POST"]
        result = handler({"value": 345})
        assert result["method"] == "MISPAR_HECHRACHI"


class TestWebUI:
    def test_ui_html_generated(self):
        from autogematria.tools.web_ui import build_ui_html

        html = build_ui_html("http://localhost:8080")
        assert "AutoGematria" in html
        assert "name-input" in html
        assert "/api/full-report" in html
        assert "/api/reverse-lookup" in html

    def test_ui_has_all_views(self):
        from autogematria.tools.web_ui import build_ui_html

        html = build_ui_html("")
        assert "view-search" in html
        assert "view-reverse" in html
        assert "view-about" in html
