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
ag-search "משה"          # Search all of Tanakh
ag-search "אברהם" Genesis  # Search within Genesis
```

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
```

## Tests

```bash
pytest tests/ -v
```

## Roadmap

- **Phase 3**: Autoresearch loop — autonomous agent iterating on search strategies with a scoring metric
- **Phase 4**: MCP server for LLM tool-use integration + sefaria-mcp for live commentary
