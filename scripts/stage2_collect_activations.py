"""Stage 2: collect residual-stream activations for train and held-out text.

Usage:
  python scripts/stage2_collect_activations.py --smoke      # tiny run to test the code
  caffeinate -i python scripts/stage2_collect_activations.py  # full run (resumable: just rerun)
Writes data/{train,heldout}_*.npy and results/stage2_stats.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from src.collect import collect, load_split
from src.config import ROOT, get_device, load_config, set_seed
from src.data import load_parquet_texts, select_stories
from src.model import get_activations, load_model

ap = argparse.ArgumentParser()
ap.add_argument("--smoke", action="store_true", help="tiny run into data_smoke/ to test the code")
args = ap.parse_args()

cfg = load_config()
set_seed(cfg["seed"])
device = get_device(cfg)
d, layer = cfg["data"], cfg["model"]["layer"]
out_dir = ROOT / (cfg["paths"]["data_dir"] + ("_smoke" if args.smoke else ""))
res = ROOT / cfg["paths"]["results_dir"]
res.mkdir(exist_ok=True)
budgets = {"train": 20_000 if args.smoke else d["num_train_tokens"],
           "heldout": 5_000 if args.smoke else d["num_heldout_tokens"]}

model, tok = load_model(cfg, device=device)
cache = ROOT / cfg["paths"]["hf_cache_dir"]
files = {"train": d["parquet_train_file"], "heldout": d["parquet_valid_file"]}
seeds = {"train": cfg["seed"], "heldout": cfg["seed"] + 1}

t0 = time.time()
train_story_bytes = None
for name in ["train", "heldout"]:
    texts = load_parquet_texts(files[name], cache)
    print(f"{name}: {len(texts)} stories available in shard")
    seqs = select_stories(texts, tok, cfg["model"]["max_seq_len"], budgets[name], seeds[name],
                          exclude=train_story_bytes)
    if name == "train":  # TinyStories has duplicate stories; keep held-out disjoint from train
        train_story_bytes = {s.tobytes() for s in seqs}
    del texts
    info = collect(model, seqs, out_dir, name, layer, device, d["collect_batch_size"],
                   d["collect_checkpoint_every"], pad_id=tok.eos_token_id)
    print(info, f"elapsed {time.time() - t0:.0f}s")

# ---------------- statistics ----------------
stats = {"model": cfg["model"]["name"], "layer": layer, "device": device, "smoke": args.smoke,
         "seed": cfg["seed"], "splits": {}}
for name in ["train", "heldout"]:
    acts, tokens, story, pos, offsets = load_split(out_dir, name)
    norms = np.linalg.norm(np.asarray(acts), axis=1)
    nz = pos > 0  # excluding the EOS prefix token
    size = (out_dir / f"{name}_acts.npy").stat().st_size
    total = sum(p.stat().st_size for p in out_dir.glob(f"{name}_*"))
    q = lambda x: {k: float(np.percentile(x, p)) for k, p in
                   [("p1", 1), ("p25", 25), ("p50", 50), ("p75", 75), ("p99", 99), ("max", 100)]}
    stats["splits"][name] = {
        "num_tokens": int(len(tokens)), "num_stories": int(len(offsets) - 1),
        "acts_file_bytes": int(size), "all_files_bytes": int(total),
        "acts_file_GB": size / 1e9,
        "norm_all": {"mean": float(norms.mean()), "std": float(norms.std()), **q(norms)},
        "norm_excluding_pos0": {"mean": float(norms[nz].mean()), "std": float(norms[nz].std()), **q(norms[nz])},
        "norm_pos0_only": {"mean": float(norms[~nz].mean()), "std": float(norms[~nz].std()),
                           "n": int((~nz).sum())},
        "has_nan_or_inf": bool(~np.isfinite(np.asarray(acts)).all()),
        "per_dim_std_mean": float(np.asarray(acts)[nz].std(axis=0).mean()),
    }

# ------------- verification: saved rows vs freshly computed (CPU, single story) -------------
cpu_model, _ = load_model(cfg, device="cpu")
rng = np.random.default_rng(cfg["seed"])
diffs = []
for name in ["train", "heldout"]:
    acts, tokens, story, pos, offsets = load_split(out_dir, name)
    for sid in rng.choice(len(offsets) - 1, size=min(25, len(offsets) - 1), replace=False):
        a, b = offsets[sid], offsets[sid + 1]
        fresh = get_activations(cpu_model, torch.from_numpy(tokens[a:b].astype(np.int64))[None], layer)[0].numpy()
        diffs.append(float(np.abs(fresh - np.asarray(acts[a:b])).max()))
stats["verification"] = {"stories_checked": len(diffs), "max_abs_diff": max(diffs),
                         "mean_of_max_abs_diff": float(np.mean(diffs)),
                         "atol_used": d["tolerance_atol"], "passed": bool(max(diffs) <= d["tolerance_atol"])}
stats["wall_seconds"] = time.time() - t0
out_json = res / ("stage2_stats_smoke.json" if args.smoke else "stage2_stats.json")
out_json.write_text(json.dumps(stats, indent=2))
print(json.dumps(stats, indent=2))
