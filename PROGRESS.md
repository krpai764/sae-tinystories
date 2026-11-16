# PROGRESS

Brief: `BRIEF_sparse_autoencoders.md`. Working rules there apply (stop after each stage, no invented numbers, etc).

## Status
- [x] Stage 0 Setup — done and committed (089d099)
- [x] Stage 1 Load the model — committed (efd12f2)
- [x] Stage 2 Collect activations — done 2026-11-16, awaiting user approval/commit
- [ ] Stage 3 Train SAEs
- [ ] Stage 4 Faithfulness
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
