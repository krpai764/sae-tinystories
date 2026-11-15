# PROGRESS

Brief: `BRIEF_sparse_autoencoders.md`. Working rules there apply (stop after each stage, no invented numbers, etc).

## Status
- [x] Stage 0 Setup — done 2026-11-15, awaiting user approval to continue
- [ ] Stage 1 Load the model
- [ ] Stage 2 Collect activations
- [ ] Stage 3 Train SAEs
- [ ] Stage 4 Faithfulness
- [ ] Stage 5 Interpret features
- [ ] Stage 6 Steering
- [ ] Stage 7 Trace a behaviour (time-boxed, max 2 sessions)
- [ ] Stage 8 Browser + README + REPORT

## Next
Stage 1: check which `roneneldan/TinyStories-*` IDs exist, pick one (ask before any download > 1 GB), fill `model.name`, `model.layer`, `generation.prompts` in `config.yaml`. Re-time cpu vs mps on the real model forward pass.

## Decisions
- Python 3.13.3 venv at `.venv` (system default is 3.14; 3.13 chosen for PyTorch wheel safety). Activate: `source .venv/bin/activate`; run tests with `.venv/bin/python -m pytest`.
- Seed 1234 in `config.yaml`; every script loads settings through `src/config.py`.
- Config is YAML; `model.name`, `model.layer`, `sae.l1_coeffs`, `generation.prompts` are intentionally empty until their stages.
- Device: `mps` set in config. Stage 0 matmul benchmark: mps ~1.33-1.37x faster than CPU (results/device_test.json). Matmul-only, so re-check on the real model in Stage 1.
- Pinned versions seen: torch 2.15.0, transformers 5.23.0, datasets 5.2.0, numpy 2.5.4, pandas 3.1.1, matplotlib 3.11.2, pytest 9.2.0.
- Not a git repo yet; user to decide on `git init` and approve commits.

## Where things live
- Config: `config.yaml`; helpers `src/config.py`, `src/device_bench.py`
- Scripts: `scripts/device_test.py` -> `results/device_test.json`
- Tests: `tests/test_setup.py`
