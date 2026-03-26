# AutoResearch Program (Current Campaign)

## Objective

Improve conservative reliability on the **dev** benchmark while preserving recall.

Scalar metric: `composite = 0.4 * recall + 0.3 * MRR - 0.3 * FPR`

## Benchmark Contract

- Fixed benchmark: `python -m autogematria.autoresearch.harness --split dev`
- Baseline for this campaign: `composite=0.6388`, `recall=1.0`, `mrr=0.8485`, `fpr=0.0526`
- Target: reduce false positives to `0.0` without dropping recall

## Constraints

- Keep default corpus scope conservative (`torah`)
- Keep deterministic ranking path unchanged by display diversification
- Do not optimize for always returning a finding

## Hypotheses (ranked)

1. Long ELS-only strings with no direct exact support are mostly random-like and should be gated.
2. Config-only skip-range tuning will not fully remove hard-negative leakage.
3. Explainability improves if gematria results include source-backed connection graphs.

## Experiment Log

| # | Hypothesis | Change | Score | Delta | Kept? |
|---|-----------|--------|-------|-------|-------|
| 0 | baseline | pre-gate conservative scorer | 0.6388 | -- | -- |
| 1 | config-only sweep | els_min/els_max tuning | 0.6388 | +0.0000 | no |
| 2 | long-query ELS gate | require same-verse + low-skip for long no-direct queries | 0.6545 | +0.0157 | yes |

## What Worked

- The long-query ELS gate removed the remaining dev hard-negative false positive.
- Recall stayed at `1.0`, so the gain came from cleaner abstention behavior.

## Next Hypotheses

1. Add method-specific task balancing so `multi_word_full_name` has positive anchor entries.
2. Introduce a compactness floor for ELS ranking when query length >= 5.
3. Add constrained within-verse null checks for the top-k ELS candidates during scoring.
