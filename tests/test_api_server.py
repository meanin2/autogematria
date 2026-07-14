"""Tests for the API server routes and web UI."""


import pytest

from autogematria.tools.api_server import (
    AutoGematriaHandler,
    _build_routes,
    _handle_search_name,
)


class TestRoutes:
    def test_routes_have_all_endpoints(self):
        routes = _build_routes()
        assert "/health" in routes
        assert "/api/showcase-name" in routes
        assert "/api/search-name" in routes
        assert "/api/full-report" in routes
        assert "/api/reverse-lookup" in routes
        assert "/api/estimate" in routes
        assert "/api/run-stats" in routes
        assert "/api/jobs" in routes

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


class TestEstimateHandler:
    def test_estimate_returns_seconds(self):
        routes = _build_routes()
        handler = routes["/api/estimate"]["POST"]
        result = handler({"query": "משה", "operation": "full_report"})
        assert "estimated_seconds" in result
        assert result["estimated_seconds"] > 0

    def test_run_stats(self):
        routes = _build_routes()
        handler = routes["/api/run-stats"]["GET"]
        result = handler(None)
        assert "total_runs" in result


class TestInputValidation:
    def test_unknown_search_method_is_rejected_before_search(self):
        with pytest.raises(ValueError, match="Unknown methods"):
            _handle_search_name({"query": "משה", "methods": ["made_up"]})

    def test_out_of_range_search_budget_is_rejected(self):
        with pytest.raises(ValueError, match="max_results"):
            _handle_search_name({"query": "משה", "max_results": 1000})

    def test_reverse_lookup_rejects_unknown_method(self):
        handler = _build_routes()["/api/reverse-lookup"]["POST"]
        with pytest.raises(ValueError, match="method"):
            handler({"value": 345, "method": "NOT_A_METHOD"})


def _dispatch_capture(path: str, headers: dict[str, str] | None = None):
    handler = object.__new__(AutoGematriaHandler)
    handler.path = path
    handler.headers = headers or {}
    captured = []
    handler._json_response = lambda payload, status=200: captured.append((status, payload))
    handler._html_response = lambda payload, status=200: captured.append((status, payload))
    handler._text_response = lambda payload, status=200: captured.append((status, payload))
    handler._base_url = lambda: "http://test"
    return handler, captured


class TestAuthenticationAndHealth:
    def test_health_is_public_when_api_is_protected(self, monkeypatch):
        monkeypatch.setenv("AUTOGEMATRIA_API_TOKEN", "secret")
        handler, captured = _dispatch_capture("/health")
        handler._dispatch("GET")
        assert captured == [(200, {"status": "ok"})]

    def test_job_status_requires_authentication(self, monkeypatch):
        monkeypatch.setenv("AUTOGEMATRIA_API_TOKEN", "secret")
        handler, captured = _dispatch_capture("/api/jobs/private-job-id")
        handler._dispatch("GET")
        assert captured == [(401, {"error": "Unauthorized"})]

    def test_readiness_is_public_and_uses_503_when_not_ready(self, monkeypatch):
        monkeypatch.setenv("AUTOGEMATRIA_API_TOKEN", "secret")
        monkeypatch.setattr(
            "autogematria.tools.api_server.readiness_payload",
            lambda: ({"status": "not_ready", "error": "missing corpus"}, False),
        )
        handler, captured = _dispatch_capture("/ready")
        handler._dispatch("GET")
        assert captured == [
            (503, {"status": "not_ready", "error": "missing corpus"})
        ]


class TestWebUI:
    def test_ui_html_generated(self):
        from autogematria.tools.web_ui import build_ui_html

        html = build_ui_html("http://localhost:8080")
        assert "AutoGematria" in html
        assert "name-input" in html
        assert "/api/jobs" in html
        assert "/api/reverse-lookup" in html

    def test_ui_has_all_views(self):
        from autogematria.tools.web_ui import build_ui_html

        html = build_ui_html("")
        assert "view-search" in html
        assert "view-reverse" in html
        assert "view-about" in html

    def test_ui_has_progress_bar(self):
        from autogematria.tools.web_ui import build_ui_html

        html = build_ui_html("")
        assert "progress-bar" in html
        assert "progress-fill" in html
        assert "/api/estimate" in html

    def test_ui_has_hardware_info(self):
        from autogematria.tools.web_ui import build_ui_html

        html = build_ui_html("")
        assert "No GPU needed" in html
        assert "~40 MB" in html
        assert "~194 MB" in html

    def test_ui_can_send_optional_api_token(self):
        from autogematria.tools.web_ui import build_ui_html

        html = build_ui_html("")
        assert "autogematria_api_token" in html
        assert "Authorization" in html
        assert "apiFetch('/api/jobs'" in html
        assert "renderAcrosticMatches(r)" in html

    def test_ui_has_example_names(self):
        from autogematria.tools.web_ui import build_ui_html

        html = build_ui_html("")
        assert "example-chip" in html
