# Pre-Registration of Parameter Ranges

Locked before any autoresearch experiments are run.
Changes to these ranges require explicit justification and a new pre-registration.

## Search Method Parameters

### ELS (Equidistant Letter Sequences)
- `min_skip`: [1, 100]
- `max_skip`: [50, 10,000]
- Direction: forward, backward, or both
- Book filter: any single book or entire Tanakh

### Roshei Tevot (First Letters)
- Cross-verse boundary: allowed
- Max verse span: [1, 10] consecutive words

### Sofei Tevot (Last Letters)
- Same constraints as Roshei Tevot

### Substring
- Within-word: always enabled
- Cross-word (spaces removed): configurable

### Unified Search
- `max_results_per_method`: [5, 100]
- All methods can be individually enabled/disabled

## Scoring Weights
- Recall weight: 0.4
- MRR weight: 0.3
- FPR weight: -0.3 (penalizes false positives)

## Significance Testing
- Null model permutations: [100, 10,000]
- Significance alpha: [0.01, 0.10]
- Multiple testing correction: Benjamini-Hochberg (BH)

## Ground Truth Split
- Train: 60% (used freely during development)
- Dev: 25% (used for scoring experiments)
- Holdout: 15% (NEVER touched until final evaluation)
