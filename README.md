# AutoGematria

A Torah name-finding and gematria autoresearch system. Given a Hebrew name, find where it appears in the Torah through traditional methods — direct text, equidistant letter sequences (ELS), roshei/sofei tevot, and gematria equivalences.

There is a Jewish tradition that every person's name can be found in the Torah. This project builds the tools to systematically discover those connections.

## What's Inside

**Full Tanakh corpus** — 39 books, 23,206 verses, 306,869 words, 1,205,822 letters, all stored in SQLite with gapless absolute letter indices for efficient ELS searching.

**22 gematria methods** — Standard (Mispar Hechrachi), Gadol, Katan, Siduri, Atbash, Albam, and 16 more, precomputed for all 40,664 unique word forms (894,608 total values).

**5 search methods:**
- **Substring** — direct text matching within and across words
- **ELS** — equidistant letter sequences with fast skip-string search (Boyer-Moore)
- **ELS Proximity** — co-located ELS pairs for multi-word names (the standard Bible codes methodology)
- **Roshei Tevot** — first letters of consecutive words
- **Sofei Tevot** — last letters of consecutive words

**Statistical significance** — empirical p-values against null models (letter shuffle, Markov chain, word permutation) with Benjamini-Hochberg FDR correction.

## Setup

```bash
pip install -e ".[dev]"
```

## Usage

### Download the corpus

Downloads the full Tanakh from the Sefaria API (consonantal Hebrew, ~8 minutes):

```bash
ag-download
```

### Build the database

```bash
ag-ingest   # Parse JSON → SQLite
ag-index    # Precompute all gematria values
```

### Search for a name

```bash
ag-search "משה"                         # Default scope: Torah/Chumash only
ag-search "אברהם" Genesis               # Restrict to one book
ag-search "משה" --corpus-scope tanakh   # Optional: full Tanakh scope
```

### Generate a visual Torah name report

Creates an HTML report with highlighted pesukim showing exactly where the name is encoded, publishes to here.now, and returns the link:

```bash
ag-name-report "משה גינדי" --publish --json
ag-name-report "משה גינדי" --variant "משה גנדי" --label "Aleppo spelling" --publish
```

For multi-word names, the report uses **ELS Proximity Search** — finding regions where both the first name and surname appear encoded near each other in the Torah text. Each finding shows the verse with the exact letters highlighted: gold for the surname's ELS letters, green for the first name.

Common first names (משה, אברהם, דוד, etc.) are not presented as standalone findings — instead, the report notes their frequency as a stat and focuses on where both parts co-locate.

### Verify findings (deterministic + optional GLM audit)

```bash
ag-verify "משה"
ag-verify "משה גינדי" --max-results 30 --els-max-skip 800
ag-verify "משה גינדי" --word-breakdown
ag-verify "moshe gindi" --word-breakdown   # auto transliteration to Hebrew variants
ag-verify "moshe gindi" --corpus-scope tanakh
```

Optional GLM-5 audit (global Z.AI API):

```bash
export GLM_API_KEY="your-key"
ag-verify "משה" --glm-audit --glm-model glm-5
ag-verify "משה" --glm-audit --glm-model glm-5 --glm-strict-model
```

Default GLM endpoint is `https://api.z.ai/api/paas/v4`. You can override with
`GLM_BASE_URL` or `--glm-base-url` (for coding plan endpoint, etc.).
When `--glm-strict-model` is not set, the client can fallback from `glm-5*` to
`glm-4.7` automatically if the plan does not include GLM-5.

### Python API

```python
from autogematria.search.unified import UnifiedSearch, UnifiedSearchConfig

cfg = UnifiedSearchConfig(els_max_skip=500)
searcher = UnifiedSearch(cfg)
results = searcher.search("משה")

for r in results[:10]:
    print(f"[{r.method}] {r.location_start.book} {r.location_start.chapter}:{r.location_start.verse}")
    print(f"  {r.context}")
```

### Manual Verification

`find_name_in_torah()` / `search_name` now attach a deterministic `verification` payload to every
result, including:
- whether the match re-check passed (`verified`)
- exact indices used (letter indices for ELS, word spans for acrostics/cross-word)
- reconstructed sequence (`expected_sequence` vs `actual_sequence`)

For ELS results, use `skip` + `start_index` directly with:

```python
from autogematria.tools.tool_functions import els_detail

detail = els_detail("תורה", skip=50, start_index=5)
print(detail["letters"])
```

This gives a letter-by-letter trace with absolute indices and references so any finding can be
audited manually.

### Gematria lookup

```python
from hebrew import Hebrew
from hebrew.gematria import GematriaTypes
from autogematria.tools.tool_functions import gematria_connections

h = Hebrew("אלהים")
print(h.gematria())                              # 86 (standard)
print(h.gematria(GematriaTypes.MISPAR_GADOL))     # 646

connections = gematria_connections("משה")
print(connections["related_words"][:5])  # graph-ranked value-equivalent links
```

## Architecture

- **Data source**: Sefaria API, "Tanach with Text Only" (Public Domain)
- **Data layer**: SQLite (single file, ~50MB)
- **Gematria engine**: [hebrew](https://pypi.org/project/hebrew/) PyPI package (23 methods)
- **Search**: Pure Python, in-memory letter arrays for ELS
- **Stats**: scipy for BH/FDR correction, custom null models
- **Gematria connection library**: curated source-backed equivalence records in
  `data/gematria/connections.json` plus graph-ranked related-term expansion

### Conservative verdict contract

The search pipeline now separates:

1. candidate generation
2. evidence scoring/calibration
3. report formatting

and emits an explicit final verdict:

- `strong_evidence`
- `moderate_evidence`
- `weak_evidence`
- `no_convincing_evidence` (explicit abstain)

## Full Report

Generate a complete report for any Hebrew name:

```bash
python -m autogematria.tools.pipeline "משה"
python -m autogematria.tools.pipeline "אברהם" Genesis
```

This runs all search methods + gematria across multiple methods, and for multi-word names searches each word separately too.

## CLI Tools

The repo now exposes its higher-level tool surface via CLI instead of MCP:

```bash
ag-search-name "משה" --json
ag-lookup-gematria "משה" --json
ag-search-gematria-patterns "בראשית ברא" --json
ag-explore-gematria-connections "משה" --json
ag-read-verse Genesis 1 1 --json
ag-inspect-els "תורה" 50 5 --json
ag-corpus-stats --json
ag-show-name "משה" --json
ag-show-name "משה" --html-out exports/moshe.html
ag-research-name "moshe gindi" --json
ag-name-report "משה גינדי" --publish --json
ag-serve-api --port 8080
```

## Agent API

If you want other agents to call the system over HTTP instead of shelling into the CLI, run the API server:

```bash
ag-serve-api --port 8080
```

Endpoints:

```bash
curl http://localhost:8080/health

curl http://localhost:8080/for-agents
curl http://localhost:8080/agent.txt
curl http://localhost:8080/.well-known/autogematria-agent.json

curl -X POST http://localhost:8080/api/showcase-name \
  -H "Content-Type: application/json" \
  -d '{"query":"משה"}'

curl -X POST http://localhost:8080/api/search-name \
  -H "Content-Type: application/json" \
  -d '{"query":"משה","corpus_scope":"torah"}'
```

Set `AUTOGEMATRIA_API_TOKEN` to require `Authorization: Bearer <token>` or `X-API-Key: <token>` on every request.

The intended external-agent flow is:

1. Send the agent to `/for-agents` or `/agent.txt`.
2. Let it read the discovery/instruction surface.
3. Have it call `/api/showcase-name` or `/api/search-name`.

## Report API

A lightweight HTTP server for generating reports, used by the WhatsApp agent (Yoni) and other services:

```bash
python3 serve_report_api.py  # Listens on port 8077
```

Endpoints:

```bash
# Health check
curl http://localhost:8077/health

# Quick text search
curl -X POST http://localhost:8077/search \
  -H "Content-Type: application/json" \
  -d '{"name":"עובדיה יוסף"}'

# Full HTML report with here.now publishing
curl -X POST http://localhost:8077/report \
  -H "Content-Type: application/json" \
  -d '{"name":"משה גינדי","variant":"משה גנדי","label":"Aleppo spelling"}'
```

Reports are cached by name — repeated requests for the same name return the cached link instantly.

## Container Deploy

The repo now includes a `Dockerfile` that packages the code and bundled SQLite corpus into a single service image. That makes it straightforward to deploy on a container host such as Render, Cloud Run, or Fly.io.

Local container smoke test:

```bash
docker build -t autogematria-api .
docker run --rm -p 8080:8080 autogematria-api
```

## Public Agent Entry Point

If you want users to tell their AI system "go to this website and use it", the clean setup is:

1. Run the API on your own server or a container host.
2. Put Cloudflare or another reverse proxy in front of it.
3. Give agents a single public URL such as `https://tanakh.example.com/for-agents`.

That public entry point should be the canonical instruction surface. It explains the workflow and links to:

- `/for-agents` for branded HTML instructions
- `/agent.txt` for plain-text instructions
- `/.well-known/autogematria-agent.json` for machine-readable discovery

Recommended pattern:

```text
https://tanakh.example.com/for-agents
```

Then the agent can discover the API and call:

```text
POST https://tanakh.example.com/api/showcase-name
POST https://tanakh.example.com/api/search-name
```

If you already have a server, the simplest production path is to run the container there and put Cloudflare in front of it. Cloudflare Pages alone is not enough for the live search engine because the app is a Python + SQLite service, not just a static site.

## Autoresearch Loop

The system includes an autonomous experiment loop for optimizing search parameters:

```bash
# Run benchmark on dev split
python -m autogematria.autoresearch.harness --split dev

# Run with custom config
python -m autogematria.autoresearch.harness --config experiments/configs/baseline.json --split dev

# Increase ranking depth per-entry during benchmarking
python -m autogematria.autoresearch.harness --split dev --top-k 200

# Rebuild v2 eval set (tracks/tasks + explicit negatives + generated hard negatives)
python -m autogematria.autoresearch.dataset_rebuild --hard-negatives 40

# Run quick benchmark ablations
python -m autogematria.autoresearch.ablation --split dev
```

**Ground truth (v2)**: dataset tracks are split into `source_backed_positive`, `expected_but_unverified`, `hard_negative`, `trivial_negative`, and `holdout`, with explicit `is_negative` labels and per-entry task tags (`direct_substring`, `hint_substring`, `acrostic`, `els`, `gematria`, `multi_word_full_name`).

**Current baseline scores**: Train composite=0.678, Dev composite=0.639

## Project Structure

```
src/autogematria/
  config.py           # Book registry, paths
  download.py         # Sefaria API → local JSON
  normalize.py        # Hebrew text normalization
  schema.py           # SQLite DDL
  ingest.py           # JSON → SQLite
  gematria_index.py   # Precompute gematria values
  gematria_connections.py # Source-backed gematria relationship graph
  search/
    base.py           # SearchResult, SearchMethod ABC
    els.py            # Equidistant Letter Sequences
    els_proximity.py  # Co-located ELS pairs for multi-word names
    roshei_tevot.py   # First/last letters of consecutive words
    substring.py      # Direct text matching
    unified.py        # Fan-out across all methods
  stats/
    null_models.py    # Null corpus generators
    significance.py   # Empirical p-values, BH correction
  autoresearch/
    ground_truth.py   # Dataset loader, train/dev/holdout
    scorer.py         # Composite scoring metric
    harness.py        # Frozen benchmark runner
    dataset_rebuild.py # Legacy->v2 dataset migration + labeling
    hard_negatives.py  # Reproducible hard-negative generator
    ablation.py        # Quick benchmark ablation runs
    logger.py         # JSONL experiment logging
  scoring/
    calibrated.py     # Deterministic per-result evidence scoring
    verdict.py        # Full-name conservative verdict combiner
  tools/
    tool_functions.py # Typed Python functions for LLM tool-use
    verification.py   # Deterministic per-finding manual verification payloads
    report_builder.py # HTML report generator with highlighted pesukim
    cli_entrypoints.py # CLI surface mirroring the former tool endpoints
    pipeline.py       # End-to-end "find name" report
serve_report_api.py   # Lightweight HTTP API for report generation (port 8077)
```

## Tests

```bash
pytest tests/ -v  # 115 tests
```
