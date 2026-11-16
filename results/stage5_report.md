# Stage 5 report: interpreting features (SAE λ=1)

> **All feature labels in this project are AI-written (by Claude) and have NOT been verified by a human.**
> The user chose not to hand-label. Labels were written from the top-20 and 5 random firing snippets plus
> promoted output tokens, and then scored with a blind test (below), but nobody checked them by hand.

## What was labelled
- 200 features chosen at random (seed 1234) from the 2048 in the λ=1 SAE (all 2048 fire on training data).
- Control: SAE with the same settings trained on a **shuffled-weights** copy of the model (Bricken et al. 2023);
  357783 training tokens (fp16), final VE 0.899, L0 56.2
  (real SAE: VE 0.890, L0 26.7). The first 50 of 200 randomly chosen control features were labelled the same way.

## Clear vs unclear (labeller's own verdict)
A feature is **clear** only if one concept explains the top examples **and** the 5 uniformly random firings also fit ("yes").
- Real SAE: **37/200 clear (18.5%)**. If random firings are ignored, 181/200 look clear from top examples alone.
- Control: **1/50 clear (2.0%)**; 41/50 look clear from top examples alone.
- Lesson: top examples flatter both SAEs, including the one trained on a meaningless model. Random firings separate them.

## Blind test of the labels
For each feature, a fresh model instance that never saw the evidence got only the label and 10 snippets from text not used
for labelling (real: held-out split; control: rows not shown), each with one marked token: 5 where the feature fires
(sampled uniformly among all firings, so many are weak) and 5 where it does not. It had to pick the 5 firing ones.
Puzzles from both SAEs were anonymised and shuffled together. Chance = 0.50.

| Set | n | mean accuracy | 5/5 correct | ≤ 3/5 correct | p vs chance |
|---|---|---|---|---|---|
| Real SAE, all | 200 | 0.779 | 55 | 61 | 0.00000 |
| Real SAE, first 50 (size-matched) | 50 | 0.800 | 15 | 10 | 0.00000 |
| Real, labelled clear | 37 | 0.886 | 20 | 4 | |
| Real, not clear | 163 | 0.755 | 35 | 57 | |
| Real, labeller said "unclear" | 19 | 0.779 | | | |
| Shuffled-weights control | 50 | 0.564 | 2 | 40 | 0.00285 |

p = probability of a mean at least this high under random guessing (100,000 simulations; 0.00000 means none reached it).
Per feature, only 5/5 is significant at p<0.05 (p=0.004); 4/5 has p=0.10. Per-feature results: `results/stage5_blind_per_feature.csv`.

Detection of firing snippets by firing strength (terciles): real weak/middle/strong =
0.64 / 0.75 / 0.94;
control = 0.52 / 0.54 / 0.63.
Labels describe strong firings well; weak firings are often off-label.

## Examples (not only good ones)
Clear and perfectly predicted:
- #0 (feature 1905): '.' ending a story's closing/moral sentence (e.g. 'happily ever after.') — blind accuracy 1.0
- #1 (feature 592): ',' before the last item of a list ('a, b, c[,] and d') — blind accuracy 1.0
- #4 (feature 1806): '.' ending a sentence about having an idea/plan — blind accuracy 1.0
- #7 (feature 294): ',' after 'X was sad' (predicts 'but') — blind accuracy 1.0
- #8 (feature 1541): ' was' after 'He' in a character introduction ('named Tim. He was') — blind accuracy 1.0

Labelled clear but blind accuracy ≤ 0.6:
- #49 (feature 1137): ' rain' in 'started to rain' — blind accuracy 0.6
- #62 (feature 512): Sentence-initial 'She' for a parent/adult taking action — blind accuracy 0.6
- #163 (feature 88): ' day' in story-initial 'One day' — blind accuracy 0.6
- #168 (feature 1214): ' one' in 'But then one (of / day)' — blind accuracy 0.6

Labeller said unclear:
- #38 (feature 426): Dense, mixed tokens near the end of a story (7.4% of tokens) — blind accuracy 0.8
- #45 (feature 397): Sentence-initial 'She', often after 'smiled.' (weak theme) — blind accuracy 0.8
- #47 (feature 264): Adjective after 'saw a' for a newly noticed thing (mixed) — blind accuracy 1.0
- #52 (feature 1938): Dense (5%): 'it'/adjectives when describing or touching an animal; mixed — blind accuracy 0.8
- #63 (feature 1491): Dense (5.6%): opening quotes / dialogue boundaries; mixed — blind accuracy 0.6

Lowest blind accuracy:
- #82 (feature 1693): ' time' in 'it was time to go home' — blind accuracy 0.2
- #12 (feature 137): Mojibake byte of an opening curly quote after 'said,' (dataset encoding artefact) — blind accuracy 0.4
- #19 (feature 336): ' grandma' after 'going to visit (their)' — blind accuracy 0.4
- #21 (feature 2038): ' part' in 'be part of the family/band' — blind accuracy 0.4
- #35 (feature 978): ' sunshine' in 'in the sunshine' — blind accuracy 0.4
- #46 (feature 1408): 'John' as first token of a story — blind accuracy 0.4

## Caveats
- One AI wrote the labels and another instance of the same model family guessed; shared biases could inflate scores.
- The labeller's "unclear" verdicts did not predict blind accuracy (see table), so those verdicts are weak evidence.
- Control used 400k tokens (fp16) vs 2.5M (fp32), and its eval is a random 10% of the same stories, so it is not a perfectly matched comparison.
- Non-firing snippets are random tokens, an easy contrast; harder distractors (same token, feature off) would lower scores.
