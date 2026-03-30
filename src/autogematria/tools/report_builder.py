"""Build highlighted HTML Torah name reports with ELS proximity analysis.

Generates self-contained HTML pages with highlighted pesukim showing
exactly which letters encode the name.  Supports publishing to here.now.
"""

import json
import sqlite3
from html import escape
from pathlib import Path

import httpx

from autogematria.config import DB_PATH, SEFARIA_BASE
from autogematria.normalize import extract_letters, FinalsPolicy
from autogematria.search.els_proximity import find_proximity_pairs
from autogematria.tools.tool_functions import find_name_in_torah, gematria_lookup, get_verse

# ---------------------------------------------------------------------------
# Verse highlighting
# ---------------------------------------------------------------------------

def _get_highlighted_verses(conn, highlight_map, max_verses=6):
    """Given {abs_letter_index: css_class}, return annotated verse HTML.

    Returns list of {ref, html, book, chapter, verse}.
    """
    if not highlight_map:
        return []

    all_indices = sorted(highlight_map.keys())
    # Find which verses contain highlighted letters
    placeholders = ",".join("?" * len(all_indices))
    rows = conn.execute(
        f"SELECT DISTINCT v.verse_id, b.api_name, c.chapter_num, v.verse_num "
        f"FROM letters l "
        f"JOIN verses v ON l.verse_id = v.verse_id "
        f"JOIN chapters c ON v.chapter_id = c.chapter_id "
        f"JOIN books b ON c.book_id = b.book_id "
        f"WHERE l.absolute_letter_index IN ({placeholders}) "
        f"ORDER BY v.verse_id",
        all_indices,
    ).fetchall()

    results = []
    for vrow in rows[:max_verses]:
        vid = vrow["verse_id"]
        letters = conn.execute(
            "SELECT l.absolute_letter_index, l.letter_raw, l.word_id "
            "FROM letters l WHERE l.verse_id = ? ORDER BY l.absolute_letter_index",
            (vid,),
        ).fetchall()

        html_parts = []
        prev_wid = None
        for lt in letters:
            if prev_wid is not None and lt["word_id"] != prev_wid:
                html_parts.append(" ")
            prev_wid = lt["word_id"]
            aidx = lt["absolute_letter_index"]
            raw = lt["letter_raw"]
            if aidx in highlight_map:
                cls = highlight_map[aidx]
                html_parts.append(f'<span class="{cls}">{escape(raw)}</span>')
            else:
                html_parts.append(escape(raw))

        results.append({
            "ref": f"{vrow['api_name']} {vrow['chapter_num']}:{vrow['verse_num']}",
            "html": "".join(html_parts),
            "book": vrow["api_name"],
            "chapter": vrow["chapter_num"],
            "verse": vrow["verse_num"],
        })
    return results


def _compute_els_indices(token, skip, start_index):
    """Return list of absolute letter indices for an ELS."""
    norm = extract_letters(token, FinalsPolicy.NORMALIZE)
    if skip == 0:
        return [start_index + i for i in range(len(norm))]
    return [start_index + i * skip for i in range(len(norm))]


def build_highlighted_finding(conn, params):
    """Build highlighted verse HTML for a proximity finding."""
    surname_indices = _compute_els_indices(
        params["surname_token"],
        params["surname_skip"],
        params["surname_start_index"],
    )
    firstname_skip = params.get("firstname_skip") or 0
    firstname_start = params.get("firstname_start_index")
    if firstname_start is None:
        firstname_indices = []
    elif params.get("firstname_method") == "SUBSTRING" or firstname_skip == 0:
        norm = extract_letters(params["firstname_token"], FinalsPolicy.NORMALIZE)
        firstname_indices = [firstname_start + i for i in range(len(norm))]
    else:
        firstname_indices = _compute_els_indices(
            params["firstname_token"],
            firstname_skip,
            firstname_start,
        )

    highlight_map = {}
    for idx in surname_indices:
        highlight_map[idx] = "hl-surname"
    for idx in firstname_indices:
        highlight_map[idx] = "hl-firstname"

    return _get_highlighted_verses(conn, highlight_map, max_verses=6)


# ---------------------------------------------------------------------------
# English translations
# ---------------------------------------------------------------------------

_eng_cache = {}

def _fetch_english(book, chapter, verse):
    key = (book, chapter)
    if key not in _eng_cache:
        try:
            url = f"{SEFARIA_BASE}/{book}.{chapter}?commentary=0&context=0"
            resp = httpx.get(url, timeout=20.0)
            resp.raise_for_status()
            import re
            texts = resp.json().get("text", [])
            _eng_cache[key] = [
                re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(v or ""))).strip()
                for v in texts
            ]
        except Exception:
            _eng_cache[key] = []
    verses = _eng_cache[key]
    if 1 <= verse <= len(verses):
        return verses[verse - 1]
    return ""


# ---------------------------------------------------------------------------
# Report data generation
# ---------------------------------------------------------------------------

def generate_report_data(name, conn):
    data = find_name_in_torah(name, max_results=20, els_max_skip=500)
    enriched = []
    for r in data.get("results", [])[:8]:
        if r["method"] != "ELS_PROXIMITY":
            continue
        p = r["params"]
        highlighted_verses = build_highlighted_finding(conn, p)

        # Fetch English for each highlighted verse
        for hv in highlighted_verses:
            hv["english"] = _fetch_english(hv["book"], hv["chapter"], hv["verse"])

        r["highlighted_verses"] = highlighted_verses
        enriched.append(r)
    return {
        "results": enriched,
        "verdict": data["final_verdict"],
        "first_name_stats": data.get("first_name_stats"),
        "surname_gematria": data.get("surname_gematria"),
    }


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def render_finding_card(r, tone):
    p = r["params"]
    conf = r.get("confidence", {})
    score = conf.get("score", 0)
    score_pct = int(score * 100)
    distance = p.get("proximity_distance", "?")
    surname_skip = p.get("surname_skip", "?")
    firstname_skip = p.get("firstname_skip", "?")
    firstname_method = p.get("firstname_method", "?")
    bar_color = "#b8872f" if score >= 0.82 else "#4e8a78" if score >= 0.62 else "#815486"

    if firstname_method == "SUBSTRING" or firstname_skip == 0:
        fn_desc = "direct word"
    else:
        fn_desc = f"ELS skip {firstname_skip}"

    # Build highlighted verses HTML
    verses_html = ""
    for hv in r.get("highlighted_verses", []):
        eng = escape(hv.get("english", ""))
        eng_block = f'<p class="verse-english">{eng}</p>' if eng else ""
        verses_html += f'''
        <div class="annotated-verse">
          <div class="verse-ref">{escape(hv["ref"])}</div>
          <p class="verse-hebrew">{hv["html"]}</p>
          {eng_block}
        </div>
        '''

    return f'''
    <article class="finding-card {tone}">
      <div class="finding-meta">
        <span class="pill">ELS PROXIMITY</span>
        <span class="confidence-pct">{score_pct}%</span>
      </div>
      <div class="prox-stats">
        <div class="prox-stat">
          <div class="prox-label">Distance</div>
          <div class="prox-value">{distance} letters</div>
        </div>
        <div class="prox-stat">
          <div class="prox-label">Surname Skip</div>
          <div class="prox-value">{surname_skip}</div>
        </div>
        <div class="prox-stat">
          <div class="prox-label">First Name</div>
          <div class="prox-value">{fn_desc}</div>
        </div>
      </div>
      <p class="finding-explainer">
        <span class="hl-surname-label">{escape(str(p.get("surname_token", "")))}</span>
        encoded at equidistant skip {surname_skip},
        <span class="hl-firstname-label">{escape(str(p.get("firstname_token", "")))}</span>
        as {fn_desc} — {distance} letters apart.
      </p>
      <div class="verses-container">
        {verses_html}
      </div>
      <div class="confidence-bar">
        <div class="confidence-fill" style="width:{score_pct}%;background:{bar_color}"></div>
      </div>
    </article>
    '''


def render_gematria(gem):
    if not gem:
        return ""
    word = escape(str(gem.get("word", "")))
    value = gem.get("value", 0)
    items = ""
    for eq in gem.get("equivalents", [])[:6]:
        sample = eq.get("sample_location")
        loc = f" — {sample['book']} {sample['chapter']}:{sample['verse']}" if sample else ""
        items += f'<li><span class="gem-word">{escape(eq["word"])}</span> <span class="gem-freq">({eq["frequency"]}x{escape(loc)})</span></li>'
    return f'''
    <div class="gematria-box">
      <div class="gem-header">
        <span class="gem-name">{word}</span>
        <span class="gem-equals">=</span>
        <span class="gem-value">{value}</span>
      </div>
      <ul class="gem-list">{items}</ul>
    </div>
    '''


def render_section(hebrew_name, label, report, tone):
    verdict = report["verdict"]
    verdict_text = verdict["verdict"].replace("_", " ").title()
    confidence = int(float(verdict["confidence_score"]) * 100)
    rationale = ", ".join(verdict.get("rationale", []))
    stats = report.get("first_name_stats", {})
    stats_html = ""
    if stats:
        stats_html = f'<div class="stats-note">{escape(stats.get("note", ""))}</div>'

    cards = "".join(render_finding_card(r, tone) for r in report["results"][:6])
    gem_html = render_gematria(report.get("surname_gematria"))

    return f'''
    <section class="spelling-section">
      <div class="spelling-header {tone}-bg">
        <div class="spelling-label">{escape(label)}</div>
        <h2 class="spelling-name">{escape(hebrew_name)}</h2>
        <div class="spelling-verdict">
          <span class="verdict-badge">{escape(verdict_text)}</span>
          <span class="verdict-confidence">{confidence}% confidence</span>
        </div>
        <p class="spelling-rationale">{escape(rationale)}</p>
      </div>
      {stats_html}
      <div class="legend">
        <span class="legend-item"><span class="hl-surname">surname</span> ELS letters</span>
        <span class="legend-item"><span class="hl-firstname">first name</span> letters</span>
      </div>
      <div class="finding-grid">{cards}</div>
      {gem_html}
    </section>
    '''


def build_page(
    primary_name: str,
    sections: list[tuple[str, str, dict, str]],
    *,
    subtitle: str = "",
    first_name_count: int | None = None,
):
    """Build a complete HTML report page.

    Args:
        primary_name: Display name for the hero (e.g. "משה גינדי")
        sections: List of (hebrew_name, label, report_data, tone) tuples
        subtitle: Optional hero subtitle text
        first_name_count: Occurrence count for the first name (for stats)
    """
    first_token = primary_name.split()[0] if " " in primary_name else primary_name
    fn_stat = f"{escape(first_token)} · {first_name_count} occurrences" if first_name_count else escape(first_token)
    sub_text = escape(subtitle) if subtitle else (
        f"Torah source report for {escape(primary_name)}. "
        "The highlighted letters in each pasuk show exactly where the name is encoded — "
        '<span class="hl-surname">surname</span> in gold, '
        '<span class="hl-firstname">first name</span> in green.'
    )
    # sub_text may contain HTML spans, don't double-escape
    if not subtitle:
        sub_text = (
            f"Torah source report for {escape(primary_name)}. "
            "The highlighted letters in each pasuk show exactly where the name is encoded — "
            '<span class="hl-surname">surname</span> in gold, '
            '<span class="hl-firstname">first name</span> in green.'
        )

    sections_html = "\n".join(
        render_section(hname, label, report, tone)
        for hname, label, report, tone in sections
    )

    return f'''<!doctype html>
<html lang="en" dir="ltr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(primary_name)} · Torah Name Report</title>
  <style>
    :root {{
      --ink: #1e1c1a; --paper: #f5efe2; --gold: #b8872f; --gold-soft: #d5b46d;
      --forest: #315441; --slate: #364353; --shadow: rgba(34,23,8,0.14);
    }}
    * {{ box-sizing: border-box; margin: 0; }}
    body {{
      color: var(--ink);
      font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(184,135,47,0.28), transparent 24rem),
        radial-gradient(circle at bottom right, rgba(49,84,65,0.18), transparent 24rem),
        linear-gradient(135deg, #f9f3e7 0%, #efe5d1 48%, #f6ecdb 100%);
      min-height: 100vh;
    }}
    .page {{ max-width: 1200px; margin: 0 auto; padding: 48px 24px 72px; }}

    /* Highlights */
    .hl-surname {{
      background: linear-gradient(to bottom, rgba(184,135,47,0.35), rgba(184,135,47,0.18));
      border-bottom: 2.5px solid #b8872f;
      font-weight: 700; padding: 1px 2px; border-radius: 3px;
      font-size: 1.15em;
    }}
    .hl-firstname {{
      background: linear-gradient(to bottom, rgba(49,84,65,0.35), rgba(49,84,65,0.18));
      border-bottom: 2.5px solid #3a7a5a;
      font-weight: 700; padding: 1px 2px; border-radius: 3px;
      font-size: 1.15em;
    }}
    .hl-surname-label {{
      color: #8f6424; font-weight: 700;
      border-bottom: 2px solid #b8872f; padding-bottom: 1px;
    }}
    .hl-firstname-label {{
      color: #2d6b4f; font-weight: 700;
      border-bottom: 2px solid #3a7a5a; padding-bottom: 1px;
    }}

    /* Hero */
    .hero {{
      position: relative; overflow: hidden;
      border-radius: 28px; padding: 42px 36px;
      background: linear-gradient(135deg, rgba(31,28,26,0.96), rgba(57,43,20,0.95)),
                  linear-gradient(45deg, rgba(184,135,47,0.32), transparent);
      color: #fff8ea; box-shadow: 0 24px 80px var(--shadow);
    }}
    .hero::after {{
      content: ""; position: absolute; inset: 0;
      background: linear-gradient(90deg, transparent 0, rgba(255,255,255,0.05) 50%, transparent 100%);
      transform: translateX(-100%); animation: shimmer 6s infinite;
    }}
    @keyframes shimmer {{ to {{ transform: translateX(100%); }} }}
    .brand {{
      display: inline-flex; align-items: center; gap: 10px;
      font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--gold-soft);
    }}
    .brand-mark {{
      width: 12px; height: 12px; border-radius: 999px;
      background: linear-gradient(135deg, var(--gold-soft), #fff4c7);
      box-shadow: 0 0 24px rgba(213,180,109,0.7);
    }}
    .hero-content {{ margin-top: 20px; }}
    .hero-name {{
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Garamond, serif;
      font-size: clamp(48px, 10vw, 96px); line-height: 0.95; letter-spacing: -0.04em;
    }}
    .hero-sub {{
      margin-top: 18px; max-width: 52rem;
      font-size: 18px; line-height: 1.6; color: rgba(255,248,234,0.88);
    }}
    .hero-stats {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }}
    .hero-stat {{
      border: 1px solid rgba(255,255,255,0.14); border-radius: 16px;
      padding: 12px 18px; background: rgba(255,255,255,0.06); backdrop-filter: blur(10px);
    }}
    .hero-stat-label {{
      font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase;
      color: rgba(255,248,234,0.72);
    }}
    .hero-stat-value {{ margin-top: 6px; font-size: 20px; font-weight: 700; }}

    /* Spelling sections */
    .spelling-section {{ margin-top: 40px; }}
    .spelling-header {{
      border-radius: 22px; padding: 28px 30px; color: white;
      box-shadow: 0 16px 48px var(--shadow);
    }}
    .gold-bg {{ background: linear-gradient(135deg, #5c3d10, #8f6424 40%, #caa24e); }}
    .forest-bg {{ background: linear-gradient(135deg, #1a3d2e, #2d6b4f 40%, #5da67a); }}
    .spelling-label {{
      font-size: 13px; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.82;
    }}
    .spelling-name {{
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Garamond, serif;
      font-size: clamp(36px, 7vw, 60px); line-height: 1; margin-top: 8px;
    }}
    .spelling-verdict {{ display: flex; align-items: center; gap: 12px; margin-top: 16px; }}
    .verdict-badge {{
      display: inline-flex; padding: 6px 14px; border-radius: 999px;
      background: rgba(255,255,255,0.18); border: 1px solid rgba(255,255,255,0.24);
      font-size: 14px; font-weight: 600;
    }}
    .verdict-confidence {{ font-size: 15px; opacity: 0.88; }}
    .spelling-rationale {{ margin-top: 10px; font-size: 15px; opacity: 0.8; line-height: 1.5; }}

    .stats-note {{
      margin-top: 16px; padding: 14px 18px; border-radius: 16px;
      background: rgba(255,255,255,0.7); border: 1px solid rgba(54,67,83,0.1);
      font-size: 14px; color: var(--slate); line-height: 1.5;
    }}

    /* Legend */
    .legend {{
      display: flex; gap: 20px; margin: 16px 0 8px; font-size: 13px; color: var(--slate);
    }}
    .legend-item {{ display: flex; align-items: center; gap: 6px; }}

    /* Finding grid */
    .finding-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 16px; margin-top: 12px;
    }}
    .finding-card {{
      border-radius: 20px; padding: 20px;
      box-shadow: 0 14px 36px var(--shadow);
    }}
    .finding-card.gold {{
      background: linear-gradient(145deg, #faf2e0, #fff9ee);
      border: 1px solid rgba(184,135,47,0.22); color: var(--ink);
    }}
    .finding-card.forest {{
      background: linear-gradient(145deg, #eef6f1, #f5fbf7);
      border: 1px solid rgba(49,84,65,0.18); color: var(--ink);
    }}
    .finding-meta {{
      display: flex; align-items: center; justify-content: space-between;
    }}
    .pill {{
      display: inline-flex; padding: 5px 10px; border-radius: 999px; font-size: 11px;
      font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
    }}
    .gold .pill {{ background: rgba(184,135,47,0.14); color: #8f6424; border: 1px solid rgba(184,135,47,0.2); }}
    .forest .pill {{ background: rgba(49,84,65,0.12); color: #2d6b4f; border: 1px solid rgba(49,84,65,0.18); }}
    .confidence-pct {{ font-size: 18px; font-weight: 700; color: var(--slate); }}

    .prox-stats {{ display: flex; gap: 10px; margin: 14px 0; }}
    .prox-stat {{
      flex: 1; padding: 8px 10px; border-radius: 12px;
      background: rgba(0,0,0,0.04); text-align: center;
    }}
    .prox-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.6; }}
    .prox-value {{ font-size: 15px; font-weight: 700; margin-top: 2px; }}
    .finding-explainer {{ font-size: 14px; line-height: 1.6; margin: 10px 0 14px; color: #555; }}

    /* Annotated verses */
    .verses-container {{ display: flex; flex-direction: column; gap: 8px; }}
    .annotated-verse {{
      padding: 12px 14px; border-radius: 14px;
      background: rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.06);
    }}
    .verse-ref {{
      font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase;
      color: var(--slate); opacity: 0.7; margin-bottom: 6px;
    }}
    .verse-hebrew {{
      direction: rtl; font-size: 18px; line-height: 2;
      font-family: "David", "Times New Roman", serif;
    }}
    .verse-english {{
      font-size: 13px; line-height: 1.5; color: #777; margin-top: 6px;
      border-top: 1px solid rgba(0,0,0,0.06); padding-top: 6px;
    }}

    .confidence-bar {{
      margin-top: 12px; height: 4px; border-radius: 4px;
      background: rgba(0,0,0,0.08); overflow: hidden;
    }}
    .confidence-fill {{ height: 100%; border-radius: 4px; }}

    /* Gematria */
    .gematria-box {{
      margin-top: 20px; padding: 20px 24px; border-radius: 20px;
      background: rgba(255,255,255,0.8); border: 1px solid rgba(54,67,83,0.1);
      box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    }}
    .gem-header {{
      display: flex; align-items: center; gap: 12px;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
    }}
    .gem-name {{ font-size: 28px; direction: rtl; }}
    .gem-equals {{ font-size: 22px; color: var(--gold); }}
    .gem-value {{ font-size: 32px; font-weight: 700; color: var(--gold); }}
    .gem-list {{
      list-style: none; padding: 0; margin: 14px 0 0;
      display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px;
    }}
    .gem-list li {{ padding: 8px 12px; border-radius: 10px; background: rgba(0,0,0,0.03); font-size: 14px; }}
    .gem-word {{ font-size: 18px; font-weight: 600; direction: rtl; unicode-bidi: embed; font-family: "David", serif; }}
    .gem-freq {{ color: #888; font-size: 12px; }}

    /* Footer */
    .footer-note {{
      margin-top: 36px; padding: 18px 22px; border-radius: 18px;
      background: rgba(255,255,255,0.58); border: 1px solid rgba(54,67,83,0.08);
      color: var(--slate); font-size: 13px; line-height: 1.6;
    }}
    .footer-note code {{
      padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.06); font-size: 12px;
    }}

    @media (max-width: 860px) {{
      .page {{ padding: 24px 16px 48px; }}
      .hero {{ padding: 26px; }}
      .finding-grid {{ grid-template-columns: 1fr; }}
      .hero-stats, .prox-stats {{ flex-direction: column; }}
      .gem-list {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="brand"><span class="brand-mark"></span> AutoGematria</div>
      <div class="hero-content">
        <h1 class="hero-name">{escape(primary_name)}</h1>
        <p class="hero-sub">{sub_text}</p>
        <div class="hero-stats">
          <div class="hero-stat">
            <div class="hero-stat-label">First Name</div>
            <div class="hero-stat-value">{fn_stat}</div>
          </div>
          <div class="hero-stat">
            <div class="hero-stat-label">Method</div>
            <div class="hero-stat-value">ELS Proximity</div>
          </div>
          <div class="hero-stat">
            <div class="hero-stat-label">Scope</div>
            <div class="hero-stat-value">Torah (5 Books)</div>
          </div>
        </div>
      </div>
    </section>

    {sections_html}

    <div class="footer-note">
      <strong>How to read:</strong> Each card shows the Torah verses where both parts of the name
      are encoded near each other. The <span class="hl-surname">gold highlighted letters</span>
      spell the surname at equidistant intervals (ELS), while the
      <span class="hl-firstname">green highlighted letters</span> mark the first name.
      The "distance" is how many letters apart they are in the Torah text.
      <br><br>
      Generated by <strong>AutoGematria</strong> · deterministic, conservative, verifiable.
    </div>
  </main>
</body>
</html>
'''


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_TONES = ["gold", "forest", "slate"]


def build_name_report(
    names: list[tuple[str, str]],
    *,
    output_dir: str | Path = "/tmp/torah_name_report",
    primary_display: str | None = None,
    subtitle: str = "",
) -> dict:
    """Generate a complete HTML report for one or more name spellings.

    Args:
        names: List of (hebrew_name, label) tuples.
               e.g. [("משה גינדי", "Israeli spelling"), ("משה גנדי", "Aleppo spelling")]
        output_dir: Directory to write index.html to
        primary_display: Name to show in the hero. Defaults to names[0][0].
        subtitle: Optional subtitle for hero section.

    Returns:
        Dict with 'html_path' and 'reports' data.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    sections = []
    first_name_count = None
    for i, (name, label) in enumerate(names):
        report = generate_report_data(name, conn)
        tone = _TONES[i % len(_TONES)]
        sections.append((name, label, report, tone))
        if first_name_count is None and report.get("first_name_stats"):
            first_name_count = report["first_name_stats"].get("total_occurrences_in_scope")

    conn.close()

    display = primary_display or names[0][0]
    html = build_page(display, sections, subtitle=subtitle, first_name_count=first_name_count)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    html_path = out / "index.html"
    html_path.write_text(html, encoding="utf-8")

    return {
        "html_path": str(html_path),
        "html_size": html_path.stat().st_size,
        "sections": [
            {"name": n, "label": l, "findings": len(r["results"])}
            for n, l, r, _ in sections
        ],
    }


def main():
    """CLI entry point: ag-name-report 'משה גינדי' [--variant 'משה גנדי' --label 'Aleppo'] [--publish]"""
    import argparse

    parser = argparse.ArgumentParser(prog="ag-name-report", description="Generate a Torah name report")
    parser.add_argument("name", help="Primary Hebrew name (e.g. 'משה גינדי')")
    parser.add_argument("--variant", action="append", default=[], help="Additional spelling variant")
    parser.add_argument("--label", action="append", default=[], help="Label for each variant (matches --variant order)")
    parser.add_argument("--output", default="/tmp/torah_name_report", help="Output directory")
    parser.add_argument("--publish", action="store_true", help="Publish to here.now after generation")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    names = [(args.name, "Primary Spelling")]
    for i, variant in enumerate(args.variant):
        label = args.label[i] if i < len(args.label) else f"Variant {i + 1}"
        names.append((variant, label))

    result = build_name_report(names, output_dir=args.output)

    if args.publish:
        from autogematria.publish.herenow import publish_directory
        pub = publish_directory(
            args.output,
            viewer_title=f"{args.name} · Torah Name Report",
            viewer_description="AutoGematria Torah name report with highlighted ELS findings",
        )
        result["url"] = pub.get("site_url")
        result["slug"] = pub.get("slug")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Report generated: {result['html_path']} ({result['html_size']:,} bytes)")
        for s in result["sections"]:
            print(f"  {s['name']}: {s['findings']} findings")
        if result.get("url"):
            print(f"\nPublished: {result['url']}")


if __name__ == "__main__":
    main()
