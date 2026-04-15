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
<title>AutoGematria — Torah Name Analysis</title>
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
  background: radial-gradient(ellipse at 20% 0%,rgba(184,135,47,0.18),transparent 50%),
    radial-gradient(ellipse at 80% 100%,rgba(49,84,65,0.12),transparent 40%),
    linear-gradient(160deg,#faf4ea 0%,#f0e6d2 40%,#f6eddb 100%);
  min-height:100vh; line-height:1.55;
}}
.page {{ max-width:1080px; margin:0 auto; padding:28px 20px 80px; }}

header {{
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 0; margin-bottom:24px;
}}
.logo {{ display:flex; align-items:center; gap:10px; }}
.logo-mark {{
  width:32px; height:32px; border-radius:10px;
  background:linear-gradient(135deg,var(--gold),#e8c164);
  display:flex; align-items:center; justify-content:center;
  font-size:16px; color:white; font-weight:800;
  box-shadow:0 4px 12px rgba(184,135,47,0.3);
}}
.logo-text {{ font-size:18px; font-weight:700; color:var(--ink); letter-spacing:-0.02em; }}
.logo-sub {{ font-size:11px; color:var(--slate); margin-left:8px; }}
nav {{ display:flex; gap:4px; background:rgba(0,0,0,0.04); border-radius:12px; padding:3px; }}
nav button {{
  padding:8px 16px; border-radius:10px; border:none;
  background:transparent; color:var(--slate); font-size:13px; cursor:pointer;
  font-weight:600; transition:all 0.2s;
}}
nav button:hover {{ background:rgba(0,0,0,0.04); }}
nav button.active {{ background:white; color:var(--ink); box-shadow:0 2px 8px rgba(0,0,0,0.08); }}

/* Hero search */
.hero-search {{
  background:linear-gradient(135deg,rgba(28,25,22,0.96),rgba(52,40,22,0.94));
  border-radius:var(--radius-lg); padding:32px; margin-bottom:24px;
  box-shadow:0 20px 60px var(--shadow);
}}
.hero-title {{
  font-family:"Iowan Old Style","Palatino Linotype",Garamond,serif;
  font-size:clamp(28px,5vw,42px); color:#fff8ea; line-height:1.05; letter-spacing:-0.03em;
}}
.hero-desc {{ font-size:14px; color:rgba(255,248,234,0.7); margin:8px 0 20px; max-width:36rem; }}
.search-row {{ display:flex; gap:8px; }}
.search-input {{
  flex:1; padding:14px 18px; border-radius:14px; border:2px solid rgba(255,255,255,0.1);
  background:rgba(255,255,255,0.08); font-size:18px; font-family:inherit; color:white;
  transition:border-color 0.2s; direction:auto;
}}
.search-input:focus {{ outline:none; border-color:var(--gold-soft); }}
.search-input::placeholder {{ color:rgba(255,248,234,0.35); }}
.search-btn {{
  padding:14px 28px; border-radius:14px; border:none;
  background:linear-gradient(135deg,var(--gold),#d4a63a);
  color:white; font-size:15px; font-weight:700; cursor:pointer;
  box-shadow:0 4px 16px rgba(184,135,47,0.35); transition:transform 0.15s;
  white-space:nowrap;
}}
.search-btn:hover {{ transform:scale(1.03); }}
.search-btn:disabled {{ opacity:0.5; cursor:not-allowed; transform:none; }}
.example-names {{
  display:flex; gap:6px; margin-top:12px; flex-wrap:wrap;
}}
.example-chip {{
  padding:5px 12px; border-radius:999px; border:1px solid rgba(255,255,255,0.12);
  background:rgba(255,255,255,0.06); color:rgba(255,248,234,0.65);
  font-size:12px; cursor:pointer; transition:all 0.2s;
}}
.example-chip:hover {{ background:rgba(255,255,255,0.12); color:rgba(255,248,234,0.9); }}

/* Progress bar */
.progress-bar {{ display:none; margin-top:16px; }}
.progress-bar.active {{ display:block; }}
.progress-track {{
  height:6px; border-radius:3px; background:rgba(255,255,255,0.1); overflow:hidden;
}}
.progress-fill {{
  height:100%; border-radius:3px; background:linear-gradient(90deg,var(--gold),#e8c164);
  transition:width 0.5s ease; width:0%;
}}
.progress-text {{
  display:flex; justify-content:space-between; margin-top:6px;
  font-size:11px; color:rgba(255,248,234,0.55);
}}

/* Cards */
.card {{
  border-radius:var(--radius-lg); padding:24px; margin-bottom:14px;
  background:var(--card); box-shadow:0 6px 24px var(--shadow);
  border:1px solid rgba(184,135,47,0.1);
}}
.card-title {{
  font-size:11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase;
  color:var(--gold); margin-bottom:14px;
  display:flex; align-items:center; gap:8px;
}}
.card-title::before {{
  content:''; width:4px; height:14px; border-radius:2px; background:var(--gold);
}}

/* Name breakdown */
.name-parts {{ display:flex; gap:10px; flex-wrap:wrap; }}
.name-part {{
  border-radius:14px; padding:14px 20px; text-align:center;
  background:linear-gradient(145deg,#f4ead6,#faf4e8);
  border:1px solid rgba(184,135,47,0.15); min-width:100px; flex:1;
}}
.name-part-role {{ font-size:9px; letter-spacing:0.14em; text-transform:uppercase; color:var(--gold); font-weight:700; }}
.name-part-text {{ font-size:24px; margin:6px 0 4px; direction:rtl; font-family:"David","Times New Roman",serif; color:var(--ink); }}
.name-part-val {{ font-size:13px; color:var(--slate); font-weight:600; }}

/* Gematria table */
.gem-table {{ width:100%; border-collapse:separate; border-spacing:0; font-size:13px; }}
.gem-table th {{ text-align:left; padding:10px 10px; border-bottom:2px solid var(--gold-soft);
  font-size:9px; letter-spacing:0.12em; text-transform:uppercase; color:var(--slate); position:sticky; top:0; background:var(--card); }}
.gem-table td {{ padding:9px 10px; border-bottom:1px solid rgba(54,67,83,0.05); }}
.gem-table tbody tr:hover {{ background:rgba(184,135,47,0.04); }}
.gem-table .name-col {{ direction:rtl; font-family:"David","Times New Roman",serif; font-size:17px; font-weight:600; }}
.gem-table .role-col {{ font-size:9px; color:var(--gold); text-transform:uppercase; letter-spacing:0.08em; }}
.gem-table .val {{ text-align:center; font-weight:600; font-size:14px; font-variant-numeric:tabular-nums; }}

/* Letters */
.letters-row {{ display:flex; gap:6px; flex-wrap:wrap; justify-content:center; }}
.letter-card {{
  width:70px; border-radius:12px; padding:8px 4px; text-align:center;
  background:linear-gradient(145deg,#f8f0de,#fdf7ec);
  border:1px solid rgba(184,135,47,0.12); transition:transform 0.15s;
}}
.letter-card:hover {{ transform:translateY(-2px); }}
.letter-char {{ font-size:28px; font-family:"David","Times New Roman",serif; color:var(--gold); }}
.letter-name {{ font-size:8px; font-weight:700; color:var(--slate); text-transform:uppercase; letter-spacing:0.05em; }}
.letter-val {{ font-size:11px; color:var(--ink); font-weight:600; }}
.letter-meaning {{ font-size:7.5px; color:var(--forest); margin-top:2px; line-height:1.2; }}

/* Analysis blocks */
.analysis-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
.analysis-block {{ padding:16px; border-radius:14px; background:rgba(0,0,0,0.02); border:1px solid rgba(0,0,0,0.03); }}
.analysis-label {{ font-size:10px; font-weight:700; color:var(--slate); letter-spacing:0.1em; text-transform:uppercase; }}
.analysis-hebrew {{ direction:rtl; font-family:"David","Times New Roman",serif; font-size:18px; color:var(--gold); margin:6px 0; }}
.analysis-value {{ font-size:22px; font-weight:700; }}

/* Sefirah */
.sefirah-badge {{
  display:inline-flex; align-items:center; gap:8px; padding:8px 16px;
  border-radius:12px; background:linear-gradient(135deg,rgba(184,135,47,0.08),rgba(184,135,47,0.03));
  border:1px solid rgba(184,135,47,0.15);
}}
.sefirah-name {{ font-size:15px; font-weight:700; color:var(--gold); }}
.sefirah-desc {{ font-size:12px; color:var(--slate); }}

/* Torah words */
.torah-words {{ display:flex; gap:5px; flex-wrap:wrap; }}
.torah-word {{
  display:inline-flex; align-items:center; gap:4px;
  padding:4px 11px; border-radius:999px;
  background:rgba(49,84,65,0.06); border:1px solid rgba(49,84,65,0.1);
  font-size:14px; direction:rtl; font-family:"David","Times New Roman",serif;
  transition:background 0.15s;
}}
.torah-word:hover {{ background:rgba(49,84,65,0.12); }}
.torah-word-freq {{ font-size:8px; color:var(--slate); direction:ltr; }}

/* Four worlds */
.worlds-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }}

/* Finding cards */
.finding-card {{
  border-radius:var(--radius-lg); padding:16px; margin-bottom:10px;
  color:white; box-shadow:0 6px 20px var(--shadow);
}}
.finding-card.headline {{ background:linear-gradient(135deg,#8f6424,#caa24e 54%,#f6ddb1); color:#1d1204; }}
.finding-card.supporting {{ background:linear-gradient(135deg,#1f4e4b,#4e8a78 60%,#b7dbc7); }}
.finding-card.interesting {{ background:linear-gradient(135deg,#4a304c,#815486 55%,#d9bfdc); }}
.finding-meta {{ display:flex; align-items:center; justify-content:space-between; font-size:11px; }}
.pill {{ padding:4px 10px; border-radius:999px; background:rgba(255,255,255,0.16);
  border:1px solid rgba(255,255,255,0.18); font-size:10px; font-weight:600; }}
.finding-text {{ margin:10px 0 6px; font-size:18px; font-family:"Iowan Old Style",Garamond,serif; }}
.finding-explainer {{ font-size:12px; line-height:1.5; opacity:0.9; }}
.verse-block {{ margin-top:8px; padding:8px 12px; border-radius:12px; background:rgba(255,255,255,0.08);
  border:1px solid rgba(255,255,255,0.12); }}
.verse-label {{ font-size:8px; letter-spacing:0.12em; text-transform:uppercase; opacity:0.55; font-weight:700; }}
.verse-hebrew {{ direction:rtl; font-size:15px; font-family:"David","Times New Roman",serif; margin:4px 0 0; line-height:1.55; }}
.verse-english {{ font-size:11px; margin:4px 0 0; line-height:1.4; }}

/* Reverse lookup */
.reverse-input {{
  display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; align-items:center;
}}
.reverse-input input {{
  padding:12px 16px; border-radius:14px; border:2px solid rgba(184,135,47,0.15);
  font-size:18px; width:160px; background:white; font-weight:600;
}}
.reverse-input input:focus {{ outline:none; border-color:var(--gold); }}
.reverse-input select {{
  padding:12px 14px; border-radius:14px; border:2px solid rgba(184,135,47,0.15);
  font-size:13px; background:white;
}}
.reverse-input button {{
  padding:12px 20px; border-radius:14px; border:none;
  background:var(--forest); color:white; font-size:13px; font-weight:700; cursor:pointer;
  box-shadow:0 4px 12px rgba(49,84,65,0.25);
}}

/* Match cards */
.match-card {{
  border-radius:12px; padding:12px 16px; margin-bottom:8px;
  background:linear-gradient(135deg,rgba(45,90,123,0.05),rgba(49,84,65,0.03));
  border:1px solid rgba(45,90,123,0.1);
}}
.match-value {{ font-size:18px; font-weight:700; color:var(--accent); }}
.match-detail {{ font-size:12px; color:var(--ink); margin-top:3px; }}

/* Loading */
.loading {{ text-align:center; padding:40px; color:var(--slate); }}
.spinner {{ display:inline-block; width:20px; height:20px; border:3px solid rgba(184,135,47,0.2);
  border-top-color:var(--gold); border-radius:50%; animation:spin 0.8s linear infinite; }}
@keyframes spin {{ to {{ transform:rotate(360deg); }} }}

/* Timing badge */
.timing-badge {{
  display:inline-flex; align-items:center; gap:6px; padding:6px 14px;
  border-radius:999px; background:rgba(49,84,65,0.06); border:1px solid rgba(49,84,65,0.1);
  font-size:12px; color:var(--forest); font-weight:600; margin-bottom:14px;
}}

.hidden {{ display:none !important; }}
.error {{ padding:14px 18px; background:#fef2f2; border:1px solid #e8b4b4; border-radius:14px;
  color:#7a2f2f; font-size:13px; margin-bottom:14px; }}

/* Stats */
.stat-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; }}
.stat-card {{
  border-radius:14px; padding:16px; text-align:center;
  background:linear-gradient(145deg,#f4ead6,#faf4e8);
  border:1px solid rgba(184,135,47,0.12);
}}
.stat-label {{ font-size:9px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:var(--gold); }}
.stat-val {{ font-size:28px; font-weight:700; margin:4px 0; color:var(--ink); }}
.stat-sub {{ font-size:11px; color:var(--slate); }}

/* Copy-for-LLM button */
.copy-bar {{
  display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;
}}
.copy-btn {{
  display:inline-flex; align-items:center; gap:8px;
  padding:10px 16px; border-radius:12px; border:1px solid rgba(45,90,123,0.2);
  background:linear-gradient(135deg,#2d5a7b,#4178a0); color:white;
  font-size:13px; font-weight:700; cursor:pointer; font-family:inherit;
  box-shadow:0 4px 14px rgba(45,90,123,0.25); transition:transform 0.15s;
  min-height:44px;
}}
.copy-btn:hover {{ transform:translateY(-1px); }}
.copy-btn.copied {{ background:linear-gradient(135deg,#315441,#4e8a78); }}
.copy-btn svg {{ width:16px; height:16px; }}
.copy-hint {{
  font-size:11px; color:var(--slate); align-self:center; max-width:320px;
}}

@media(max-width:860px) {{
  .page {{ padding:18px 14px 60px; }}
  .analysis-grid {{ grid-template-columns:1fr; }}
  .worlds-row {{ grid-template-columns:1fr 1fr; }}
  .search-row {{ flex-direction:column; }}
  .search-btn {{ width:100%; }}
  .hero-search {{ padding:22px 18px; border-radius:var(--radius); }}
  .card {{ padding:18px 16px; border-radius:var(--radius); }}
  .finding-card {{ padding:14px; border-radius:var(--radius); }}
  .letter-card {{ width:58px; padding:6px 2px; }}
  .letter-char {{ font-size:24px; }}
  .letter-meaning {{ display:none; }}
  .name-part {{ padding:10px 14px; min-width:90px; }}
  .name-part-text {{ font-size:20px; }}
  .finding-text {{ font-size:16px; }}
  .gem-table {{ font-size:12px; }}
  .gem-table th, .gem-table td {{ padding:6px 6px; }}
  nav button {{ padding:8px 12px; font-size:12px; }}
  .logo-sub {{ display:none; }}
  header {{ margin-bottom:16px; padding:10px 0; }}
  .hero-title {{ font-size:26px; }}
  .hero-desc {{ font-size:13px; margin:6px 0 14px; }}
  .search-input {{ padding:14px 16px; font-size:16px; }}
}}
@media(max-width:480px) {{
  .page {{ padding:14px 12px 50px; }}
  .worlds-row {{ grid-template-columns:1fr 1fr; gap:6px; }}
  .name-parts {{ flex-direction:column; }}
  .letter-card {{ width:46px; }}
  .letter-char {{ font-size:20px; }}
  .letter-name {{ font-size:7px; }}
  .reverse-input {{ flex-direction:column; align-items:stretch; }}
  .reverse-input input, .reverse-input select, .reverse-input button {{ width:100%; }}
  .copy-btn {{ width:100%; justify-content:center; }}
  .copy-hint {{ display:none; }}
  nav {{ gap:2px; padding:2px; }}
  nav button {{ padding:6px 10px; font-size:11px; }}
  .hero-search {{ padding:18px 14px; }}
  .card {{ padding:14px 12px; }}
  .card-title {{ font-size:10px; }}
  .hero-title {{ font-size:22px; }}
  .finding-card {{ padding:12px; }}
  .finding-text {{ font-size:15px; }}
  .verse-hebrew {{ font-size:14px; }}
  .gem-table {{ font-size:11px; }}
  .gem-table .name-col {{ font-size:15px; }}
  .gem-table th, .gem-table td {{ padding:5px 4px; }}
}}
</style>
</head>
<body>
<div class="page">
  <header>
    <div class="logo">
      <div class="logo-mark">AG</div>
      <span class="logo-text">AutoGematria</span>
      <span class="logo-sub">Torah Name Analysis</span>
    </div>
    <nav>
      <button class="active" onclick="showView('search',this)">Analyze</button>
      <button onclick="showView('reverse',this)">Reverse Lookup</button>
      <button onclick="showView('about',this)">About</button>
    </nav>
  </header>

  <div id="view-search">
    <div class="hero-search">
      <div class="hero-title">Find your name in the Torah</div>
      <div class="hero-desc">Enter a Hebrew or English name. Supports complex structures like "moshe ben yitzchak v'miriam gindi" or "שרה בת אברהם ורבקה כהן".</div>
      <div class="search-row">
        <input class="search-input" id="name-input" type="text"
          placeholder="Enter a name..." dir="auto" autofocus>
        <button class="search-btn" id="search-btn" onclick="runSearch()">Analyze Name</button>
      </div>
      <div class="example-names">
        <span class="example-chip" onclick="setExample('דוד בן ישי')">דוד בן ישי</span>
        <span class="example-chip" onclick="setExample('שרה בת אברהם ורבקה כהן')">שרה בת אברהם ורבקה כהן</span>
        <span class="example-chip" onclick="setExample('david ben shlomo')">david ben shlomo</span>
      </div>
      <div class="progress-bar" id="progress-bar">
        <div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
        <div class="progress-text">
          <span id="progress-label">Analyzing...</span>
          <span id="progress-eta"></span>
        </div>
      </div>
    </div>
    <div id="search-error" class="error hidden"></div>
    <div id="search-results" class="hidden"></div>
  </div>

  <div id="view-reverse" class="hidden">
    <div class="card">
      <div class="card-title">Gematria Reverse Lookup</div>
      <p style="color:var(--slate);font-size:13px;margin-bottom:14px;">
        Enter a number to find all Tanakh words with that gematria value.
      </p>
      <div class="reverse-input">
        <input type="number" id="reverse-value" placeholder="345" min="1"
          onkeydown="if(event.key==='Enter')runReverseLookup()">
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
  </div>

  <div id="view-about" class="hidden">
    <div class="card">
      <div class="card-title">About</div>
      <p style="font-size:14px;line-height:1.7;">
        AutoGematria is a deterministic Torah name-finding and gematria analysis engine.
        Every person's name can be found in the Torah — this tool systematically discovers those connections
        through direct text search, equidistant letter sequences (ELS), acrostics, and gematria equivalences.
      </p>
      <p style="font-size:14px;line-height:1.7;margin-top:10px;">
        Kabbalistic analysis uses traditional Orthodox sources: letter meanings (Sefer Yetzirah, Arizal),
        milui (letter-filling), AtBash cipher, sefirot associations, and four-worlds (ABYA) breakdown.
      </p>
    </div>
    <div class="card">
      <div class="card-title">System Requirements</div>
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-label">CPU</div><div class="stat-val">Any</div><div class="stat-sub">No GPU needed</div></div>
        <div class="stat-card"><div class="stat-label">Memory</div><div class="stat-val">~52 MB</div><div class="stat-sub">Peak RSS during search</div></div>
        <div class="stat-card"><div class="stat-label">Storage</div><div class="stat-val">~50 MB</div><div class="stat-sub">SQLite database</div></div>
        <div class="stat-card"><div class="stat-label">Python</div><div class="stat-val">3.11+</div><div class="stat-sub">No LLM required</div></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Corpus</div>
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-label">Books</div><div class="stat-val">39</div><div class="stat-sub">Full Tanakh</div></div>
        <div class="stat-card"><div class="stat-label">Verses</div><div class="stat-val">23,206</div><div class="stat-sub">Torah + Nevi'im + Ketuvim</div></div>
        <div class="stat-card"><div class="stat-label">Words</div><div class="stat-val">306,869</div><div class="stat-sub">All word forms indexed</div></div>
        <div class="stat-card"><div class="stat-label">Letters</div><div class="stat-val">1,205,822</div><div class="stat-sub">With absolute indices</div></div>
        <div class="stat-card"><div class="stat-label">Gematria Methods</div><div class="stat-val">22</div><div class="stat-sub">894,608 precomputed values</div></div>
        <div class="stat-card"><div class="stat-label">Unique Forms</div><div class="stat-val">40,664</div><div class="stat-sub">Distinct word forms</div></div>
      </div>
    </div>
    <div class="card" id="run-stats-card" style="display:none;">
      <div class="card-title">Run History</div>
      <div id="run-stats-content"></div>
    </div>
  </div>
</div>

<script>
const API = "{base_url}";
let progressInterval = null;

function showView(name, btn) {{
  document.querySelectorAll('[id^="view-"]').forEach(v => v.classList.add('hidden'));
  document.getElementById('view-' + name).classList.remove('hidden');
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  if (name === 'about') loadRunStats();
}}

function setExample(text) {{
  document.getElementById('name-input').value = text;
  document.getElementById('name-input').focus();
}}

document.getElementById('name-input').value = '';
document.getElementById('name-input').addEventListener('keydown', e => {{
  if (e.key === 'Enter') runSearch();
}});

function startProgress(estSeconds) {{
  const bar = document.getElementById('progress-bar');
  const fill = document.getElementById('progress-fill');
  const label = document.getElementById('progress-label');
  const eta = document.getElementById('progress-eta');
  bar.classList.add('active');
  fill.style.width = '0%';

  const steps = ['Parsing name...', 'Computing gematria...', 'Kabbalistic analysis...', 'Searching Torah...', 'Building graph...', 'Finalizing...'];
  let stepIdx = 0;
  const startTime = Date.now();
  const totalMs = estSeconds * 1000;

  progressInterval = setInterval(() => {{
    const elapsed = Date.now() - startTime;
    const pct = Math.min(95, (elapsed / totalMs) * 100);
    fill.style.width = pct + '%';
    const remaining = Math.max(0, Math.ceil((totalMs - elapsed) / 1000));
    eta.textContent = remaining > 0 ? remaining + 's remaining' : 'almost done...';
    const newStep = Math.min(steps.length - 1, Math.floor(pct / (100 / steps.length)));
    if (newStep !== stepIdx) {{ stepIdx = newStep; label.textContent = steps[stepIdx]; }}
  }}, 200);
}}

function stopProgress() {{
  if (progressInterval) {{ clearInterval(progressInterval); progressInterval = null; }}
  const fill = document.getElementById('progress-fill');
  fill.style.width = '100%';
  setTimeout(() => {{ document.getElementById('progress-bar').classList.remove('active'); }}, 600);
}}

async function runSearch() {{
  const q = document.getElementById('name-input').value.trim();
  if (!q) return;
  const btn = document.getElementById('search-btn');
  const results = document.getElementById('search-results');
  const errDiv = document.getElementById('search-error');
  btn.disabled = true; results.classList.add('hidden'); errDiv.classList.add('hidden');

  let estSec = 90;
  try {{
    const estResp = await fetch(API + '/api/estimate', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{query: q, operation: 'full_report'}})
    }});
    if (estResp.ok) {{ const ed = await estResp.json(); estSec = Math.max(60, ed.estimated_seconds || 90); }}
  }} catch(e) {{}}

  startProgress(estSec);
  const label = document.getElementById('progress-label');

  try {{
    const submit = await fetch(API + '/api/jobs', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{operation: 'full_report', query: q}})
    }});
    if (!submit.ok) throw new Error('Submit failed: ' + submit.status);
    const sub = await submit.json();
    const jobId = sub.job_id;

    let job;
    while (true) {{
      await new Promise(r => setTimeout(r, 1500));
      const pr = await fetch(API + '/api/jobs/' + jobId);
      if (!pr.ok) throw new Error('Poll failed: ' + pr.status);
      job = await pr.json();
      if (job.status === 'queued') {{
        label.textContent = 'In queue — position ' + (job.queue_position || '?');
      }} else if (job.status === 'running') {{
        label.textContent = 'Analyzing your name...';
      }} else if (job.status === 'done') {{
        break;
      }} else if (job.status === 'error') {{
        throw new Error(job.error || 'job failed');
      }}
    }}

    stopProgress();
    results.innerHTML = renderReport(job.result);
    results.classList.remove('hidden');
    results.scrollIntoView({{behavior:'smooth', block:'start'}});
  }} catch(e) {{
    stopProgress();
    errDiv.textContent = 'Error: ' + e.message;
    errDiv.classList.remove('hidden');
  }} finally {{
    btn.disabled = false;
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

async function loadRunStats() {{
  try {{
    const resp = await fetch(API + '/api/run-stats');
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.total_runs > 0) {{
      const card = document.getElementById('run-stats-card');
      const content = document.getElementById('run-stats-content');
      card.style.display = '';
      let html = '<div class="stat-grid">';
      html += '<div class="stat-card"><div class="stat-label">Total Runs</div><div class="stat-val">' + data.total_runs + '</div></div>';
      for (const [op, s] of Object.entries(data.operations || {{}})) {{
        html += '<div class="stat-card"><div class="stat-label">' + esc(op.replace(/_/g,' ')) + '</div><div class="stat-val">' + s.count + '</div><div class="stat-sub">avg ' + s.avg_seconds + 's</div></div>';
      }}
      html += '</div>';
      content.innerHTML = html;
    }}
  }} catch(e) {{}}
}}

const ROLE_LABELS = {{
  first_name: 'First Name', father_name: "Father's Name", mother_name: "Mother's Name",
  surname: 'Surname', extra: 'Additional', combined_all: 'Full Combined',
}};
const METHOD_LABELS = {{
  MISPAR_HECHRACHI: 'Standard', MISPAR_GADOL: 'Full Value', MISPAR_KATAN: 'Reduced',
  MISPAR_SIDURI: 'Ordinal', ATBASH: 'AtBash', MISPAR_KOLEL: 'Kolel',
}};

function esc(s) {{ if (!s) return ''; const d=document.createElement('div'); d.textContent=String(s); return d.innerHTML; }}

let _lastReport = null;

function renderReport(d) {{
  _lastReport = d;
  const r = d.report || {{}};
  const s = d.showcase || {{}};
  const timing = d.timing || {{}};
  let html = '';

  html += '<div class="copy-bar">' +
    '<button class="copy-btn" id="copy-md-btn" onclick="copyMarkdown()">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>' +
    '<span id="copy-md-label">Copy for ChatGPT / Claude / Gemini</span>' +
    '</button>' +
    '<span class="copy-hint">Copies a full markdown report you can paste into any AI chat to discuss the results.</span>' +
    '</div>';

  if (timing.elapsed_seconds) {{
    html += '<div class="timing-badge">Completed in ' + timing.elapsed_seconds + 's</div>';
  }}

  const comps = r.hebrew_components || [];
  if (comps.length) {{
    html += '<div class="card"><div class="card-title">Name Breakdown</div><div class="name-parts">';
    comps.forEach(c => {{
      html += '<div class="name-part"><div class="name-part-role">' + esc(ROLE_LABELS[c.role]||c.role) +
        '</div><div class="name-part-text">' + esc(c.text) + '</div><div class="name-part-val">= ' + c.gematria + '</div></div>';
    }});
    html += '</div></div>';
  }}

  const gt = (r.cross_comparison||{{}}).gematria_table || {{}};
  const methods = gt.methods || [];
  const gtcomps = gt.components || [];
  if (methods.length && gtcomps.length) {{
    html += '<div class="card"><div class="card-title">Gematria Across Methods</div><div style="overflow-x:auto;"><table class="gem-table"><thead><tr><th>Name</th><th>Role</th>';
    methods.forEach(m => html += '<th class="val">' + esc(m.display) + '</th>');
    html += '</tr></thead><tbody>';
    gtcomps.forEach(c => {{
      html += '<tr><td class="name-col">' + esc(c.text) + '</td><td class="role-col">' + esc(ROLE_LABELS[c.role]||c.role) + '</td>';
      methods.forEach(m => html += '<td class="val">' + (c.values[m.name]||'') + '</td>');
      html += '</tr>';
    }});
    html += '</tbody></table></div></div>';
  }}

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
        '<div style="font-size:11px;color:var(--slate);margin-top:4px;">Gematria ' + (sef.value||'') + ' reduces to ' + (sef.reduced_to||'') + '</div></div>';
    }}
    html += '</div>';
  }}

  const milui = kab.milui || {{}};
  const atbash = kab.atbash || {{}};
  if (milui.full_milui_text || atbash.atbash_text) {{
    html += '<div class="card"><div class="card-title">Kabbalistic Analysis</div><div class="analysis-grid">';
    if (milui.full_milui_text) {{
      html += '<div class="analysis-block"><div class="analysis-label">Milui (Letter Filling)</div>' +
        '<div class="analysis-hebrew">' + esc(milui.full_milui_text) + '</div>' +
        '<div class="analysis-value">' + milui.milui_value + '</div>' +
        '<div style="font-size:11px;color:var(--slate);margin-top:4px;">Hidden: ' + esc(milui.hidden_text||'') + ' = ' + (milui.hidden_value||0) + '</div></div>';
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

  const fw = (kab.four_worlds||{{}}).worlds || [];
  if (fw.length) {{
    const colors = {{Atzilut:'#b8872f',Beriah:'#2d5a7b',Yetzirah:'#315441',Asiyah:'#7a2f2f'}};
    html += '<div class="card"><div class="card-title">Four Worlds (ABYA)</div><div class="worlds-row">';
    fw.forEach(w => {{
      const c = colors[w.world]||'#364353';
      html += '<div style="border-radius:14px;padding:14px;text-align:center;background:' + c + '10;border:1px solid ' + c + '25;">' +
        '<div style="font-size:9px;font-weight:700;color:' + c + ';text-transform:uppercase;letter-spacing:0.12em;">' + esc(w.world) + '</div>' +
        '<div style="font-size:8px;color:var(--slate);">' + esc(w.soul_level||'') + '</div>' +
        '<div style="font-size:22px;direction:rtl;font-family:David,serif;margin:6px 0;color:' + c + ';">' + esc((w.letters||[]).join(' ')) + '</div>' +
        '<div style="font-size:16px;font-weight:700;">' + (w.value||0) + '</div></div>';
    }});
    html += '</div></div>';
  }}

  const twm = (r.cross_comparison||{{}}).torah_word_matches || {{}};
  const twKeys = Object.keys(twm).filter(k => (twm[k]||[]).length > 0);
  if (twKeys.length) {{
    html += '<div class="card"><div class="card-title">Torah Words with Same Gematria</div>';
    twKeys.forEach(key => {{
      const [text, role] = key.split('|');
      const val = (twm[key][0]||{{}}).shared_value || '';
      html += '<div style="margin-bottom:12px;"><div style="font-size:11px;font-weight:600;color:var(--slate);">' +
        esc(text) + ' (' + esc(ROLE_LABELS[role]||role) + ') = ' + val + '</div><div class="torah-words" style="margin-top:4px;">';
      (twm[key]||[]).slice(0,10).forEach(w => {{
        html += '<span class="torah-word">' + esc(w.word) + ' <span class="torah-word-freq">\\u00d7' + w.frequency + '</span></span>';
      }});
      html += '</div></div>';
    }});
    html += '</div>';
  }}

  const cm = (r.cross_comparison||{{}}).cross_matches || [];
  if (cm.length) {{
    html += '<div class="card"><div class="card-title">Cross-Comparison Discoveries</div>';
    cm.slice(0,8).forEach(m => {{
      const a = m.component_a||{{}}, b = m.component_b||{{}};
      html += '<div class="match-card"><div style="display:flex;align-items:center;gap:8px;">' +
        '<div class="match-value">' + (m.value||'') + '</div>' +
        '<span class="pill" style="background:rgba(45,90,123,0.08);color:var(--accent);border-color:rgba(45,90,123,0.15);">' +
        esc((m.match_type||'').replace(/_/g,' ')) + '</span></div>' +
        '<div class="match-detail"><strong>' + esc(a.text||'') + '</strong> (' + esc(ROLE_LABELS[a.role]||a.role||'') + ', ' + esc(METHOD_LABELS[a.method]||a.method||'') + ')' +
        ' = <strong>' + esc(b.text||'') + '</strong> (' + esc(ROLE_LABELS[b.role]||b.role||'') + ', ' + esc(METHOD_LABELS[b.method]||b.method||'') + ')</div></div>';
    }});
    html += '</div>';
  }}

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
      html += '<h3 style="font-size:13px;margin:12px 0 8px;color:var(--slate);font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">' + esc(title) + '</h3>';
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

  const graph = d.graph || {{}};
  const gnodes = graph.nodes || [];
  if (gnodes.length > 1) {{
    const gs = graph.summary || {{}};
    html += '<div class="card"><div class="card-title">Gematria Relationship Graph</div>' +
      '<p style="font-size:11px;color:var(--slate);margin-bottom:8px;">' +
      (gs.name_components||0) + ' components, ' + (gs.torah_words||0) + ' Torah words, ' +
      (gs.same_value_edges||0) + ' same-value, ' + (gs.cross_method_edges||0) + ' cross-method</p>';
    const nameNodes = gnodes.filter(n => n.type === 'name_component');
    const torahNodes = gnodes.filter(n => n.type === 'torah_word').slice(0, 20);
    html += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;">';
    nameNodes.forEach(n => {{
      html += '<div style="padding:6px 14px;border-radius:999px;background:var(--gold);color:white;font-size:12px;font-weight:700;direction:rtl;">' + esc(n.text) + '</div>';
    }});
    html += '</div><div class="torah-words">';
    torahNodes.forEach(n => {{
      html += '<span class="torah-word">' + esc(n.text) + ' <span class="torah-word-freq">' + esc(METHOD_LABELS[n.method]||n.method) + '=' + n.value + '</span></span>';
    }});
    html += '</div></div>';
  }}

  return html || '<div class="card"><p style="color:var(--slate);">No results found.</p></div>';
}}

function buildReportMarkdown(d) {{
  if (!d) return '';
  const r = d.report || {{}};
  const s = d.showcase || {{}};
  const kab = r.kabbalistic_full_name || {{}};
  const cc = r.cross_comparison || {{}};
  const lines = [];
  const push = (x) => lines.push(x);

  const fullName = r.full_hebrew_name || r.raw_input || '';
  push('# AutoGematria Report — ' + fullName);
  push('');
  push('Source: https://gematria.jewishaiart.com');
  push('Query: `' + (r.raw_input || '') + '`');
  if ((d.timing||{{}}).elapsed_seconds) push('Compute time: ' + d.timing.elapsed_seconds + 's');
  push('');
  push('> This is an automated Torah name analysis produced by AutoGematria, a deterministic (non-LLM) Hebrew gematria and Tanakh search engine. Use this as structured reference material to discuss Jewish numerology, kabbalistic symbolism, and Torah word connections for the name above. All Hebrew is unpointed consonantal text. Gematria values are computed by classical methods (Mispar Hechrachi, Gadol, Katan, Siduri, AtBash, Kolel).');
  push('');

  const comps = r.hebrew_components || [];
  if (comps.length) {{
    push('## Name Breakdown');
    push('');
    comps.forEach(c => {{
      push('- **' + (ROLE_LABELS[c.role]||c.role) + ':** ' + c.text + ' = **' + c.gematria + '**');
    }});
    push('');
  }}

  const gt = cc.gematria_table || {{}};
  const methods = gt.methods || [];
  const gtcomps = gt.components || [];
  if (methods.length && gtcomps.length) {{
    push('## Gematria Across Methods');
    push('');
    const header = ['Name','Role', ...methods.map(m => m.display)];
    push('| ' + header.join(' | ') + ' |');
    push('|' + header.map(() => '---').join('|') + '|');
    gtcomps.forEach(c => {{
      const row = [c.text, (ROLE_LABELS[c.role]||c.role), ...methods.map(m => c.values[m.name] || '')];
      push('| ' + row.join(' | ') + ' |');
    }});
    push('');
  }}

  const letters = kab.letter_meanings || [];
  if (letters.length) {{
    push('## Letter-by-Letter Analysis');
    push('');
    push('| Letter | Name | Value | Meaning |');
    push('|---|---|---|---|');
    letters.forEach(l => {{
      const m = (l.meaning||'').replace(/\\|/g,'/');
      push('| ' + l.letter + ' | ' + l.name + ' | ' + l.value + ' | ' + m + ' |');
    }});
    push('');
  }}

  const sef = kab.sefirah || {{}};
  if (sef.sefirah) {{
    push('## Sefirah Association');
    push('');
    push('- **Sefirah:** ' + sef.sefirah);
    if (sef.description) push('- **Description:** ' + sef.description);
    if (sef.value !== undefined) push('- **Gematria value:** ' + sef.value + ' (reduces to ' + (sef.reduced_to || '') + ')');
    push('');
  }}

  const milui = kab.milui || {{}};
  if (milui.full_milui_text) {{
    push('## Milui (Letter Filling)');
    push('');
    push('- **Expanded:** ' + milui.full_milui_text);
    push('- **Milui value:** ' + milui.milui_value);
    if (milui.hidden_text) push('- **Hidden:** ' + milui.hidden_text + ' = ' + milui.hidden_value);
    push('');
  }}

  const atbash = kab.atbash || {{}};
  if (atbash.atbash_text) {{
    push('## AtBash Transformation');
    push('');
    push('- **AtBash text:** ' + atbash.atbash_text);
    push('- **Original value:** ' + (atbash.original_value||''));
    push('- **AtBash value:** ' + (atbash.atbash_value||''));
    push('- **Sum:** ' + (atbash.sum_with_original||''));
    push('');
  }}

  const worlds = (kab.four_worlds||{{}}).worlds || [];
  if (worlds.length) {{
    push('## Four Worlds (ABYA)');
    push('');
    push('| World | Soul Level | Letters | Value |');
    push('|---|---|---|---|');
    worlds.forEach(w => {{
      push('| ' + w.world + ' | ' + (w.soul_level||'') + ' | ' + (w.letters||[]).join(' ') + ' | ' + (w.value||0) + ' |');
    }});
    push('');
  }}

  const twm = cc.torah_word_matches || {{}};
  const twKeys = Object.keys(twm).filter(k => (twm[k]||[]).length > 0);
  if (twKeys.length) {{
    push('## Torah Words with Same Gematria');
    push('');
    twKeys.forEach(key => {{
      const [text, role] = key.split('|');
      const list = twm[key] || [];
      const val = (list[0]||{{}}).shared_value || '';
      push('**' + text + '** (' + (ROLE_LABELS[role]||role) + ') = ' + val);
      push('');
      const words = list.slice(0, 20).map(w => w.word + ' (×' + w.frequency + ')').join(', ');
      push(words);
      push('');
    }});
  }}

  const cm = cc.cross_matches || [];
  if (cm.length) {{
    push('## Cross-Comparison Discoveries');
    push('');
    cm.slice(0, 20).forEach(m => {{
      const a = m.component_a||{{}}, b = m.component_b||{{}};
      push('- **' + (m.value||'') + '** [' + (m.match_type||'').replace(/_/g,' ') + '] — `' +
        (a.text||'') + '` (' + (ROLE_LABELS[a.role]||a.role||'') + ', ' + (METHOD_LABELS[a.method]||a.method||'') +
        ') = `' + (b.text||'') + '` (' + (ROLE_LABELS[b.role]||b.role||'') + ', ' + (METHOD_LABELS[b.method]||b.method||'') + ')');
    }});
    push('');
  }}

  const vl = s.verdict_label || '';
  if (vl) {{
    push('## Verdict: ' + vl);
    push('');
  }}

  const groups = [
    ['Primary Torah Findings', s.headline_findings || []],
    ['Supporting Findings', s.supporting_findings || []],
    ['Additional Discoveries', s.interesting_findings || []],
  ];
  groups.forEach(([title, rows]) => {{
    if (!rows.length) return;
    push('## ' + title);
    push('');
    rows.slice(0, 10).forEach((f, i) => {{
      const v = f.verse_context || {{}};
      const ref = v.ref || '';
      const p = f.params || {{}};
      const tag = (f.method || '') + (p.mode ? ' / ' + p.mode : '');
      push('### ' + (i+1) + '. ' + (f.found_text || '') + (ref ? ' — ' + ref : ''));
      push('');
      push('- **Method:** ' + tag);
      if (f.explanation) push('- **Explanation:** ' + f.explanation);
      if (v.hebrew) {{ push(''); push('> **Hebrew:** ' + v.hebrew); }}
      if (v.english) {{ push(''); push('> **English:** ' + v.english); }}
      push('');
    }});
  }});

  const graph = d.graph || {{}};
  const gs = graph.summary || {{}};
  if (gs.name_components || gs.torah_words) {{
    push('## Gematria Relationship Graph');
    push('');
    push('- Name components: ' + (gs.name_components || 0));
    push('- Torah words: ' + (gs.torah_words || 0));
    push('- Same-value edges: ' + (gs.same_value_edges || 0));
    push('- Cross-method edges: ' + (gs.cross_method_edges || 0));
    push('');
  }}

  push('---');
  push('Ask the AI to explain any finding, compare to other traditions, or explore the symbolism of the letters and sefirot.');
  return lines.join('\\n');
}}

async function copyMarkdown() {{
  const md = buildReportMarkdown(_lastReport);
  if (!md) return;
  const btn = document.getElementById('copy-md-btn');
  const label = document.getElementById('copy-md-label');
  const original = label.textContent;
  let ok = false;
  try {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      await navigator.clipboard.writeText(md);
      ok = true;
    }}
  }} catch(e) {{}}
  if (!ok) {{
    try {{
      const ta = document.createElement('textarea');
      ta.value = md; ta.style.position='fixed'; ta.style.left='-9999px';
      document.body.appendChild(ta); ta.focus(); ta.select();
      ok = document.execCommand('copy');
      document.body.removeChild(ta);
    }} catch(e) {{}}
  }}
  label.textContent = ok ? 'Copied!  Now paste into ChatGPT / Claude / Gemini' : 'Copy failed — long-press to select';
  btn.classList.toggle('copied', ok);
  setTimeout(() => {{ label.textContent = original; btn.classList.remove('copied'); }}, 3200);
}}

function renderReverseLookup(data, val, method) {{
  const words = data.words || [];
  if (!words.length) return '<p style="color:var(--slate);padding:12px;">No words found with value ' + val + '.</p>';
  let html = '<div style="margin-top:12px;"><div style="font-size:13px;color:var(--slate);margin-bottom:8px;">' + words.length + ' word forms with value <strong>' + val + '</strong> (' + esc(METHOD_LABELS[method]||method) + ')</div>';
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
