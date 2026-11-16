"""Stage 3 pilot: short runs over a wide lambda grid, NO resampling, to find the lambda range
giving ~5-60 active features/token and to watch whether dead features climb with repeated epochs.

Usage:
  python scripts/stage3_pilot.py --smoke            # 100k tokens, 2 epochs, checks the code
  caffeinate -i python scripts/stage3_pilot.py      # full pilot (resumable)
Writes results/stage3_pilot.json (+ _smoke), figures/stage3_pilot.png, checkpoints/pilot/.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

from src.config import ROOT, get_device, load_config, set_seed
from src.train import load_activations, rescale_factor, train_sae

ap = argparse.ArgumentParser()
ap.add_argument("--smoke", action="store_true")
args = ap.parse_args()

cfg = load_config()
p = cfg["sae_pilot"]
set_seed(cfg["seed"])
device = get_device(cfg)
dd = ROOT / cfg["paths"]["data_dir"]
x_train = load_activations(dd, "train")
x_eval = load_activations(dd, "heldout")
c = rescale_factor(x_train)  # computed on train only
x_train *= c
x_eval *= c
epochs = p["epochs"]
lams = p["lambdas"]
if args.smoke:
    x_train, x_eval, epochs, lams = x_train[:100_000], x_eval[:20_000], 2, lams[:2]
print(f"device {device}; train {tuple(x_train.shape)}, eval {tuple(x_eval.shape)}; rescale factor {c:.4f}")

tag = "pilot_smoke" if args.smoke else "pilot"
results = {"rescale_factor": c, "epochs": epochs, "batch_size": cfg["sae"]["batch_size"],
           "lr": cfg["sae"]["lr"], "seed": cfg["seed"], "resampling": False,
           "train_tokens": len(x_train), "eval_tokens": len(x_eval), "runs": {}}
for lam in lams:
    out = train_sae(x_train, x_eval, lam, cfg, ROOT / cfg["paths"]["checkpoint_dir"] / tag / f"lam_{lam}",
                    epochs, device, cfg["seed"])
    results["runs"][str(lam)] = {"final": out["final"], "epochs": out["hist"]["epochs"],
                                 "b_d_init": out["hist"].get("b_d_init")}
    del out
    if device == "mps":
        torch.mps.empty_cache()

res = ROOT / cfg["paths"]["results_dir"]
(res / f"stage3_{tag}.json").write_text(json.dumps(results, indent=2))

if not args.smoke:
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for lam, r in results["runs"].items():
        e = [x["epoch"] for x in r["epochs"]]
        ax[0].plot(e, [x["dead_fraction_train_epoch"] for x in r["epochs"]], marker="o", label=f"λ={lam}")
        ax[1].plot(e, [x["l0"] for x in r["epochs"]], marker="o", label=f"λ={lam}")
        ax[2].scatter(r["final"]["l0"], r["final"]["variance_explained"], s=40)
        ax[2].annotate(f"λ={lam}", (r["final"]["l0"], r["final"]["variance_explained"]),
                       textcoords="offset points", xytext=(5, 3))
    ax[0].set(xlabel="epoch", ylabel="fraction of features dead in epoch", title="Dead features per epoch (no resampling)")
    ax[1].set(xlabel="epoch", ylabel="L0 (held-out)", yscale="log", title="Active features per token")
    ax[2].set(xlabel="L0 (held-out)", ylabel="variance explained (held-out)", xscale="log", title="Sparsity vs reconstruction")
    ax[2].axvspan(5, 60, alpha=0.1, color="green")
    ax[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ROOT / cfg["paths"]["figures_dir"] / "stage3_pilot.png", dpi=120)
print(json.dumps({k: {kk: round(vv, 4) for kk, vv in v["final"].items()} for k, v in results["runs"].items()}, indent=1))
