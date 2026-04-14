"""Self-contained web UI for AutoGematria.

Serves a single-page application that calls the JSON API endpoints.
No LLM dependency — all computation is done server-side in Python.
"""

from __future__ import annotations


def build_ui_html(base_url: str = "") -> str:
    """Return the complete single-page app HTML."""
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoGematria</title>
<style>
:root {{
  --ink: #1e1c1a; --paper: #f5efe2; --gold: #b8872f; --gold-soft: #d5b46d;
  --forest: #315441; --slate: #364353; --shadow: rgba(34,23,8,0.14);
  --accent: #2d5a7b; --bg: #f9f3e7; --card: rgba(255,249,239,0.94);
  --radius: 16px; --radius-lg: 24px;
}}
*{{ box-sizing:border-box; margin:0; padding:0; }}
body {{
  color:var(--ink); font-family:"Avenir Next","Trebuchet MS","Segoe UI",sans-serif;
  background: radial-gradient(circle at top left,rgba(184,135,47,0.22),transparent 24rem),
    radial-gradient(circle at bottom right,rgba(49,84,65,0.15),transparent 24rem),
    linear-gradient(135deg,#f9f3e7 0%,#efe5d1 48%,#f6ecdb 100%);
  min-height:100vh; line-height:1.5;
}}
.page {{ max-width:1100px; margin:0 auto; padding:32px 20px 64px; }}

/* Header */
header {{
  display:flex; align-items:center; justify-content:space-between;
  padding:16px 0; border-bottom:1px solid rgba(184,135,47,0.2); margin-bottom:28px;
}}
.logo {{ display:flex; align-items:center; gap:10px; }}
.logo-mark {{
  width:10px; height:10px; border-radius:999px;
  background:linear-gradient(135deg,var(--gold-soft),#fff4c7);
  box-shadow:0 0 16px rgba(213,180,109,0.6);
}}
.logo-text {{
  font-size:13px; letter-spacing:0.16em; text-transform:uppercase;
  color:var(--gold); font-weight:600;
}}
nav {{ display:flex; gap:8px; }}
nav button {{
  padding:7px 14px; border-radius:999px; border:1px solid rgba(184,135,47,0.2);
  background:transparent; color:var(--slate); font-size:12px; cursor:pointer;
  font-weight:600; letter-spacing:0.04em; transition:all 0.2s;
}}
nav button:hover,nav button.active {{
  background:var(--gold); color:white; border-color:var(--gold);
}}

/* Search */
.search-box {{
  position:relative; margin-bottom:24px;
}}
.search-input {{
  width:100%; padding:16px 20px 16px 20px; border-radius:var(--radius-lg);
  border:2px solid rgba(184,135,47,0.2); background:white;
  font-size:20px; font-family:inherit; color:var(--ink);
  box-shadow:0 8px 32px var(--shadow); transition:border-color 0.2s;
  direction:auto;
}}
.search-input:focus {{ outline:none; border-color:var(--gold); }}
.search-input::placeholder {{ color:#b0a890; }}
.search-btn {{
  position:absolute; right:8px; top:50%; transform:translateY(-50%);
  padding:10px 24px; border-radius:var(--radius); border:none;
  background:linear-gradient(135deg,var(--gold),#caa24e);
  color:white; font-size:15px; font-weight:700; cursor:pointer;
  box-shadow:0 4px 12px rgba(184,135,47,0.3); transition:transform 0.15s;
}}
.search-btn:hover {{ transform:translateY(-50%) scale(1.03); }}
.search-btn:disabled {{ opacity:0.6; cursor:not-allowed; }}

/* Tabs */
.tabs {{ display:flex; gap:6px; margin-bottom:20px; flex-wrap:wrap; }}
.tab {{
  padding:8px 16px; border-radius:999px; border:1px solid rgba(54,67,83,0.12);
  background:rgba(255,255,255,0.6); color:var(--slate); font-size:13px;
  cursor:pointer; font-weight:600; transition:all 0.2s;
}}
.tab:hover,.tab.active {{ background:var(--forest); color:white; border-color:var(--forest); }}

/* Cards */
.card {{
  border-radius:var(--radius-lg); padding:24px; margin-bottom:16px;
  background:var(--card); box-shadow:0 8px 28px var(--shadow);
  border:1px solid rgba(184,135,47,0.12);
}}
.card-title {{
  font-size:13px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase;
  color:var(--gold); margin-bottom:12px;
}}
.section-title {{
  font-family:"Iowan Old Style","Palatino Linotype","Book Antiqua",Garamond,serif;
  font-size:24px; margin-bottom:16px; color:var(--ink);
}}

/* Parsed name */
.name-parts {{ display:flex; gap:12px; flex-wrap:wrap; }}
.name-part {{
  border-radius:var(--radius); padding:12px 18px; text-align:center;
  background:linear-gradient(135deg,#f0e6d0,#faf4e8);
  border:1px solid rgba(184,135,47,0.18); min-width:100px;
}}
.name-part-role {{ font-size:10px; letter-spacing:0.12em; text-transform:uppercase; color:var(--gold); }}
.name-part-text {{ font-size:22px; margin:4px 0; direction:rtl; font-family:"David","Times New Roman",serif; }}
.name-part-val {{ font-size:13px; color:var(--slate); }}

/* Gematria table */
.gem-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
.gem-table th {{ text-align:left; padding:8px 10px; border-bottom:2px solid var(--gold-soft);
  font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:var(--slate); }}
.gem-table td {{ padding:8px 10px; border-bottom:1px solid rgba(54,67,83,0.06); }}
.gem-table .name-col {{ direction:rtl; font-family:"David","Times New Roman",serif; font-size:17px; font-weight:600; }}
.gem-table .role-col {{ font-size:10px; color:var(--gold); text-transform:uppercase; }}
.gem-table .val {{ text-align:center; font-weight:600; font-size:14px; }}
.gem-table .val.highlight {{ background:rgba(184,135,47,0.1); border-radius:6px; }}

/* Letters */
.letters-row {{ display:flex; gap:6px; flex-wrap:wrap; justify-content:center; }}
.letter-card {{
  width:72px; border-radius:12px; padding:8px; text-align:center;
  background:linear-gradient(135deg,#f8f0de,#fdf7ec);
  border:1px solid rgba(184,135,47,0.15);
}}
.letter-char {{ font-size:28px; font-family:"David","Times New Roman",serif; color:var(--gold); }}
.letter-name {{ font-size:9px; font-weight:700; color:var(--slate); }}
.letter-val {{ font-size:11px; }}
.letter-meaning {{ font-size:8px; color:var(--forest); margin-top:2px; line-height:1.2; }}

/* Analysis blocks */
.analysis-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.analysis-block {{ padding:16px; border-radius:var(--radius); background:rgba(0,0,0,0.02); }}
.analysis-label {{ font-size:11px; font-weight:700; color:var(--slate); letter-spacing:0.08em; text-transform:uppercase; }}
.analysis-hebrew {{ direction:rtl; font-family:"David","Times New Roman",serif; font-size:20px; color:var(--gold); margin:4px 0; }}
.analysis-value {{ font-size:20px; font-weight:700; }}

/* Sefirah */
.sefirah-badge {{
  display:inline-flex; align-items:center; gap:8px; padding:8px 16px;
  border-radius:12px; background:linear-gradient(135deg,rgba(184,135,47,0.1),rgba(184,135,47,0.04));
  border:1px solid rgba(184,135,47,0.18);
}}
.sefirah-name {{ font-size:16px; font-weight:700; color:var(--gold); }}
.sefirah-desc {{ font-size:12px; color:var(--slate); }}

/* Torah words */
.torah-words {{ display:flex; gap:6px; flex-wrap:wrap; }}
.torah-word {{
  display:inline-flex; align-items:center; gap:4px;
  padding:4px 12px; border-radius:999px;
  background:rgba(49,84,65,0.08); border:1px solid rgba(49,84,65,0.12);
  font-size:14px; direction:rtl; font-family:"David","Times New Roman",serif;
}}
.torah-word-freq {{ font-size:9px; color:var(--slate); direction:ltr; }}

/* Four worlds */
.worlds-row {{ display:flex; gap:10px; flex-wrap:wrap; }}
.world-card {{
  flex:1; min-width:120px; border-radius:12px; padding:12px; text-align:center;
}}

/* Findings */
.finding-card {{
  border-radius:var(--radius-lg); padding:16px; margin-bottom:12px;
  color:white; box-shadow:0 8px 24px var(--shadow);
}}
.finding-card.headline {{ background:linear-gradient(135deg,#8f6424,#caa24e 54%,#f6ddb1); color:#1d1204; }}
.finding-card.supporting {{ background:linear-gradient(135deg,#1f4e4b,#4e8a78 60%,#b7dbc7); }}
.finding-card.interesting {{ background:linear-gradient(135deg,#4a304c,#815486 55%,#d9bfdc); }}
.finding-meta {{ display:flex; align-items:center; justify-content:space-between; font-size:11px; }}
.pill {{ padding:4px 10px; border-radius:999px; background:rgba(255,255,255,0.16);
  border:1px solid rgba(255,255,255,0.2); font-size:11px; }}
.finding-text {{ margin:12px 0 8px; font-size:20px; font-family:"Iowan Old Style",Garamond,serif; }}
.finding-explainer {{ font-size:13px; line-height:1.5; opacity:0.9; }}
.verse-block {{ margin-top:8px; padding:8px 12px; border-radius:12px; background:rgba(255,255,255,0.1);
  border:1px solid rgba(255,255,255,0.15); }}
.verse-label {{ font-size:9px; letter-spacing:0.1em; text-transform:uppercase; opacity:0.65; }}
.verse-hebrew {{ direction:rtl; font-size:16px; font-family:"David","Times New Roman",serif; margin:4px 0 0; line-height:1.6; }}
.verse-english {{ font-size:12px; margin:4px 0 0; line-height:1.4; }}

/* Reverse lookup */
.reverse-input {{
  display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; align-items:center;
}}
.reverse-input input {{
  padding:10px 14px; border-radius:var(--radius); border:1px solid rgba(184,135,47,0.2);
  font-size:16px; width:140px; background:white;
}}
.reverse-input select {{
  padding:10px 14px; border-radius:var(--radius); border:1px solid rgba(184,135,47,0.2);
  font-size:13px; background:white;
}}
.reverse-input button {{
  padding:10px 18px; border-radius:var(--radius); border:none;
  background:var(--forest); color:white; font-size:13px; font-weight:600; cursor:pointer;
}}

/* Graph / match cards */
.match-card {{
  border-radius:12px; padding:12px 16px; margin-bottom:8px;
  background:linear-gradient(135deg,rgba(45,90,123,0.06),rgba(49,84,65,0.04));
  border:1px solid rgba(45,90,123,0.12);
}}
.match-value {{ font-size:20px; font-weight:700; color:var(--accent); }}
.match-detail {{ font-size:13px; color:var(--ink); margin-top:3px; }}

/* Loading */
.loading {{ text-align:center; padding:40px; color:var(--slate); }}
.spinner {{ display:inline-block; width:24px; height:24px; border:3px solid rgba(184,135,47,0.2);
  border-top-color:var(--gold); border-radius:50%; animation:spin 0.8s linear infinite; }}
@keyframes spin {{ to {{ transform:rotate(360deg); }} }}

.hidden {{ display:none !important; }}
.error {{ padding:16px; background:#fff0f0; border:1px solid #e0b0b0; border-radius:var(--radius);
  color:#7a2f2f; font-size:14px; margin-bottom:16px; }}

@media(max-width:860px) {{
  .analysis-grid {{ grid-template-columns:1fr; }}
  .worlds-row {{ flex-direction:column; }}
}}
</style>
</head>
<body>
<div class="page">
  <header>
    <div class="logo"><span class="logo-mark"></span><span class="logo-text">AutoGematria</span></div>
    <nav>
      <button class="active" onclick="showView('search')">Name Analysis</button>
      <button onclick="showView('reverse')">Reverse Lookup</button>
      <button onclick="showView('about')">About</button>
    </nav>
  </header>

  <!-- Search View -->
  <div id="view-search">
    <div class="search-box">
      <input class="search-input" id="name-input" type="text" placeholder="Enter a name: moshe ben yitzchak gindi, שרה בת אברהם..."
        dir="auto" autofocus>
      <button class="search-btn" id="search-btn" onclick="runSearch()">Analyze</button>
    </div>
    <div id="search-error" class="error hidden"></div>
    <div id="search-loading" class="loading hidden"><div class="spinner"></div><p>Analyzing name...</p></div>
    <div id="search-results" class="hidden"></div>
  </div>

  <!-- Reverse Lookup View -->
  <div id="view-reverse" class="hidden">
    <h2 class="section-title">Gematria Reverse Lookup</h2>
    <p style="color:var(--slate);font-size:14px;margin-bottom:16px;">
      Enter a number to find all Tanakh words with that gematria value.
    </p>
    <div class="reverse-input">
      <input type="number" id="reverse-value" placeholder="345" min="1">
      <select id="reverse-method">
        <option value="MISPAR_HECHRACHI">Standard</option>
        <option value="MISPAR_GADOL">Full Value</option>
        <option value="MISPAR_KATAN">Reduced</option>
        <option value="MISPAR_SIDURI">Ordinal</option>
        <option value="ATBASH">AtBash</option>
        <option value="MISPAR_KOLEL">Kolel</option>
      </select>
      <button onclick="runReverseLookup()">Search</button>
    </div>
    <div id="reverse-loading" class="loading hidden"><div class="spinner"></div></div>
    <div id="reverse-results"></div>
  </div>

  <!-- About View -->
  <div id="view-about" class="hidden">
    <h2 class="section-title">About AutoGematria</h2>
    <div class="card">
      <p style="font-size:15px;line-height:1.7;">
        AutoGematria is a deterministic Torah name-finding and gematria analysis engine.
        Given a Hebrew name (or an English name that it transliterates), it finds where the name
        appears in the Torah/Tanakh through traditional methods: direct text, equidistant letter
        sequences (ELS), roshei/sofei tevot (acrostics), and gematria equivalences.
      </p>
      <p style="font-size:15px;line-height:1.7;margin-top:12px;">
        It also provides kabbalistic analysis rooted in traditional Orthodox sources:
        letter meanings (Sefer Yetzirah, Arizal), milui (letter-filling), AtBash cipher,
        sefirot associations, and four-worlds (ABYA) breakdown.
      </p>
      <p style="font-size:14px;color:var(--slate);margin-top:16px;">
        <strong>Corpus:</strong> Full Tanakh &mdash; 39 books, 23,206 verses, 306,869 words, 1,205,822 letters.<br>
        <strong>Gematria:</strong> 22 methods precomputed for all 40,664 unique word forms (894,608 values).<br>
        <strong>Sources:</strong> Sefaria API (Public Domain), hebrew PyPI package.
      </p>
    </div>
  </div>
</div>

<script>
const API = "{base_url}";

function showView(name) {{
  document.querySelectorAll('[id^="view-"]').forEach(v => v.classList.add('hidden'));
  document.getElementById('view-' + name).classList.remove('hidden');
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
}}

document.getElementById('name-input').addEventListener('keydown', e => {{
  if (e.key === 'Enter') runSearch();
}});

async function runSearch() {{
  const q = document.getElementById('name-input').value.trim();
  if (!q) return;
  const btn = document.getElementById('search-btn');
  const loading = document.getElementById('search-loading');
  const results = document.getElementById('search-results');
  const errDiv = document.getElementById('search-error');
  btn.disabled = true; loading.classList.remove('hidden'); results.classList.add('hidden');
  errDiv.classList.add('hidden');
  try {{
    const resp = await fetch(API + '/api/full-report', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{query: q}})
    }});
    if (!resp.ok) throw new Error('Server error: ' + resp.status);
    const data = await resp.json();
    results.innerHTML = renderReport(data);
    results.classList.remove('hidden');
  }} catch(e) {{
    errDiv.textContent = 'Error: ' + e.message;
    errDiv.classList.remove('hidden');
  }} finally {{
    btn.disabled = false; loading.classList.add('hidden');
  }}
}}

async function runReverseLookup() {{
  const val = document.getElementById('reverse-value').value;
  const method = document.getElementById('reverse-method').value;
  if (!val) return;
  const loading = document.getElementById('reverse-loading');
  const results = document.getElementById('reverse-results');
  loading.classList.remove('hidden');
  try {{
    const resp = await fetch(API + '/api/reverse-lookup', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{value: parseInt(val), method: method}})
    }});
    const data = await resp.json();
    results.innerHTML = renderReverseLookup(data, val, method);
  }} catch(e) {{
    results.innerHTML = '<div class="error">Error: ' + e.message + '</div>';
  }} finally {{
    loading.classList.add('hidden');
  }}
}}

const ROLE_LABELS = {{
  first_name: 'First Name', father_name: "Father's Name", mother_name: "Mother's Name",
  surname: 'Surname', extra: 'Additional', 'combined_all': 'Full Combined',
}};
const METHOD_LABELS = {{
  MISPAR_HECHRACHI: 'Standard', MISPAR_GADOL: 'Full Value', MISPAR_KATAN: 'Reduced',
  MISPAR_SIDURI: 'Ordinal', ATBASH: 'AtBash', MISPAR_KOLEL: 'Kolel',
}};

function esc(s) {{ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}

function renderReport(d) {{
  const r = d.report || {{}};
  const s = d.showcase || {{}};
  let html = '';

  // Name breakdown
  const comps = r.hebrew_components || [];
  if (comps.length) {{
    html += '<div class="card"><div class="card-title">Name Breakdown</div><div class="name-parts">';
    comps.forEach(c => {{
      html += '<div class="name-part"><div class="name-part-role">' + esc(ROLE_LABELS[c.role]||c.role) +
        '</div><div class="name-part-text">' + esc(c.text) + '</div><div class="name-part-val">= ' + c.gematria + '</div></div>';
    }});
    html += '</div></div>';
  }}

  // Gematria table
  const gt = (r.cross_comparison||{{}}).gematria_table || {{}};
  const methods = gt.methods || [];
  const gtcomps = gt.components || [];
  if (methods.length && gtcomps.length) {{
    html += '<div class="card"><div class="card-title">Gematria Across Methods</div><table class="gem-table"><thead><tr><th>Name</th><th>Role</th>';
    methods.forEach(m => html += '<th class="val">' + esc(m.display) + '</th>');
    html += '</tr></thead><tbody>';
    gtcomps.forEach(c => {{
      html += '<tr><td class="name-col">' + esc(c.text) + '</td><td class="role-col">' + esc(ROLE_LABELS[c.role]||c.role) + '</td>';
      methods.forEach(m => html += '<td class="val">' + (c.values[m.name]||'') + '</td>');
      html += '</tr>';
    }});
    html += '</tbody></table></div>';
  }}

  // Letter analysis
  const kab = r.kabbalistic_full_name || {{}};
  const letters = kab.letter_meanings || [];
  if (letters.length) {{
    html += '<div class="card"><div class="card-title">Letter-by-Letter Analysis</div><div class="letters-row">';
    letters.forEach(l => {{
      const short = (l.meaning||'').split(',')[0];
      html += '<div class="letter-card"><div class="letter-char">' + esc(l.letter) + '</div><div class="letter-name">' +
        esc(l.name) + '</div><div class="letter-val">= ' + l.value + '</div><div class="letter-meaning">' + esc(short) + '</div></div>';
    }});
    html += '</div>';
    const sef = kab.sefirah || {{}};
    if (sef.sefirah) {{
      html += '<div style="margin-top:12px"><div class="sefirah-badge"><span class="sefirah-name">' + esc(sef.sefirah) +
        '</span><span class="sefirah-desc">' + esc(sef.description||'') + '</span></div>' +
        '<div style="font-size:12px;color:var(--slate);margin-top:4px;">Gematria ' + (sef.value||'') + ' reduces to ' + (sef.reduced_to||'') + '</div></div>';
    }}
    html += '</div>';
  }}

  // Milui & AtBash
  const milui = kab.milui || {{}};
  const atbash = kab.atbash || {{}};
  if (milui.full_milui_text || atbash.atbash_text) {{
    html += '<div class="card"><div class="card-title">Kabbalistic Analysis</div><div class="analysis-grid">';
    if (milui.full_milui_text) {{
      html += '<div class="analysis-block"><div class="analysis-label">Milui (Letter Filling)</div>' +
        '<div class="analysis-hebrew">' + esc(milui.full_milui_text) + '</div>' +
        '<div class="analysis-value">' + milui.milui_value + '</div>' +
        '<div style="font-size:12px;color:var(--slate);margin-top:4px;">Hidden: ' + esc(milui.hidden_text||'') + ' = ' + (milui.hidden_value||0) + '</div></div>';
    }}
    if (atbash.atbash_text) {{
      html += '<div class="analysis-block"><div class="analysis-label">AtBash Transformation</div>' +
        '<div class="analysis-hebrew">' + esc(atbash.atbash_text) + '</div>' +
        '<div style="display:flex;gap:16px;margin-top:4px;"><div><div class="analysis-label">Original</div><div class="analysis-value">' +
        (atbash.original_value||'') + '</div></div><div><div class="analysis-label">AtBash</div><div class="analysis-value">' +
        (atbash.atbash_value||'') + '</div></div><div><div class="analysis-label">Sum</div><div class="analysis-value">' +
        (atbash.sum_with_original||'') + '</div></div></div></div>';
    }}
    html += '</div></div>';
  }}

  // Four worlds
  const fw = (kab.four_worlds||{{}}).worlds || [];
  if (fw.length) {{
    const colors = {{Atzilut:'#b8872f',Beriah:'#2d5a7b',Yetzirah:'#315441',Asiyah:'#7a2f2f'}};
    html += '<div class="card"><div class="card-title">Four Worlds (ABYA)</div><div class="worlds-row">';
    fw.forEach(w => {{
      const c = colors[w.world]||'#364353';
      html += '<div class="world-card" style="background:' + c + '10;border:1px solid ' + c + '30;">' +
        '<div style="font-size:10px;font-weight:700;color:' + c + ';text-transform:uppercase;letter-spacing:0.1em;">' + esc(w.world) + '</div>' +
        '<div style="font-size:9px;color:var(--slate);">' + esc(w.soul_level||'') + '</div>' +
        '<div style="font-size:20px;direction:rtl;font-family:David,serif;margin:6px 0;color:' + c + ';">' + esc((w.letters||[]).join(' ')) + '</div>' +
        '<div style="font-size:15px;font-weight:700;">' + (w.value||0) + '</div></div>';
    }});
    html += '</div></div>';
  }}

  // Torah word matches
  const twm = (r.cross_comparison||{{}}).torah_word_matches || {{}};
  const twKeys = Object.keys(twm).filter(k => (twm[k]||[]).length > 0);
  if (twKeys.length) {{
    html += '<div class="card"><div class="card-title">Torah Words with Same Gematria</div>';
    twKeys.forEach(key => {{
      const [text, role] = key.split('|');
      const val = (twm[key][0]||{{}}).shared_value || '';
      html += '<div style="margin-bottom:12px;"><div style="font-size:12px;font-weight:600;color:var(--slate);">' +
        esc(text) + ' (' + esc(ROLE_LABELS[role]||role) + ') — value ' + val + '</div><div class="torah-words" style="margin-top:4px;">';
      (twm[key]||[]).slice(0,10).forEach(w => {{
        html += '<span class="torah-word">' + esc(w.word) + ' <span class="torah-word-freq">\\u00d7' + w.frequency + '</span></span>';
      }});
      html += '</div></div>';
    }});
    html += '</div>';
  }}

  // Cross matches
  const cm = (r.cross_comparison||{{}}).cross_matches || [];
  if (cm.length) {{
    html += '<div class="card"><div class="card-title">Cross-Comparison Discoveries</div>';
    cm.slice(0,8).forEach(m => {{
      const a = m.component_a||{{}}, b = m.component_b||{{}};
      html += '<div class="match-card"><div style="display:flex;align-items:center;gap:10px;">' +
        '<div class="match-value">' + (m.value||'') + '</div>' +
        '<span class="pill" style="background:rgba(45,90,123,0.1);color:var(--accent);border:1px solid rgba(45,90,123,0.2);">' +
        esc((m.match_type||'').replace(/_/g,' ')) + '</span></div>' +
        '<div class="match-detail"><strong>' + esc(a.text||'') + '</strong> (' + esc(ROLE_LABELS[a.role]||a.role||'') + ', ' + esc(METHOD_LABELS[a.method]||a.method||'') + ')' +
        ' = <strong>' + esc(b.text||'') + '</strong> (' + esc(ROLE_LABELS[b.role]||b.role||'') + ', ' + esc(METHOD_LABELS[b.method]||b.method||'') + ')</div></div>';
    }});
    html += '</div>';
  }}

  // Torah findings
  const findings = [
    [s.headline_findings||[], 'Primary Torah Findings', 'headline'],
    [s.supporting_findings||[], 'Supporting Findings', 'supporting'],
    [s.interesting_findings||[], 'Additional Discoveries', 'interesting'],
  ].filter(f => f[0].length > 0);
  if (findings.length) {{
    const vl = s.verdict_label || '';
    html += '<div class="card"><div class="card-title">Torah Encodings</div>';
    if (vl) html += '<div class="sefirah-badge" style="margin-bottom:12px;"><span class="sefirah-name">' + esc(vl) + '</span></div>';
    findings.forEach(([rows, title, tone]) => {{
      html += '<h3 style="font-size:15px;margin:12px 0 8px;color:var(--slate);">' + esc(title) + '</h3>';
      rows.slice(0,5).forEach(f => {{
        const v = f.verse_context || {{}};
        const ref = v.ref || '';
        const p = f.params || {{}};
        const tag = (f.method||'') + (p.mode ? ' / ' + p.mode : '');
        html += '<div class="finding-card ' + tone + '"><div class="finding-meta"><span class="pill">' + esc(tag) +
          '</span><span>' + esc(ref) + '</span></div><div class="finding-text">' + esc(f.found_text||'') + '</div>' +
          '<div class="finding-explainer">' + esc(f.explanation||'') + '</div>';
        if (v.hebrew) html += '<div class="verse-block"><div class="verse-label">Hebrew</div><div class="verse-hebrew">' + esc(v.hebrew) + '</div></div>';
        if (v.english) html += '<div class="verse-block" style="background:rgba(255,255,255,0.06);"><div class="verse-label">English</div><div class="verse-english">' + esc(v.english) + '</div></div>';
        html += '</div>';
      }});
    }});
    html += '</div>';
  }}

  // Graph data
  const graph = d.graph || {{}};
  const gnodes = graph.nodes || [];
  const gedges = graph.edges || [];
  if (gnodes.length > 1) {{
    const gs = graph.summary || {{}};
    html += '<div class="card"><div class="card-title">Gematria Relationship Graph</div>' +
      '<p style="font-size:12px;color:var(--slate);margin-bottom:8px;">' +
      (gs.name_components||0) + ' name components, ' + (gs.torah_words||0) + ' Torah words, ' +
      (gs.same_value_edges||0) + ' same-value links, ' + (gs.cross_method_edges||0) + ' cross-method matches</p>';
    const nameNodes = gnodes.filter(n => n.type === 'name_component');
    const torahNodes = gnodes.filter(n => n.type === 'torah_word').slice(0, 20);
    html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;">';
    nameNodes.forEach(n => {{
      html += '<div style="padding:6px 14px;border-radius:999px;background:var(--gold);color:white;font-size:13px;font-weight:600;direction:rtl;">' + esc(n.text) + '</div>';
    }});
    html += '</div><div class="torah-words">';
    torahNodes.forEach(n => {{
      html += '<span class="torah-word">' + esc(n.text) + ' <span class="torah-word-freq">' + esc(METHOD_LABELS[n.method]||n.method) + '=' + n.value + '</span></span>';
    }});
    html += '</div></div>';
  }}

  return html || '<div class="card"><p style="color:var(--slate);">No results found.</p></div>';
}}

function renderReverseLookup(data, val, method) {{
  const words = data.words || [];
  if (!words.length) return '<div class="card"><p style="color:var(--slate);">No words found with value ' + val + '.</p></div>';
  let html = '<div class="card"><div class="card-title">Value ' + val + ' (' + esc(METHOD_LABELS[method]||method) + ')</div>';
  html += '<p style="font-size:13px;color:var(--slate);margin-bottom:10px;">' + words.length + ' word forms found</p>';
  html += '<div class="torah-words">';
  words.forEach(w => {{
    html += '<span class="torah-word">' + esc(w.word) + ' <span class="torah-word-freq">\\u00d7' + w.frequency + '</span></span>';
  }});
  html += '</div></div>';
  return html;
}}
</script>
</body>
</html>'''
