# AutoGematria — Agent Instructions

Torah name-finding and gematria analysis engine. All computation is deterministic — no LLM calls are needed for the core pipeline.

## Production Context

This checkout is not the running service. Production is a manual Docker Compose deployment on
this machine; commits and pushes do not deploy it. Read `docs/production.md` before any image,
container, corpus, state-volume, Caddy, or `/home/ubuntu/server-setup-v2` work. Never restart or
change the live deployment without explicit production authorization and a rollback image/backup.

## Quick Start

```bash
cd /home/ubuntu/gematria
source .venv/bin/activate
```

## Running Tests

```bash
source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short
```

The project venv at `/home/ubuntu/gematria/.venv/` is an editable install of the package (`pip install -e ".[dev]"`) with all dependencies (`hebrew`, `httpx`, `networkx`, `tqdm`, `pytest`) already resolved. Activate it and everything imports without extra `PYTHONPATH` tweaks.

## Key Architecture Decisions

- **Generated corpus data is external runtime data.** In a checkout it defaults to
  `data/autogematria.db`; deployments set `AUTOGEMATRIA_DATA_DIR` and mount it read-only.
- **Writable state is separate** under `AUTOGEMATRIA_VAR_DIR` (default
  `/tmp/autogematria`) for the job queue and timing log.
- **Packaged reference resources** live under `src/autogematria/resources/`, not `data/`.
- **Use `ag-prepare-data`** for atomic download/ingest/index/validate/activation and
  `ag-data-check` for release validation.
- **Corpus connections are read-only.** All 22 gematria methods are precomputed for all 40,664
  unique word forms.
- **One API replica** owns one worker thread and a local SQLite job queue. Do not share its
  writable state volume between replicas.
- **No LLM dependency** for name analysis, gematria, or Torah search. The web UI and all CLIs are fully deterministic.
- **Emtzaei Tevot is experimental and explicit-only** in unified search. Its odd-word unique-center
  findings stay visible but are excluded from conservative verdicts.
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
| `runtime_data.py` | Read-only DB connections, validation, readiness |
| `prepare_data.py` | Safe end-to-end corpus build |
| `report_service.py` | Canonical full-report composition |
| `tools/api_server.py` | HTTP API + web UI (port 8080) |
| `tools/web_ui.py` | Browser SPA served at `/` |
| `tools/name_parser.py` | Name structure parser |
| `tools/full_report_cli.py` | `ag-full-report` CLI |

## API Endpoints

The server (`ag-serve-api`) exposes:

- `GET /` — Web UI
- `GET /health` — process liveness
- `GET /ready` — corpus/state readiness
- `POST /api/jobs` and `GET /api/jobs/{id}` — asynchronous full reports
- `POST /api/full-report` — `{"query": "david ben yishai"}` → full analysis + graph
- `POST /api/reverse-lookup` — `{"value": 345, "method": "MISPAR_HECHRACHI"}` → matching words
- `POST /api/estimate` — `{"query": "...", "operation": "full_report"}` → ETA in seconds
- `GET /api/run-stats` — aggregated run history
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

**Expand gematria connections library:** Edit
`src/autogematria/resources/gematria/connections.json` (source-backed pairs with
Talmudic/Kabbalistic references).

**Add gender recognition for names:** Update `_FEMALE_NAMES_HEBREW` / `_MALE_NAMES_HEBREW` in `tools/name_parser.py`.
