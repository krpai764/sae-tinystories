# PROGRESS

Brief: `BRIEF_sparse_autoencoders.md`. Working rules there apply (stop after each stage, no invented numbers, etc).

## Status
- [x] Stage 0 Setup — done and committed (089d099)
- [x] Stage 1 Load the model — done 2026-11-15, awaiting user approval/commit
- [ ] Stage 2 Collect activations
- [ ] Stage 3 Train SAEs
- [ ] Stage 4 Faithfulness
- [ ] Stage 5 Interpret features
- [ ] Stage 6 Steering
- [ ] Stage 7 Trace a behaviour (time-boxed, max 2 sessions)
- [ ] Stage 8 Browser + README + REPORT

## Next
Stage 2: collect ~2-5M tokens of activations at layer 3 into a memmap in `data/` with matching token IDs; keep under ~3 GB (8M model width 256: fp32 is 1 KB/token so ~2.5M tokens = ~2.6 GB, or use fp16 for more). Use train split for SAE data and a separate held-out slice from the validation split. Report file size, norm mean/spread, test that a saved row equals a recomputed one. Start long runs with `caffeinate -i`, checkpoint to resume. Watch for huge-norm first-token (position 0) activations.

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
- Scripts: `scripts/device_test.py` -> `results/device_test.json`; `scripts/stage1_load_model.py` -> `results/stage1_stories.json`, `results/stage1_model_device_test.json`
- Model code: `src/model.py` (load_model, generate, residual_hook, get_activations)
- Tests: `tests/test_setup.py`, `tests/test_hooks.py` (12 tests total, all pass)
- Downloaded weights/tokenizer cached in `hf_cache/` (git-ignored, 227 MB)
