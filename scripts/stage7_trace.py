"""Stage 7: which layer-3 SAE features does 'she'/'he' after a named character depend on?

Score per prompt = logit(correct pronoun) - logit(wrong pronoun) at the last position.
Steps: (1) clean / reconstruction-only scores; (2) ablate every firing feature one at a time
(zero it at all positions > 0, decode, add SAE error back) on all prompts.
Writes results/stage7/prompts.json, baseline.json, effects.npy (features x prompts), acts.pt.
Resumable: effects are saved every 100 features.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from src.config import ROOT, load_config, set_seed
from src.model import load_model, residual_hook
from src.sae import SparseAutoencoder
from src.trace import ablate_features, reconstruct_only

cfg = load_config(); tc = cfg["trace"]; set_seed(cfg["seed"])
layer, lam = cfg["model"]["layer"], cfg["interpret"]["chosen_lambda"]
scale = json.loads((ROOT / "results" / "stage3_runs.json").read_text())["rescale_factor"]
ck = torch.load(ROOT / "checkpoints" / "sae" / f"lam_{lam}" / "ckpt.pt", map_location="cpu", weights_only=False)
sae = SparseAutoencoder(ck["d"], ck["m"]); sae.load_state_dict(ck["sae"]); sae.eval()
model, tok = load_model(cfg, device="cpu")
od = ROOT / "results" / "stage7"; od.mkdir(parents=True, exist_ok=True)
PRON = {("girl", "cap"): (" She", " He"), ("boy", "cap"): (" He", " She"),
        ("girl", "lower"): (" she", " he"), ("boy", "lower"): (" he", " she")}
tid = lambda w: tok(w).input_ids[0]

prompts = []
for fr in tc["frames"]:
    for g in ("girl", "boy"):
        for split in ("rank", "heldout"):
            for n in tc[f"{g}_names_{split}"]:
                assert len(tok(" " + n).input_ids) == 1, n
                text = fr["text"].replace("{N}", n).replace("{G}", g)
                c, w = PRON[(g, fr["case"])]
                prompts.append({"frame": fr["id"], "kind": fr["kind"], "gender": g, "split": split, "name": n,
                                "text": text, "ids": [tok.eos_token_id] + tok(text).input_ids, "correct": c, "wrong": w})
frames = [fr["id"] for fr in tc["frames"]]
groups = {f: [i for i, p in enumerate(prompts) if p["frame"] == f] for f in frames}
for f, ix in groups.items():
    assert len({len(prompts[i]["ids"]) for i in ix}) == 1, f  # same length within a frame -> no padding
(od / "prompts.json").write_text(json.dumps(prompts, indent=1))
C = torch.tensor([tid(p["correct"]) for p in prompts]); W = torch.tensor([tid(p["wrong"]) for p in prompts])


@torch.no_grad()
def run(replace=None, want_top=False):
    """Score for every prompt; replace = fn(frame_id) -> hook fn, or None."""
    sc = torch.zeros(len(prompts)); top = torch.zeros(len(prompts), dtype=torch.long)
    for f, ix in groups.items():
        ids = torch.tensor([prompts[i]["ids"] for i in ix])
        if replace is None:
            lg = model(ids).logits[:, -1]
        else:
            with residual_hook(model, layer, replace=replace(f)):
                lg = model(ids).logits[:, -1]
        sc[ix] = lg.gather(1, C[ix, None])[:, 0] - lg.gather(1, W[ix, None])[:, 0]
        top[ix] = lg.argmax(-1)
    return (sc, top) if want_top else sc


# ---- step 1: baselines ----
clean, top = run(want_top=True)
ident = run(lambda f: ablate_features(sae, scale, []))
recon = run(lambda f: reconstruct_only(sae, scale))
assert torch.allclose(clean, ident, atol=1e-3), "splicing with error added must equal the clean model"
base = {"n_prompts": len(prompts), "identity_max_abs_diff": float((clean - ident).abs().max())}
for key, m in [("all", [True] * len(prompts))] + [(f"{k}/{g}", [p["kind"] == k and p["gender"] == g for p in prompts])
                                                  for k in ("name_only", "noun_name") for g in ("girl", "boy")] + \
              [(k, [p["kind"] == k for p in prompts]) for k in ("name_only", "noun_name")]:
    m = torch.tensor(m)
    base[key] = {"n": int(m.sum()), "clean_score": float(clean[m].mean()), "clean_pair_accuracy": float((clean[m] > 0).float().mean()),
                 "clean_top1_is_correct": float((top[m] == C[m]).float().mean()),
                 "recon_only_score": float(recon[m].mean()), "recon_only_pair_accuracy": float((recon[m] > 0).float().mean())}
base["per_name_clean_score_name_only"] = {n: float(np.mean([clean[i] for i, p in enumerate(prompts) if p["name"] == n and p["kind"] == "name_only"]))
                                          for n in sorted({p["name"] for p in prompts})}
(od / "baseline.json").write_text(json.dumps(base, indent=1))
print(json.dumps({k: v for k, v in base.items() if k != "per_name_clean_score_name_only"}, indent=1))
print(base["per_name_clean_score_name_only"], flush=True)
if "--baseline-only" in sys.argv:
    sys.exit()

# ---- feature activations on every prompt (frames have aligned positions) ----
acts = {}
with torch.no_grad():
    for f, ix in groups.items():
        store = []
        with residual_hook(model, layer, store=store):
            model(torch.tensor([prompts[i]["ids"] for i in ix]))
        acts[f] = sae.encode(store[0][:, 1:] * scale)  # (n, seq-1, m), positions 1..
torch.save({"acts": acts, "groups": groups}, od / "acts.pt")
fires = torch.zeros(sae.m, dtype=torch.bool)
for f in frames:
    fires |= (acts[f] > 0).any(0).any(0)
firing = torch.nonzero(fires)[:, 0].tolist()
print(f"{len(firing)}/{sae.m} features fire on at least one prompt", flush=True)

# ---- step 2: single-feature ablations ----
ef = od / "effects.npy"
E = np.load(ef) if ef.exists() else np.full((sae.m, len(prompts)), np.nan, dtype=np.float32)
E[~fires.numpy()] = 0.0  # a feature that never fires has exactly zero effect
for k, j in enumerate(firing):
    if not np.isnan(E[j]).any():
        continue
    E[j] = (clean - run(lambda f, j=j: ablate_features(sae, scale, [j]))).numpy()  # + = feature supports the correct pronoun
    if k % 100 == 0:
        np.save(ef, E); print(f"ablated {k}/{len(firing)}", flush=True)
np.save(ef, E)
np.save(od / "clean_scores.npy", clean.numpy())
(od / "firing.json").write_text(json.dumps(firing))
print("done", flush=True)
