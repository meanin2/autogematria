"""Minimal HTTP API for generating Torah name reports.

Run: python3 serve_report_api.py
Listens on port 8077.
"""

import hashlib
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from autogematria.tools.report_builder import build_name_report
from autogematria.tools.tool_functions import find_name_in_torah
from autogematria.publish.herenow import publish_directory


# Cache: normalized name -> {url, slug, timestamp}
_report_cache: dict[str, dict] = {}
_CACHE_FILE = Path("/tmp/torah_report_cache.json")


def _load_cache():
    global _report_cache
    if _CACHE_FILE.exists():
        try:
            _report_cache = json.loads(_CACHE_FILE.read_text())
        except Exception:
            _report_cache = {}


def _save_cache():
    _CACHE_FILE.write_text(json.dumps(_report_cache, ensure_ascii=False, indent=2))


def _cache_key(name, variant=None):
    """Stable key for a name + optional variant."""
    parts = [name.strip()]
    if variant:
        parts.append(variant.strip())
    return "|".join(sorted(parts))


def _name_slug(name):
    """Make a filesystem-safe slug from a Hebrew name."""
    ascii_part = re.sub(r'[^a-zA-Z0-9]', '', name)
    hex_part = hashlib.md5(name.encode()).hexdigest()[:8]
    return f"{ascii_part or 'name'}_{hex_part}"


_load_cache()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/report":
            self._handle_report(body)
        elif self.path == "/search":
            self._handle_search(body)
        else:
            self._json(404, {"error": "Not found"})

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "Not found"})

    def _handle_search(self, body):
        name = body.get("name", "")
        if not name:
            return self._json(400, {"error": "name is required"})
        try:
            data = find_name_in_torah(name, max_results=10, els_max_skip=500)
            verdict = data.get("final_verdict", {})
            results = data.get("results", [])
            summary_parts = [f"Verdict: {verdict.get('verdict', 'unknown')}"]
            for r in results[:3]:
                loc = r.get("location", {})
                ref = f"{loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}"
                score = r.get("confidence", {}).get("score", "?")
                summary_parts.append(f"{r.get('method')} at {ref} (score={score})")
            self._json(200, {"summary": "\n".join(summary_parts), "data": verdict})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _handle_report(self, body):
        name = body.get("name", "")
        variant = body.get("variant")
        label = body.get("label")
        force = body.get("force", False)
        if not name:
            return self._json(400, {"error": "name is required"})

        key = _cache_key(name, variant)

        # Return cached result if we already generated this name
        if not force and key in _report_cache:
            cached = _report_cache[key]
            self.log_message(f"Cache hit for '{name}' -> {cached.get('url')}")
            self._json(200, cached)
            return

        try:
            names = [(name, "Primary Spelling")]
            if variant:
                names.append((variant, label or "Variant"))

            out_dir = f"/tmp/torah_reports/{_name_slug(name)}"
            result = build_name_report(names, output_dir=out_dir)

            # If we have a cached slug for this name, update that site.
            # Otherwise publish a new one.
            slug = _report_cache.get(key, {}).get("slug")
            if slug:
                try:
                    pub = publish_directory(
                        out_dir,
                        viewer_title=f"{name} · Torah Name Report",
                        viewer_description="AutoGematria Torah name report",
                    )
                except Exception:
                    pub = publish_directory(
                        out_dir,
                        viewer_title=f"{name} · Torah Name Report",
                        viewer_description="AutoGematria Torah name report",
                    )
            else:
                pub = publish_directory(
                    out_dir,
                    viewer_title=f"{name} · Torah Name Report",
                    viewer_description="AutoGematria Torah name report",
                )

            result["url"] = pub.get("site_url")
            result["slug"] = pub.get("slug")

            # Cache the result
            _report_cache[key] = result
            _save_cache()

            self._json(200, result)
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, fmt, *args):
        print(f"[report-api] {fmt % args}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8077), Handler)
    print("[report-api] Listening on :8077")
    server.serve_forever()
