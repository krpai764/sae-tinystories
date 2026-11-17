# Sparse autoencoders on TinyStories-8M: method, results, failures and limits

> **This report was rewritten after a sceptical review.** Several claims in the first version were withdrawn or weakened, three experiments were rerun under rules fixed in advance,
> and a third steering design was added. Section 9 lists what the review found and what changed. Every number below comes from a file in `results/` via `results/headline_numbers.json`.

This is a small application of published methods ([Prior work](#7-prior-work)) to one small model, not new research.

## 1. Summary

| Question | Answer | Main limit |
|---|---|---|
| Does the autoencoder capture the activations? | variance explained 0.890, L0 26.7, loss recovered 0.928 / 0.910, but perplexity +72% | weak baselines; one seed |
| Do labels say where features fire? | better than chance: blind accuracy 0.816 vs control 0.532 | no human check; easy distractors |
| Are features cleanly interpretable? | almost none by a strict blind check: 3/200, not different from control | no human check; one strict rule |
| Do features steer the model toward their label? | not supported: 1/14 (design 2), 1/14 (design 3) | narrow word lists; 14 hand-picked features |
| Can the pronoun choice be traced? | ablation shrinks the gap but never changes the choice; one flip direction works | exploratory analysis, few names |

## 2. Method

### 2.1 Model and activations
- `roneneldan/TinyStories-8M` (GPT-Neo, 8 blocks, width 256); residual stream after block 3, captured with a forward hook (`src/model.py`).
- 12,747 training stories and 1,029 held-out stories (validation split), with no exact duplicate shared between them. One row per token, fp32 memmaps (2.79 GB).
- Position 0 (the end-of-text prefix) is a constant vector (norm 4.84) and is excluded from training. Other positions have mean length 2.51; all activations are scaled by 6.364 so their mean length is √256.

### 2.2 Autoencoder and training (`src/sae.py`, `src/train.py`)
- f = ReLU(W_e (x − b_d) + b_e), x̂ = W_d f + b_d; untied weights; 2048 features (8× the width); loss = summed squared error + λ × sum of feature strengths, averaged over the batch.
- Unit-length decoder columns with the parallel gradient component removed (Bricken et al.); b_d starts at the geometric median (0.31 from the mean vector, whose norm is 10.0); W_e starts at 0.25 × W_dᵀ.
- Adam, learning rate 0.0003, batch 4096, 20 epochs over 2,487,185 tokens, λ in [0.5, 1, 2, 4]; dead features resampled after epochs [2, 4, 6, 8].

### 2.3 Faithfulness (`src/eval.py`)
Splice the reconstruction into the model at layer 3 and measure next-token loss on the held-out stories (198,858 predicted tokens), against zero-ablation and mean-ablation baselines. 95% bootstrap intervals over stories.

### 2.4 Interpretation (`scripts/stage5_*.py`, `scripts/stage5b_*.py`)
- 200 features chosen at random (seed 1234); for each, its top 20 snippets, 5 random firings and promoted output tokens. One label was written per feature. Feature labels and blind evaluations were generated with a language model and have not been human-verified.
- **Original blind test:** a fresh judge sees only the label and 10 snippets (5 firing, sampled uniformly among all firings; the rest non-firing) and picks the firing ones. Real snippets came from held-out text, but the control's came from its own training text.
- **Review rerun, blind test on fresh text:** the first 50 real and the 50 control features, on held-out stories that neither autoencoder trained on (the shuffled model was run on them), mixed and anonymised; 4 fresh guessers.
- **Review rerun, blind strict-clear verdicts:** all 250 features mixed and anonymised; each judged by 2 fresh judges who were not told there were two sources. Each counted how many of the 20 strongest examples and of 10 new uniformly sampled firings fit the label.
  Clear = at least 16 of 20 and 8 of 10, by both judges. Rules in `config.yaml` `stage5_v2`, committed before the run.
- **Control:** an autoencoder with the same settings trained on a shuffled-weights copy of the model (Bricken et al.): 357,783 half-precision tokens, 120 epochs; variance explained 0.899, L0 56.2.

### 2.5 Steering (`scripts/stage6_steer.py`, `scripts/stage6b_*.py`)
A vector along a feature's unit decoder direction is added at layer 3 at every position after the first while the model writes 50 tokens; the control is a random direction of the same length. Three designs, run in this order:
1. **Design 1 (exploratory).** Strength in multiples of the mean of the feature's top-20 activations; 2 prompts, one random direction; judged by reading, by promoted-token counts (near-circular) and, for topic features, by theme words with a success rule written afterwards.
2. **Design 2.** Strength in multiples of the feature's median firing (2, 3, 5, 7, 10×); 10 prompts, 3 random directions; label words written from the label text only.
3. **Design 3 (third and last).** Strength as a fraction of the mean activation length (0.1, 0.2, 0.35, 0.5, 0.75, 1.0); everything else as design 2.

Designs 2 and 3 share a rule fixed before each run (`config.yaml` `steering_v2`, `steering_v3`): a strength is *fluent* if the median perplexity of the steered text under the unsteered model is at most twice the 95th percentile of unsteered text
(7.12 and 7.81); *on-label* if the steered text has more label words than the mean of the random directions on at least 9 of 10 prompts and more than unsteered text; a feature *steers* if one strength is both.
**Feature selection was by hand:** the six main features were picked from the 20 that my (non-blind) verdicts called clear and that scored 5/5 blind; the six topic features were picked from the topic-like labels, not all of them (for example 1470, "Small-animal nouns (squirrel, mouse)", was left out); two not-clear features were added.

### 2.6 Tracing (`scripts/stage7_*.py`, `scripts/stage7b_*.py`)
- Behaviour: "she"/"he" after a named character. Score = logit(correct pronoun) − logit(wrong pronoun) at the last position.
- Ablation: zero one feature (or a set) at every position after the first, decode, add the reconstruction error back (`src/trace.py`, tested).
- **First run (superseded):** 20 names × 6 frames; ranking and test shared the frames; random sets not matched on activation.
- **Review rerun:** rank on ranking names × the original frames; test on held-out names × 6 new frames. Random sets matched on total activation (100 per test).
  Also reported: change in loss on the test prompts and on 64 held-out stories, and the rate at which the wrong pronoun becomes the model's top-1 next token. Rules in `config.yaml` `trace_v2`, committed before the run.
- The gender-selective analysis (features at least 5× more active on one gender's names) is **exploratory**: the idea came from seeing the first run, although the rerun fixed its rules in advance and tested it on new names and frames.

## 3. Results

### 3.1 Training and faithfulness
| λ | L0 | variance explained | loss recovered, zero [95% CI] | loss recovered, mean [95% CI] | extra loss (nats) | perplexity after splicing | perplexity rise | dead, last epoch | never fire, held-out | L0 levelled off | resampled |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.5 | 88.2 | 0.930 | 0.959 [0.959, 0.960] | 0.949 [0.948, 0.951] | 0.30 | 6.28 | 35% | 0.0% | 0.0% | yes | 0 |
| 1 (chosen) | 26.7 | 0.890 | 0.928 [0.926, 0.929] | 0.910 [0.908, 0.911] | 0.54 | 7.97 | 72% | 0.0% | 0.0% | yes | 0 |
| 2 | 10.4 | 0.850 | 0.884 [0.882, 0.885] | 0.855 [0.852, 0.857] | 0.87 | 11.06 | 138% | 0.0% | 0.0% | yes | 1 |
| 4 | 5.5 | 0.784 | 0.806 [0.804, 0.809] | 0.759 [0.755, 0.762] | 1.44 | 19.65 | 323% | 2.2% | 8.3% | no | 624 |

Unmodified loss 1.535 nats (perplexity 4.64); zero-ablation 8.991; mean-ablation 7.515.
At λ=1, 40% of features fire on more than 1% of held-out tokens. The reconstruction alone raises the pronoun logit gap of the tracing section from 9.06 to 10.06, so the autoencoder changes the behaviour studied.

![training](figures/stage3_training.png)
![faithfulness](figures/stage4_faithfulness.png)

### 3.2 Interpretability

**Blind label test.**

| Set | n | mean accuracy | 5/5 | 3/5 or fewer |
|---|---|---|---|---|
| Real, all labelled | 200 | 0.779 | 55 | 61 |
| Real, first 50 | 50 | 0.800 | 15 | 10 |
| Shuffled-weights control (its own training text) | 50 | 0.564 | 2 | 40 |
| Real, first 50, fresh text (rerun) | 50 | 0.816 | 17 | 12 |
| Control, fresh text (rerun) | 50 | 0.532 | 2 | 44 |

Fresh text: real minus control = 0.284, one-sided permutation p below 0.0001; control vs chance (0.5) p = 0.075. Each of the 4 guessers shows the same direction.
On its own training text the control scored 0.564, significantly above chance; on fresh text it does not. By firing-strength tercile (pooled across features, so this mixes strength with feature identity),
the original test detected weak firings at 0.64 and strong at 0.94.

**Blind strict-clear verdicts (rerun).**

| Set | n | strict-clear by both judges | clear by judge 1 / 2 | mean top fit (of 20) | mean random fit (of 10) | old non-blind clear | of those, confirmed |
|---|---|---|---|---|---|---|---|
| real | 200 | 3 (1.5%) | 4 / 3 | 17.8 | 0.8 | 37 | 2 |
| control | 50 | 0 (0.0%) | 0 / 0 | 17.5 | 0.5 | 1 | 0 |

One-sided Fisher exact p = 0.51: not supported. The judges agreed on 100% of calls. Random firings are mostly weak (median strength 0.35 vs 7.2 for the strongest examples),
and on most features they land on tokens that do not fit the label. A guesser can still use loose associations (a "little" feature also firing weakly on "tiny"), which explains why the label test separates real from control while the strict verdicts do not.
Per-feature results: `results/stage5b_per_feature.csv`; write-up: `results/stage5b_report.md`.

### 3.3 Steering: the three designs side by side
Vector lengths are given as a fraction of the mean activation length (2.51 in model units), so the designs can be compared. Strengths in the design 2 column are in its own unit (× median firing), in the design 3 column as fractions.

| feature | label | blind | how chosen | design 1 (exploratory): lengths covered; outcome | design 2: lengths; fluent up to; outcome | design 3: lengths; fluent up to; outcome |
|---|---|---|---|---|---|---|
| 144 | ' little' in 'there was a little boy/girl' | 5/5 | main: clear by my non-blind verdict, 5/5 blind | 0.25–4.93; both prompts broken from 0.99 | 0.75–3.77; never fluent; does not steer (on-label only where not fluent: 3, 5, 7, 10×) | 0.10–1.00; fluent up to 0.35; does not steer (on-label only where not fluent: 1.0) |
| 597 | ' big' in 'saw a big ...' (encounter) | 5/5 | main: clear by my non-blind verdict, 5/5 blind | 0.27–5.41; both prompts broken from 1.08 | 0.20–0.99; fluent up to 0.30; does not steer | 0.10–1.00; fluent up to 0.35; does not steer |
| 1211 | ' mom' as companion ('with her mom', 'her mom and dad') | 5/5 | main: clear by my non-blind verdict, 5/5 blind | 0.17–3.40; both prompts broken from 0.68 | 0.15–0.74; fluent up to 0.37; does not steer | 0.10–1.00; fluent up to 0.35; does not steer |
| 2014 | Animal noun introduced as protagonist in the opening sentence (fox, cat) | 5/5 | main: clear by my non-blind verdict, 5/5 blind | 0.22–4.40; both prompts broken from 0.88 | 0.06–0.32; fluent up to 0.32; does not steer | 0.10–1.00; fluent up to 0.50; does not steer |
| 215 | ' was' followed by 'so' + emotion after a mishap ('He was so sad') | 5/5 | main: clear by my non-blind verdict, 5/5 blind | 0.15–3.05; both prompts broken from 0.61 | 0.11–0.55; fluent up to 0.28; **steers** at 5× | 0.10–1.00; fluent up to 0.20; does not steer (on-label only where not fluent: 0.75, 1.0) |
| 1905 | '.' ending a story's closing/moral sentence (e.g. 'happily ever after.') | 5/5 | main: clear by my non-blind verdict, 5/5 blind | 0.24–4.73; both prompts broken from 0.95 | 0.14–0.68; fluent up to 0.34; does not steer | 0.10–1.00; fluent up to 0.50; does not steer |
| 1693 | ' time' in 'it was time to go home' | 1/5 | main: not clear | 0.39–7.88; both prompts broken from 0.79 | 0.05–0.23; fluent up to 0.23; does not steer | 0.10–1.00; fluent up to 0.35; does not steer |
| 978 | ' sunshine' in 'in the sunshine' | 2/5 | main: not clear | 0.12–2.49; both prompts broken from 1.24 | 0.02–0.12; fluent up to 0.12; does not steer | 0.10–1.00; fluent up to 0.35; does not steer (on-label only where not fluent: 0.75, 1.0) |
| 1137 | ' rain' in 'started to rain' | 3/5 | topic label | 0.32–1.29; theme words 3.0 vs random 0.0 (more; rule written afterwards) | 0.04–0.19; fluent up to 0.19; does not steer | 0.10–1.00; fluent up to 0.35; does not steer (on-label only where not fluent: 0.5, 0.75, 1.0) |
| 916 | Bees, hives and honey | 5/5 | topic label | 0.14–0.56; theme words 8.5 vs random 0.0 (more; rule written afterwards) | 0.03–0.16; fluent up to 0.16; does not steer | 0.10–1.00; fluent up to 0.35; **steers** at 0.35 |
| 1463 | ' cold' (weather) | 3/5 | topic label | 0.29–1.15; theme words 3.5 vs random 0.0 (more; rule written afterwards) | 0.04–0.20; fluent up to 0.20; does not steer | 0.10–1.00; fluent up to 0.35; does not steer (on-label only where not fluent: 1.0) |
| 687 | Parental safety warnings ("don't go too close"); promotes 'dangerous' | 4/5 | topic label | 0.11–0.46; theme words 1.0 vs random 1.5 (not more; rule written afterwards) | 0.03–0.14; fluent up to 0.14; does not steer | 0.10–1.00; fluent up to 0.35; does not steer |
| 1970 | Objects of household chores (dishes, laundry, weeds) | 4/5 | topic label | 0.07–0.27; theme words 0.5 vs random 0.5 (not more; rule written afterwards) | 0.02–0.11; fluent up to 0.11; does not steer | 0.10–1.00; fluent up to 0.35; does not steer |
| 715 | ' play' a musical instrument | 3/5 | topic label | 0.15–0.62; theme words 2.0 vs random 2.5 (not more; rule written afterwards) | 0.03–0.17; fluent up to 0.17; does not steer | 0.10–1.00; fluent up to 0.35; does not steer |

- Design 2 rule verdicts: main: clear by my non-blind verdict, 5/5 blind: 1/6 (not supported); main: not clear: 0/2 (n/a (group of 2)); topic label: 0/6 (not supported).
- Design 3 rule verdicts: main: clear by my non-blind verdict, 5/5 blind: 0/6 (not supported); main: not clear: 0/2 (n/a (group of 2)); topic label: 1/6 (not supported). Using design 2's numeric cut-off instead changes 0 verdicts.
- The designs disagree mostly because they cover different lengths: design 2 gave topic features very short vectors (median firings are small), design 3 gave every feature the same lengths.
  Where design 1 found topic stories (bees, rain, cold), its fluent vectors were about as long as design 3's. Under design 3's fixed rule only the bees feature passed; the rain feature wrote puddle stories at 0.35 that its word list did not count.
- Each feature had 5 or 6 chances to pass, so one pass among 14 features is consistent with chance (`config.yaml` gives the per-feature false-pass bound).

Full tables and sample text: `results/stage6b_report.md` (design 2), `results/stage6c_report.md` (design 3), `results/stage6_report.md` and `results/stage6_extension_report.md` (design 1). Figures: `figures/stage6b_steering_v2.png`, `figures/stage6b_steering_v3.png`.

### 3.4 Tracing the pronoun

**Rerun (held-out names × held-out frames, name-only prompts).** Unmodified model: correct pronoun preferred on 100% of 40 prompts, top-1 on 70%, mean gap 7.37
(girls 8.00, boys 6.75). 890 features fire on the prompts. Story loss without ablation: 1.498 nats.

| set | features | scored on | drop | matched random: mean / max | beats | pair preference correct after | top-1 correct after (random) | story loss change (random) | random/tested activation |
|---|---|---|---|---|---|---|---|---|---|
| top 10 (R1) | [1493, 88, 1314, 1511, 1384, 1879, 1416, 1869, 668, 1532] | overall | 3.69 | 0.19 / 1.06 | 100/100 | 100% | 40% (69%) | 0.247 (0.030) | 0.89 |
| girl-selective (R2, exploratory) | [1511, 1735, 905, 1630, 1324] | girl | 4.65 | 0.05 / 0.22 | 100/100 | 100% | 55% (67%) | 0.004 (0.008) | 1.00 |
| boy-selective (R2, exploratory) | [1314, 1416, 1532, 1197, 2037] | boy | 2.79 | 0.11 / 1.22 | 100/100 | 100% | 75% (72%) | 0.016 (0.011) | 1.01 |

- Specificity (own-gender drop minus other-gender drop): girl set 4.73 vs random -0.04; boy set 3.17 vs random 0.09 (each beats 100 and 100 of 100).
- Feature 1511 alone accounts for 2.20 of the girl set's drop; its activation on the held-out girls' names: Anna 0.0, Lucy 3.0, Sue 2.5, Jane 3.3, Amy 2.3. Feature 1532 fires on 5 of the 5 held-out boys' names.
- Of the top 10, 4 have an effect below 0.1 on their own in the new frames: their effect does not carry over from the ranking frames to the new ones.

**Flip test (rerun).** "pair" = the wrong pronoun's logit exceeds the correct one's; "top-1" = the wrong pronoun becomes the model's most likely next token; "names" = held-out names (of 5) with most of their prompts pair-flipped.

| prompts | features added from | strength | add: pair / top-1 / names | swap: pair / top-1 / names | random: pair / top-1 / names | add, noun-plus-name prompts: pair / top-1 |
|---|---|---|---|---|---|---|
| girl | boy | 0.5 | 0% / 0% / 0 | 75% / 35% / 4 | 0.0% / 0% / 0 | 0% / 0% |
| girl | boy | 1 | 65% / 25% / 3 | 90% / 45% / 4 | 0.0% / 0% / 0 | 0% / 0% |
| girl | boy | 1.5 | 100% / 60% / 5 | 100% / 75% / 5 | 1.5% / 0% / 0 | 0% / 0% |
| girl | boy | 2 | 100% / 75% / 5 | 100% / 75% / 5 | 1.5% / 0% / 0 | 40% / 40% |
| boy | girl | 0.5 | 0% / 0% / 0 | 40% / 25% / 2 | 0.0% / 0% / 0 | 0% / 0% |
| boy | girl | 1 | 0% / 0% / 0 | 95% / 70% / 5 | 0.0% / 0% / 0 | 0% / 0% |
| boy | girl | 1.5 | 40% / 40% / 0 | 100% / 75% / 5 | 0.0% / 0% / 0 | 0% / 0% |
| boy | girl | 2 | 100% / 75% / 5 | 100% / 75% / 5 | 0.0% / 0% / 0 | 0% / 0% |

The fixed rule (most prompts flipped for at least 4 of 5 names at a strength of at most 1.5×, random 0 names) passes for girl prompts (boy features added) and fails for boy prompts (girl features added).
Random directions flipped at most 1.5% of prompts and made the wrong pronoun the top-1 token on at most 0%.

**First run (superseded).** The top 10 lowered the gap on held-out names by 7.65 (from 9.06) against unmatched random sets averaging 0.12; 6 of the 10 fire equally on girls' and boys' names.
Its tables remain in `results/stage7_report.md`. Rerun write-up: `results/stage7b_report.md`.

## 4. Failures, surprises and things that went wrong

- **The first write-up overclaimed** (see Review and corrections): the strict-clear comparison was not blind, the steering headline had no fluent-strength evidence, the tracing control was not matched, and one selection claim was false.
- **The strict-clear verdicts collapse when made blind:** 37 non-blind to 3 blind for real features; the real and control autoencoders no longer differ on this measure.
- **The control looked above chance only on its own training text** (0.564); on fresh text 0.532.
- **Steering toward the label did not hold up** under fixed rules in two designs (1 and 1 of 14).
- **The top-10 tracing result is partly damage:** it raises story loss 0.247 nats against 0.030 for matched sets.
- **The autoencoder distorts the behaviour it is used to explain:** the reconstruction alone raises the pronoun gap (9.06 to 10.06).
- **The sparsest autoencoder is unhealthy:** at λ=4, 8.3% of features never fire on held-out text and 624 were resampled; it was not used.
- **Bugs caught during the project:** an out-of-memory crash during activation collection (fixed by padding to multiples of 64; saved activations matched a CPU recomputation to 2.0e-06), held-out stories duplicated in training (excluded), and an encoder initialisation several times too large (scaled by 0.25).
- **Dataset quirk:** TinyStories contains encoding artefacts, and at least one feature tracks them.

## 5. Limits

- One model, one layer, one dictionary size, one seed; no training-seed variation measured.
- The autoencoder is lossy (+72% perplexity) and shifts the traced behaviour; anything carried by the reconstruction error is invisible to feature-level analysis.
- **No label or verdict has been checked by a human, and the labeller, guessers and judges may share biases.** The blind test's non-firing snippets are random tokens (easy), and the strict-verdict rule (16/20 and 8/10) is one choice among many.
- Only 200 of 2048 features were labelled; the control is denser (L0 56.2 vs 26.7), used 357,783 half-precision tokens against 2,487,185, and is not a perfect match.
- p-values treat puzzles as independent, although each guesser answered 25; per-guesser results are reported.
- Steering: 14 hand-picked features, narrow label-word lists, one fluency rule; three designs in total, the last fixed by the user as final.
- Tracing: 20 names, 5 held out per gender; frames hand-written; layer 3 only; the gender-selective analysis is exploratory.
- Only exact duplicate stories were excluded from the held-out set; near-duplicates are possible.
- Promoted-token lists are approximate (the direction is multiplied by the unembedding although 4 blocks remain).

## 6. Deviations from the brief and from the papers

| Topic | Brief / papers | What I did | Why |
|---|---|---|---|
| Encoder init | W_e = W_dᵀ | 0.25 × W_dᵀ | the brief's init gave a first reconstruction several times too large (user approved) |
| b_d init | data mean | geometric median (Bricken) | cheap; close to the mean |
| Decoder gradient | rescale columns only | also remove the parallel gradient component (Bricken) | published and cheap |
| Data size | Bricken: billions of vectors | 2,487,185 tokens, 20 epochs, with resampling | disk cap |
| λ grid | 4 values about 3× apart | [0.5, 1, 2, 4] | 3× spacing would have put half the runs outside the usable range |
| Loss recovered | zero baseline | zero and mean baselines | zero-ablation flatters |
| Labels | not specified | no human check | user's decision not to hand-label |
| Steering strength | 2, 5 and 10 × "usual firing strength" | design 1 used the top-20 mean as the unit (an error); design 2 the median firing at 2, 3, 5, 7, 10×; design 3 fractions of the mean activation length | review |
| Tracing | one test | plus a rerun with held-out frames, matched controls and loss measures, and an exploratory gender-selective analysis | review |

## 7. Prior work

- Ronen Eldan and Yuanzhi Li. *TinyStories: How Small Can Language Models Be and Still Speak Coherent English?* arXiv:2305.07759, 2023.
- Trenton Bricken, Adly Templeton, Joshua Batson, Brian Chen, Adam Jermyn, Tom Conerly, Nicholas L. Turner, Cem Anil, Carson Denison, Amanda Askell, Robert Lasenby, Yifan Wu, Shauna Kravec, Nicholas Schiefer, Tim Maxwell, Nicholas Joseph, Zac Hatfield-Dodds, Alex Tamkin, Karina Nguyen, Brayden McLean, Josiah E. Burke, Tristan Hume, Shan Carter, Tom Henighan and Chris Olah.
  *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning.* Transformer Circuits Thread, 2023.
- Hoagy Cunningham, Aidan Ewart, Logan Riggs, Robert Huben and Lee Sharkey. *Sparse Autoencoders Find Highly Interpretable Features in Language Models.* arXiv:2309.08600, 2023.

## 8. Reproducibility

- Seed 1234 in `config.yaml`. The review reruns' designs and success rules are in `config.yaml` and were committed before each run (git history shows the order).
- Commands are in the README. `data/` and `checkpoints/` are git-ignored and regenerable.
- Not fully scripted: the label text and the judges' answers and verdicts, which are stored raw; scoring scripts recompute every number from them.
- README and this report are generated from `results/headline_numbers.json` by `scripts/stage8_docs.py`; `scripts/stage8_check_numbers.py` flags untraceable numbers but cannot check wording.

## 9. Review and corrections

After the first version was finished, a sceptical review listed every claim the results did not support. This was followed by reruns with rules fixed in advance,
a third and final steering design, and a rewrite. The table lists each finding, ranked by seriousness, what changed, and what the evidence now says. Nothing here has had a human check.

| # | seriousness | what the review found | what changed | outcome |
|---|---|---|---|---|
| 1 | serious | Steering headline ('moves the next word reliably') had no evidence at fluent strengths; effects appeared only where text was already broken | Two new designs with fixed rules, 10 prompts, 3 random directions, label-only word lists | 1/14 and 1/14 features steer; claim withdrawn (finding 3) |
| 2 | serious | 'The brief's strengths were too strong' was an artefact of using the top-20 mean as the unit | Design 2 uses the median firing (the brief's 'usual firing strength'); design 3 uses the mean activation length | Statement removed; the side-by-side table shows the vector lengths each design covered |
| 3 | serious | The promoted-token measure is close to circular (the decoder direction promotes those tokens by construction) | Word lists written from the label text only, fixed before the runs | Design 1 counts kept only as exploratory |
| 4 | serious | Tracing control not matched on activation size, so 'beats 100/100' was nearly guaranteed | Random sets matched on total activation (ratio reported); overall loss on held-out stories measured | Top-10 still beats matched sets, but raises story loss by 0.247 nats vs 0.030: partly general damage |
| 5 | serious | Held-out names shared the same sentence frames | 6 new frames used only for testing | 4 of the top 10 have almost no effect in the new frames |
| 6 | serious | 'Found the gender signal' overreached (post hoc, 5 names per gender, boy set barely beat the best random set) | Rules fixed in advance for the rerun; analysis labelled exploratory | Both selective sets pass; flip passes one way only (100% vs 40% at 1.5×) |
| 7 | serious | Finding 4 heading said ablation changes the pronoun choice; it only changed the logit gap | Heading and text rewritten | Choice unchanged in every ablation of the rerun |
| 8 | serious | The strict-clear comparison (37/200 vs 1/50) was judged non-blind by the labeller | Blind verdicts by 2 fresh judges per feature, real and control mixed | 3/200 vs 0/50 (p = 0.51); old claim withdrawn |
| 9 | serious | False claim that the extension used every topic label; main six were hand-picked from 20 without saying so | Selection described as hand-picked (e.g. 1470, Small-animal nouns (squirrel, mouse), was left out) | Corrected in README and REPORT |
| 10 | moderate | Control differs in more than weights; its blind-test text was its own training text | Control blind test rerun on held-out text it never saw | 0.532 (not significantly above chance); real 0.816; density and data differences stated as limits |
| 11 | moderate | Blind test is easy and partly measures label style | Stated as a limit | Unchanged |
| 12 | moderate | p-values assume independent puzzles, but answers come in batches of 25 | Per-guesser accuracies reported | All guessers show the same gap (`results/stage5b_report.md`) |
| 13 | moderate | '3 of 6 topic features steered' used a rule written afterwards | Marked exploratory; superseded by designs 2 and 3 | Designs 2 and 3: 0 and 1 of 6 topic features steer |
| 14 | moderate | 'Blind accuracy does not predict steering' drawn from 6 features | Removed | - |
| 15 | moderate | 'Reproduces the activations well' was generous; dense features not mentioned | Perplexity rise and density stated | 72% perplexity rise; 40% of features fire on more than 1% of tokens |
| 16 | moderate | Firing-strength terciles pooled across features | Stated as a limit | Unchanged |
| 17 | moderate | The reconstruction alone raises the pronoun gap; not reported | Reported in finding 1 | 9.06 to 10.06 |
| 18 | moderate | Flip rates used pair preference only | Top-1 rates reported beside them | At 1.5×, girl prompts: 100% pair, 60% top-1 |
| 19 | moderate | 'Broken' used an arbitrary perplexity of 20 | Cut-off defined from unsteered text (2 × its 95th percentile) | 7.12 (design 2), 7.81 (design 3) |
| 20 | minor | PROGRESS.md had stale headers and one over-broad sentence | Rewritten | - |
| 21 | minor | Ambiguous phrase 'the unsteered model's own perplexity on this text' | Removed | - |
| 22 | minor | The number checker cannot check wording | Stated in README | - |
| 23 | minor | Only exact duplicate stories were excluded from the held-out set | Stated as a limit | Unchanged |
| 24 | minor | Feature 1511 described as carrying the girl effect may be narrower than 'girls' names' | Its per-name activations reported | Silent on Anna |

**Claims that got weaker or were withdrawn:** "37/200 features are clear" (withdrawn; blind: 3/200); "the control is above chance" (not on fresh text); "steering moves text toward the label" (not supported);
"the brief's strengths are too strong" (an artefact of my unit); "3 of 6 topic features steered" (exploratory); "switching off features changes the pronoun choice" (it changes only the gap); "the gender signal was found" (exploratory; one flip direction fails).
**Claims that held up:** the faithfulness numbers; real labels predict firings better than control labels on fresh text; the top-10 and gender-selective ablations beat activation-matched random sets; boy features added to girl-name prompts flip the pronoun while random directions do not.
