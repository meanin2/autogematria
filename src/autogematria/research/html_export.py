"""Standalone HTML export for showcase results."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any


def _ref(row: dict[str, Any]) -> str:
    loc = row.get("location") or {}
    return f"{loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}"


def _tag(row: dict[str, Any]) -> str:
    params = row.get("params") or {}
    mode = params.get("mode") or params.get("search_kind")
    method = row.get("method") or "?"
    return f"{method} / {mode}" if mode else str(method)


def _render_rows(rows: list[dict[str, Any]], title: str, tone: str) -> str:
    if not rows:
        return ""
    cards = []
    for row in rows:
        cards.append(
            f"""
            <article class="finding-card {tone}">
              <div class="finding-meta">
                <span class="pill">{escape(_tag(row))}</span>
                <span class="ref">{escape(_ref(row))}</span>
              </div>
              <h3 class="finding-text">{escape(str(row.get("found_text") or ""))}</h3>
              <p class="finding-score">Confidence {escape(str((row.get("confidence") or {}).get("score")))} </p>
            </article>
            """
        )
    return f"""
    <section class="finding-section">
      <div class="section-head">
        <h2>{escape(title)}</h2>
      </div>
      <div class="finding-grid">
        {''.join(cards)}
      </div>
    </section>
    """


def render_showcase_html(payload: dict[str, Any]) -> str:
    """Render a standalone HTML page for a showcase payload."""
    showcase = payload["showcase"]
    headline = showcase.get("headline") or {}
    headline_ref = _ref(headline) if headline else ""
    summary = escape(str(showcase.get("summary_line") or ""))
    query = escape(str(payload.get("query") or ""))
    verdict = escape(str(showcase.get("verdict_label") or ""))
    hidden = int(showcase.get("hidden_findings") or 0)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{query} · AutoGematria Showcase</title>
  <style>
    :root {{
      --ink: #1e1c1a;
      --paper: #f5efe2;
      --paper-deep: #eadfc7;
      --gold: #b8872f;
      --gold-soft: #d5b46d;
      --crimson: #7a2f2f;
      --forest: #315441;
      --slate: #364353;
      --shadow: rgba(34, 23, 8, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(184,135,47,0.28), transparent 24rem),
        radial-gradient(circle at bottom right, rgba(49,84,65,0.18), transparent 24rem),
        linear-gradient(135deg, #f9f3e7 0%, #efe5d1 48%, #f6ecdb 100%);
    }}
    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 48px 24px 72px;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      border-radius: 28px;
      padding: 36px;
      background:
        linear-gradient(135deg, rgba(31,28,26,0.96), rgba(57,43,20,0.95)),
        linear-gradient(45deg, rgba(184,135,47,0.32), transparent);
      color: #fff8ea;
      box-shadow: 0 24px 80px var(--shadow);
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(90deg, transparent 0, rgba(255,255,255,0.05) 50%, transparent 100%);
      transform: translateX(-100%);
      animation: shimmer 6s infinite;
    }}
    @keyframes shimmer {{
      to {{ transform: translateX(100%); }}
    }}
    .brand {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--gold-soft);
    }}
    .brand-mark {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: linear-gradient(135deg, var(--gold-soft), #fff4c7);
      box-shadow: 0 0 24px rgba(213,180,109,0.7);
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1.4fr 0.8fr;
      gap: 24px;
      margin-top: 22px;
      align-items: end;
    }}
    .query {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Garamond, serif;
      font-size: clamp(42px, 9vw, 84px);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }}
    .summary {{
      margin: 18px 0 0;
      max-width: 46rem;
      font-size: 18px;
      line-height: 1.6;
      color: rgba(255, 248, 234, 0.88);
    }}
    .hero-aside {{
      display: grid;
      gap: 12px;
      justify-items: start;
    }}
    .stat {{
      width: 100%;
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 18px;
      padding: 14px 16px;
      background: rgba(255,255,255,0.06);
      backdrop-filter: blur(10px);
    }}
    .stat-label {{
      font-size: 11px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: rgba(255,248,234,0.72);
    }}
    .stat-value {{
      margin-top: 8px;
      font-size: 22px;
      font-weight: 700;
    }}
    .headline-panel {{
      margin-top: 28px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }}
    .headline-card, .ledger-card {{
      border-radius: 22px;
      padding: 22px;
      background: rgba(255, 249, 239, 0.94);
      box-shadow: 0 14px 36px var(--shadow);
    }}
    .headline-card {{
      border: 1px solid rgba(184,135,47,0.22);
    }}
    .headline-card h2, .ledger-card h2, .section-head h2 {{
      margin: 0 0 10px;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Garamond, serif;
      font-size: 30px;
      line-height: 1.1;
    }}
    .headline-big {{
      font-size: 42px;
      line-height: 1;
      letter-spacing: -0.03em;
      margin: 6px 0 14px;
    }}
    .headline-ref {{
      font-size: 16px;
      color: var(--slate);
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin: 34px 0 16px;
    }}
    .finding-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }}
    .finding-card {{
      position: relative;
      overflow: hidden;
      min-height: 172px;
      border-radius: 20px;
      padding: 18px;
      color: white;
      box-shadow: 0 16px 32px var(--shadow);
    }}
    .finding-card.headline {{
      background: linear-gradient(135deg, #8f6424, #caa24e 54%, #f6ddb1);
      color: #1d1204;
    }}
    .finding-card.supporting {{
      background: linear-gradient(135deg, #1f4e4b, #4e8a78 60%, #b7dbc7);
      color: #f6fffa;
    }}
    .finding-card.interesting {{
      background: linear-gradient(135deg, #4a304c, #815486 55%, #d9bfdc);
      color: #fff8ff;
    }}
    .finding-meta {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      font-size: 12px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.16);
      border: 1px solid rgba(255,255,255,0.22);
      backdrop-filter: blur(8px);
    }}
    .finding-text {{
      margin: 20px 0 12px;
      font-size: 28px;
      line-height: 1.05;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Garamond, serif;
    }}
    .finding-score {{
      margin: 0;
      font-size: 13px;
      opacity: 0.85;
    }}
    .footer-note {{
      margin-top: 28px;
      padding: 16px 18px;
      border-radius: 18px;
      background: rgba(255,255,255,0.58);
      border: 1px solid rgba(54,67,83,0.08);
      color: var(--slate);
      font-size: 14px;
    }}
    @media (max-width: 860px) {{
      .hero-grid, .headline-panel {{
        grid-template-columns: 1fr;
      }}
      .page {{
        padding: 24px 16px 48px;
      }}
      .hero {{
        padding: 26px;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="brand"><span class="brand-mark"></span> AutoGematria Showcase</div>
      <div class="hero-grid">
        <div>
          <h1 class="query">{query}</h1>
          <p class="summary">{summary}</p>
        </div>
        <aside class="hero-aside">
          <div class="stat">
            <div class="stat-label">Verdict</div>
            <div class="stat-value">{verdict}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Headline Ref</div>
            <div class="stat-value">{escape(headline_ref or "No direct hit")}</div>
          </div>
          <div class="stat">
            <div class="stat-label">Hidden Findings</div>
            <div class="stat-value">{hidden}</div>
          </div>
        </aside>
      </div>
    </section>

    <section class="headline-panel">
      <article class="headline-card">
        <h2>Headline Finding</h2>
        <div class="headline-big">{escape(str(headline.get("found_text") or "No presentable hit"))}</div>
        <div class="headline-ref">{escape(headline_ref or "No reference available")}</div>
      </article>
      <article class="ledger-card">
        <h2>How to Read This</h2>
        <p>This page promotes clean, verified findings first. Direct textual hits are prioritized, while gematria, acrostic, and ELS-style results are kept visible but clearly separated.</p>
      </article>
    </section>

    {_render_rows(showcase.get("headline_findings") or [], "Headline Findings", "headline")}
    {_render_rows(showcase.get("supporting_findings") or [], "Supporting Findings", "supporting")}
    {_render_rows(showcase.get("interesting_findings") or [], "Interesting Findings", "interesting")}

    <div class="footer-note">
      Built from the same deterministic research ledger used by the CLI. For the complete audit trail, run <code>ag-research-name "{query}" --json</code>.
    </div>
  </main>
</body>
</html>
"""


def write_showcase_html(payload: dict[str, Any], output_path: str | Path) -> Path:
    """Write a standalone showcase page to disk."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_showcase_html(payload), encoding="utf-8")
    return out


def write_showcase_site_bundle(payload: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
    """Write a publishable static site bundle with HTML and machine-readable JSON."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.html"
    result_path = out_dir / "result.json"
    index_path.write_text(render_showcase_html(payload), encoding="utf-8")
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "directory": out_dir,
        "index_html": index_path,
        "result_json": result_path,
    }
