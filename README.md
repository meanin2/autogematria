# AutoGematria

A Torah name-finding and gematria autoresearch system. Given a Hebrew name, find where it appears in the Torah through traditional methods — direct text, equidistant letter sequences (ELS), roshei/sofei tevot, and gematria equivalences.

There is a Jewish tradition that every person's name can be found in the Torah. This project builds the tools to systematically discover those connections.

## What's Inside

**Full Tanakh corpus** — 39 books, 23,206 verses, 306,869 words, 1,205,822 letters, all stored in SQLite with gapless absolute letter indices for efficient ELS searching.

**22 gematria methods** — Standard (Mispar Hechrachi), Gadol, Katan, Siduri, Atbash, Albam, and 16 more, precomputed for all 40,664 unique word forms (894,608 total values).

**4 search methods:**
- **Substring** — direct text matching within and across words
- **ELS** — equidistant letter sequences with fast skip-string search (Boyer-Moore)
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

h = Hebrew("אלהים")
print(h.gematria())                              # 86 (standard)
print(h.gematria(GematriaTypes.MISPAR_GADOL))     # 646
```

## Architecture

- **Data source**: Sefaria API, "Tanach with Text Only" (Public Domain)
- **Data layer**: SQLite (single file, ~50MB)
- **Gematria engine**: [hebrew](https://pypi.org/project/hebrew/) PyPI package (23 methods)
- **Search**: Pure Python, in-memory letter arrays for ELS
- **Stats**: scipy for BH/FDR correction, custom null models

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

## MCP Server

Expose all tools for LLM agents via MCP:

```bash
pip install fastmcp
python -m autogematria.tools.mcp_server
# Server runs on http://127.0.0.1:8087/sse
```

**5 MCP tools:**
- `search_name` — find a name using all methods
- `lookup_gematria` — compute gematria + find equivalent words
- `read_verse` — get a verse with word-by-word gematria
- `inspect_els` — letter-by-letter ELS breakdown
- `get_corpus_stats` — corpus summary

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
  search/
    base.py           # SearchResult, SearchMethod ABC
    els.py            # Equidistant Letter Sequences
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
    mcp_server.py     # FastMCP server (port 8087)
    pipeline.py       # End-to-end "find name" report
```

## Tests

```bash
pytest tests/ -v  # 51 tests
```
