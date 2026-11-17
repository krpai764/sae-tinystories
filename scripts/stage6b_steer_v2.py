"""Review rerun 1a: steering in units of each feature's MEDIAN non-zero firing, 10 prompts, 3 random directions.

Design, label-word lists and success rule are in config.yaml `steering_v2` (committed before this ran).
For every (feature, prompt) one batch is generated: row 0 unsteered, then for each strength k one feature-steered row
and n_random_directions random-direction rows of the same length. Vector = k * median_act * direction / rescale, added at
every position except the EOS prefix. Per row: text (cut at the first end-of-text token), label-word count, and
perplexity of the generated tokens under the UNSTEERED model.
Writes results/stage6b/steering_v2.json (resumable per feature). --smoke: one feature, one prompt, separate file.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch

from src.config import ROOT, load_config, set_seed
from src.model import load_model, residual_hook
from src.sae import SparseAutoencoder

cfg = load_config(); sc = dict(cfg["steering_v2"]); set_seed(cfg["seed"])
V3 = "--v3" in sys.argv   # third design: strength = fraction of the mean activation length (config steering_v3); all else as v2
if V3:
    sc["multipliers"] = cfg["steering_v3"]["multipliers"]
    MEAN_NORM = json.loads((ROOT / "results" / "stage2_stats.json").read_text())["splits"]["train"]["norm_excluding_pos0"]["mean"]
SMOKE = "--smoke" in sys.argv
layer, lam = cfg["model"]["layer"], cfg["interpret"]["chosen_lambda"]
scale = json.loads((ROOT / "results" / "stage3_runs.json").read_text())["rescale_factor"]
ck = torch.load(ROOT / "checkpoints" / "sae" / f"lam_{lam}" / "ckpt.pt", map_location="cpu", weights_only=False)
sae = SparseAutoencoder(ck["d"], ck["m"]); sae.load_state_dict(ck["sae"])
model, tok = load_model(cfg, device="cpu")
feats = {f["feature"]: f for f in json.loads((ROOT / "results" / "stage5" / "features.json").read_text())["features"]}
eos = tok.eos_token_id
od = ROOT / "results" / "stage6b"; od.mkdir(parents=True, exist_ok=True)
out_path = od / ("steering_v2_smoke.json" if SMOKE else "steering_v3.json" if V3 else "steering_v2.json")
K, NR, T = sc["multipliers"], sc["n_random_directions"], sc["max_new_tokens"]
groups = [(g, f) for g, fs in sc["groups"].items() for f in fs]
prompts = sc["prompts"]
if SMOKE:
    groups, prompts = groups[:1], prompts[:1]
done = json.loads(out_path.read_text()) if out_path.exists() and not SMOKE else {"features": []}
have = {f["feature"] for f in done["features"]}
words = lambda t: re.findall(r"[a-z]+", t.lower())

for group, fid in groups:
    if fid in have:
        continue
    med = feats[fid]["median_act"]
    d = sae.W_d.detach()[:, fid]
    g = torch.Generator().manual_seed(cfg["seed"] + 5000 + fid)
    rd = torch.randn(NR, d.shape[0], generator=g); rd /= rd.norm(dim=1, keepdim=True)
    meta, V = [("none", None, 0)], [torch.zeros_like(d)]
    for k in K:
        meta.append(("feature", None, k)); V.append(k * med * d / scale)
        for r in range(NR):
            meta.append(("random", r, k)); V.append(k * med * rd[r] / scale)
    V = torch.stack(V)
    # v3: rescale every steering vector so that |vector| = k x mean activation length
    if V3:
        V = torch.stack([V[0]] + [v / v.norm() * k * MEAN_NORM for v, (_, _, k) in zip(V[1:], meta[1:])])
    W = set(sc["label_words"][fid])
    rec = {"feature": fid, "group": group, "median_act": med, "label_words": sorted(W), "rows": [],
           "vector_norm_model_units": {str(k): float(k * MEAN_NORM if V3 else k * med / scale) for k in K}}
    for pi, prompt in enumerate(prompts):
        ids = torch.tensor([[eos] + tok(prompt).input_ids]).repeat(len(V), 1)
        n_p = ids.shape[1]

        def add(h):
            h = h.clone()
            s0 = 1 if h.shape[1] > 1 else 0   # skip the EOS prefix on the first (full-prompt) pass
            h[:, s0:] += V[:, None, :]
            return h

        torch.manual_seed(cfg["seed"] + 100 * fid + pi)
        with torch.no_grad(), residual_hook(model, layer, replace=add):
            out = model.generate(ids, max_new_tokens=T, do_sample=True, temperature=cfg["generation"]["temperature"], top_k=50,
                                 pad_token_id=eos, attention_mask=torch.ones_like(ids))
        with torch.no_grad():
            lp = torch.log_softmax(model(out).logits[:, :-1], -1).gather(2, out[:, 1:, None])[:, :, 0]  # lp[:, i] scores token i+1
        for row, (kind, r, k) in enumerate(meta):
            new = out[row, n_p:]
            cut = (new == eos).nonzero()
            n = int(cut[0]) if len(cut) else len(new)
            text = tok.decode(new[:n])
            rec["rows"].append({"p": pi, "kind": kind, "r": r, "k": k, "text": text, "n_tokens": n, "hits": sum(w in W for w in words(text)),
                                "ppl": float(torch.exp(-lp[row, n_p - 1:n_p - 1 + n].mean())) if n else None})
    done["features"].append(rec)
    if not SMOKE:
        out_path.write_text(json.dumps({"prompts": prompts, "multipliers": K, "n_random": NR, "rescale_factor": scale, **done}, indent=1, ensure_ascii=False))
    print(f"done feature {fid} ({group}); rows {len(rec['rows'])}", flush=True)
if SMOKE:
    r = done["features"][0]["rows"]
    print("smoke rows", len(r), "kinds", sorted({x["kind"] for x in r}), "ppl finite", sum(x["ppl"] is not None for x in r),
          "n_tokens min/max", min(x["n_tokens"] for x in r), max(x["n_tokens"] for x in r))
