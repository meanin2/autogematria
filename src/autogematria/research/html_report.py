"""Full-featured HTML report renderer for name analysis.

Renders the comprehensive report including:
  - Name breakdown with component roles
  - Gematria table across methods
  - Letter-by-letter kabbalistic analysis
  - Milui and AtBash analysis
  - Cross-comparison highlights
  - Torah findings (from the existing search pipeline)
"""

from __future__ import annotations

from html import escape
from typing import Any


def _css() -> str:
    return """
    :root {
      --ink: #1e1c1a;
      --paper: #f5efe2;
      --gold: #b8872f;
      --gold-soft: #d5b46d;
      --crimson: #7a2f2f;
      --forest: #315441;
      --slate: #364353;
      --shadow: rgba(34, 23, 8, 0.14);
      --accent-blue: #2d5a7b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      color: var(--ink);
      font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(184,135,47,0.28), transparent 24rem),
        radial-gradient(circle at bottom right, rgba(49,84,65,0.18), transparent 24rem),
        linear-gradient(135deg, #f9f3e7 0%, #efe5d1 48%, #f6ecdb 100%);
      line-height: 1.6;
    }
    .page { max-width: 1100px; margin: 0 auto; padding: 48px 24px 72px; }

    /* Hero */
    .hero {
      position: relative; overflow: hidden; border-radius: 28px; padding: 40px;
      background: linear-gradient(135deg, rgba(31,28,26,0.96), rgba(57,43,20,0.95)),
                  linear-gradient(45deg, rgba(184,135,47,0.32), transparent);
      color: #fff8ea;
      box-shadow: 0 24px 80px var(--shadow);
    }
    .hero::after {
      content: ""; position: absolute; inset: 0;
      background: linear-gradient(90deg, transparent 0, rgba(255,255,255,0.05) 50%, transparent 100%);
      transform: translateX(-100%); animation: shimmer 6s infinite;
    }
    @keyframes shimmer { to { transform: translateX(100%); } }
    .brand {
      display: inline-flex; align-items: center; gap: 10px;
      font-size: 12px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--gold-soft);
    }
    .brand-mark {
      width: 12px; height: 12px; border-radius: 999px;
      background: linear-gradient(135deg, var(--gold-soft), #fff4c7);
      box-shadow: 0 0 24px rgba(213,180,109,0.7);
    }
    .query {
      margin: 16px 0 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Garamond, serif;
      font-size: clamp(38px, 8vw, 72px); line-height: 0.95; letter-spacing: -0.04em;
    }
    .hero-subtitle { margin: 14px 0 0; font-size: 17px; color: rgba(255,248,234,0.85); max-width: 42rem; }
    .hero-stats { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 20px; }
    .hero-stat {
      border: 1px solid rgba(255,255,255,0.14); border-radius: 14px; padding: 10px 16px;
      background: rgba(255,255,255,0.06); backdrop-filter: blur(10px); min-width: 120px;
    }
    .hero-stat-label { font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: rgba(255,248,234,0.65); }
    .hero-stat-value { margin-top: 4px; font-size: 20px; font-weight: 700; }

    /* Section cards */
    .section { margin-top: 32px; }
    .section-title {
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Garamond, serif;
      font-size: 26px; margin-bottom: 16px; color: var(--ink);
    }
    .card {
      border-radius: 20px; padding: 24px;
      background: rgba(255,249,239,0.94); box-shadow: 0 12px 32px var(--shadow);
      border: 1px solid rgba(184,135,47,0.15); margin-bottom: 16px;
    }
    .card-title { font-size: 18px; font-weight: 700; margin-bottom: 12px; color: var(--slate); }

    /* Name breakdown */
    .name-parts { display: flex; gap: 14px; flex-wrap: wrap; }
    .name-part {
      border-radius: 16px; padding: 14px 20px;
      background: linear-gradient(135deg, #f0e6d0, #faf4e8);
      border: 1px solid rgba(184,135,47,0.2); text-align: center; min-width: 120px;
    }
    .name-part-role { font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--gold); }
    .name-part-text { font-size: 24px; margin: 6px 0; direction: rtl;
      font-family: "David", "Times New Roman", serif; }
    .name-part-value { font-size: 14px; color: var(--slate); }

    /* Gematria table */
    .gem-table { width: 100%; border-collapse: collapse; font-size: 14px; }
    .gem-table th { text-align: left; padding: 10px 12px; border-bottom: 2px solid var(--gold-soft);
      font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--slate); }
    .gem-table td { padding: 10px 12px; border-bottom: 1px solid rgba(54,67,83,0.08); }
    .gem-table tr:last-child td { border-bottom: none; }
    .gem-table .name-col { direction: rtl; font-family: "David", "Times New Roman", serif;
      font-size: 18px; font-weight: 600; }
    .gem-table .role-col { font-size: 11px; color: var(--gold); text-transform: uppercase; letter-spacing: 0.08em; }
    .gem-table .val { text-align: center; font-weight: 600; }
    .gem-table .highlight { background: rgba(184,135,47,0.1); border-radius: 8px; }

    /* Letter analysis */
    .letters-grid { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
    .letter-card {
      width: 80px; border-radius: 14px; padding: 10px; text-align: center;
      background: linear-gradient(135deg, #f8f0de, #fdf7ec);
      border: 1px solid rgba(184,135,47,0.18);
    }
    .letter-char { font-size: 32px; font-family: "David", "Times New Roman", serif; color: var(--gold); }
    .letter-name { font-size: 10px; font-weight: 600; color: var(--slate); margin-top: 2px; }
    .letter-val { font-size: 12px; color: var(--ink); }
    .letter-meaning { font-size: 9px; color: var(--forest); margin-top: 4px; line-height: 1.3; }

    /* Milui & AtBash */
    .analysis-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .analysis-detail { font-size: 15px; margin: 8px 0; }
    .analysis-label { font-weight: 700; color: var(--slate); font-size: 13px; }
    .analysis-hebrew { direction: rtl; font-family: "David", "Times New Roman", serif;
      font-size: 20px; margin: 4px 0; color: var(--gold); }
    .analysis-value { font-size: 22px; font-weight: 700; color: var(--ink); }

    /* Cross matches */
    .match-card {
      border-radius: 14px; padding: 14px 18px;
      background: linear-gradient(135deg, rgba(45,90,123,0.08), rgba(49,84,65,0.06));
      border: 1px solid rgba(45,90,123,0.15); margin-bottom: 10px;
    }
    .match-value { font-size: 24px; font-weight: 700; color: var(--accent-blue); }
    .match-detail { font-size: 14px; color: var(--ink); margin-top: 4px; }
    .match-pill {
      display: inline-block; padding: 3px 10px; border-radius: 999px;
      font-size: 11px; background: rgba(45,90,123,0.12); color: var(--accent-blue);
    }

    /* Torah words */
    .torah-words { display: flex; gap: 8px; flex-wrap: wrap; }
    .torah-word {
      display: inline-flex; align-items: center; gap: 6px;
      border-radius: 999px; padding: 6px 14px;
      background: rgba(49,84,65,0.08); border: 1px solid rgba(49,84,65,0.15);
      font-size: 14px; direction: rtl; font-family: "David", "Times New Roman", serif;
    }
    .torah-word-freq { font-size: 10px; color: var(--slate); direction: ltr; }

    /* Sefirah badge */
    .sefirah-badge {
      display: inline-flex; align-items: center; gap: 8px;
      border-radius: 14px; padding: 10px 18px;
      background: linear-gradient(135deg, rgba(184,135,47,0.12), rgba(184,135,47,0.04));
      border: 1px solid rgba(184,135,47,0.2);
    }
    .sefirah-name { font-size: 18px; font-weight: 700; color: var(--gold); }
    .sefirah-desc { font-size: 13px; color: var(--slate); }

    /* Finding cards from existing showcase */
    .finding-section { margin-top: 24px; }
    .finding-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
    .finding-card {
      position: relative; overflow: hidden; min-height: 280px;
      border-radius: 20px; padding: 18px; color: white;
      box-shadow: 0 16px 32px var(--shadow);
    }
    .finding-card.headline { background: linear-gradient(135deg, #8f6424, #caa24e 54%, #f6ddb1); color: #1d1204; }
    .finding-card.supporting { background: linear-gradient(135deg, #1f4e4b, #4e8a78 60%, #b7dbc7); color: #f6fffa; }
    .finding-card.interesting { background: linear-gradient(135deg, #4a304c, #815486 55%, #d9bfdc); color: #fff8ff; }
    .finding-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 12px; }
    .pill {
      display: inline-flex; align-items: center; padding: 6px 10px;
      border-radius: 999px; background: rgba(255,255,255,0.16);
      border: 1px solid rgba(255,255,255,0.22); backdrop-filter: blur(8px);
    }
    .finding-text {
      margin: 16px 0 10px; font-size: 24px; line-height: 1.1;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Garamond, serif;
    }
    .finding-explainer { font-size: 14px; line-height: 1.6; opacity: 0.95; margin-bottom: 12px; }
    .verse-block {
      margin-top: 10px; padding: 10px 14px; border-radius: 14px;
      background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.18);
    }
    .verse-label { font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.7; }
    .verse-hebrew { direction: rtl; font-size: 18px; font-family: "David", "Times New Roman", serif;
      margin: 6px 0 0; line-height: 1.6; }
    .verse-english { font-size: 14px; margin: 6px 0 0; line-height: 1.5; }

    .footer-note {
      margin-top: 32px; padding: 16px 18px; border-radius: 18px;
      background: rgba(255,255,255,0.58); border: 1px solid rgba(54,67,83,0.08);
      color: var(--slate); font-size: 14px;
    }

    @media (max-width: 860px) {
      .page { padding: 24px 16px 48px; }
      .hero { padding: 26px; }
      .analysis-row { grid-template-columns: 1fr; }
      .finding-grid { grid-template-columns: 1fr; }
      .name-parts { justify-content: center; }
    }
    """


ROLE_LABELS = {
    "first_name": "First Name",
    "father_name": "Father's Name",
    "mother_name": "Mother's Name",
    "surname": "Surname",
    "extra": "Additional",
    "combined_all": "Full Name Combined",
}


def _render_name_breakdown(report: dict[str, Any]) -> str:
    components = report.get("hebrew_components") or []
    if not components:
        return ""
    parts_html = []
    for comp in components:
        role = ROLE_LABELS.get(comp["role"], comp["role"])
        parts_html.append(f"""
          <div class="name-part">
            <div class="name-part-role">{escape(role)}</div>
            <div class="name-part-text">{escape(comp["text"])}</div>
            <div class="name-part-value">= {comp["gematria"]}</div>
          </div>""")
    return f"""
    <section class="section">
      <h2 class="section-title">Name Breakdown</h2>
      <div class="card">
        <div class="name-parts">{''.join(parts_html)}</div>
      </div>
    </section>"""


def _render_gematria_table(report: dict[str, Any]) -> str:
    cc = report.get("cross_comparison") or {}
    table = cc.get("gematria_table") or {}
    methods = table.get("methods") or []
    components = table.get("components") or []
    if not methods or not components:
        return ""

    header = "".join(f'<th class="val">{escape(m["display"])}</th>' for m in methods)
    rows_html = []
    for comp in components:
        role = ROLE_LABELS.get(comp["role"], comp["role"])
        vals = comp.get("values") or {}
        cells = "".join(
            f'<td class="val">{vals.get(m["name"], "")}</td>' for m in methods
        )
        rows_html.append(f"""
          <tr>
            <td class="name-col">{escape(comp["text"])}</td>
            <td class="role-col">{escape(role)}</td>
            {cells}
          </tr>""")

    return f"""
    <section class="section">
      <h2 class="section-title">Gematria Across Methods</h2>
      <div class="card">
        <table class="gem-table">
          <thead><tr><th>Name</th><th>Role</th>{header}</tr></thead>
          <tbody>{''.join(rows_html)}</tbody>
        </table>
      </div>
    </section>"""


def _render_letter_analysis(report: dict[str, Any]) -> str:
    kab = report.get("kabbalistic_full_name") or {}
    letters = kab.get("letter_meanings") or []
    if not letters:
        return ""

    cards = []
    for item in letters:
        meaning_short = str(item.get("meaning", "")).split(",")[0]
        cards.append(f"""
          <div class="letter-card">
            <div class="letter-char">{escape(item["letter"])}</div>
            <div class="letter-name">{escape(item["name"])}</div>
            <div class="letter-val">= {item["value"]}</div>
            <div class="letter-meaning">{escape(meaning_short)}</div>
          </div>""")

    sefirah = kab.get("sefirah") or {}
    sefirah_html = ""
    if sefirah.get("sefirah"):
        sefirah_html = f"""
        <div style="margin-top: 16px;">
          <div class="sefirah-badge">
            <span class="sefirah-name">{escape(sefirah["sefirah"])}</span>
            <span class="sefirah-desc">{escape(sefirah.get("description", ""))}</span>
          </div>
          <div style="font-size: 13px; color: var(--slate); margin-top: 6px;">
            Gematria {sefirah.get("value", "")} reduces to {sefirah.get("reduced_to", "")}
          </div>
        </div>"""

    return f"""
    <section class="section">
      <h2 class="section-title">Letter-by-Letter Analysis</h2>
      <div class="card">
        <div class="letters-grid">{''.join(cards)}</div>
        {sefirah_html}
      </div>
    </section>"""


def _render_milui_atbash(report: dict[str, Any]) -> str:
    kab = report.get("kabbalistic_full_name") or {}
    milui = kab.get("milui") or {}
    atbash = kab.get("atbash") or {}
    if not milui and not atbash:
        return ""

    milui_html = ""
    if milui.get("full_milui_text"):
        milui_html = f"""
        <div class="card">
          <div class="card-title">Milui (Letter Filling)</div>
          <p style="font-size: 13px; color: var(--slate); margin-bottom: 10px;">
            Each Hebrew letter has a spelled-out form that reveals hidden content.
            The 'milui' value is the gematria of all letters when fully spelled out.
          </p>
          <div class="analysis-detail">
            <div class="analysis-label">Spelled-Out Form</div>
            <div class="analysis-hebrew">{escape(milui["full_milui_text"])}</div>
          </div>
          <div class="analysis-detail">
            <div class="analysis-label">Milui Value</div>
            <div class="analysis-value">{milui.get("milui_value", "")}</div>
          </div>
          <div class="analysis-detail">
            <div class="analysis-label">Hidden Letters</div>
            <div class="analysis-hebrew">{escape(milui.get("hidden_text", ""))}</div>
            <div style="font-size: 13px; color: var(--slate);">Hidden value: {milui.get("hidden_value", "")}</div>
          </div>
        </div>"""

    atbash_html = ""
    if atbash.get("atbash_text"):
        atbash_html = f"""
        <div class="card">
          <div class="card-title">AtBash Transformation</div>
          <p style="font-size: 13px; color: var(--slate); margin-bottom: 10px;">
            AtBash maps each letter to its mirror in the aleph-bet (א↔ת, ב↔ש, etc.).
            This cipher appears in Tanakh itself (Jeremiah: ששך = בבל).
          </p>
          <div class="analysis-detail">
            <div class="analysis-label">AtBash Result</div>
            <div class="analysis-hebrew">{escape(atbash["atbash_text"])}</div>
          </div>
          <div style="display: flex; gap: 24px; margin-top: 8px;">
            <div>
              <div class="analysis-label">Original Value</div>
              <div class="analysis-value">{atbash.get("original_value", "")}</div>
            </div>
            <div>
              <div class="analysis-label">AtBash Value</div>
              <div class="analysis-value">{atbash.get("atbash_value", "")}</div>
            </div>
            <div>
              <div class="analysis-label">Sum</div>
              <div class="analysis-value">{atbash.get("sum_with_original", "")}</div>
            </div>
          </div>
        </div>"""

    return f"""
    <section class="section">
      <h2 class="section-title">Kabbalistic Analysis</h2>
      <div class="analysis-row">
        {milui_html}
        {atbash_html}
      </div>
    </section>"""


def _render_cross_matches(report: dict[str, Any]) -> str:
    cc = report.get("cross_comparison") or {}
    matches = cc.get("noteworthy_matches") or cc.get("cross_matches") or []
    if not matches:
        return ""

    top = matches[:8]
    cards = []
    for m in top:
        a = m.get("component_a") or {}
        b = m.get("component_b") or {}
        cards.append(f"""
          <div class="match-card">
            <div style="display: flex; align-items: center; gap: 12px;">
              <div class="match-value">{m.get("value", "")}</div>
              <div class="match-pill">{escape(m.get("match_type", "").replace("_", " "))}</div>
            </div>
            <div class="match-detail">
              <strong>{escape(a.get("text", ""))}</strong> ({escape(ROLE_LABELS.get(a.get("role",""), a.get("role","")))}, {escape(a.get("method",""))})
              = <strong>{escape(b.get("text", ""))}</strong> ({escape(ROLE_LABELS.get(b.get("role",""), b.get("role","")))}, {escape(b.get("method",""))})
            </div>
          </div>""")

    return f"""
    <section class="section">
      <h2 class="section-title">Cross-Comparison Discoveries</h2>
      <div class="card">
        <p style="font-size: 13px; color: var(--slate); margin-bottom: 12px;">
          Matching gematria values found across different name components and calculation methods.
        </p>
        {''.join(cards)}
      </div>
    </section>"""


def _render_torah_words(report: dict[str, Any]) -> str:
    cc = report.get("cross_comparison") or {}
    torah = cc.get("torah_word_matches") or {}
    if not torah:
        return ""

    sections = []
    for key, words in torah.items():
        if not words:
            continue
        text, role = key.split("|", 1) if "|" in key else (key, "")
        role_label = ROLE_LABELS.get(role, role)
        value = words[0].get("shared_value", "") if words else ""
        word_tags = "".join(
            f'<span class="torah-word">{escape(w["word"])} '
            f'<span class="torah-word-freq">×{w["frequency"]}</span></span>'
            for w in words[:10]
        )
        sections.append(f"""
          <div style="margin-bottom: 14px;">
            <div style="font-size: 13px; font-weight: 600; color: var(--slate);">
              {escape(text)} ({escape(role_label)}) — value {value}
            </div>
            <div class="torah-words" style="margin-top: 6px;">{word_tags}</div>
          </div>""")

    if not sections:
        return ""
    return f"""
    <section class="section">
      <h2 class="section-title">Torah Words with Same Gematria</h2>
      <div class="card">
        <p style="font-size: 13px; color: var(--slate); margin-bottom: 12px;">
          Words found in Tanakh that share the same standard gematria value as each name component.
        </p>
        {''.join(sections)}
      </div>
    </section>"""


def _render_four_worlds(report: dict[str, Any]) -> str:
    kab = report.get("kabbalistic_full_name") or {}
    fw = kab.get("four_worlds") or {}
    worlds = fw.get("worlds") or []
    if not worlds:
        return ""

    world_colors = {
        "Atzilut": "#b8872f",
        "Beriah": "#2d5a7b",
        "Yetzirah": "#315441",
        "Asiyah": "#7a2f2f",
    }
    cards = []
    for w in worlds:
        color = world_colors.get(w["world"], "#364353")
        letters_display = " ".join(w.get("letters") or [])
        cards.append(f"""
          <div style="flex: 1; min-width: 140px; border-radius: 14px; padding: 14px;
                      background: linear-gradient(135deg, {color}15, {color}08);
                      border: 1px solid {color}30; text-align: center;">
            <div style="font-size: 11px; font-weight: 700; color: {color}; text-transform: uppercase;
                        letter-spacing: 0.12em;">{escape(w["world"])}</div>
            <div style="font-size: 10px; color: var(--slate); margin-top: 2px;">
              {escape(w.get("soul_level", ""))}
            </div>
            <div style="font-size: 22px; direction: rtl; font-family: 'David', serif;
                        margin: 8px 0; color: {color};">{escape(letters_display)}</div>
            <div style="font-size: 16px; font-weight: 700;">{w.get("value", 0)}</div>
          </div>""")

    return f"""
    <section class="section">
      <h2 class="section-title">Four Worlds (ABYA)</h2>
      <div class="card">
        <p style="font-size: 13px; color: var(--slate); margin-bottom: 12px;">
          The letters of the name divided across the four kabbalistic worlds:
          Atzilut (Emanation), Beriah (Creation), Yetzirah (Formation), Asiyah (Action).
        </p>
        <div style="display: flex; gap: 12px; flex-wrap: wrap;">{''.join(cards)}</div>
      </div>
    </section>"""


def _render_findings(showcase: dict[str, Any]) -> str:
    """Render Torah search findings from the existing showcase pipeline."""
    if not showcase:
        return ""

    def _finding_cards(rows: list[dict[str, Any]], tone: str) -> str:
        if not rows:
            return ""
        cards = []
        for row in rows:
            verse = row.get("verse_context") or {}
            loc = row.get("location") or {}
            ref = verse.get("ref") or f"{loc.get('book')} {loc.get('chapter')}:{loc.get('verse')}"
            method = row.get("method") or "?"
            mode = (row.get("params") or {}).get("mode") or ""
            tag = f"{method} / {mode}" if mode else method
            cards.append(f"""
              <article class="finding-card {tone}">
                <div class="finding-meta">
                  <span class="pill">{escape(tag)}</span>
                  <span>{escape(ref)}</span>
                </div>
                <h3 class="finding-text">{escape(str(row.get("found_text") or ""))}</h3>
                <p class="finding-explainer">{escape(str(row.get("explanation") or ""))}</p>
                <div class="verse-block">
                  <div class="verse-label">Hebrew</div>
                  <p class="verse-hebrew">{escape(str(verse.get("hebrew") or ""))}</p>
                </div>
                <div class="verse-block" style="background: rgba(255,255,255,0.08);">
                  <div class="verse-label">English</div>
                  <p class="verse-english">{escape(str(verse.get("english") or "Translation unavailable."))}</p>
                </div>
              </article>""")
        return "".join(cards)

    sections = []
    for key, title, tone in [
        ("headline_findings", "Primary Torah Findings", "headline"),
        ("supporting_findings", "Supporting Findings", "supporting"),
        ("interesting_findings", "Additional Discoveries", "interesting"),
    ]:
        rows = showcase.get(key) or []
        if rows:
            sections.append(f"""
              <div class="finding-section">
                <h3 style="font-size: 18px; margin-bottom: 12px; color: var(--slate);">{title}</h3>
                <div class="finding-grid">{_finding_cards(rows, tone)}</div>
              </div>""")

    if not sections:
        return ""

    verdict_label = showcase.get("verdict_label") or ""
    summary = showcase.get("summary_line") or ""
    return f"""
    <section class="section">
      <h2 class="section-title">Torah Encodings</h2>
      <div class="card">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
          <div class="sefirah-badge">
            <span class="sefirah-name">{escape(verdict_label)}</span>
          </div>
          <span style="font-size: 14px; color: var(--slate);">{escape(summary)}</span>
        </div>
        {''.join(sections)}
      </div>
    </section>"""


def render_full_report_html(
    report: dict[str, Any],
    showcase: dict[str, Any] | None = None,
) -> str:
    """Render the complete HTML report page."""
    query = escape(report.get("full_hebrew_name") or report.get("raw_input") or "")
    raw_input = escape(report.get("raw_input") or "")
    parsed = report.get("parsed_name") or {}
    full_gem = report.get("full_name_gematria") or 0
    num_components = len(report.get("hebrew_components") or [])
    kab = report.get("kabbalistic_full_name") or {}
    letter_count = kab.get("letter_count") or 0
    sefirah = (kab.get("sefirah") or {}).get("sefirah") or ""

    patron = parsed.get("patronymic_type") or ""
    subtitle_parts = []
    if parsed.get("father_name"):
        subtitle_parts.append(f"{'Son' if patron != 'bat' else 'Daughter'} of {parsed['father_name']}")
    if parsed.get("mother_name"):
        subtitle_parts.append(f"and {parsed['mother_name']}")
    if parsed.get("surname"):
        subtitle_parts.append(f"Family: {parsed['surname']}")
    subtitle = " · ".join(subtitle_parts) if subtitle_parts else raw_input

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{query} · AutoGematria Name Report</title>
  <style>{_css()}</style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="brand"><span class="brand-mark"></span> AutoGematria Name Report</div>
      <h1 class="query">{query}</h1>
      <p class="hero-subtitle">{escape(subtitle)}</p>
      <div class="hero-stats">
        <div class="hero-stat">
          <div class="hero-stat-label">Standard Gematria</div>
          <div class="hero-stat-value">{full_gem}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">Letters</div>
          <div class="hero-stat-value">{letter_count}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">Components</div>
          <div class="hero-stat-value">{num_components}</div>
        </div>
        <div class="hero-stat">
          <div class="hero-stat-label">Sefirah</div>
          <div class="hero-stat-value">{escape(sefirah)}</div>
        </div>
      </div>
    </section>

    {_render_name_breakdown(report)}
    {_render_gematria_table(report)}
    {_render_letter_analysis(report)}
    {_render_milui_atbash(report)}
    {_render_four_worlds(report)}
    {_render_cross_matches(report)}
    {_render_torah_words(report)}
    {_render_findings(showcase or {})}

    <div class="footer-note">
      Generated by AutoGematria · Deterministic Torah name analysis engine
      · For the full audit trail, run <code>ag-research-name "{escape(report.get('raw_input', ''))}" --json</code>
    </div>
  </main>
</body>
</html>"""
