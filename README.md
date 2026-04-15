# AutoGematria

A Torah name-finding, gematria analysis, and kabbalistic insight engine. Given a Hebrew name (or English — it transliterates automatically), find where it appears in the Torah through traditional methods and discover deep numerical and spiritual connections.

There is a Jewish tradition that every person's name can be found in the Torah. This project builds the tools to systematically discover those connections.

## What's Inside

**Full Tanakh corpus** — 39 books, 23,206 verses, 306,869 words, 1,205,822 letters, all stored in SQLite with gapless absolute letter indices for efficient ELS searching.

**22 gematria methods** — Standard (Mispar Hechrachi), Gadol, Katan, Siduri, Atbash, Albam, and 16 more, precomputed for all 40,664 unique word forms (894,608 total values).

**Reverse gematria lookup** — Given any number, instantly find all Tanakh words with that value across all 6 report methods (Standard, Full Value, Reduced, Ordinal, AtBash, Kolel).

**5 search methods:**
- **Substring** — direct text matching within and across words
- **ELS** — equidistant letter sequences with fast skip-string search (Boyer-Moore)
- **ELS Proximity** — co-located ELS pairs for multi-word names
- **Roshei Tevot** — first letters of consecutive words
- **Sofei Tevot** — last letters of consecutive words

**Name parsing** — Understands complex Jewish name structures: `moshe ben yitzchak and miriam gindi`, `שרה בת אברהם ורחל כהן`. Identifies first name, patronymic, father/mother, and surname.

**Kabbalistic analysis** — Orthodox sources (Sefer Yetzirah, Arizal, Zohar):
- Letter meanings and symbolism
- Milui (letter-filling) with hidden values
- AtBash cipher transformation
- Sefirah association
- Four Worlds (ABYA) breakdown

**Cross-comparison engine** — Finds surprising gematria matches across all combinations of name components and methods. Includes Torah word matching.

**Statistical significance** — empirical p-values against null models with Benjamini-Hochberg FDR correction.

**Web UI** — Full browser interface at `http://localhost:8080/` with name analysis, reverse lookup, progress bar with ETA, and interactive results. No LLM required.

**Run logging** — Every operation is timed and logged to `data/run_log.jsonl`. The ETA estimator uses historical data to predict completion time based on input complexity.

## Hardware Requirements

- **CPU only** — no GPU needed. All computation is pure Python + SQLite.
- **Memory**: ~52 MB peak RSS during a full search. ~16 MB idle.
- **Storage**: ~50 MB for the SQLite database.
- **Python**: 3.11+ required.

## Setup

```bash
pip install -e ".[dev]"
```

## Usage

### Download and build the corpus

```bash
ag-download                   # Fetch Tanakh from Sefaria API (~8 min)
ag-ingest                     # Parse JSON → SQLite
ag-index                      # Precompute all 22 gematria methods
ag-index-report-methods       # Add optimized reverse-lookup indexes
```

### Web UI

Start the server and open `http://localhost:8080` in your browser:

```bash
ag-serve-api --port 8080
```

The web UI provides:
- **Name Analysis** — Enter any name (Hebrew or English) for a full report
- **Reverse Lookup** — Search any number to find matching Torah words
- **About** — Corpus stats and methodology

### CLI tools

```bash
# Search for a name in Torah
ag-search "משה"
ag-search "אברהם" Genesis
ag-search "משה" --corpus-scope tanakh

# Comprehensive name analysis report
ag-full-report "moshe ben yitzchak gindi"
ag-full-report "שרה בת אברהם" --publish --json

# Visual Torah name report with highlighted pesukim
ag-name-report "משה גינדי" --publish --json

# Research-grade multi-method search
ag-research-name "moshe gindi" --json

# Individual tools
ag-search-name "משה" --json
ag-lookup-gematria "משה" --json
ag-explore-gematria-connections "משה" --json
ag-read-verse Genesis 1 1 --json
ag-inspect-els "תורה" 50 5 --json
ag-corpus-stats --json
ag-verify "משה גינדי" --word-breakdown
```

### Python API

```python
from autogematria.search.unified import UnifiedSearch, UnifiedSearchConfig

cfg = UnifiedSearchConfig(els_max_skip=500)
searcher = UnifiedSearch(cfg)
results = searcher.search("משה")

for r in results[:10]:
    print(f"[{r.method}] {r.location_start.book} {r.location_start.chapter}:{r.location_start.verse}")
```

```python
# Full name report
from autogematria.research.name_report import build_name_report
report = build_name_report("moshe ben yitzchak gindi")

# Reverse gematria lookup
from autogematria.search.gematria_reverse import reverse_lookup
words = reverse_lookup(345, method="MISPAR_HECHRACHI")

# Gematria relationship graph
from autogematria.search.gematria_reverse import build_name_gematria_graph
graph = build_name_gematria_graph([("משה", "first_name"), ("גינדי", "surname")])

# Kabbalistic analysis
from autogematria.research.kabbalistic import full_kabbalistic_analysis
analysis = full_kabbalistic_analysis("משה")
```

## HTTP API

```bash
ag-serve-api --port 8080
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI |
| GET | `/health` | Health check |
| POST | `/api/full-report` | Comprehensive name analysis with graph |
| POST | `/api/reverse-lookup` | Find words by gematria value |
| POST | `/api/estimate` | ETA estimate for an operation |
| GET | `/api/run-stats` | Aggregated run history stats |
| POST | `/api/showcase-name` | Curated presentable result |
| POST | `/api/search-name` | Direct multi-method search |
| GET | `/for-agents` | Agent instruction page |
| GET | `/agent.txt` | Plain-text agent instructions |
| GET | `/.well-known/autogematria-agent.json` | Machine-readable manifest |

### Examples

```bash
# Full report
curl -X POST http://localhost:8080/api/full-report \
  -H "Content-Type: application/json" \
  -d '{"query":"moshe ben yitzchak gindi"}'

# Reverse lookup
curl -X POST http://localhost:8080/api/reverse-lookup \
  -H "Content-Type: application/json" \
  -d '{"value":345,"method":"MISPAR_HECHRACHI"}'
```

Set `AUTOGEMATRIA_API_TOKEN` to require `Authorization: Bearer <token>` on requests.

## Architecture

- **Data source**: Sefaria API, "Tanach with Text Only" (Public Domain)
- **Storage**: SQLite (single file, ~50MB)
- **Gematria engine**: [hebrew](https://pypi.org/project/hebrew/) PyPI package
- **Search**: Pure Python, in-memory letter arrays for ELS
- **Stats**: scipy for BH/FDR correction, custom null models
- **Name parsing**: Regex-based parser for Hebrew/English/mixed input
- **Kabbalistic data**: Letter meanings, milui spellings, sefirot from traditional sources
- **Connection library**: Curated source-backed equivalence records in `data/gematria/connections.json`

## Project Structure

```
src/autogematria/
  config.py                   # Book registry, paths
  normalize.py                # Hebrew text normalization
  schema.py                   # SQLite DDL
  download.py                 # Sefaria API → local JSON
  ingest.py                   # JSON → SQLite
  gematria_index.py           # Precompute all 22 gematria methods
  gematria_report_index.py    # Optimized reverse-lookup indexes
  gematria_connections.py     # Source-backed relationship graph
  search/
    unified.py                # Fan-out across all methods
    substring.py              # Direct text matching
    els.py                    # Equidistant Letter Sequences
    els_proximity.py          # Co-located ELS pairs
    roshei_tevot.py           # First/last letter acrostics
    gematria.py               # Corpus-wide gematria search
    gematria_reverse.py       # Reverse lookup: value → words, graph builder
  research/
    name_report.py            # Top-level name report orchestrator
    kabbalistic.py            # Letter meanings, milui, AtBash, four worlds
    cross_compare.py          # Cross-comparison engine
    html_report.py            # Full HTML report renderer
    html_export.py            # Showcase HTML export with Sefaria translations
    runner.py                 # Research task runner
    tasks.py                  # Task queue builder
    presentation.py           # Finding curation (headline/supporting/interesting)
  scoring/
    calibrated.py             # Deterministic per-result evidence scoring
    verdict.py                # Conservative verdict combiner
  tools/
    api_server.py             # HTTP API + web UI server
    web_ui.py                 # Browser UI (single-page app)
    name_parser.py            # Jewish name structure parser
    name_variants.py          # Hebrew variant generation & transliteration
    full_report_cli.py        # ag-full-report CLI
    report_builder.py         # ag-name-report CLI
    research_cli.py           # ag-research-name CLI
    cli_entrypoints.py        # Individual tool CLIs
    tool_functions.py         # Typed Python functions
    verification.py           # Per-finding verification payloads
    agent_site.py             # Agent instruction surfaces
  stats/
    significance.py           # Empirical p-values, BH correction
    null_models.py            # Null corpus generators
  autoresearch/
    harness.py                # Frozen benchmark runner
    scorer.py                 # Composite scoring metric
    ground_truth.py           # Dataset loader
  run_logger.py               # Run timing, logging, ETA estimation
tests/                        # 136 tests
```

## Tests

```bash
pytest tests/ -v
```

## Container Deploy

```bash
docker build -t autogematria-api .
docker run --rm -p 8080:8080 autogematria-api
```
