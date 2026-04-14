# AutoGematria — Agent Instructions

Torah name-finding and gematria analysis engine. All computation is deterministic — no LLM calls are needed for the core pipeline.

## Quick Start

```bash
export PYTHONPATH="/home/moshe/autogematria/src:/home/moshe/.local/lib/python3.12/site-packages"
cd /home/moshe/autogematria
```

## Running Tests

```bash
python3 -m pytest tests/ -v --tb=short
```

The venv at `.venv/` has `python3` and `pytest` but **no pip**. Dependencies (`hebrew`, `httpx`, `networkx`, `tqdm`, `scipy`) are installed in `~/.local/lib/python3.12/site-packages`. Always include that path in `PYTHONPATH`.

## Key Architecture Decisions

- **SQLite single-file DB** at `data/autogematria.db`. All 22 gematria methods are precomputed for all 40,664 unique word forms.
- **No LLM dependency** for name analysis, gematria, or Torah search. The web UI and all CLIs are fully deterministic.
- **Name parsing** handles Hebrew, English, and mixed input. The parser in `tools/name_parser.py` identifies first name, patronymic (ben/bat), father/mother names, and surname.
- **Transliteration** uses an expanded dictionary of ~100+ common Jewish names in `tools/name_variants.py`.
- **Kabbalistic analysis** in `research/kabbalistic.py` covers letter meanings, milui, AtBash, sefirot, and four worlds from traditional Orthodox sources.

## Important Modules

| Module | Purpose |
|--------|---------|
| `search/gematria_reverse.py` | Reverse lookup (value→words), graph builder |
| `research/name_report.py` | Top-level name report orchestrator |
| `research/cross_compare.py` | Cross-comparison engine for name components |
| `research/kabbalistic.py` | Letter analysis, milui, AtBash, four worlds |
| `tools/api_server.py` | HTTP API + web UI (port 8080) |
| `tools/web_ui.py` | Browser SPA served at `/` |
| `tools/name_parser.py` | Name structure parser |
| `tools/full_report_cli.py` | `ag-full-report` CLI |

## API Endpoints

The server (`ag-serve-api`) exposes:

- `GET /` — Web UI
- `POST /api/full-report` — `{"query": "moshe ben yitzchak"}` → full analysis + graph
- `POST /api/reverse-lookup` — `{"value": 345, "method": "MISPAR_HECHRACHI"}` → matching words
- `POST /api/showcase-name` — curated presentable result
- `POST /api/search-name` — raw multi-method search

## Coding Conventions

- Hebrew text is normalized via `normalize.py` (strip nikkud/taamim, handle final letters).
- Gematria methods are referenced by `GematriaTypes` enum names (e.g., `MISPAR_HECHRACHI`).
- The 6 report methods used in name analysis: `MISPAR_HECHRACHI`, `MISPAR_GADOL`, `MISPAR_KATAN`, `MISPAR_SIDURI`, `ATBASH`, `MISPAR_KOLEL`.
- Test files mirror source structure in `tests/`.
- Line length limit: 100 (ruff).

## Common Tasks

**Add a new gematria method to reports:** Update `REPORT_METHODS` in `search/gematria_reverse.py` and `METHODS_FOR_REPORT` in `research/cross_compare.py`.

**Add a new name transliteration:** Add to `_COMMON_VARIANTS` in `tools/name_variants.py`.

**Add a new kabbalistic concept:** Extend `research/kabbalistic.py` and wire into `research/name_report.py`.

**Expand gematria connections library:** Edit `data/gematria/connections.json` (source-backed pairs with Talmudic/Kabbalistic references).
