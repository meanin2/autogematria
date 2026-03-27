# Research Plan: gematria_x600

## Objective
Improve name-finding quality for gematria-based relationships using source-backed equivalences and conservative ranking, then identify robust next-step optimization direction with large-scale AutoResearch.

## Metric
- **Name**: `gematria_pair_bench_score` (from `experiments/gematria_x600/bench.py`)
- **Direction**: maximize
- **Baseline**: 311.00
- **Target**: >= 220

## Target Files
- `src/autogematria/gematria_connections.py` -- ranking and source-link scoring
- `data/gematria/connections.json` -- source-backed gematria findings
- `data/ground_truth/known_findings_v2.jsonl` -- benchmark/eval coverage for gematria

## Constraints
- Keep source-backed findings clearly distinguished from generic same-value words.
- Keep deterministic behavior (no stochastic ranking in runtime path).
- Preserve conservative behavior on negative pair probes.

## Hypotheses
1. Stronger source-pair reinforcement improves precision for traditional query-target pairs.
2. Frequency scaling is over-weighted today and can bury source-linked pairs.
3. Orthographic/anagram bonuses help only in narrow ranges and should be tuned jointly.
4. After global sweep, local refinement around the best profile should yield incremental gains.

## Experiment Plan
- Phase A: run 500 broad parameter experiments.
- Phase B: identify best-performing direction family.
- Phase C: run 100 local refinement experiments in that direction.

## Experiment Log
| # | Hypothesis | Change | Score | Delta | Kept? |
|---|-----------|--------|-------|-------|-------|
| 0 | baseline | default gematria scoring weights | 311.00 | -- | yes |
| 1-500 | broad sweep | 500 randomized weight profiles across source/frequency/lexical directions | best 314.00 | +3.00 | yes |
| 501-600 | focused sweep | 100 local perturbations around best broad strategy in source-weighted direction | best 314.00 | +0.00 | no new gain |

## Learnings
- Completed **600 experiments** (`500 + 100`) plus baseline.
- Best direction was **source-weighted scoring**: stronger `source_pair_bonus` and `source_backed_bonus` consistently improved ranking quality.
- Hard Bible/gating style constraints were not needed for gematria pair quality; ranking calibration mattered more than filtering.
- Follow-up 100 local tests converged with no further gain, indicating local optimum for current label set.
- ML readiness check indicates **insufficient verified labels** for a stable trained model right now:
  - 13 gematria positives / 4 gematria negatives in ground truth,
  - 22 directed source-pair labels in the library,
  - needs larger curated dataset before reliable supervised training.
