"""Deployable HTTP API for AutoGematria agent access and web UI."""

from __future__ import annotations

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from autogematria.config import TANAKH_BOOKS, normalize_corpus_scope
from autogematria.gematria_index import ALL_METHODS
from autogematria.report_service import build_full_report_payload
from autogematria.runtime_data import readiness_payload
from autogematria.tools.agent_site import (
    build_agent_html,
    build_agent_manifest,
    build_agent_text,
)
from autogematria.tools.tool_functions import find_name_in_torah, showcase_name


DEFAULT_PORT = 8080
SEARCH_METHODS = {
    "substring",
    "roshei_tevot",
    "sofei_tevot",
    "emtzaei_tevot",
    "els",
}
RESEARCH_METHODS = SEARCH_METHODS | {"gematria"}
GEMATRIA_METHODS = {method.name for method in ALL_METHODS}
BOOK_NAMES = {book[0] for book in TANAKH_BOOKS}


def _normalize_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _handle_full_report(body: dict[str, Any]) -> dict[str, Any]:
    return build_full_report_payload(_validate_query(body))


def _handle_reverse_lookup(body: dict[str, Any]) -> dict[str, Any]:
    from autogematria.run_logger import RunTimer
    from autogematria.search.gematria_reverse import reverse_lookup

    value = _bounded_int(body.get("value"), name="value", default=None, lo=0, hi=10_000_000)
    method = body.get("method", "MISPAR_HECHRACHI")
    if not isinstance(method, str) or method not in GEMATRIA_METHODS:
        raise ValueError(f"'method' must be one of {sorted(GEMATRIA_METHODS)}")
    max_results = _bounded_int(
        body.get("max_results"), name="max_results", default=50, lo=1, hi=500
    )

    with RunTimer(operation="reverse_lookup", input_text=str(value)):
        words = reverse_lookup(value, method=method, max_results=max_results)

    return {"value": value, "method": method, "words": words}


def _handle_estimate(body: dict[str, Any]) -> dict[str, Any]:
    from autogematria.normalize import FinalsPolicy, normalize_hebrew
    from autogematria.run_logger import estimate_seconds

    query = _validate_query(body)
    operation = body.get("operation", "full_report")
    if operation not in {"full_report", "name_report", "reverse_lookup", "showcase", "search"}:
        raise ValueError("Unknown operation")
    clean = normalize_hebrew(query, FinalsPolicy.PRESERVE).replace(" ", "")
    est = estimate_seconds(
        operation,
        letter_count=len(clean),
        word_count=len(query.split()) if query else 0,
    )
    return {"estimated_seconds": est, "operation": operation}


def _handle_run_stats(_body: dict[str, Any]) -> dict[str, Any]:
    from autogematria.run_logger import get_run_stats
    return get_run_stats()


def _bounded_int(
    value: Any,
    *,
    name: str,
    default: int | None,
    lo: int,
    hi: int,
) -> int:
    if value is None:
        if default is None:
            raise ValueError(f"Missing required field: {name}")
        value = default
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise ValueError(f"'{name}' must be an integer between {lo} and {hi}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{name}' must be an integer between {lo} and {hi}") from exc
    if parsed < lo or parsed > hi:
        raise ValueError(f"'{name}' must be between {lo} and {hi}")
    return parsed


def _validate_methods(value: Any, *, allowed: set[str], field: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"'{field}' must be a JSON list of method names")
    if not value:
        raise ValueError(f"'{field}' must contain at least one method")
    methods = [item.strip().lower() for item in value]
    unknown = sorted(set(methods) - allowed)
    if unknown:
        raise ValueError(f"Unknown {field}: {', '.join(unknown)}")
    return methods


def _validate_gematria_methods(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("'gematria_methods' must be a JSON list of method names")
    if not value:
        raise ValueError("'gematria_methods' must contain at least one method")
    methods = [item.strip().upper() for item in value]
    unknown = sorted(set(methods) - GEMATRIA_METHODS)
    if unknown:
        raise ValueError(f"Unknown gematria_methods: {', '.join(unknown)}")
    return methods


def _validate_book(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in BOOK_NAMES:
        raise ValueError("'book' must be an English Tanakh book name")
    return value


def _validate_scope(body: dict[str, Any]) -> str:
    value = body.get("corpus_scope", "torah")
    if not isinstance(value, str):
        raise ValueError("'corpus_scope' must be 'torah' or 'tanakh'")
    return normalize_corpus_scope(value)


def _validate_query(body: dict[str, Any]) -> str:
    query = body["query"]
    if not isinstance(query, str) or not query.strip():
        raise ValueError("'query' must be a non-empty string")
    query = query.strip()
    if len(query) > 500:
        raise ValueError(f"'query' too long ({len(query)} chars, max 500)")
    return query


def _handle_submit_full_report(body: dict[str, Any]) -> dict[str, Any]:
    from autogematria import jobs

    _validate_query(body)
    job_id = jobs.create_job("full_report", {"query": body["query"]})
    job = jobs.get_job(job_id) or {}
    return {
        "job_id": job_id,
        "status": job.get("status", "queued"),
        "queue_position": job.get("queue_position", 1),
    }


def _handle_showcase_name(body: dict[str, Any]) -> dict[str, Any]:
    return showcase_name(
        _validate_query(body),
        corpus_scope=_validate_scope(body),
        include_tanakh_expansion=_normalize_bool(
            body.get("include_tanakh_expansion"), default=True
        ),
        methods=_validate_methods(
            body.get("methods"), allowed=RESEARCH_METHODS, field="methods"
        ),
        max_variants=_bounded_int(
            body.get("max_variants"), name="max_variants", default=8, lo=1, hi=24
        ),
        max_tasks=_bounded_int(
            body.get("max_tasks"), name="max_tasks", default=40, lo=1, hi=100
        ),
        max_results_per_task=_bounded_int(
            body.get("max_results_per_task"),
            name="max_results_per_task",
            default=6,
            lo=1,
            hi=20,
        ),
        els_max_skip=_bounded_int(
            body.get("els_max_skip"), name="els_max_skip", default=60, lo=1, hi=500
        ),
        gematria_methods=_validate_gematria_methods(body.get("gematria_methods")),
        max_gematria_span_words=_bounded_int(
            body.get("max_gematria_span_words"),
            name="max_gematria_span_words",
            default=3,
            lo=1,
            hi=10,
        ),
    )


def _handle_search_name(body: dict[str, Any]) -> dict[str, Any]:
    return find_name_in_torah(
        name=_validate_query(body),
        methods=_validate_methods(
            body.get("methods"), allowed=SEARCH_METHODS, field="methods"
        ),
        book=_validate_book(body.get("book")),
        max_results=_bounded_int(
            body.get("max_results"), name="max_results", default=20, lo=1, hi=100
        ),
        els_max_skip=_bounded_int(
            body.get("els_max_skip"), name="els_max_skip", default=500, lo=1, hi=1000
        ),
        include_verification=_normalize_bool(
            body.get("include_verification"), default=True
        ),
        corpus_scope=_validate_scope(body),
    )


def _build_routes() -> dict[str, dict[str, Any]]:
    return {
        "/health": {
            "GET": lambda _body: {"status": "ok"},
        },
        "/api/showcase-name": {
            "POST": _handle_showcase_name,
        },
        "/api/search-name": {
            "POST": _handle_search_name,
        },
        "/api/full-report": {
            "POST": _handle_full_report,
        },
        "/api/reverse-lookup": {
            "POST": _handle_reverse_lookup,
        },
        "/api/estimate": {
            "POST": _handle_estimate,
        },
        "/api/run-stats": {
            "GET": lambda _body: _handle_run_stats({}),
        },
        "/api/jobs": {
            "POST": _handle_submit_full_report,
        },
    }


class AutoGematriaHandler(BaseHTTPRequestHandler):
    routes = _build_routes()
    token_env_var = "AUTOGEMATRIA_API_TOKEN"

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._set_headers("application/json")
        self.end_headers()

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        if method == "GET" and parsed.path in ("/", "/ui"):
            from autogematria.tools.web_ui import build_ui_html
            self._html_response(build_ui_html(self._base_url()))
            return
        if method == "GET" and parsed.path == "/for-agents":
            self._html_response(build_agent_html(self._base_url()))
            return
        if method == "GET" and parsed.path == "/agent.txt":
            self._text_response(build_agent_text(self._base_url()))
            return
        if method == "GET" and parsed.path == "/.well-known/autogematria-agent.json":
            self._json_response(build_agent_manifest(self._base_url()))
            return
        if method == "GET" and parsed.path == "/ready":
            payload, ready = readiness_payload()
            self._json_response(payload, status=200 if ready else 503)
            return
        if parsed.path.startswith("/api/") and not self._authorize():
            self._json_response({"error": "Unauthorized"}, status=401)
            return
        if method == "GET" and parsed.path.startswith("/api/jobs/"):
            from autogematria import jobs as _jobs

            job_id = parsed.path[len("/api/jobs/") :]
            if not job_id or "/" in job_id:
                self._json_response({"error": "Not found"}, status=404)
                return
            job = _jobs.get_job(job_id)
            if job is None:
                self._json_response({"error": "job not found"}, status=404)
                return
            self._json_response(job)
            return
        route = self.routes.get(parsed.path)
        if route is None or method not in route:
            self._json_response({"error": "Not found"}, status=404)
            return
        try:
            body = self._read_json_body() if method == "POST" else {}
            payload = route[method](body)
        except json.JSONDecodeError as exc:
            self._json_response({"error": f"Invalid JSON: {exc}"}, status=400)
            return
        except KeyError as exc:
            self._json_response({"error": f"Missing required field: {exc.args[0]}"}, status=400)
            return
        except ValueError as exc:
            self._json_response({"error": str(exc)}, status=400)
            return
        except Exception as exc:  # pragma: no cover - defensive error boundary
            self._json_response({"error": str(exc)}, status=500)
            return
        self._json_response(payload)

    def _authorize(self) -> bool:
        expected = os.environ.get(self.token_env_var)
        if not expected:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return hmac.compare_digest(auth[len("Bearer ") :], expected)
        provided = self.headers.get("X-API-Key") or ""
        return hmac.compare_digest(provided, expected)

    _MAX_BODY_BYTES = 65_536  # 64 KB

    def _read_json_body(self) -> dict[str, Any]:
        try:
            content_len = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header") from exc
        if content_len <= 0:
            return {}
        if content_len > self._MAX_BODY_BYTES:
            raise ValueError(f"Request body too large ({content_len} bytes, max {self._MAX_BODY_BYTES})")
        raw = self.rfile.read(content_len)
        if not raw:
            return {}
        body = json.loads(raw.decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object")
        return body

    def _set_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-API-Key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def _base_url(self) -> str:
        proto = self.headers.get("X-Forwarded-Proto") or "http"
        host = self.headers.get("Host") or f"127.0.0.1:{self.server.server_port}"
        return f"{proto}://{host}"

    def _json_response(self, payload: dict[str, Any], *, status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self._set_headers("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _text_response(self, payload: str, *, status: int = 200) -> None:
        encoded = payload.encode("utf-8")
        self.send_response(status)
        self._set_headers("text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _html_response(self, payload: str, *, status: int = 200) -> None:
        encoded = payload.encode("utf-8")
        self.send_response(status)
        self._set_headers("text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def create_server(port: int) -> ThreadingHTTPServer:
    from autogematria.job_worker import start_worker
    from autogematria.runtime_data import ensure_runtime_state, validate_corpus_database

    validate_corpus_database()
    ensure_runtime_state()
    start_worker()
    ThreadingHTTPServer.allow_reuse_address = True
    return ThreadingHTTPServer(("0.0.0.0", port), AutoGematriaHandler)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ag-serve-api")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", DEFAULT_PORT)))
    args = parser.parse_args()
    server = create_server(args.port)
    print(f"AutoGematria API listening on 0.0.0.0:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
