"""Stage 5 sanity check: SAE on a shuffled-weights copy of the model (Bricken et al. 2023).

Collects 400k train tokens (fp16, data/random/) from the shuffled model at the same layer, trains an
SAE with the chosen lambda for ~the same number of steps as the real one, and saves its checkpoint.
Example extraction: scripts/stage5_examples.py --random.
Usage: caffeinate -i python scripts/stage5_random_control.py   (resumable)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from src.collect import collect
from src.config import ROOT, get_device, load_config, set_seed
from src.data import load_parquet_texts, select_stories
from src.model import load_model, shuffle_weights
from src.train import load_activations, rescale_factor, train_sae

cfg = load_config()
rc = cfg["random_control"]
set_seed(cfg["seed"])
device = get_device(cfg)
model, tok = load_model(cfg, device="cpu")
shuffle_weights(model, rc["shuffle_seed"])
model.to(device)
dd = ROOT / cfg["paths"]["data_dir"] / "random"
texts = load_parquet_texts(cfg["data"]["parquet_train_file"], ROOT / cfg["paths"]["hf_cache_dir"])
seqs = select_stories(texts, tok, cfg["model"]["max_seq_len"], rc["num_tokens"], cfg["seed"])
del texts
collect(model, seqs, dd, "train", cfg["model"]["layer"], device, 32, 50, pad_id=tok.eos_token_id,
        dtype=np.float16, log=lambda m: print(m, flush=True))

x = load_activations(dd, "train")
g = torch.Generator().manual_seed(cfg["seed"])
perm = torch.randperm(len(x), generator=g)
n_eval = rc["eval_tokens"]
x_eval, x_train = x[perm[:n_eval]].clone(), x[perm[n_eval:]].clone()
del x
c = rescale_factor(x_train)
x_train *= c
x_eval *= c
cfg_r = json.loads(json.dumps(cfg))
cfg_r["sae"]["epochs"] = rc["epochs"]
lam = cfg["interpret"]["chosen_lambda"]
print(f"random-model acts: train {tuple(x_train.shape)}, eval {tuple(x_eval.shape)}, rescale {c:.4f}", flush=True)
r = train_sae(x_train, x_eval, lam, cfg_r, ROOT / cfg["paths"]["checkpoint_dir"] / "sae_random" / f"lam_{lam}",
              rc["epochs"], device, cfg["seed"], tuple(rc["resample_after_epochs"]), 100_000,
              log=lambda m: print(m, flush=True))
out = {"lambda": lam, "rescale_factor": c, "shuffle_seed": rc["shuffle_seed"], "train_tokens": len(x_train),
       "eval_tokens": len(x_eval), "epochs": rc["epochs"], "final": r["final"],
       "epochs_log": r["hist"]["epochs"], "note": "eval = random 10% of the same stories' tokens (not a separate split)"}
(ROOT / "results" / "stage5_random_control.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out["final"], indent=1))
