# Review rerun 1c: blind strict-clear verdicts and control blind test on fresh text

> No feature label or verdict here has been verified by a human.

Design and rules were committed in `config.yaml` (`stage5_v2`) before the run.

## Blind verdicts

250 items (real and control mixed, anonymised), each judged by 2 fresh judges who were not told there were two sources; 0 invalid. Rule: a judge calls a feature clear if top_fit >= 16 of 20 AND random_fit >= 8 of 10; the feature is strict-clear only if BOTH judges call it clear

| set | n | blind strict-clear (both judges) | clear by judge 1 / judge 2 | mean top fit (of 20) | mean random fit (of 10) | old non-blind clear | of those, confirmed blind |
|---|---|---|---|---|---|---|---|
| real | 200 | **3 (1.5%)** | 4 / 3 | 17.8 | 0.8 | 37 | 2 |
| control | 50 | **0 (0.0%)** | 0 / 0 | 17.5 | 0.5 | 1 | 0 |

One-sided Fisher exact p = 0.5105; claim 'real more often strict-clear than control' supported: **False**. Judges agreed on the clear/not-clear call for 100% of items; their random-fit counts correlate at 0.94 (mean absolute difference 0.1 of 10).

## Blind label test on fresh text (control never trained on it)

| set | n | mean accuracy | 5/5 | 3/5 or fewer |
|---|---|---|---|---|
| real, first 50 | 50 | 0.816 | 17 | 12 |
| control | 50 | 0.532 | 2 | 44 |

Difference 0.284, one-sided permutation p = 0.0000; supported: **True**. Control vs chance (0.5): p = 0.0745. 0 invalid answers.
Original test for comparison: real first 50 = 0.800, control on its own training text = 0.564.
Per guesser (real / control): puzzles_00: 0.80 / 0.57; puzzles_01: 0.82 / 0.51; puzzles_02: 0.88 / 0.52; puzzles_03: 0.78 / 0.53

Known limits (stated before the run): labels themselves were written non-blind; the control SAE is denser (L0 56 vs 27) and saw less data; labeller, judges and guessers may share biases.
