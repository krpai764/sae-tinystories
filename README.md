# Sparse autoencoders on TinyStories-8M

Sparse autoencoders on the activations of a small story-writing model (roneneldan/TinyStories-8M): find features, test whether their labels are any good, steer the model with them, trace one behaviour.
A careful small-scale application of published methods ([Prior work](#prior-work)), **not new research**: one model, one layer, one dictionary size, one seed.

> **All feature labels in this project are AI-written (by Claude) and have not been verified by a human.** They were scored with an automated blind test (see below and `results/stage5_report.md`), but nobody checked them by hand. The same model family wrote the labels and took the blind test.

## Main findings, and what limits each one

**1. The autoencoder reproduces the model's activations well, but not perfectly.**
The chosen autoencoder (λ=1, 2048 features, residual stream after block 3) explains 0.890 of the
variance of held-out activations using about 26.7 active features per token, with 0% dead features. Splicing its reconstruction
back into the model recovers 0.928 of the loss gap against zeroing the activations and 0.910 against replacing them
with their mean, but still raises the model's loss by 0.54 nats (perplexity 4.64 to 7.97).
*Limits:* "loss recovered" is measured against very bad baselines, so it flatters. Even the least sparse autoencoder (λ=0.5) adds
0.30 nats; the sparsest (λ=4) recovers 0.806 and has 2.2% dead features in its last epoch.
One training run per λ; the confidence intervals in `results/stage4_faithfulness.json` are over held-out stories, not over training seeds.

**2. Most features are not cleanly interpretable, though they are better than chance.**
Of 200 randomly chosen features, only **37 (18.5%) pass a strict rule**: one concept explains the strongest examples *and*
randomly chosen firings. Judged on strongest examples alone, 181 would look clear. In a blind test (a fresh reader, given only the label, must pick
5 firing snippets out of 10 from text not used for labelling) the labels scored **0.779** against 0.5 for guessing.
A control autoencoder trained on a copy of the model with shuffled weights scored 0.564, and only 1 of its 50 labelled features
pass the strict rule (41 look clear on strongest examples alone). Labels describe strong firings far better than weak ones:
blind accuracy 0.94 on the strongest third of firings, 0.64 on the weakest.
*Limits:* **every label is AI-written and none was checked by a human.** The same model family wrote the labels and took the blind test, the non-firing
snippets are random tokens (an easy contrast), the control used less data (stored at half precision), and the labeller's own "unclear" verdict did not predict blind accuracy
(0.779 for those 19 features, against 0.779 overall).

**3. Steering moves the next word reliably, topics only sometimes, and only in a narrow strength window.**
I added a multiple of a feature's decoder direction to the activations while the model wrote, with a random direction of the same length as control.
For the 6 features chosen because they were strict-clear *and* scored 5/5 blind, text stayed fluent at 0.5× the feature's usual strong firing in 6 of 6 cases (neither of the two prompts broke) and
broke on both prompts at 2× in 6 of 6 (the unsteered model's own perplexity on this text is 1.4 to 2.5; "broken" means above 20.0). Broken text repeated what the feature predicts next ("girl girl girl", "so so so"):
at 2× the feature's promoted tokens made up 4.0 to 43.0 of 50 generated tokens, against at most 1.0 for random directions, which also broke the text in 5 of 6 cases but into unrelated words.
In an extension on 6 features whose labels name a topic, 3 (1137, 916, 1463) produced more theme words than the random control at strengths where the text stayed fluent;
3 (687, 1970, 715) did not.
*Limits:* two prompts per feature, 14 features in all, success judged by word counts and reading the text. The brief's strengths were too strong: all 8 main-run features broke on both prompts at 5× and at 10×, so gentler strengths were added.
Topic steering worked for 3 of the 6 topic features tried, and blind-test accuracy did not predict which (blind scores of those that worked: 3/5, 5/5, 3/5; of those that did not: 4/5, 4/5, 3/5).

**4. Switching off features changes the model's pronoun choice, but the obvious test was misleading.**
The model prefers the right pronoun after a name on all 120 prompts (mean logit gap 9.06 on name-only prompts).
The test I fixed in advance passed: switching off the top 10 features together lowers the gap by 7.65 on held-out names, against a mean of 0.12
(largest 1.30) for 100 random sets, and it beats all 100. **But 6 of those 10 features fire equally on girls' and boys' names**
(on these prompts they peak on "One", "day", commas, "park" and "because"), so the test shows the behaviour depends on context features; it does not isolate gender. A follow-up restricted to gender-selective features found
the gender signal: switching off the top 5 girl-selective features lowers the gap on held-out girl-name prompts by 5.66 (from 9.42) and the boy-selective ones by 4.34 (from 8.70).
Adding the boy-selective features to girl-name prompts, at their average activation on boy names, flipped the preferred pronoun on 75% of prompts; adding the girl-selective features to boy-name prompts flipped 0%
(at 1.5× that level, 100% and 30%; random directions of the same length: at most 3%).
*Limits:* the gender-selective analysis was designed after seeing the first result, so it is exploratory. There are only 20 names and 6 sentence frames; flip rates are out of 20 prompts.
Nearly all of the girl effect comes from one feature (1511, 5.25 of the 5.66); the boy features are largely tied to particular names (Tom, Tim, Bob) and transfer less
well to held-out names (drop 10.24 on the names they were ranked on, 4.34 on held-out names, against 4.28 for the best random set).
Switching these features off never changed which pronoun the model preferred (the correct pronoun is still preferred on all of the held-out prompts), so other features or the autoencoder's reconstruction error also carry gender. Layer 3 only.

## Feature browser

Open [`browser/index.html`](browser/index.html) in any browser (no server, no network). Pick a feature to see its AI-written label, whether it passed the strict rule,
its blind-test score, its strongest and random firings, and any steering or tracing results. A toggle switches to the shuffled-weights control's features for comparison.
It holds the 200 labelled features, the 50 labelled control features, and the features used in Stage 7 that were not among the 200.

## Results at a glance

| λ | active features per token (L0) | variance explained | loss recovered (zero / mean baseline) | extra loss (nats) | dead in last epoch |
|---|---|---|---|---|---|
| 0.5 | 88.2 | 0.930 | 0.959 / 0.949 | 0.30 | 0.0% |
| 1 (chosen) | 26.7 | 0.890 | 0.928 / 0.910 | 0.54 | 0.0% |
| 2 | 10.4 | 0.850 | 0.884 / 0.855 | 0.87 | 0.0% |
| 4 | 5.5 | 0.784 | 0.806 / 0.759 | 1.44 | 2.2% |

Held-out set: 1029 stories, 198,858 predicted tokens. Unmodified model loss 1.535 nats; zero-ablation 8.991; mean-ablation 7.515.
Training data: 2,487,185 tokens from 12,747 stories, 20 epochs.

Figures are in [`figures/`](figures/). Full write-up with method, failures and limits: [`REPORT.md`](REPORT.md).

## How to run

```
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
pytest                                              # tests for the autoencoder, hooks, evaluation and ablation code
```

Some tests load the model from the Hugging Face cache and some read the collected activations, so run `pytest` after Stages 1 and 2.

Everything is configured in `config.yaml` (seed 1234); results land in `results/`, figures in `figures/`. Long steps checkpoint and can be re-run to resume; start them with `caffeinate -i` on a laptop.
The collected activations take 2.79 GB (`data/`, git-ignored, regenerable); checkpoints are git-ignored too. Designed for an M1 MacBook Air (CPU or `mps`), no paid services.

| Stage | Command(s) | Writes |
|---|---|---|
| 0–1 setup, model | `python scripts/device_test.py`, `python scripts/stage1_load_model.py` | `results/device_test.json`, `results/stage1_*.json` |
| 2 activations | `caffeinate -i python scripts/stage2_collect_activations.py`, `python scripts/stage2_checks.py` | `data/`, `results/stage2_*.json` |
| 3 train | `python scripts/stage3_pilot.py`, `caffeinate -i python scripts/stage3_train.py` | `checkpoints/sae/`, `results/stage3_*.json` |
| 4 faithfulness | `python scripts/stage4_faithfulness.py`, `python scripts/stage4_table.py` | `results/stage4_*` |
| 5 features | `python scripts/stage5_examples.py`, `python scripts/stage5_write_labels.py`, `python scripts/stage5_random_control.py`, `python scripts/stage5_examples.py --random`, `python scripts/stage5_write_labels_random.py`, `python scripts/stage5_blind_build.py`, *(blind answering, see note)*, `python scripts/stage5_blind_score.py`, `python scripts/stage5_report.py` | `results/stage5*` |
| 6 steering | `python scripts/stage6_steer.py`, `python scripts/stage6_steer.py --ext`, `python scripts/stage6_report.py`, `python scripts/stage6_ext_report.py` | `results/stage6*` |
| 7 tracing | `python scripts/stage7_trace.py`, `python scripts/stage7_analyse.py`, `python scripts/stage7_selective.py`, `python scripts/stage7_report.py` | `results/stage7*` |
| 8 browser, docs | `python scripts/stage8_numbers.py`, `python scripts/stage8_browser.py`, `python scripts/stage8_docs.py`, `python scripts/stage8_check_numbers.py` | `results/headline_numbers.json`, `browser/index.html`, `README.md`, `REPORT.md` |

**Two steps are not fully scripted.** The labels were written by Claude reading the examples; `stage5_write_labels.py` stores that text, so re-running it rebuilds `labels.csv` but does not re-label.
The blind answers came from 10 fresh Claude sub-agents reading only the puzzle files in `results/stage5_blind/`; their raw answers are saved in `results/stage5_blind/responses.json`, and `stage5_blind_score.py` recomputes every blind-test number from them.
Re-doing the blind test would need new answers and would give slightly different numbers.

**Where numbers come from.** `scripts/stage8_numbers.py` gathers every number cited here into `results/headline_numbers.json`, and `scripts/stage8_docs.py` fills this README and `REPORT.md` from it, and `scripts/stage8_check_numbers.py` flags any number in either document that it cannot trace to that file. Don't edit the numbers by hand.

## Repository layout

```
config.yaml        every setting and the seed
src/               model hooks, data, activation collection, autoencoder, training, evaluation, tracing helpers
scripts/           one or two scripts per stage (table above)
tests/             tests for the autoencoder, hooks, collection, evaluation and ablation code
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

## Credits

Built by a student with Claude Code (Anthropic) as the coding assistant. Claude also wrote all feature labels and took the blind label test, which is why the labels count as unverified.
