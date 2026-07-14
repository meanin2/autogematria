# AutoGematria

AutoGematria is a deterministic Hebrew text-research application. It parses Jewish names,
computes classical gematria profiles, searches a prepared Tanakh corpus, and produces the same
structured report through a browser UI, HTTP API, or CLI.

The output is exploratory. Text patterns, ELS results, acrostics, and numerical equivalences are
not proof of personal, historical, statistical, or theological significance. The scorer verifies
mechanical claims and can abstain; interpretation remains with the reader.

## What works

- A full Tanakh corpus represented as 39 API book units (the 24-book Jewish canon with Samuel,
  Kings, Chronicles, and the Twelve represented as separate source units).
- 23,206 verses, 306,869 words, 1,205,822 letters, and gapless absolute positions in SQLite.
- 22 precomputed gematria methods across 40,664 unique word forms (894,608 values).
- Direct substring, ELS, ELS-proximity, Roshei Tevot, and Sofei Tevot searches.
- Reverse gematria lookup, structured name parsing, cross-component comparisons, and a
  source-backed connection library.
- One canonical full-report composer shared by the web API, background jobs, and
  `ag-full-report`.
- An optional experimental Emtzaei Tevot search with an explicit, testable policy.

Emtzaei Tevot uses only the unique interior center of odd-length words containing at least three
letters. One-letter and even-length words are hard sequence breaks. It is opt-in for ordinary
searches, is visibly labeled experimental in reports, and is excluded from conservative verdicts.

## Requirements

- Python 3.11 or newer
- CPU only; no GPU or LLM service is required
- About 194 MB for the prepared SQLite database
- At least 450 MB free while rebuilding, because the old and new databases can coexist briefly

A representative full-corpus search used about 38–40 MB peak RSS on the development machine;
the complete report path used about 60 MB and finished in roughly 5 seconds. Actual memory and
runtime vary with query breadth and configured search limits.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Prepare all runtime data in one resumable command:

```bash
ag-prepare-data
ag-data-check
```

`ag-prepare-data` downloads the configured Sefaria text, validates all expected books and
chapters, builds a temporary SQLite database, computes all gematria values and indexes, validates
the result, and atomically activates it. If corpus JSON already exists, avoid network access with:

```bash
ag-prepare-data --skip-download
```

Stop the API before replacing its corpus. Long-running processes cache compact corpus indexes and
should be restarted after a successful rebuild.

The lower-level `ag-download`, `ag-ingest`, `ag-index`, and `ag-index-report-methods` commands are
kept for development, but `ag-prepare-data` is the supported end-to-end path.

## Run the app

```bash
ag-serve-api --port 8080
```

Open <http://localhost:8080>. The UI supports full name reports, reverse lookup, progress/status,
and copyable Markdown output.

Useful process checks:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

`/health` is a liveness check. `/ready` validates the corpus and writable state directory, and
returns HTTP 503 when the service cannot accept work.

## CLI

```bash
# Conservative unified search (experimental Emtzaei is off)
ag-search "משה"
ag-search "אברהם" Genesis
ag-search "משה" --corpus-scope tanakh

# Canonical comprehensive report
ag-full-report "david ben yishai"
ag-full-report "שרה בת אברהם" --json

# Specialized visual/research wrappers retained for compatibility
ag-name-report "דוד בן ישי" --json
ag-research-name "david ben yishai" --json

# Focused tools
ag-search-name "משה" --json
ag-lookup-gematria "משה" --json
ag-explore-gematria-connections "משה" --json
ag-read-verse Genesis 1 1 --json
ag-inspect-els "תורה" 50 5 --json
ag-corpus-stats --json
ag-verify "דוד בן ישי" --word-breakdown
```

Python callers can opt in to the experimental method explicitly:

```python
from autogematria.search.unified import UnifiedSearch, UnifiedSearchConfig

config = UnifiedSearchConfig(
    els_max_skip=100,
    enable_emtzaei=True,
)
results = UnifiedSearch(config).search("משה")
```

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` or `/ui` | Browser UI |
| GET | `/health` | Process liveness |
| GET | `/ready` | Corpus and writable-state readiness |
| POST | `/api/jobs` | Queue a full report |
| GET | `/api/jobs/{id}` | Read queued/running/completed report status |
| POST | `/api/full-report` | Build a full report synchronously |
| POST | `/api/search-name` | Direct multi-method search |
| POST | `/api/showcase-name` | Bounded research plus curated presentation |
| POST | `/api/reverse-lookup` | Find corpus words by gematria value |
| POST | `/api/estimate` | Estimate an operation's runtime |
| GET | `/api/run-stats` | Aggregated local run timings |
| GET | `/for-agents` | Human-readable agent instructions |
| GET | `/agent.txt` | Plain-text agent instructions |
| GET | `/.well-known/autogematria-agent.json` | Machine-readable manifest |

Example:

```bash
curl -X POST http://localhost:8080/api/search-name \
  -H 'Content-Type: application/json' \
  -d '{"query":"משה","methods":["substring","els"],"max_results":10}'

curl -X POST http://localhost:8080/api/search-name \
  -H 'Content-Type: application/json' \
  -d '{"query":"אב","methods":["emtzaei_tevot"],"max_results":10}'
```

Set `AUTOGEMATRIA_API_TOKEN` to protect every `/api/*` route. Public UI/documentation and health
routes remain accessible. API clients may send either `Authorization: Bearer <token>` or
`X-API-Key: <token>`. The browser UI has an optional token field under About; it stores the token
only in local storage for that origin.

Request bodies are limited to 64 KiB. Queries, method names, scopes, books, and search budgets are
validated at the HTTP boundary.

## Runtime data model

AutoGematria separates immutable corpus data, packaged reference resources, and writable state:

| Data | Default in a checkout | Override |
| --- | --- | --- |
| Corpus JSON + `autogematria.db` | `./data` | `AUTOGEMATRIA_DATA_DIR` |
| Jobs + timing log | `/tmp/autogematria` | `AUTOGEMATRIA_VAR_DIR` |
| Curated connections + evaluation data | installed package resources | none |

Corpus queries use read-only SQLite connections. The API uses a local SQLite job queue and one
worker thread. Running jobs abandoned by a process restart are requeued once by default and then
failed rather than remaining stuck forever.

At startup, every job left in the running state by the previous single worker is recovered
immediately. `AUTOGEMATRIA_JOB_MAX_ATTEMPTS` controls the total claim attempts before failure
(default `2`).

This design intentionally supports one API replica. Do not mount one writable state volume into
multiple replicas; use an external queue before scaling horizontally.

## Container deployment

The live experimental host uses a manual Docker Compose deployment; Git pushes do not deploy it.
Read [docs/production.md](docs/production.md) before changing images, mounts, replicas, or anything
under `/home/ubuntu/server-setup-v2`. The currently running April image and Compose layout are not
drop-in compatible with the image built from current `main`.

The image contains application code and packaged reference resources, not the 194 MB generated
corpus. Prepare a persistent data volume first, then mount it read-only into the API container:

```bash
docker build -t autogematria-api .
docker volume create autogematria-data
docker volume create autogematria-state

# One-time preparation; rerun to rebuild safely.
docker run --rm \
  -v autogematria-data:/data \
  -v autogematria-state:/var/lib/autogematria \
  autogematria-api ag-prepare-data

# Single production replica.
docker run -d --name autogematria \
  --restart unless-stopped \
  -p 8080:8080 \
  -v autogematria-data:/data:ro \
  -v autogematria-state:/var/lib/autogematria \
  -e AUTOGEMATRIA_API_TOKEN='replace-with-a-long-random-token' \
  autogematria-api
```

For a bind mount, make the state directory writable by the image's non-root `autogematria` user.
The corpus mount can and should remain read-only. The image health check calls `/ready`.

## Architecture

```text
Sefaria corpus JSON
        │
        ▼
ag-prepare-data ──► versioned, validated SQLite corpus (read-only at runtime)
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
      compact indexes      gematria lookup    report components
             └──────────────────┼──────────────────┘
                                ▼
                   canonical report service
                   ┌────────────┼────────────┐
                   ▼            ▼            ▼
                  CLI      synchronous API   SQLite job worker
```

Important modules:

- `runtime_data.py` — read-only connections, schema/integrity checks, readiness.
- `prepare_data.py` — safe download/build/validate/activate workflow.
- `search/corpus_index.py` — shared compact letter and word-letter sequences.
- `search/unified.py` — method fan-out and conservative defaults.
- `scoring/calibrated.py` and `scoring/verdict.py` — evidence features and abstention.
- `report_service.py` — canonical full-report composition.
- `tools/api_server.py`, `jobs.py`, and `job_worker.py` — HTTP and asynchronous execution.

## Tests and release checks

```bash
ruff check .
pytest -q
python -m pip wheel --no-deps . --wheel-dir dist
ag-data-check --allow-legacy   # current checkout DB only; rebuilt DBs should omit this flag
```

Tests that require the full corpus skip when no prepared database is present. The committed
GitHub Actions file is a reproducible validation recipe, but this production host has no CI/CD
connection: release checks and deployment are manual. A release must run the unit contracts,
lint, wheel/resource packaging checks, full-corpus tests, performance smoke test, and container
readiness check before the operator changes the live Compose project.
