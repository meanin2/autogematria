# Research Plan: משה גנדי query quality

## Objective
Improve correctness and usefulness of the system response for the target full-name query `משה גנדי` while preserving conservative abstention behavior on hard-negative multi-word names.

## Metric
- **Name**: `moshe_gandi_bench_score` (from `experiments/moshe_gandi/bench.py`)
- **Direction**: maximize
- **Baseline**: 40.00
- **Target**: >= 85

## Target Files
- `src/autogematria/scoring/verdict.py` -- full-name verdict fallback logic
- `src/autogematria/tools/tool_functions.py` -- evidence rows surfaced in query payload
- `src/autogematria/tools/verify_cli.py` -- optional display behavior for token fallback rows
- `src/autogematria/tools/name_variants.py` -- Latin-script transliteration quality for non-Hebrew inputs

## Constraints
- Keep conservative abstention behavior for hard-negative multi-word names.
- Do not claim strong evidence when only weak token-level support exists.
- Keep benchmark deterministic and avoid changing `bench.py` during this campaign.
- Keep existing test suite behavior stable.

## Hypotheses (ranked by expected impact)
1. Multi-word queries with no full-query candidates are incorrectly short-circuited to `no_convincing_evidence`; token-support fallback should recover a weak/moderate verdict when evidence exists.
2. Returning zero `results` for multi-word queries hides valid token-level findings; surfacing explicit token fallback rows should improve usability without changing strict scoring internals.
3. Conservative guardrails (common first-name + weak surname handling) must still suppress overclaims on hard-negative full names.

## Experiment Log
| # | Hypothesis | Change | Score | Delta | Kept? |
|---|-----------|--------|-------|-------|-------|
| 0 | baseline | none | 40.00 | -- | -- |
| 1 | verdict-only fallback | token support fallback when strongest result is missing | 0.00 | -40.00 | no |
| 2 | strict token fallback rows | synthesize rows in tool layer behind direct+quality gates | 90.00 | +50.00 | yes |
| 3 | transliteration quality | add curated `elisa` variants and tests | 90.00 | +0.00 | yes |
| 4 | confidence calibration | add conservative token-fallback confidence discount in verdict aggregation | 100.00 | +10.00 | yes |
| 5 | stronger confidence discount | raise fallback discount from 0.12 to 0.18 | 100.00 | +0.00 | no |
| 6 | lighter confidence discount | lower fallback discount from 0.12 to 0.08 | 90.00 | -10.00 | no |
| 7 | tanakh scope sweep | compare torah vs tanakh on targets + all multi-word hard negatives | 100.00 | +0.00 | yes |
| 8 | latin auto-hebrew resolver | prefer verified alternate when curated-first transliteration has no evidence; add `gandi/gandy` variants | 100.00 | +0.00 | yes |

## Learnings
- Baseline failure mode is structural: token-level support exists for both words, but verdict and surfaced rows remain empty when full-query hits are absent.
- Verdict-only fallback is unsafe: without surfaced candidate rows it overclaims on hard negatives that have incidental token-level ELS support.
- Strict fallback row synthesis in the tool layer solves the target query while preserving conservative abstention for negative controls.
- Transliteration quality matters for perceived correctness: mapping `elisa` to canonical Hebrew forms avoids low-quality resolved queries while keeping evidence standards unchanged.
- A small verdict-layer discount for token-fallback rows calibrates multi-word confidence (`0.865 -> 0.745`) without changing verdict class or hard-negative abstention.
- Stronger discounting (`0.18`) does not improve benchmark quality over `0.12`; lighter discounting (`0.08`) regresses.
- Scope probe across 21 queries shows no behavior drift between Torah-only and full Tanakh for this campaign's target/negative set.
- Latin usability can regress even with a perfect Hebrew benchmark score; keep a resolver guardrail that prefers evidence-backed alternate transliterations when curated-first has zero support.
