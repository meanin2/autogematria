"""Public instruction surfaces for external agents."""

from __future__ import annotations

import json
from html import escape
from typing import Any


def build_agent_manifest(base_url: str) -> dict[str, Any]:
    """Return a machine-readable description of the service for agents."""
    return {
        "name": "AutoGematria Agent API",
        "description": (
            "Research and showcase where a Hebrew name or phrase appears in Torah/Tanakh "
            "using direct text search, acrostics, ELS, and gematria methods."
        ),
        "base_url": base_url,
        "instructions_url": f"{base_url}/for-agents",
        "text_instructions_url": f"{base_url}/agent.txt",
        "healthcheck_url": f"{base_url}/health",
        "preferred_flow": [
            "Fetch /for-agents or /agent.txt for operator guidance.",
            "POST /api/showcase-name with a Hebrew query for the presentable result.",
            "Use POST /api/search-name only when raw direct search results are needed.",
            "Treat direct verified substring results as strongest evidence.",
            "Do not treat weak ELS or gematria findings as proof without reading method metadata.",
        ],
        "auth": {
            "optional_bearer_env": "AUTOGEMATRIA_API_TOKEN",
            "headers": ["Authorization: Bearer <token>", "X-API-Key: <token>"],
        },
        "endpoints": {
            "showcase_name": {
                "method": "POST",
                "path": "/api/showcase-name",
                "content_type": "application/json",
                "body": {
                    "query": "משה",
                    "corpus_scope": "torah",
                    "include_tanakh_expansion": True,
                },
                "returns": "Curated presentable result plus full research ledger.",
            },
            "search_name": {
                "method": "POST",
                "path": "/api/search-name",
                "content_type": "application/json",
                "body": {
                    "query": "משה",
                    "corpus_scope": "torah",
                    "include_verification": True,
                },
                "returns": "Direct multi-method search output.",
            },
        },
    }


def build_agent_text(base_url: str) -> str:
    """Return concise plaintext instructions aimed at external agents."""
    return (
        "AutoGematria Agent Instructions\n\n"
        f"Base URL: {base_url}\n"
        "1. Check health with GET /health.\n"
        "2. For the normal user-facing result, POST /api/showcase-name with JSON like "
        '{"query":"משה"}.\n'
        "3. Read showcase.headline and showcase.summary_line first.\n"
        "4. If you need raw search evidence, POST /api/search-name.\n"
        "5. Prefer verified direct textual hits over weaker methods such as high-skip ELS "
        "or indirect gematria matches.\n"
        "6. If the service is protected, send Authorization: Bearer <token>.\n"
    )


def build_agent_html(base_url: str) -> str:
    """Return a public branded HTML page that explains how other agents should use the API."""
    manifest = build_agent_manifest(base_url)
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    example_url = f"{base_url}/api/showcase-name"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AutoGematria for Agents</title>
  <style>
    :root {{
      --bg: #f4ecdc;
      --ink: #1b1712;
      --gold: #af7f2e;
      --forest: #355746;
      --panel: rgba(255,255,255,0.82);
      --shadow: rgba(37, 26, 11, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(175,127,46,0.22), transparent 25rem),
        radial-gradient(circle at bottom right, rgba(53,87,70,0.18), transparent 20rem),
        linear-gradient(135deg, #f8f2e6 0%, #f1e6d2 100%);
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(22,20,18,0.96), rgba(61,48,27,0.94));
      color: #fff6e8;
      border-radius: 28px;
      padding: 34px;
      box-shadow: 0 24px 60px var(--shadow);
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 12px;
      color: #d8b97b;
    }}
    h1 {{
      margin: 12px 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      font-size: clamp(38px, 7vw, 72px);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }}
    .hero p {{
      max-width: 46rem;
      font-size: 18px;
      line-height: 1.6;
      color: rgba(255,246,232,0.88);
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 18px;
      margin-top: 24px;
    }}
    .card {{
      background: var(--panel);
      border-radius: 22px;
      padding: 22px;
      box-shadow: 0 16px 34px var(--shadow);
    }}
    h2 {{
      margin: 0 0 12px;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      font-size: 30px;
    }}
    ol, ul {{
      margin: 0;
      padding-left: 20px;
      line-height: 1.7;
    }}
    pre {{
      margin: 0;
      padding: 16px;
      overflow-x: auto;
      border-radius: 16px;
      background: #181614;
      color: #fdf4df;
      font-size: 13px;
      line-height: 1.6;
    }}
    code {{
      font-family: "SFMono-Regular", "Menlo", monospace;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .links a {{
      text-decoration: none;
      color: white;
      background: linear-gradient(135deg, var(--forest), #4f7f67);
      padding: 10px 14px;
      border-radius: 999px;
    }}
    @media (max-width: 860px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="eyebrow">AutoGematria</div>
      <h1>Instructions for AI Agents</h1>
      <p>
        This service lets an agent look up a Hebrew name or phrase across Torah/Tanakh and receive either
        a curated presentable answer or the raw direct-search output. Start with the showcase endpoint unless
        you specifically need lower-level search results.
      </p>
      <div class="links">
        <a href="{escape(base_url)}/health">Health</a>
        <a href="{escape(base_url)}/agent.txt">Plain text instructions</a>
        <a href="{escape(base_url)}/.well-known/autogematria-agent.json">Machine-readable manifest</a>
      </div>
    </section>

    <section class="grid">
      <article class="card">
        <h2>Recommended Flow</h2>
        <ol>
          <li>Call <code>GET /health</code>.</li>
          <li>Call <code>POST /api/showcase-name</code> with a Hebrew <code>query</code>.</li>
          <li>Read <code>showcase.summary_line</code> and <code>showcase.headline</code> first.</li>
          <li>Only use <code>/api/search-name</code> when you need lower-level direct search output.</li>
          <li>Prefer direct verified textual hits over weaker ELS or indirect gematria findings.</li>
        </ol>
      </article>
      <article class="card">
        <h2>Example Request</h2>
        <pre><code>POST {escape(example_url)}
Content-Type: application/json

{{
  "query": "משה",
  "corpus_scope": "torah",
  "include_tanakh_expansion": true
}}</code></pre>
      </article>
    </section>

    <section class="grid">
      <article class="card">
        <h2>Auth</h2>
        <ul>
          <li>If the operator set <code>AUTOGEMATRIA_API_TOKEN</code>, send <code>Authorization: Bearer &lt;token&gt;</code>.</li>
          <li><code>X-API-Key</code> is also accepted.</li>
          <li>If no token is configured, the API is public.</li>
        </ul>
      </article>
      <article class="card">
        <h2>Machine-Readable Manifest</h2>
        <pre><code>{escape(manifest_json)}</code></pre>
      </article>
    </section>
  </main>
</body>
</html>
"""
