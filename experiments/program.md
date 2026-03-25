# AutoGematria Autoresearch Program

## Goal

Maximize the `composite_score` on the **DEV** split by tuning search parameters and methods.

The composite score is: `0.4 * recall + 0.3 * MRR - 0.3 * FPR`

## What You Can Modify

- `experiments/configs/*.json` — search configuration files
- `src/autogematria/search/` — search method implementations (with care)

## What You CANNOT Modify

- `src/autogematria/autoresearch/harness.py` — the benchmark harness
- `src/autogematria/autoresearch/scorer.py` — the scoring metric
- `src/autogematria/autoresearch/ground_truth.py` — the data loader
- `data/ground_truth/` — the ground truth dataset
- `data/autogematria.db` — the corpus database

## Workflow

```
LOOP FOREVER:
  1. Read the current best score: python -c "from autogematria.autoresearch.logger import best_so_far; print(best_so_far())"
  2. Propose a new configuration or search improvement
  3. Write config to experiments/configs/<name>.json
  4. Run: python -m autogematria.autoresearch.harness --config experiments/configs/<name>.json --split dev
  5. Compare new ScoreCard to current best
  6. If improved: git commit with descriptive message, log the result
  7. If not: revert changes, log the attempt anyway
  8. NEVER STOP — repeat
```

## Config Format

```json
{
  "enable_substring": true,
  "enable_roshei": true,
  "enable_sofei": true,
  "enable_els": true,
  "els_min_skip": 1,
  "els_max_skip": 500,
  "els_use_fast": true,
  "max_results_per_method": 20,
  "book": null
}
```

## Pre-Registered Parameter Ranges

These ranges are LOCKED. Do not search outside them.

| Parameter | Min | Max | Notes |
|-----------|-----|-----|-------|
| els_min_skip | 1 | 100 | Skip 1 = direct consecutive letters |
| els_max_skip | 50 | 10000 | Higher skips are statistically weaker |
| max_results_per_method | 5 | 100 | Trade-off: speed vs completeness |

## Ground Truth

- **Train split**: 20 entries. Use for development and debugging.
- **Dev split**: 9 entries. Use for scoring experiments.
- **Holdout split**: 6 entries. NEVER touch during development.

Positive entries: known traditional findings (ELS, substring, roshei tevot, gematria)
Negative controls: modern Hebrew words that should NOT produce significant findings

## Ideas to Explore

1. Tune ELS max_skip — higher values find more but may increase false positives
2. Adjust max_results_per_method — more results may improve recall
3. Improve ELS scoring — weight by skip distance, verse context
4. Add gematria-based search to the unified search pipeline
5. Experiment with search order and result merging strategies
6. Try restricting search to Torah-only vs full Tanakh
