"""Stage 3: train the four SAEs (lambdas from config), 20 epochs, Bricken resampling.

Usage: caffeinate -i python scripts/stage3_train.py   (resumable: rerun to continue)
Writes checkpoints/sae/lam_*/, results/stage3_runs.json, figures/stage3_*.png
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from src.config import ROOT, get_device, load_config, set_seed
from src.train import load_activations, rescale_factor, train_sae

cfg = load_config()
s = cfg["sae"]
set_seed(cfg["seed"])
device = get_device(cfg)
dd = ROOT / cfg["paths"]["data_dir"]
x_train = load_activations(dd, "train")
x_eval = load_activations(dd, "heldout")
c = rescale_factor(x_train)
x_train *= c
x_eval *= c
print(f"device {device}; train {tuple(x_train.shape)}; eval {tuple(x_eval.shape)}; rescale {c:.4f}", flush=True)

res, figs = ROOT / cfg["paths"]["results_dir"], ROOT / cfg["paths"]["figures_dir"]
out = {"rescale_factor": c, "seed": cfg["seed"], "settings": {k: s[k] for k in
       ["expansion", "lr", "batch_size", "epochs", "resample_after_epochs", "resample_pool", "enc_init_scale"]},
       "train_tokens": len(x_train), "eval_tokens": len(x_eval), "runs": {}}
for lam in s["l1_coeffs"]:
    r = train_sae(x_train, x_eval, lam, cfg, ROOT / cfg["paths"]["checkpoint_dir"] / "sae" / f"lam_{lam}",
                  s["epochs"], device, cfg["seed"], tuple(s["resample_after_epochs"]), s["resample_pool"],
                  log=lambda m: print(m, flush=True))
    l0 = [e["l0"] for e in r["hist"]["epochs"]]
    rel = [abs(l0[i] - l0[i - 1]) / l0[i - 1] for i in range(len(l0) - 3, len(l0))]
    out["runs"][str(lam)] = {"final": r["final"], "epochs": r["hist"]["epochs"],
                             "b_d_init": r["hist"].get("b_d_init"),
                             "l0_rel_change_last3": rel,
                             "l0_levelled_off": bool(max(rel) < s["l0_plateau_rel_change"]),
                             "total_resampled": sum(e["resampled"] for e in r["hist"]["epochs"])}
    del r
    if device == "mps":
        torch.mps.empty_cache()
    (res / "stage3_runs.json").write_text(json.dumps(out, indent=2))

# ---- figures ----
runs = out["runs"]
fig, ax = plt.subplots(2, 2, figsize=(12, 8))
for lam, r in runs.items():
    e = [x["epoch"] for x in r["epochs"]]
    ax[0, 0].plot(e, [x["variance_explained"] for x in r["epochs"]], marker=".", label=f"λ={lam}")
    ax[0, 1].plot(e, [x["l0"] for x in r["epochs"]], marker=".", label=f"λ={lam}")
    ax[1, 0].plot(e, [x["dead_fraction_train_epoch"] for x in r["epochs"]], marker=".", label=f"λ={lam}")
    h = json.loads((ROOT / cfg["paths"]["checkpoint_dir"] / "sae" / f"lam_{lam}" / "history.json").read_text())
    ax[1, 1].plot([x["step"] for x in h["steps"]], [x["loss"] for x in h["steps"]], lw=0.7, label=f"λ={lam}")
for ep in s["resample_after_epochs"]:
    ax[1, 0].axvline(ep, color="grey", ls=":", lw=0.8)
ax[0, 0].set(xlabel="epoch", ylabel="variance explained (held-out)", title="Reconstruction")
ax[0, 1].set(xlabel="epoch", ylabel="L0 (held-out)", yscale="log", title="Active features per token")
ax[1, 0].set(xlabel="epoch", ylabel="fraction dead in training epoch", title="Dead features (dotted = resampling)")
ax[1, 1].set(xlabel="step", ylabel="training loss", yscale="log", title="Training loss (every 50 steps)")
ax[0, 0].legend()
fig.tight_layout()
fig.savefig(figs / "stage3_training.png", dpi=120)

fig, ax = plt.subplots(figsize=(7, 4))
for lam in runs:
    dens = np.load(ROOT / cfg["paths"]["checkpoint_dir"] / "sae" / f"lam_{lam}" / "density_heldout.npy")
    ax.hist(np.log10(dens[dens > 0]), bins=60, histtype="step", label=f"λ={lam} ({(dens == 0).sum()} never fire)")
ax.set(xlabel="log10 firing frequency on held-out (200k tokens)", ylabel="features", title="Feature density")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(figs / "stage3_density.png", dpi=120)
print("done", flush=True)
