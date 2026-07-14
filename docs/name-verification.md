# Name and Gematria Verification

This document records the name-focused manual verification performed on **2026-07-14 UTC**.
It is both a regression checklist and a statement of the intended report semantics. Re-run the
checks after changing parsing, transliteration, gematria, research variants, evidence provenance,
or presentation tiers.

## Contract to preserve

- Standard gematria uses `א=1` through `ת=400`; final letters have their ordinary values in the
  standard method (`ך=20`, `ם=40`, `ן=50`, `ף=80`, `ץ=90`).
- `full_hebrew_name` and `full_name_gematria` contain meaningful name components only. Structural
  words such as `בן`, `בת`, and a conjunction are excluded from the arithmetic total.
- `search_hebrew_name` restores those relationship words for corpus search. For example,
  `david ben yishai` calculates `דוד ישי = 334` but searches `דוד בן ישי`.
- Mispar Kolel in this application is the standard total plus one for the word as a whole. It is
  not the standard total plus the number of letters.
- Hebrew points and maqaf are normalized before structural parsing while `raw_input` preserves
  exactly what the caller supplied.
- Extra given names stay in input order before the surname.
- A component hit must not be relabeled as a full-name hit. For a multi-token query, only verified
  evidence attached to a full-name variant can receive the `Direct textual hit` verdict; an exact
  component occurrence is supporting evidence. Common biblical namesakes are separated.
- A generated initials seed is an initials variant and may schedule only Roshei Tevot work. It is
  not a literal full-name substring, ELS, or gematria query.
- The bounded research runner schedules token variants itself and therefore calls the lower search
  layer with automatic token fallback disabled. This prevents duplicate work and preserves
  finding provenance.

## Independently checked arithmetic

The manual oracle was a separate explicit Hebrew letter-value table, not a call back into the
application. These standard totals matched the application:

| Name | Expected |
| --- | ---: |
| `משה` | 345 |
| `דוד` | 14 |
| `אברהם` | 248 |
| `שרה` | 505 |
| `רחל` | 238 |
| `יצחק` | 208 |
| `יעקב` | 182 |
| `מרים` | 290 |
| `שלמה` | 375 |
| `אסתר` | 661 |
| `מלך` | 90 |
| `נח` | 58 |

Six-method profiles were also checked as known answers:

| Name | Standard | Gadol | Katan | Siduri | Atbash | Kolel |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `משה` | 345 | 345 | 12 | 39 | 102 | 346 |
| `אברהם` | 248 | 808 | 14 | 52 | 803 | 249 |
| `מלך` | 90 | 570 | 9 | 48 | 60 | 91 |

The durable known-answer cases live in `tests/test_manual_name_matrix.py`.

## Full-report matrix

Every reported standard total below matched the independent letter sum. Timings are cold local
processes with a 20-second manual ceiling after the performance fixes; they are observations, not
hard API guarantees.

| Input | Arithmetic form | Search form | Total | Verdict | Seconds |
| --- | --- | --- | ---: | --- | ---: |
| `david ben yishai` | `דוד ישי` | `דוד בן ישי` | 334 | Direct textual hit | 9.63 |
| `D'vorah bat Yaakov` | `דבורה יעקב` | `דבורה בת יעקב` | 399 | Indirect but solid hit | 11.80 |
| `Moshe Chaim Cohen` | `משה חיים כהן` | `משה חיים כהן` | 488 | Indirect but solid hit | 10.52 |
| `שרה בת אברהם ורבקה` | `שרה אברהם רבקה` | `שרה בת אברהם ורבקה` | 1060 | Indirect but solid hit | 14.78 |

The complete-name direct hit for `דוד בן ישי` was verified at II Samuel 23:1. The other three
multi-part inputs correctly had no direct headline; individual common-name or common-word
occurrences were no longer promoted as if the whole name appeared.

Additional parser/report checks included Hebrew and Latin single names, pointed Hebrew,
maqaf-separated patronymics, `ben`/`bat`, father-and-mother forms, surnames, extra given names,
mixed-script input, and final-letter words. No arithmetic mismatch remained.

## Problems found and fixed

- `yishai` and `D'vorah` previously produced nonstandard spellings (`ישאי`, `דוראה`). Curated
  variants now produce `ישי` and `דבורה`, and every Latin name recognized by the parser's gender
  heuristic has a curated transliteration.
- Repeated variant generation mutated a global curated list. Each call now works on a copy.
- Extra names were displayed and searched after the surname. Input order is now preserved.
- Pointed Hebrew joined with maqaf was not structurally parsed. Structural normalization now runs
  before parsing while preserving the raw input field.
- The research runner used a high-level token fallback inside every full-name task, then tagged the
  returned component row with the full-name variant. This created false direct headlines such as
  presenting `ישי` alone as a match for `דוד ישי`. Research tasks now search only their declared
  variant; explicit token tasks retain honest provenance.
- Patronymic connectors were removed for arithmetic and accidentally removed for textual search as
  well. Reports now expose a separate relationship-aware search form.
- Initials were tagged as complete names and searched by every method. They are now restricted to
  Roshei Tevot.
- Gematria span result loading repeatedly joined the entire 894,608-row value table. It now resolves
  matched words by indexed absolute position and attaches values from the cached method array.
- Long unsupported ELS queries performed SQL location lookups for skips that the existing policy
  would always reject. The location-independent skip gate now runs first. The slowest representative
  family report fell from 23.6 seconds to 14.8 seconds without relaxing the acceptance policy.
- UI and report copy incorrectly described Kolel as standard plus letter count. It now matches the
  implemented `standard + 1` method.

## End-to-end checks

The source checkout passed:

```text
ruff check .                         passed
pytest -q                            287 passed in 76.42s
ag-data-check --allow-legacy         integrity=ok, methods=22
git diff --check                     passed
```

A disposable image tagged `autogematria:codex-name-smoke` was built from the working tree and run
off-route on loopback with `/home/ubuntu/gematria/data` mounted read-only and state on a temporary
filesystem. It passed:

- `/health` and `/ready`;
- browser UI HTML loading;
- reverse lookup `345`, including `משה`;
- synchronous `david ben yishai` full report (`334`, complete-phrase headline at II Samuel 23:1);
- queued `משה` report from `queued` through `done` (`345`).

The disposable container was then removed. The candidate tag is not a deployment.

## Production status at verification time

Production was deliberately not restarted or changed. The four live containers continued running
the April `autogematria:latest` image. A small public smoke returned:

- `/health`: HTTP 200 with `{"status":"ok"}`;
- `/ready`: HTTP 404, expected for the old release;
- substring-only `משה` search: three results, first result `משה`, deterministically verified.

Current source fixes will not reach that service merely by committing or pushing. See
`docs/production.md` for the observed topology, incompatibilities, and manual release runbook.

## Re-run checklist

```bash
source .venv/bin/activate
ruff check .
pytest -q
ag-data-check --allow-legacy
```

Then repeat at least the four multi-part cold reports above, independently sum their arithmetic
forms, build a commit-specific disposable image (never overwrite `autogematria:latest`), and test
health, readiness, reverse lookup, synchronous report, and one queued report off-route. Production
deployment remains a separate, explicitly authorized operation.
