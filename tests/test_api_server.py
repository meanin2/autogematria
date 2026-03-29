"""Tests for the deployable HTTP API."""

from __future__ import annotations

import json
import threading
from urllib import error, request

import pytest

from autogematria.config import DB_PATH
from autogematria.tools.api_server import create_server


@pytest.fixture(autouse=True)
def skip_no_db():
    if not DB_PATH.exists():
        pytest.skip("Database not yet created")


@pytest.fixture
def api_server():
    server = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _json_request(url: str, *, method: str = "GET", payload: dict | None = None, headers=None):
    data = None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method=method, headers=request_headers)
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def test_health_endpoint(api_server):
    payload = _json_request(f"{api_server}/health")
    assert payload == {"status": "ok"}


def test_agent_instruction_surfaces(api_server):
    with request.urlopen(f"{api_server}/for-agents") as response:
        html = response.read().decode("utf-8")
    assert "Instructions for AI Agents" in html
    assert "/api/showcase-name" in html

    with request.urlopen(f"{api_server}/agent.txt") as response:
        text = response.read().decode("utf-8")
    assert "AutoGematria Agent Instructions" in text
    assert "POST /api/showcase-name" in text

    payload = _json_request(f"{api_server}/.well-known/autogematria-agent.json")
    assert payload["name"] == "AutoGematria Agent API"
    assert payload["endpoints"]["showcase_name"]["path"] == "/api/showcase-name"


def test_showcase_endpoint_returns_curated_payload(api_server):
    payload = _json_request(
        f"{api_server}/api/showcase-name",
        method="POST",
        payload={"query": "משה"},
    )
    assert payload["query"] == "משה"
    assert payload["showcase"]["headline"] is not None


def test_api_token_is_enforced(api_server, monkeypatch):
    monkeypatch.setenv("AUTOGEMATRIA_API_TOKEN", "secret-token")
    try:
        with pytest.raises(error.HTTPError) as excinfo:
            _json_request(
                f"{api_server}/api/showcase-name",
                method="POST",
                payload={"query": "משה"},
            )
        assert excinfo.value.code == 401

        payload = _json_request(
            f"{api_server}/api/showcase-name",
            method="POST",
            payload={"query": "משה"},
            headers={"Authorization": "Bearer secret-token"},
        )
        assert payload["query"] == "משה"
    finally:
        monkeypatch.delenv("AUTOGEMATRIA_API_TOKEN", raising=False)
