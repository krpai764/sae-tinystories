"""Stage 4: faithfulness of each SAE on held-out text.

Loss recovered = (L_base - L_spliced) / (L_base - L_clean), for base = zero-ablation (brief)
and base = mean-ablation (stricter). Bootstrap over held-out stories gives 95% intervals.
Writes results/stage4_faithfulness.json and figures/stage4_faithfulness.png.
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

from src.collect import load_split
from src.config import ROOT, get_device, load_config, set_seed
from src.eval import (const_replace, keep_pos0, loss_recovered, sae_replace, seqs_from_split,
                      story_losses)
from src.model import load_model
from src.sae import SparseAutoencoder
from src.train import load_activations

cfg = load_config()
set_seed(cfg["seed"])
device = get_device(cfg)
layer = cfg["model"]["layer"]
dd = ROOT / cfg["paths"]["data_dir"]
runs = json.loads((ROOT / cfg["paths"]["results_dir"] / "stage3_runs.json").read_text())
scale = runs["rescale_factor"]

model, tok = load_model(cfg, device=device)
_, tokens, _, _, offsets = load_split(dd, "heldout")
seqs = seqs_from_split(tokens, offsets)
mean_vec = load_activations(dd, "train").mean(0)  # training-set mean, original units, pos0 excluded
print(f"{len(seqs)} held-out stories, {sum(len(s) - 1 for s in seqs)} predicted tokens; device {device}", flush=True)

pad = tok.eos_token_id
run = lambda rep: story_losses(model, seqs, layer, device, rep, batch_size=8, pad_id=pad)  # batch 8: logits are 50k wide
clean = run(None)
conds = {"p0kept": keep_pos0, "all_positions": lambda f: f}  # how position 0 is treated
stories = {"clean": clean}
for tag, wrap in conds.items():
    stories[f"zero/{tag}"] = run(wrap(const_replace(None)))
    stories[f"mean/{tag}"] = run(wrap(const_replace(mean_vec)))
    print(f"baselines done ({tag})", flush=True)
    for lam in runs["runs"]:
        ck = torch.load(ROOT / cfg["paths"]["checkpoint_dir"] / "sae" / f"lam_{lam}" / "ckpt.pt",
                        map_location=device, weights_only=False)
        sae = SparseAutoencoder(ck["d"], ck["m"]).to(device)
        sae.load_state_dict(ck["sae"])
        sae.eval()
        stories[f"sae{lam}/{tag}"] = run(wrap(sae_replace(sae, scale)))
        print(f"  lam {lam} {tag} done", flush=True)

tot = lambda key, idx=slice(None): stories[key][0][idx].sum() / stories[key][1][idx].sum()
rng = np.random.default_rng(cfg["seed"])
boots = [rng.integers(0, len(seqs), len(seqs)) for _ in range(1000)]
ci = lambda f: [float(np.percentile([f(b) for b in boots], q)) for q in (2.5, 97.5)]

out = {"n_stories": len(seqs), "n_predicted_tokens": int(clean[1].sum()), "rescale_factor": scale,
       "device": device, "bootstrap_resamples": 1000,
       "L_clean": float(tot("clean")), "settings": {}}
for tag in conds:
    S = out["settings"][tag] = {"L_zero": float(tot(f"zero/{tag}")), "L_mean": float(tot(f"mean/{tag}")),
                                "saes": {}}
    for base in ("zero", "mean"):
        S[f"loss_ratio_{base}_over_clean"] = S[f"L_{base}"] / out["L_clean"]
    for lam, r in runs["runs"].items():
        key = f"sae{lam}/{tag}"
        e = {"L_spliced": float(tot(key)), "stage3": {k: r["final"][k] for k in
             ["variance_explained", "l0", "dead_fraction"]},
             "dead_fraction_last_train_epoch": r["epochs"][-1]["dead_fraction_train_epoch"]}
        for base in ("zero", "mean"):
            f = lambda b, base=base: loss_recovered(tot("clean", b), tot(f"{base}/{tag}", b), tot(key, b))
            e[f"loss_recovered_{base}"] = float(f(slice(None)))
            e[f"loss_recovered_{base}_ci95"] = ci(f)
        e["extra_loss_nats"] = e["L_spliced"] - out["L_clean"]
        S["saes"][lam] = e
(ROOT / cfg["paths"]["results_dir"] / "stage4_faithfulness.json").write_text(json.dumps(out, indent=2))

fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
for a, tag in zip(ax, conds):
    for base, mk in (("zero", "o"), ("mean", "s")):
        xs = [out["settings"][tag]["saes"][l]["stage3"]["l0"] for l in runs["runs"]]
        ys = [out["settings"][tag]["saes"][l][f"loss_recovered_{base}"] for l in runs["runs"]]
        lo = [out["settings"][tag]["saes"][l][f"loss_recovered_{base}_ci95"][0] for l in runs["runs"]]
        hi = [out["settings"][tag]["saes"][l][f"loss_recovered_{base}_ci95"][1] for l in runs["runs"]]
        a.errorbar(xs, ys, yerr=[np.array(ys) - lo, np.array(hi) - ys], marker=mk, capsize=3, label=f"{base}-ablation baseline")
        if base == "zero":
            for x, y, l in zip(xs, ys, runs["runs"]):
                a.annotate(f"λ={l}", (x, y), textcoords="offset points", xytext=(6, -12), fontsize=8)
    a.set(xscale="log", xlabel="L0 (active features per token)", title=f"position 0: {'kept real' if tag == 'p0kept' else 'also replaced'}")
    a.axhline(1, color="grey", lw=0.6)
ax[0].set_ylabel("loss recovered")
ax[0].legend()
fig.tight_layout()
fig.savefig(ROOT / cfg["paths"]["figures_dir"] / "stage4_faithfulness.png", dpi=120)
print(json.dumps(out, indent=1))
