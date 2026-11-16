"""Stage 6: steering with SAE decoder directions, plus a random-direction control.

Feature selection (fixed in config.yaml `steering`): features labelled clear under the strict rule
in Stage 5 that also scored 5/5 on the blind test, plus 2 features that were NOT clear (weak labels).

Steering: during generation add  alpha * s * d / c  to the residual stream after block `layer` at every
position except the EOS prefix, where d is the feature's unit decoder direction (SAE units), s is the
feature's typical strong firing (mean of its top-20 activations on train, from Stage 5), alpha is the
multiplier (2, 5, 10, plus larger values to find where text breaks), and c is the rescale factor
(converts SAE units back to model units). Control: a random unit direction (fixed seed per feature)
with the same norm.

Measures per generation:
  - promoted_hits: count of the feature's top-10 promoted tokens among generated tokens
  - ppl_clean: perplexity of the generated text under the UNSTEERED model (high = broken text)
Writes results/stage6/steering.json and results/stage6/steering.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch

from src.config import ROOT, load_config, set_seed
from src.model import load_model, residual_hook
from src.sae import SparseAutoencoder

cfg = load_config()
sc = cfg["steering"]
set_seed(cfg["seed"])
layer, lam = cfg["model"]["layer"], cfg["interpret"]["chosen_lambda"]
scale = json.loads((ROOT / "results" / "stage3_runs.json").read_text())["rescale_factor"]
ck = torch.load(ROOT / "checkpoints" / "sae" / f"lam_{lam}" / "ckpt.pt", map_location="cpu", weights_only=False)
sae = SparseAutoencoder(ck["d"], ck["m"])
sae.load_state_dict(ck["sae"])
model, tok = load_model(cfg, device="cpu")
feats = {f["feature"]: f for f in json.loads((ROOT / "results" / "stage5" / "features.json").read_text())["features"]}
labels = {}
import csv
with open(ROOT / "results" / "stage5_blind_per_feature.csv") as fh:
    for r in csv.DictReader(fh):
        if r["set"] == "real":
            labels[int(r["feature"])] = r
eos = tok.eos_token_id


def gen(prompt, vec, seed):
    ids = torch.tensor([[eos] + tok(prompt).input_ids])

    def add(h):
        if vec is None:
            return h
        h = h.clone()
        start = 1 if h.shape[1] > 1 else 0  # skip EOS prefix on the first (full-prompt) pass
        h[:, start:] += vec
        return h

    torch.manual_seed(seed)
    with torch.no_grad(), residual_hook(model, layer, replace=add):
        out = model.generate(ids, max_new_tokens=sc["max_new_tokens"], do_sample=True,
                             temperature=cfg["generation"]["temperature"], top_k=50,
                             pad_token_id=eos, attention_mask=torch.ones_like(ids))
    return ids.shape[1], out[0]


@torch.no_grad()
def ppl_clean(seq, n_prompt):
    logits = model(seq[None]).logits[0, :-1]
    lp = torch.log_softmax(logits, -1).gather(1, seq[1:, None])[:, 0]
    return float(torch.exp(-lp[n_prompt - 1:].mean()))


results = []
groups = [("clear_5of5", f) for f in sc["clear_features"]] + [("not_clear", f) for f in sc["unclear_features"]]
if "--smoke" in sys.argv:  # one feature, one prompt, written to a separate file
    groups, sc["prompts"] = groups[:1], sc["prompts"][:1]
for group, fid in groups:
    f = feats[fid]
    s = sum(e["act"] for e in f["top"]) / len(f["top"])
    d = sae.W_d.detach()[:, fid]
    g = torch.Generator().manual_seed(cfg["seed"] + fid)
    rdir = torch.randn(d.shape, generator=g)
    rdir /= rdir.norm()
    promoted = set(tok.convert_tokens_to_ids(tok.tokenize(t))[0] for t in f["promoted_tokens"])
    rec = {"feature": fid, "group": group, "label": labels[fid]["label"],
           "blind_correct_of_5": int(labels[fid]["correct_of_5"]), "typical_strength_sae_units": s,
           "promoted_tokens": f["promoted_tokens"], "runs": []}
    for pi, prompt in enumerate(sc["prompts"]):
        for kind, alpha in [("none", 0)] + [(k, a) for a in sc["multipliers"] for k in ("feature", "random")]:
            if kind == "none":
                vec = None
            else:
                vec = alpha * s * (d if kind == "feature" else rdir) / scale
            n_p, seq = gen(prompt, vec, cfg["generation"]["seed"] + pi)
            new = seq[n_p:]
            rec["runs"].append({
                "prompt_index": pi, "kind": kind, "multiplier": alpha,
                "vector_norm_model_units": 0.0 if vec is None else float(vec.norm()),
                "text": tok.decode(new, skip_special_tokens=True),
                "promoted_hits": int(sum(int(t) in promoted for t in new)),
                "ppl_clean": ppl_clean(seq, n_p),
            })
    results.append(rec)
    print(f"done feature {fid} ({group})", flush=True)

od = ROOT / "results" / "stage6"
od.mkdir(parents=True, exist_ok=True)
mean_norm = 16 / scale  # mean activation norm in model units (rescaling sets it to sqrt(256)=16)
(od / ("steering_smoke.json" if "--smoke" in sys.argv else "steering.json")).write_text(json.dumps({
    "layer": layer, "lambda": lam, "rescale_factor": scale, "mean_activation_norm_model_units": mean_norm,
    "selection": "strictly clear in Stage 5 AND 5/5 on the blind test (clear_5of5); plus 2 not-clear features",
    "prompts": sc["prompts"], "multipliers": sc["multipliers"], "seed": cfg["generation"]["seed"],
    "features": results}, indent=1, ensure_ascii=False))
print("wrote", od)
