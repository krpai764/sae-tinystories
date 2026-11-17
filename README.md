# Sparse autoencoders on TinyStories-8M

Sparse autoencoders on the activations of a small story-writing model (roneneldan/TinyStories-8M): find features, test whether their labels hold up, steer the model with them, trace one behaviour.
A careful small-scale application of published methods ([Prior work](#prior-work)), **not new research**: one model, one layer, one dictionary size, one seed.

> Feature labels and blind evaluations were generated with a language model and have not been human-verified.

> **This README was rewritten after a sceptical review, and several earlier claims were withdrawn or weakened.** The [Review and corrections](REPORT.md#9-review-and-corrections) section of REPORT.md lists what the review found and what changed.

## Main findings, and what limits each one

**1. The autoencoder reconstructs the activations closely, but it is lossy and changes behaviour.**
The chosen autoencoder (λ=1, 2048 features, residual stream after block 3) explains 0.890 of the variance of held-out activations
with about 26.7 active features per token. No feature is dead, but 40% of features fire on more than 1% of tokens, so many are not sparse in the usual sense.
Splicing the reconstruction back into the model recovers 0.928 of the loss gap against zero-ablation and 0.910 against mean-ablation, yet raises the loss by
0.54 nats: perplexity goes from 4.64 to 7.97, a 72% rise. It also changes the behaviour traced below: with the reconstruction alone,
the model's "she/he" logit gap after a name rises from 9.06 to 10.06.
*Limits:* "loss recovered" is measured against very bad baselines. One training run per λ; confidence intervals are over held-out stories, not training seeds.

**2. Labels predict where features fire better than chance, but almost no feature passes a strict blind check.**
In a blind test on text neither autoencoder was trained on, a fresh reader given only the label picked the firing snippets with accuracy **0.816** for the real autoencoder
against **0.532** for a control trained on a copy of the model with shuffled weights (chance 0.5; difference p below 0.0001). The control is not significantly
above chance (p = 0.075).
A stricter test fails: fresh judges, blind to which autoencoder a feature came from, rated a feature clear only if 16 of its 20 strongest examples *and* 8 of 10 randomly chosen firings fit its label.
Only **3 of 200 real features (1.5%)** and 0 of 50 control features passed, which does not separate them (p = 0.51).
Strongest examples fit the labels about equally for both (17.8 and 17.5 of 20), but random firings almost never do (0.8 of 10 for real features):
a typical firing is weak (median strength 0.35 against 7.2 for the strongest examples) and lands on loosely related tokens.
**An earlier claim that 37 of 200 features were clear is withdrawn:** I made those verdicts myself, knowing which features were controls, and the blind judges confirmed 2 of them.
*Limits:* no label or verdict has been checked by a human, and the labeller, guessers and judges may share biases; the non-firing snippets in the blind test are random tokens, an easy contrast; the control autoencoder is denser (L0 56.2 against 26.7) and saw less data.

**3. Steering toward a label at fluent strengths is not supported.**
I steered 14 features by adding a multiple of their decoder direction during generation, against random directions of the same length, with three designs.
Under a rule fixed in advance (fluent text, and more label words than the random directions on at least 9 of 10 prompts), **1 of 14** features passed in design 2
(strength in units of each feature's median firing: 215) and **1 of 14** in design 3 (strength as a fraction of the mean activation length: 916).
Feature 916 ("bees, hives and honey") steered at 0.35 of the mean activation length; design 2 never pushed it that far (at most 0.16).
The first design's examples (bee, rain and cold stories, "girl girl girl" repeats) came from 2 prompts judged by reading, with success rules written afterwards; they are **exploratory** and are not evidence for the claim.
*Limits:* the label-word lists are narrow (the "rain" feature at 0.35 of the mean length produced puddle stories that the list did not count); one fluency cut-off; 14 hand-picked features.
These are the last steering designs; no further ones were run.

**4. Switching off features shrinks the model's pronoun preference but never changes its choice.**
The model prefers the right pronoun after a name on every test prompt. In a rerun that held out both names and sentence frames and compared against random features matched on activation size:
- Switching off the top 10 features together lowers the logit gap by 3.69 (from 7.37), against 0.19 for matched random sets (beats all 100).
  **But it also raises the model's loss on ordinary held-out stories by 0.247 nats, against 0.030 for matched random sets**, and 4 of the 10 have almost no effect on their own in the new frames.
  Part of this drop is general damage, not pronoun-specific.
- *Exploratory* (the idea came from seeing the first result, though the rerun fixed its rules in advance): 5 girl-selective features lower the gap on held-out girl-name prompts by 4.65 (from 8.00)
  while the boy-name gap rises by 0.08; 5 boy-selective features lower the boy gap by 2.79 (from 6.75) while the girl-name gap rises by 0.38.
  Their effect on ordinary story loss is small (0.004 and 0.016 nats, against 0.008 and 0.011 for matched random sets).
  One feature (1511) alone accounts for 2.20 of the girls' 4.65, and it does not fire on Anna.
- In none of these ablations did the model's preferred pronoun change (still correct on every prompt afterwards).
- Adding the boy-selective features to girl-name prompts at 1.5× their usual level flips the preferred pronoun on 100% of prompts (the wrong pronoun becomes the single most likely next word on 60%).
  The reverse direction fails the fixed rule: 40% at 1.5×, and 100% only at 2×. Random directions of the same length flipped at most 1.5%.
*Limits:* 20 names in total (5 held out per gender), layer 3 only, and the autoencoder itself shifts this behaviour (finding 1).

## Feature browser

Open [`browser/index.html`](browser/index.html) in any browser (no server, no network). Pick a feature to see its label, the blind judges' counts, its blind-test score,
its strongest and random firings, and steering and tracing results. A toggle switches to the shuffled-weights control's features.
It holds the 200 labelled features, the 50 labelled control features, and the Stage 7 features that were not among the 200.

## Results at a glance

| λ | active features per token (L0) | variance explained | loss recovered (zero / mean baseline) | extra loss (nats) | perplexity rise | dead in last epoch |
|---|---|---|---|---|---|---|
| 0.5 | 88.2 | 0.930 | 0.959 / 0.949 | 0.30 | 35% | 0.0% |
| 1 (chosen) | 26.7 | 0.890 | 0.928 / 0.910 | 0.54 | 72% | 0.0% |
| 2 | 10.4 | 0.850 | 0.884 / 0.855 | 0.87 | 138% | 0.0% |
| 4 | 5.5 | 0.784 | 0.806 / 0.759 | 1.44 | 323% | 2.2% |

| Check on the labels | Real | Control |
|---|---|---|
| Blind label test, fresh text (50 features each) | 0.816 | 0.532 |
| Blind strict-clear verdicts | 3/200 | 0/50 |
| Earlier non-blind verdicts (withdrawn) | 37/200 | 1/50 |

| Steering design | Strength unit | Prompts | Features that steer under the fixed rule |
|---|---|---|---|
| 1 (exploratory) | multiples of the mean of the top-20 activations | 2 | no fixed rule; judged by reading |
| 2 | multiples of the median firing | 10 | 1 of 14 |
| 3 | fraction of the mean activation length | 10 | 1 of 14 |

Held-out set: 1029 stories, 198,858 predicted tokens. Training data: 2,487,185 tokens from 12,747 stories, 20 epochs.
Figures are in [`figures/`](figures/). Full write-up with method, failures, limits and the review: [`REPORT.md`](REPORT.md).

## How to run

```
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
pytest                                              # tests for the autoencoder, hooks, evaluation, ablation code and docs
```

Some tests load the model from the Hugging Face cache and some read the collected activations, so run `pytest` after Stages 1 and 2.
Everything is configured in `config.yaml` (seed 1234). The review reruns' designs and success rules are the `steering_v2`, `steering_v3`, `trace_v2` and `stage5_v2` blocks, each committed before its run.
The collected activations take 2.79 GB (`data/`, git-ignored, regenerable); checkpoints are git-ignored too. Long steps checkpoint and resume; start them with `caffeinate -i` on a laptop.

| Stage | Command(s) | Writes |
|---|---|---|
| 0–1 setup, model | `python scripts/device_test.py`, `python scripts/stage1_load_model.py` | `results/device_test.json`, `results/stage1_*.json` |
| 2 activations | `caffeinate -i python scripts/stage2_collect_activations.py`, `python scripts/stage2_checks.py` | `data/`, `results/stage2_*.json` |
| 3 train | `python scripts/stage3_pilot.py`, `caffeinate -i python scripts/stage3_train.py` | `checkpoints/sae/`, `results/stage3_*.json` |
| 4 faithfulness | `python scripts/stage4_faithfulness.py`, `python scripts/stage4_table.py` | `results/stage4_*` |
| 5 features | `python scripts/stage5_examples.py`, `python scripts/stage5_write_labels.py`, `python scripts/stage5_random_control.py`, `python scripts/stage5_examples.py --random`, `python scripts/stage5_write_labels_random.py`, `python scripts/stage5_blind_build.py`, *(blind answering)*, `python scripts/stage5_blind_score.py`, `python scripts/stage5_report.py` | `results/stage5*` |
| 5 review rerun | `python scripts/stage5b_build.py`, *(blind judging and answering)*, `python scripts/stage5b_score.py` | `results/stage5b*` |
| 6 steering, design 1 | `python scripts/stage6_steer.py`, `python scripts/stage6_steer.py --ext`, `python scripts/stage6_report.py`, `python scripts/stage6_ext_report.py` | `results/stage6*` |
| 6 steering, designs 2 and 3 | `python scripts/stage6b_steer_v2.py`, `python scripts/stage6b_report.py`, `python scripts/stage6b_steer_v2.py --v3`, `python scripts/stage6b_report.py --v3` | `results/stage6b*`, `results/stage6c*` |
| 7 tracing | `python scripts/stage7_trace.py`, `python scripts/stage7_analyse.py`, `python scripts/stage7_selective.py`, `python scripts/stage7_report.py` | `results/stage7*` |
| 7 review rerun | `python scripts/stage7b_trace_v2.py`, `python scripts/stage7b_report.py` | `results/stage7b*` |
| 8 browser, docs | `python scripts/stage8_numbers.py`, `python scripts/stage8_browser.py`, `python scripts/stage8_docs.py`, `python scripts/stage8_check_numbers.py` | `results/headline_numbers.json`, `browser/index.html`, `README.md`, `REPORT.md` |

**Not fully scripted.** The label text is stored in `stage5_write_labels.py`, so re-running it does not re-label. The blind answers and blind verdicts came from fresh judges
reading only the puzzle or item files; their raw answers are saved under `results/stage5_blind/` and `results/stage5b/responses/`, and the scoring scripts recompute every number from them. Re-doing these steps needs new answers and would give slightly different numbers.

**Where numbers come from.** `scripts/stage8_numbers.py` gathers every number cited here into `results/headline_numbers.json`; `scripts/stage8_docs.py` fills this README and `REPORT.md` from it;
`scripts/stage8_check_numbers.py` flags any number it cannot trace to that file. The checker cannot check wording; the review in REPORT section 9 is where wording was checked.

## Repository layout

```
config.yaml        every setting, the seed, and the pre-registered rules of the review reruns
src/               model hooks, data, activation collection, autoencoder, training, evaluation, tracing helpers
scripts/           one or more scripts per stage (table above)
tests/             tests for the autoencoder, hooks, collection, evaluation, ablation code and docs
results/           every result file; results/stage*_report.md are per-stage write-ups
figures/           plots
browser/           the static feature browser
docs/              method comparison against the papers
PROGRESS.md        stage-by-stage log and decisions
LEARNING_NOTES.md  plain-language explanations and interview questions per stage
```

## Prior work

- Ronen Eldan and Yuanzhi Li. *TinyStories: How Small Can Language Models Be and Still Speak Coherent English?* arXiv:2305.07759, 2023. (The model and data.)
- Trenton Bricken et al. *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning.* Transformer Circuits Thread, 2023. (Autoencoder design, resampling, shuffled-weights control.)
- Hoagy Cunningham, Aidan Ewart, Logan Riggs, Robert Huben and Lee Sharkey. *Sparse Autoencoders Find Highly Interpretable Features in Language Models.* arXiv:2309.08600, 2023.

`docs/method_comparison.md` lists where this project follows each paper and where it differs.
