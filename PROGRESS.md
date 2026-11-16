# PROGRESS

Brief: `BRIEF_sparse_autoencoders.md`. Working rules there apply (stop after each stage, no invented numbers, etc).

## Status
- [x] Stage 0 Setup — done and committed (089d099)
- [x] Stage 1 Load the model — committed (efd12f2)
- [x] Stage 2 Collect activations — done 2026-11-16, awaiting user approval/commit
- [x] Stage 3 Train SAEs — committed (6999550)
- [x] Stage 4 Faithfulness — done 2026-11-16, awaiting user review/commit
- [ ] Stage 5 Interpret features
- [ ] Stage 6 Steering
- [ ] Stage 7 Trace a behaviour (time-boxed, max 2 sessions)
- [ ] Stage 8 Browser + README + REPORT

## Next
Stage 3: read the two SAE papers first (Bricken et al 2023; Cunningham et al 2023) and tell the user where they differ from the brief's method notes. Implement SAE from scratch in `src/sae.py`, mask `pos == 0` rows (the constant EOS-prefix vector) out of training, rescale activations by one constant (~6.36, in results/stage2_checks.json) so mean norm = sqrt(256)=16, init b_d at the mean, 2048 features, short pilot to find lambda range (10-100 active features/token), then 4 lambdas spaced ~3x. Metrics per run: variance explained, mean L0, dead fraction, curves. Use `caffeinate -i`, checkpoint to `checkpoints/`.

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
- Tests: `tests/test_setup.py`, `tests/test_hooks.py`, `tests/test_collect.py` (16 tests total, all pass)
- Downloaded weights/tokenizer cached in `hf_cache/` (git-ignored, 227 MB)

## Stage 2 notes (2026-11-16)
- Data: train = random sample (seed 1234) of stories from TinyStories parquet shard 0 -> 12,747 stories, 2,499,932 tokens; held-out = sample (seed 1235) from the validation parquet -> 1,029 stories, 199,887 tokens, with any story identical to a train story excluded (first sample had 3 duplicates; TinyStories contains duplicate stories). Download total ~260 MB.
- Preprocessing (`src/data.py::tokenize_story`): `<|endoftext|>` + story tokens, truncated to 256 tokens total; one story per sequence; stored flat with `story`, `pos` and `offsets` arrays so any row traces back to text. Same preprocessing must be used in Stages 4 and 7.
- Files in `data/` (git-ignored, 2.79 GB total, under the 3 GB cap): `{train,heldout}_{acts,tokens,story,pos,offsets}.npy`, `*_progress.json`. Loader: `src/collect.py::load_split`. Activations fp32, shape (N, 256).
- Position 0 (the EOS prefix) is always the same vector (norm 4.844, std 0). Stage 3 should mask it out of SAE training. Other tokens: norm mean 2.51, std 0.175.
- The mean vector holds 39% of the squared norm, so centre (b_d init = mean).
- BUG FOUND AND FIXED: the first full collection crashed with an MPS out-of-memory after ~1600 stories (and was ~20x slow). Cause: each batch had a different padded length, and MPS memory grew with distinct tensor shapes (driver memory went 2.8 -> 7 GB on an 8.6 GB machine). Fix: pad to multiples of 64 and call `torch.mps.empty_cache()` every 10 batches. Full run then took ~5 min with flat 1.1 GB. Resume from the checkpoint worked (1600 stories were kept from the first attempt, computed with the old padding; the verification passed on a random sample covering them).
- Verification: 50 random stories recomputed on CPU one at a time vs saved (mps, padded batches): max abs diff 1.9e-6.
- Machine has 8.6 GB RAM, so keep Stage 3 batches/dictionary modest, and avoid loading all of train_acts into RAM twice (2.56 GB; memmap or one copy is fine).
- Note for later: `data/` is regenerable by `scripts/stage2_collect_activations.py` (rerun resumes).
- Results: `results/stage2_stats.json` (smoke run: `stage2_stats_smoke.json`, 20k tokens, kept as a record), `results/stage2_checks.json`.

## Stage 3 notes (in progress, 2026-11-16)
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
