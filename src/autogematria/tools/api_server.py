"""Lightweight HTTP API for the AutoGematria pipeline.

Runs on port 8077, exposes a single endpoint for name search.
Designed to be called from the WhatsApp bridge container.
"""

from __future__ import annotations

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from autogematria.tools.pipeline import find_name_full_report


PORT = 8077


class GematriaHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json_response({"status": "ok"})
            return
        self._json_response({"error": "Use POST /search"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/search":
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len)) if content_len else {}
            name = body.get("name", "")
            book = body.get("book")
            els_max_skip = body.get("els_max_skip", 500)

            if not name:
                self._json_response({"error": "name is required"}, 400)
                return

            try:
                report = find_name_full_report(
                    name, book=book, els_max_skip=els_max_skip, max_results=15,
                )
                # Format a human-readable summary
                summary = format_report(report)
                self._json_response({"name": name, "summary": summary, "data": report})
            except Exception as e:
                self._json_response({"error": str(e)}, 500)
            return

        self._json_response({"error": "Not found"}, 404)

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Suppress default logging


def format_report(report: dict) -> str:
    """Format a pipeline report into a WhatsApp-friendly text summary."""
    lines = []
    name = report.get("name", "")
    lines.append(f"*{name} in the Torah*\n")

    # Gematria
    gem = report.get("gematria", {})
    std = gem.get("MISPAR_HECHRACHI", {})
    if std:
        equivs = std.get("equivalents", [])[:4]
        lines.append(f"*Gematria:* {std.get('value', '?')}")
        if equivs:
            lines.append(f"  Equivalent words: {', '.join(equivs)}")

    # Word gematria for multi-word names
    wg = report.get("word_gematria")
    if wg:
        for word, info in wg.items():
            equivs = info.get("equivalents", [])[:3]
            lines.append(f"  _{word}_ = {info.get('value', '?')} ({', '.join(equivs)})")

    # Other gematria methods
    for method in ["MISPAR_KATAN", "ATBASH"]:
        m = gem.get(method, {})
        if m:
            lines.append(f"  {method.replace('MISPAR_', '')}: {m.get('value', '?')}")

    # Search results
    results = report.get("search_results", {}).get("results", [])
    if results:
        lines.append(f"\n*Findings ({len(results)} total):*")
        for i, r in enumerate(results[:8], 1):
            loc = r.get("location", {})
            ref = f"{loc.get('book', '?')} {loc.get('chapter', '?')}:{loc.get('verse', '?')}"
            method = r.get("method", "?")
            if method == "ELS":
                skip = r.get("params", {}).get("skip", "?")
                lines.append(f"  {i}. ELS skip {skip} — {ref}")
            elif method == "SUBSTRING":
                lines.append(f"  {i}. Direct text — {ref}")
                if r.get("context"):
                    ctx = r["context"][:60] + "..." if len(r["context"]) > 60 else r["context"]
                    lines.append(f"     _{ctx}_")
            elif method in ("ROSHEI_TEVOT", "SOFEI_TEVOT"):
                label = "First letters" if method == "ROSHEI_TEVOT" else "Last letters"
                lines.append(f"  {i}. {label} — {ref}")
                if r.get("context"):
                    lines.append(f"     _{r['context'][:60]}_")
            else:
                lines.append(f"  {i}. {method} — {ref}")

    # Word results for multi-word names
    wr = report.get("word_results")
    if wr:
        for word, wresults in wr.items():
            hits = wresults.get("results", [])
            if hits:
                lines.append(f"\n*{word}* ({len(hits)} findings):")
                for r in hits[:3]:
                    loc = r.get("location", {})
                    ref = f"{loc.get('book', '?')} {loc.get('chapter', '?')}:{loc.get('verse', '?')}"
                    lines.append(f"  [{r.get('method', '?')}] {ref}")

    return "\n".join(lines)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    server = HTTPServer(("0.0.0.0", port), GematriaHandler)
    print(f"AutoGematria API running on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
