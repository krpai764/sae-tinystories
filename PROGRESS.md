# PROGRESS

Brief: `BRIEF_sparse_autoencoders.md`. Working rules there apply (stop after each stage, no invented numbers, etc).

## Status
- [x] Stage 0 Setup — committed (089d099)
- [x] Stage 1 Load the model — committed (efd12f2)
- [x] Stage 2 Collect activations — committed (5615a3b)
- [x] Stage 3 Train SAEs — committed (6999550)
- [x] Stage 4 Faithfulness — committed (a712af2)
- [x] Stage 5 Interpret features (+ blind test, shuffled-weights control) — committed (5fa4669)
- [x] Stage 6 Steering — committed (49f2508); extension committed (24ccec3)
- [x] Stage 7 Trace a behaviour — committed (9b63f2b)
- [x] Stage 8 Browser + README + REPORT — committed (eca4357)
- [x] Review: read-only sceptical review, then reruns pre-registered in config.yaml before each run (rules: 5debad1, 1c68583, fff9e26; results: d096f52), steering design 3 (rule 55db959, results dc948e0), and a rewrite of README/REPORT/PROGRESS/browser — rewrite awaiting user review/commit

## Current claims (after the review; README.md and REPORT.md are generated from results/headline_numbers.json)
Read this before the per-stage notes below: several claims in those notes were later withdrawn. REPORT.md section 9 "Review and corrections" is the authoritative list.
- Faithfulness (unchanged): lam=1 VE 0.890, L0 26.7, loss recovered 0.928 (zero) / 0.910 (mean), +0.54 nats = perplexity 4.64 -> 7.97 (+72%). 40% of features fire on >1% of tokens. The reconstruction alone raises the pronoun gap 9.06 -> 10.06.
- Labels: blind label test on fresh text, real-50 0.816 vs control 0.532 (supported; control not significantly above chance, p = 0.075). Blind strict-clear verdicts (2 judges, >=16/20 top and >=8/10 random): real 3/200, control 0/50, Fisher p = 0.51 (not supported). My earlier non-blind 37/200 is WITHDRAWN (2 of the 37 confirmed blind).
- Steering: three designs, no more to be run (user instruction). Design 1 (top-20-mean units, 2 prompts, judged by reading) is exploratory. Design 2 (median-firing units, 10 prompts, 3 random directions, label-only word lists, fixed 9/10 rule): 1/14 steer (215). Design 3 (fraction of mean activation length 0.1-1.0, same rule): 1/14 (916 at 0.35). "Steering toward the label at fluent strengths" is NOT supported.
- Tracing rerun (held-out names x held-out frames, activation-matched random sets): top-10 drop 3.69 of 7.37 vs matched 0.19 (passes) but story loss +0.247 nats vs 0.030 (partly general damage); 4 of the 10 ~0 effect in new frames. Gender-selective sets (EXPLORATORY): girl 4.65 of 8.00 (1511 alone 2.20; silent on Anna), boy 2.79 of 6.75; other gender's gap rises slightly; story loss small. No ablation changes the preferred pronoun. Flip: boy features into girl prompts pass (1.5x: 100% pair, 60% top-1, 5/5 names); girl features into boy prompts fail (1.5x: 40%; 100% only at 2x). Random directions <= 1.5%.

## Next
Nothing further is planned in the brief. User to review and commit the rewrite. Possible follow-ups (not in the brief): a human check of a random sample of labels; harder distractors in the blind test; more training seeds; a second layer.

## Decisions
- Python 3.13.3 venv at `.venv` (system default is 3.14; 3.13 chosen for PyTorch wheel safety). Activate: `source .venv/bin/activate`; run tests with `.venv/bin/python -m pytest`.
- Seed 1234 in `config.yaml`; every script loads settings through `src/config.py`.
- Config is YAML; `model.name`, `model.layer`, `sae.l1_coeffs`, `generation.prompts` are intentionally empty until their stages.
- Device: `mps` set in config. Stage 0 matmul benchmark: mps ~1.33-1.37x faster than CPU (results/device_test.json). Matmul-only, so re-check on the real model in Stage 1.
- Pinned versions seen: torch 2.15.0, transformers 5.23.0, datasets 5.2.0, numpy 2.5.4, pandas 3.1.1, matplotlib 3.11.2, pytest 9.2.0.
- Git: repo initialised on `main`; identity is the user's global gitconfig (confirmed by user). Commit after each stage only with user approval.
- Model: `roneneldan/TinyStories-8M` (GPT-Neo, 8 blocks, width 256, 19.7M params, 112 MB). Chosen over 28M (width 512: activations would be ~6 GB for 3M tokens, over the 3 GB cap) and 33M (only 4 blocks, width 768). 1M/3M too small/weak. Dictionary will be 8 x 256 = 2048 features. Candidate IDs listed from the HF API (14 under roneneldan/TinyStories-*).
- Layer convention: `layer=3` = residual stream AFTER block 3 (0-indexed), the output of `model.transformer.h[3]`; midpoint (4 blocks run, 4 to go). Equals HF `hidden_states[4]` (tested).
- GPT-Neo blocks return a tuple (hidden, ...); `src/model.py::residual_hook` handles that and supports capture (`store`) and splice (`replace`).
- Local attention window is 256 and we use max_seq_len 256, so local attention behaves like global.
- Stage 1 device timing on the real model (batch 32 x 256 tokens): mps 1.39 s vs cpu 2.97 s, mps 2.1x faster -> keep `mps`. Stories are generated on CPU so text is device-independent.
- Generation: temperature 0.8, top_k 50, seed = 1234 + prompt index, 80 new tokens. Prompts in config.yaml.
- Quirk: loading prints harmless UNEXPECTED keys (`attn.bias`, `masked_bias`), old buffers newer transformers recomputes.
- First-prompt mean activation norm at layer 3 is ~3.0 (13 tokens only; Stage 2 will measure properly).

## Where things live
- Config: `config.yaml`; helpers `src/config.py`, `src/device_bench.py`
- Scripts: `scripts/stage2_collect_activations.py`, `scripts/stage2_checks.py`; `scripts/device_test.py` -> `results/device_test.json`; `scripts/stage1_load_model.py` -> `results/stage1_stories.json`, `results/stage1_model_device_test.json`
- Model code: `src/model.py` (load_model, generate, residual_hook, get_activations)
- Tests: `tests/` (16 tests at Stage 1; 37 at the end of the review)
- Downloaded weights/tokenizer cached in `hf_cache/` (git-ignored, 227 MB)

## Stage 2 notes (2026-11-16)
- Data: train = random sample (seed 1234) of stories from TinyStories parquet shard 0 -> 12,747 stories, 2,499,932 tokens; held-out = sample (seed 1235) from the validation parquet -> 1,029 stories, 199,887 tokens, with any story identical to a train story excluded (first sample had 3 duplicates; TinyStories contains duplicate stories). Download total ~260 MB.
- Preprocessing (`src/data.py::tokenize_story`): `<|endoftext|>` + story tokens, truncated to 256 tokens total; one story per sequence; stored flat with `story`, `pos` and `offsets` arrays so any row traces back to text. Same preprocessing must be used in Stages 4 and 7.
- Files in `data/` (git-ignored, 2.79 GB total, under the 3 GB cap): `{train,heldout}_{acts,tokens,story,pos,offsets}.npy`, `*_progress.json`. Loader: `src/collect.py::load_split`. Activations fp32, shape (N, 256).
- Position 0 (the EOS prefix) is always the same vector (norm 4.844, std 0). Stage 3 should mask it out of SAE training. Other tokens: norm mean 2.51, std 0.175.
- The mean vector holds 39% of the squared norm, so centre the data. (Stage 3 then initialised b_d at the geometric median instead of the mean; see docs/method_comparison.md.)
- BUG FOUND AND FIXED: the first full collection crashed with an MPS out-of-memory after ~1600 stories (and was ~20x slow). Cause: each batch had a different padded length, and MPS memory grew with distinct tensor shapes (driver memory went 2.8 -> 7 GB on an 8.6 GB machine). Fix: pad to multiples of 64 and call `torch.mps.empty_cache()` every 10 batches. Full run then took ~5 min with flat 1.1 GB. Resume from the checkpoint worked (1600 stories were kept from the first attempt, computed with the old padding; the verification passed on a random sample covering them).
- Verification: 50 random stories recomputed on CPU one at a time vs saved (mps, padded batches): max abs diff 1.9e-6.
- Machine has 8.6 GB RAM, so keep Stage 3 batches/dictionary modest, and avoid loading all of train_acts into RAM twice (2.56 GB; memmap or one copy is fine).
- Note for later: `data/` is regenerable by `scripts/stage2_collect_activations.py` (rerun resumes).
- Results: `results/stage2_stats.json` (smoke run: `stage2_stats_smoke.json`, 20k tokens, kept as a record), `results/stage2_checks.json`.

## Stage 3 notes (done, 2026-11-16)
- Read both papers; differences + decisions in `docs/method_comparison.md`. User approved all 12 proposals.
- Deviation #13 (found while testing): brief's W_e = W_d^T init makes the initial reconstruction ~4x too large (W_d W_d^T ~ 8I, ReLU halves). `sae.enc_init_scale: 0.25` (= 2d/m) keeps the direction, fixes the scale. 1-epoch test on 1M tokens, lam=3: loss after 244 steps 114 (scaled) vs 317 (brief's). Needs user sign-off.
- Toy-problem test initially failed because lam=0.02 was too weak for the toy scale (L0 ~15 vs true ~1.6); at lam=0.2 all 32 true directions recovered (median cos 0.994). Not a code bug.
- Code: `src/sae.py` (SAE, parallel-grad removal, resampling, geometric median), `src/train.py` (loop, eval, checkpoint/resume), `tests/test_sae.py` (25 tests total pass), `scripts/stage3_pilot.py`.
- Pilot (5 epochs, no resampling, lambdas 0.3/1/3/10/30): `results/stage3_pilot.json`, `figures/stage3_pilot.png`. L0 still falling at epoch 5 for every lambda (not converged). Dead-in-epoch climbs for lam=3 (0, 0, 0.7%, 2.5%, 3.0%). lam>=10 collapses (VE <= 0.11). Epoch time rose from ~40 s to ~70 s during the run (likely thermal throttling on the fanless Air).
- User decided: keep 2.5M fp32 data, lambdas [0.5,1,2,4], W_e scale 0.25 approved, 20 epochs, resampling after epochs 2/4/6/8.
- Full runs: `scripts/stage3_train.py` -> `results/stage3_runs.json`, `results/stage3_train.log`, `figures/stage3_training.png`, `figures/stage3_density.png`, checkpoints `checkpoints/sae/lam_*/ckpt.pt`.
- Final (held-out): lam 0.5 VE 0.930 L0 88.2 dead 0; lam 1 VE 0.890 L0 26.7 dead 0; lam 2 VE 0.850 L0 10.4 dead 0 (1 resampled); lam 4 VE 0.784 L0 5.5, dead-in-epoch 2.2%, 171/2048 never fire on held-out (624 resampled; dead peaked 23% at epoch 4).
- L0 levelled off (<2%/epoch over last 3) for 0.5, 1, 2 (still drifting ~1%/epoch); NOT for lam 4 (~2.2%/epoch).
- Next: Stage 4 faithfulness (zero- and mean-ablation baselines), then choose one SAE.

## Stage 4 notes (2026-11-16)
- `src/eval.py`, `scripts/stage4_faithfulness.py` -> `results/stage4_faithfulness.json`, `figures/stage4_faithfulness.png`; `scripts/stage4_table.py` -> `results/stage4_table.md`; `tests/test_eval.py` (32 tests total).
- Held-out: 1,029 stories, 198,858 predicted tokens. Clean loss 1.535 nats; zero-ablation 8.991; mean-ablation 7.515 (pos 0 left real). Position 0 treated two ways (kept real = main; also replaced = variant); conclusions identical.
- Loss recovered (zero / mean base, pos0 kept): lam0.5 .959/.949; lam1 .928/.910; lam2 .884/.855; lam4 .806/.759. Extra loss vs clean: +0.30/+0.54/+0.87/+1.44 nats. Bootstrap 95% CIs (over stories) are within ~±0.002.
- Caveat: even best SAE adds 0.30 nats (loss 1.84 vs 1.54, perplexity ~6.3 vs ~4.6); 96% recovered is relative to a very bad baseline (Bricken warned). Mean-ablation gives 1-4 points lower recovery.
- MPS OOM at eval batch 32 (50k-vocab logits); use batch 8.
- Carry-forward recommendation: lam=1 (L0 26.7, 0 dead, 0.928/0.910 recovered). User to confirm.

## Stage 5 notes (done, committed 5fa4669, 2026-11-16)
- Chosen SAE: lam=1 (`interpret.chosen_lambda`). All 2048 features fire on train. 200 random live features (seed 1234), presented in random order and split into 4 batches of 50.
- `scripts/stage5_examples.py` -> `results/stage5/features.json` (all 200: top-20, 5 random, frequency, promoted/suppressed tokens), `results/stage5/batch_{1..4}.md`.
- `scripts/stage5_write_labels.py` holds Claude's suggestions (batch 1 done: 47 clear / 3 unclear by suggestion) -> `results/stage5/labels.csv`; user fills `your_*` columns. Guide: `results/stage5/LABELLING.md`.
- Observation: random (typical) firings are often weak and on unrelated tokens even when the top examples are clean. 'random_examples_agree' records this: yes 19, partly 19, no 12 in batch 1.
- Data quirk: TinyStories contains mojibake (curly quotes as 'â€œ'); one feature (#12, f137) tracks it.
- USER CHANGE OF PLAN (2026-11-16): user will NOT hand-label. Claude's labels for all 200 are final. Final 'clear' = suggested verdict clear AND random_examples_agree == 'yes'. README and REPORT must state clearly that ALL labels are AI-written and not human-verified (README.md stub already says so).
- Random-model control: `scripts/stage5_random_control.py` (shuffled weights, seed 4321, 400k tokens fp16 in data/random/, 120 epochs) -> `results/stage5_random_control.json`, checkpoints/sae_random/. Examples: `scripts/stage5_examples.py --random` -> results/stage5_random/. Labels for its first 50 features: `scripts/stage5_write_labels_random.py`.
- Blind test: `scripts/stage5_blind_build.py` (puzzles: label + 5 firing [uniform among firings] + 5 non-firing snippets from unseen text; real+control anonymised and shuffled; key in results/stage5_blind/key.json) -> 10 fresh subagents (sonnet) answered from the puzzle files only -> raw answers saved in results/stage5_blind/responses.json -> `scripts/stage5_blind_score.py` -> results/stage5_blind_scores.json, results/stage5_blind_per_feature.csv, figures/stage5_blind.png. Report: `scripts/stage5_report.py` -> results/stage5_report.md.
- Headline AT THE TIME (non-blind 'clear' verdicts, later WITHDRAWN; blind rerun gives 3/200 vs 0/50): real 37/200 clear (18.5%), control 1/50 (2%). Blind accuracy real 0.779 (n=200) vs control 0.564 (n=50), chance 0.5. Labeller's 'unclear' verdict did not predict blind accuracy (0.779).
- Stage 5 done pending user review/commit. Next: Stage 6 steering (pick 5-8 features with high blind accuracy and 'clear').

## Stage 6 notes (2026-11-16) — design 1, EXPLORATORY; its conclusions are superseded by designs 2 and 3 (see Current claims)
- Selection (user instruction): main features ONLY from Stage 5 strictly-clear AND 5/5 blind (20 such); picked 6 with content-visible labels: 144, 597, 1211, 2014, 215, 1905. Plus 2 NOT-clear: 1693 ('time', 1/5 blind), 978 ('sunshine', 2/5). In config.yaml `steering`.
- `scripts/stage6_steer.py` (CPU, `--smoke` for 1 feature) -> results/stage6/steering.json; `scripts/stage6_report.py` -> results/stage6_summary.json, figures/stage6_steering.png, results/stage6_report.md.
- Vector = k x s x d / rescale, s = mean of top-20 activations, added at all positions except EOS prefix; control = random unit direction, same length. 2 prompts, seeds 1234/1235, 50 tokens.
- Deviation: brief's 2/5/10x; smoke test showed 2x already breaks text (vector ~ as long as the mean activation, 2.51 model units), so k = [0.5,1,2,5,10].
- Findings: at k=0.5 all text stays fluent (mild drift); at k=1 one prompt breaks for 597 and both for 1693 (not clear); at k=2 all 6 clear features break (ppl>20 under unsteered model) into their promoted next-tokens (little->'girl/boy', big-encounter->'scary monster', mom->'my', was-so->'so sad', story-end '.'->'The/They'). Random directions of equal length also break text at k>=2 but produce 0 promoted tokens. Steering mostly acts on the NEXT-token prediction, not a theme. Not-clear 'sunshine' (978) gave the most on-topic fluent steering ('sky was bright and sun was warm' at 2x, 'sunshine' at 5x); 'time' (1693) collapsed to 'to to to' by 2x.
- Next: Stage 7 (trace one behaviour), brief suggests Fable.

## Stage 6 extension (2026-11-16) — design 1, EXPLORATORY; the 'success' rule here was written after reading the text, and the selection was hand-picked (e.g. 1470 left out), not 'every topic label'
- User asked: 4-6 context/theme features at k = 0.5, 0.75, 1, 1.25, 1.5, 2, same random control, report failures too.
- Selection rule: every Stage 5 label naming a topic/domain (not a syntactic slot / single next token), any verdict or blind score, not already steered -> 1137 rain (clear, 3/5), 916 bees/honey (5/5), 1463 cold (3/5), 687 safety warnings (4/5), 1970 chores (4/5), 715 musical 'play' (3/5). Config `steering_extension` incl. theme word lists fixed before reading steered text.
- `scripts/stage6_steer.py --ext` -> results/stage6/steering_extension.json; `scripts/stage6_ext_report.py` -> results/stage6_extension_summary.json, figures/stage6_extension.png, results/stage6_extension_report.md.
- Result (from reading the text; the automatic 'fluent & on-theme' count is loose, 1-2 words suffice): clear successes 916 bees (fluent bee/hive/honey stories at 1.25-1.5x), 1137 rain (puddles/raincoat at 0.5-0.75x, breaks from 1.25x), 1463 cold (snow/icy wind/shiver at 0.5-0.75x, breaks from 1.25x). Weak: 687 (some 'be careful' warnings, but the random control also produced one). Failures: 1970 chores, 715 music: fluent at every k but no theme.

## Stage 7 notes (2026-11-16, session 1 of max 2) — first run; superseded by the rerun in the Review section (unmatched control, shared frames)
- Behaviour: 'she'/'he' after a named character. Design approved by user before running (name-only headline; per-gender breakdown; flip test if top-10 passes). Config `trace`.
- Code: `src/trace.py` (+ `tests/test_trace.py`, 35 tests total); `scripts/stage7_trace.py` (baselines + single-feature ablations -> results/stage7/{prompts,baseline,firing}.json, effects.npy, acts.pt); `scripts/stage7_analyse.py` (pre-registered top-10 test + first flip test -> analysis.json, flip.json, top_feature_examples.json); `scripts/stage7_selective.py` (POST-HOC gender-selective analysis + flip test -> selective.json); `scripts/stage7_report.py` -> results/stage7_report.md, figures/stage7_trace.png.
- Frames changed from the proposal's example: name always after an opening phrase, since most girls' names are single tokens only with a leading space.
- Baseline: correct pronoun beats wrong on 120/120; name-only clean score 9.06 logits; 559/2048 features fire on the prompts.
- Pre-registered top-10 test PASSES (held-out drop 7.65 of 9.06; beats 100/100 random sets) BUT is dominated by gender-neutral context features (1493 'One', 88 'day', 1384/1879 commas, 1869 'park', 668 'because') that fire equally for both genders. So it does not isolate gender. First flip test (flip.json) is confounded by the same features.
- Post-hoc: gender-selective features (activation >= 5x on one gender's ranking names). Girl top-5 [1511,1735,905,1630,1324]: held-out girl drop 5.66 of 9.42 (random mean 0.10, max 1.72), boys unaffected (-0.21). Almost all from ONE feature, 1511 (generic girl name; does not fire on Anna). Boy top-5 [1314,1416,1532,1197,2037]: held-out boy drop 4.34 of 8.70 (random mean 0.17, max 4.28: only narrowly above the best random set), ranking-names drop 10.24 -> boy features are largely name-specific (Tom, Tim, Bob) and transfer less.
- Flip (selective, name-only, 20 held-out prompts per gender): adding boy features to girl prompts flips 0% at 0.5x, 75% at 1x, 100% at 1.5x; adding girl features to boy prompts 0% at 1x, 30% at 1.5x, 100% at 2x; with own features also switched off: 75%/90% and 35%/100% at 0.5x/1x. Random directions: 0-3%.
- Ablating the gender-selective sets never flips the pronoun (accuracy stays 100%); ablating the top-10 set left 85% correct. In the rerun no ablation changed the preferred pronoun. The rest of the gender signal is in other features / the SAE error.
- Next: Stage 8 (browser + README + REPORT), brief suggests Sonnet. README/REPORT must carry the AI-label disclaimer.

## Stage 8 notes (2026-11-16)
- `scripts/stage8_numbers.py` -> results/headline_numbers.json (every number cited in the docs, read from results/ and config.yaml). `scripts/stage8_docs.py` writes README.md and REPORT.md from it (numbers are format fields; edit the script for wording, never the generated files). `scripts/stage8_check_numbers.py` flags any number in the docs that does not trace to the JSON (0 untraceable at commit time; it is a safety net: small integers and strength values are allowed through). `scripts/stage8_browser.py` -> browser/index.html (single self-contained file, ~0.9 MB, no network): 200 real + 50 control features, plus 14 Stage-7 features not among the 200, with AI label, strict-clear verdict, blind score, top/random snippets, steering tables, tracing info. Checked in headless Chrome (desktop and 500 px width, dark mode).
- README leads with the four main findings, each with its limits, then the AI-label disclaimer is at the top. REPORT: method, results, failures, limits, deviations table, prior work, reproducibility.
- Tests: `tests/test_docs.py` (page is offline, disclaimer present, 200/50 features, docs numbers trace) -> 37 tests total.
- Honest gaps stated in README: label text and blind answers are stored, not regenerated by script; browser unlabelled Stage-7 features have no AI label (1324 and 2037 also have no saved examples).
- Run order for Stage 8: stage8_numbers.py -> stage8_browser.py -> stage8_docs.py -> stage8_check_numbers.py.

## Review and reruns (2026-11-17)
- A sceptical review of README/REPORT (by Claude, read-only) found overreach; user ordered fixes in 3 parts, plus a third and last steering design. All parts are done: reruns (each pre-registered in config.yaml and committed before running), design 3 (config `steering_v3`, commit 55db959; results dc948e0: 1/14 steer, 916 at 0.35), the rewrite (stage8_numbers.py now also reads the rerun results; stage8_docs.py rewritten; browser shows blind verdicts and designs 2-3), and REPORT section 9 'Review and corrections'.
- 1a steering v2 (config `steering_v2`, commit 5debad1): `scripts/stage6b_steer_v2.py`, `scripts/stage6b_report.py` -> results/stage6b/steering_v2.json, results/stage6b_summary.json, results/stage6b_report.md, figures/stage6b_steering_v2.png. Strength in units of median firing (2,3,5,7,10x), 10 prompts, 3 random directions, label-only word lists. RESULT under the rule: main_clear 1/6 steer (215 only) = "not supported"; main_unclear 0/2; topic 0/6 = "not supported". In these units topic features get tiny vectors (10x median ~0.3-0.5 model units); 144 breaks at 2x. The earlier topic successes were at ~10-40x median, outside this range, and stay exploratory (2 prompts).
- 1b tracing v2 (config `trace_v2`, commit 1c68583): `scripts/stage7b_trace_v2.py`, `scripts/stage7b_report.py` -> results/stage7b/analysis.json, results/stage7b_report.md. Held-out frames AND names, activation-matched random sets (ratio 0.89-1.01), loss changes, top-1 rates. RESULT: R1 top-10 passes (drop 3.69 of 7.37 vs matched mean 0.19, 100/100) but it raises story loss by 0.247 nats (matched random 0.030) and 4 of its context features have ~0 effect on held-out frames; R2 passes for girl (4.65 of 8.00, other gender -0.08, story loss +0.004) and boy (2.79 of 6.75, other -0.38); pair preference stays 100% under every ablation; R3 flip passes for girl prompts + boy features (1.5x: 100% pair, 60% top-1, 5/5 names) and FAILS for boy prompts + girl features (1.5x: 40%, 0/5 names; 100% only at 2x). Random directions: 0-1.5%. Feature 1532 fires on all five held-out boy names (more general than 'name-specific').
- 1c Stage 5 v2 (config `stage5_v2`, commit fff9e26): `scripts/stage5b_build.py`, `scripts/stage5b_score.py` -> results/stage5b/ (items, puzzles, key, raw responses), results/stage5b_scores.json, results/stage5b_per_feature.csv, results/stage5b_report.md. RESULT: blind strict-clear (2 judges, top>=16/20 and random>=8/10 on 10 fresh uniform firings): real 3/200 (1.5%), control 0/50, Fisher p=0.51 -> 'real more often strict-clear' NOT supported; the old non-blind 37/200 does not survive (2 of 37 confirmed). Mean random fit 0.8/10 real vs 0.5/10 control: uniformly sampled firings are mostly tiny activations (median 0.35 vs 7.2 for top examples) on off-label tokens. Checked for a build bug: none found. Blind label test on fresh text: real-50 0.816 vs control 0.532 (permutation p<0.0001; supported); control vs chance p=0.075 (no longer significantly above chance).
- Rerun results committed in d096f52.
