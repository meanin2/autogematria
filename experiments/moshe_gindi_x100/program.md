# Research Plan: moshe gindi x100 directional sweep

## Objective
Run a large AutoResearch campaign (100+ experiments) to maximize usable, conservative evidence quality for Moshe Gindi name queries across Hebrew and Latin inputs, while preserving abstention on hard negatives.

## Metric
- **Name**: `moshe_gindi_x100_score` (from `experiments/moshe_gindi_x100/bench.py`)
- **Direction**: maximize
- **Baseline**: 162.00
- **Target**: >= 130

## Target Files
- `src/autogematria/tools/verify_cli.py` -- variant resolver policy controls
- `src/autogematria/tools/name_variants.py` -- transliteration variants for real-world spelling drift
- `experiments/moshe_gindi_x100/bench.py` -- fixed benchmark and strategy evaluator
- `experiments/moshe_gindi_x100/run_sweep.py` -- high-volume experiment generator and runner

## Constraints
- Keep conservative abstention for hard-negative multi-word names.
- Do not weaken deterministic verification requirements.
- Keep benchmark deterministic and fixed during this campaign.
- Evaluate Torah and Tanakh behavior explicitly, do not conflate them.

## Hypotheses (ranked)
1. **Token fallback threshold tuning** can improve Latin/Hebrew usability without opening false positives.
2. **Bible-code style proximity constraints** (same book/chapter/verse) can reduce random ELS overclaims.
3. **Scope escalation policies** (Torah -> Tanakh) can recover true positives for spelling variants while preserving negatives.
4. **Joined full-name ELS gate** is likely too strict for this query family but should be tested at scale.
5. **Variant resolver policies** (`curated_first`, `best_verified`, `weighted`) materially affect end-user outcomes.

## Experiment Tracks
- Track A: fallback threshold sweeps (score, skip, confidence penalty, verification count)
- Track B: Bible-code proximity constraints (same book/chapter/verse gates)
- Track C: transliteration + scope policies (curated vs verified, escalation modes)
- Track D: joined-name ELS gate (chain-style skip constraints)

## Experiment Log
| # | Hypothesis | Change | Score | Delta | Kept? |
|---|-----------|--------|-------|-------|-------|
| 0 | baseline | default strategy | 162.00 | -- | yes |
| 1-96 | threshold sweeps | vary surname score/skip gates, confidence penalty, min verified rows | best 186.00 | +24.00 | yes |
| 97-144 | bible proximity | require same book/chapter/verse token locality | best 24.00 | -138.00 | no |
| 145-180 | resolver + scope + joined ELS | vary transliteration policy, Torah->Tanakh escalation, joined-name ELS gate | best 162.00 | +0.00 | no |

## Learnings
- Ran **181 experiments total** (`1 baseline + 180 sweeps`) via `run_sweep.py`.
- Best strategy came from threshold tuning (`exp 15`): `surname_score_min=0.5`, `surname_skip_max=12`, `confidence_penalty=0.2`.
- Bible-proximity hard gates (same book/chapter/verse) were too strict for this name pattern and collapsed recall.
- Joined full-name ELS gate did not help this target family (`משהגנדי` / `משהגינדי` has no low-skip joined ELS hit).
- Best strategy kept safety intact on benchmark negatives (`negatives_flagged=0`) while improving positive calibration (`+24`).
