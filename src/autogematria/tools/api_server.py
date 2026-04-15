"""Deployable HTTP API for AutoGematria agent access and web UI."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from autogematria.tools.agent_site import (
    build_agent_html,
    build_agent_manifest,
    build_agent_text,
)
from autogematria.tools.tool_functions import find_name_in_torah, showcase_name


DEFAULT_PORT = 8080


def _normalize_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _handle_full_report(body: dict[str, Any]) -> dict[str, Any]:
    from autogematria.normalize import FinalsPolicy, normalize_hebrew
    from autogematria.research.html_export import prepare_showcase_payload
    from autogematria.research.name_report import build_name_report
    from autogematria.run_logger import RunTimer
    from autogematria.search.gematria_reverse import build_name_gematria_graph
    from autogematria.tools.tool_functions import showcase_name as _showcase

    query = body["query"]
    clean = normalize_hebrew(query, FinalsPolicy.PRESERVE).replace(" ", "")
    timer = RunTimer(
        operation="full_report",
        input_text=query,
        letter_count=len(clean),
        word_count=len(query.split()),
    )

    with timer:
        report = build_name_report(query)
        components = [(c["text"], c["role"]) for c in report.get("hebrew_components", [])]
        timer.component_count = len(components)

        showcase_raw = _showcase(report["full_hebrew_name"])
        prepared = prepare_showcase_payload(showcase_raw)
        showcase = prepared.get("showcase", {})

        graph = build_name_gematria_graph(components) if components else {}
        timer.set_result_metadata(
            verdict=showcase.get("verdict_label", ""),
            cross_matches=report.get("cross_comparison", {}).get("summary", {}).get("total_cross_matches", 0),
        )

    return {
        "report": report,
        "showcase": showcase,
        "graph": graph,
        "timing": {"elapsed_seconds": round(timer.elapsed_seconds, 2)},
    }


def _handle_reverse_lookup(body: dict[str, Any]) -> dict[str, Any]:
    from autogematria.run_logger import RunTimer
    from autogematria.search.gematria_reverse import reverse_lookup

    value = int(body["value"])
    method = body.get("method", "MISPAR_HECHRACHI")
    max_results = int(body.get("max_results", 50))

    with RunTimer(operation="reverse_lookup", input_text=str(value)):
        words = reverse_lookup(value, method=method, max_results=max_results)

    return {"value": value, "method": method, "words": words}


def _handle_estimate(body: dict[str, Any]) -> dict[str, Any]:
    from autogematria.normalize import FinalsPolicy, normalize_hebrew
    from autogematria.run_logger import estimate_seconds

    query = body.get("query", "")
    operation = body.get("operation", "full_report")
    clean = normalize_hebrew(query, FinalsPolicy.PRESERVE).replace(" ", "") if query else ""
    est = estimate_seconds(
        operation,
        letter_count=len(clean),
        word_count=len(query.split()) if query else 0,
    )
    return {"estimated_seconds": est, "operation": operation}


def _handle_run_stats(_body: dict[str, Any]) -> dict[str, Any]:
    from autogematria.run_logger import get_run_stats
    return get_run_stats()


def _handle_submit_full_report(body: dict[str, Any]) -> dict[str, Any]:
    from autogematria import jobs

    if "query" not in body or not str(body["query"]).strip():
        raise ValueError("query is required")
    job_id = jobs.create_job("full_report", {"query": body["query"]})
    job = jobs.get_job(job_id) or {}
    return {
        "job_id": job_id,
        "status": job.get("status", "queued"),
        "queue_position": job.get("queue_position", 1),
    }


def _build_routes() -> dict[str, dict[str, Any]]:
    return {
        "/health": {
            "GET": lambda _body: {"status": "ok"},
        },
        "/api/showcase-name": {
            "POST": lambda body: showcase_name(
                body["query"],
                corpus_scope=body.get("corpus_scope", "torah"),
                include_tanakh_expansion=_normalize_bool(
                    body.get("include_tanakh_expansion"),
                    default=True,
                ),
                methods=body.get("methods"),
                max_variants=int(body.get("max_variants", 8)),
                max_tasks=int(body.get("max_tasks", 40)),
                max_results_per_task=int(body.get("max_results_per_task", 6)),
                els_max_skip=int(body.get("els_max_skip", 60)),
                gematria_methods=body.get("gematria_methods"),
                max_gematria_span_words=int(body.get("max_gematria_span_words", 3)),
            ),
        },
        "/api/search-name": {
            "POST": lambda body: find_name_in_torah(
                name=body["query"],
                methods=body.get("methods"),
                book=body.get("book"),
                max_results=int(body.get("max_results", 20)),
                els_max_skip=int(body.get("els_max_skip", 500)),
                include_verification=_normalize_bool(
                    body.get("include_verification"),
                    default=True,
                ),
                corpus_scope=body.get("corpus_scope", "torah"),
            ),
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
        if method == "GET" and parsed.path.startswith("/api/jobs/"):
            from autogematria import jobs as _jobs

            job_id = parsed.path[len("/api/jobs/") :]
            job = _jobs.get_job(job_id)
            if job is None:
                self._json_response({"error": "job not found"}, status=404)
                return
            self._json_response(job)
            return
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
        route = self.routes.get(parsed.path)
        if route is None or method not in route:
            self._json_response({"error": "Not found"}, status=404)
            return
        if not self._authorize():
            self._json_response({"error": "Unauthorized"}, status=401)
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
            return auth[len("Bearer ") :] == expected
        return self.headers.get("X-API-Key") == expected

    def _read_json_body(self) -> dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", "0"))
        if content_len <= 0:
            return {}
        raw = self.rfile.read(content_len)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

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
