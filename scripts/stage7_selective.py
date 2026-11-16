"""Stage 7 POST-HOC analysis (designed after seeing the first results): gender-selective features.

The pre-registered top-10 was dominated by context features that fire equally for both genders. Here a
feature is 'girl-selective' if its mean peak activation on girl ranking-name prompts (name-only) is at least
`selective_ratio` x that on boy ranking-name prompts (and vice versa). Selective features are ranked by their
ablation effect on their own gender's ranking names; the top `selective_k` are (a) ablated together on held-out
names vs random sets, and (b) used in the flip test. Writes results/stage7/selective.json.
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
from src.trace import ablate_features, add_vector

cfg = load_config(); tc = cfg["trace"]; set_seed(cfg["seed"])
layer, lam = cfg["model"]["layer"], cfg["interpret"]["chosen_lambda"]
scale = json.loads((ROOT / "results" / "stage3_runs.json").read_text())["rescale_factor"]
ck = torch.load(ROOT / "checkpoints" / "sae" / f"lam_{lam}" / "ckpt.pt", map_location="cpu", weights_only=False)
sae = SparseAutoencoder(ck["d"], ck["m"]); sae.load_state_dict(ck["sae"]); sae.eval()
model, tok = load_model(cfg, device="cpu")
od = ROOT / "results" / "stage7"
prompts = json.loads((od / "prompts.json").read_text())
E = np.load(od / "effects.npy"); firing = json.loads((od / "firing.json").read_text())
A = torch.load(od / "acts.pt"); acts, groups = A["acts"], A["groups"]
P, K, R = len(prompts), tc["selective_k"], tc["selective_ratio"]
tid = lambda w: tok(w).input_ids[0]
C = torch.tensor([tid(p["correct"]) for p in prompts]); W = torch.tensor([tid(p["wrong"]) for p in prompts])
is_ = lambda **kw: np.array([all(p[k] == v for k, v in kw.items()) for p in prompts])
NO, RK, HO = is_(kind="name_only"), is_(split="rank"), is_(split="heldout")
GM = {"girl": is_(gender="girl"), "boy": is_(gender="boy")}
OTHER = {"girl": "boy", "boy": "girl"}


@torch.no_grad()
def run(replace=None):
    sc = torch.zeros(P); top = torch.zeros(P, dtype=torch.long)
    for f, ix in groups.items():
        ids = torch.tensor([prompts[i]["ids"] for i in ix])
        if replace is None:
            lg = model(ids).logits[:, -1]
        else:
            with residual_hook(model, layer, replace=replace(f)):
                lg = model(ids).logits[:, -1]
        sc[ix] = lg.gather(1, C[ix, None])[:, 0] - lg.gather(1, W[ix, None])[:, 0]
        top[ix] = lg.argmax(-1)
    return sc.numpy(), top


clean, _ = run()
peak = np.zeros((sae.m, P), dtype=np.float32)   # peak activation of every feature on every prompt
for f, ix in groups.items():
    peak[:, ix] = acts[f].max(1).values.T.numpy()
mean_peak = {g: {s: peak[:, NO & m & GM[g]].mean(1) for s, m in (("rank", RK), ("heldout", HO))} for g in GM}

out = {"definition": f"selective = mean peak activation on own-gender ranking-name prompts >= {R}x other gender's (name-only prompts)",
       "post_hoc": True, "k": K, "sets": {}, "flip": []}
sel = {}
rng = np.random.default_rng(cfg["seed"] + 1)
drop = lambda idx: clean - run(lambda f: ablate_features(sae, scale, idx))[0]
for g in GM:
    o = OTHER[g]
    cand = [j for j in firing if mean_peak[g]["rank"][j] > 0 and mean_peak[g]["rank"][j] >= R * mean_peak[o]["rank"][j]]
    eff = E[:, NO & RK & GM[g]].mean(1)
    top = sorted(cand, key=lambda j: -eff[j])[:K]
    sel[g] = top
    d_top = drop(top)
    rsets = [rng.choice([j for j in firing if j not in top], K, replace=False).tolist() for _ in range(tc["n_random_sets"])]
    d_rand = np.stack([drop(s) for s in rsets])
    rec = {"n_selective_candidates": len(cand), "features": top, "per_feature": {}}
    for j in top:
        rec["per_feature"][str(j)] = {"rank_effect_own": float(eff[j]), "heldout_effect_own": float(E[j, NO & HO & GM[g]].mean()),
                                      "heldout_effect_other": float(E[j, NO & HO & GM[o]].mean()),
                                      "mean_peak_act": {f"{gg}_{s}": float(mean_peak[gg][s][j]) for gg in GM for s in ("rank", "heldout")},
                                      "heldout_names_peak_act": {n: float(peak[j, NO & is_(name=n)].mean()) for n in tc[f"{g}_names_heldout"]}}
    for tg in GM:
        m = NO & HO & GM[tg]; t, r = float(d_top[m].mean()), d_rand[:, m].mean(1)
        rec[f"heldout_{tg}_prompts"] = {"clean_score": float(clean[m].mean()), "drop": t, "score_after": float((clean - d_top)[m].mean()),
                                        "pair_accuracy_after": float(((clean - d_top)[m] > 0).mean()),
                                        "random_drop_mean": float(r.mean()), "random_drop_max": float(r.max()),
                                        "beats_n_random": int((t > r).sum()), "n_random": len(r)}
    m = NO & RK & GM[g]
    rec["ranking_names_own_gender_drop"] = float(d_top[m].mean()); rec["ranking_names_clean_score"] = float(clean[m].mean())
    out["sets"][g] = rec
    print(g, "selective:", len(cand), "top", top, "held-out own drop %.2f (random mean %.2f, beats %d/100); other-gender drop %.2f; ranking-names drop %.2f" % (
        rec[f"heldout_{g}_prompts"]["drop"], rec[f"heldout_{g}_prompts"]["random_drop_mean"], rec[f"heldout_{g}_prompts"]["beats_n_random"],
        rec[f"heldout_{o}_prompts"]["drop"], rec["ranking_names_own_gender_drop"]), flush=True)

# ---- flip test with selective features ----
D = sae.W_d.detach(); g2 = torch.Generator().manual_seed(cfg["seed"] + 78)
for target in GM:
    source = OTHER[target]
    prof = {}
    for f, ix in groups.items():
        src = [n for n, i in enumerate(ix) if prompts[i]["gender"] == source and prompts[i]["split"] == "rank"]
        prof[f] = acts[f][src].mean(0)[:, sel[source]] @ D[:, sel[source]].T / scale
    for s in tc["flip_strengths"]:
        def vec(f, v=None):
            z = torch.zeros(prof[f].shape[0] + 1, prof[f].shape[1]); z[1:] = s * prof[f] if v is None else v
            return z
        runs = {"feature_add": run(lambda f: add_vector(vec(f))),
                "feature_swap": run(lambda f: (lambda h, f=f: ablate_features(sae, scale, sel[target])(h) + vec(f))),
                "ablate_own_only": run(lambda f: ablate_features(sae, scale, sel[target]))}
        rs = []
        for _ in range(tc["flip_random_draws"]):
            rv = {}
            for f in groups:
                r = torch.randn(prof[f].shape, generator=g2)
                rv[f] = r / r.norm(dim=-1, keepdim=True) * (s * prof[f]).norm(dim=-1, keepdim=True)
            rs.append(run(lambda f: add_vector(vec(f, rv[f]))))
        for kind in ("name_only", "noun_name"):
            m = is_(kind=kind, split="heldout", gender=target); mt = torch.from_numpy(m)
            rec = {"target_prompts": target, "added_features_of": source, "added_features": sel[source], "strength": s, "prompt_kind": kind,
                   "n": int(m.sum()), "clean_score": float(clean[m].mean()),
                   "max_added_norm_model_units": float(max((s * prof[f]).norm(dim=-1).max() for f in groups))}
            for name, (sc, tp) in runs.items():
                rec[name] = {"score": float(sc[m].mean()), "flip_rate_pair": float((sc[m] < 0).mean()),
                             "top1_is_other_pronoun": float((tp[mt] == W[mt]).float().mean())}
            rec["random_add"] = {"score": float(np.mean([x[0][m].mean() for x in rs])), "flip_rate_pair": float(np.mean([(x[0][m] < 0).mean() for x in rs])),
                                 "top1_is_other_pronoun": float(np.mean([(x[1][mt] == W[mt]).float().mean() for x in rs]))}
            out["flip"].append(rec)
            if kind == "name_only":
                print(target, "<-", source, "s", s, {n: (round(rec[n]["score"], 2), round(rec[n]["flip_rate_pair"], 3), round(rec[n]["top1_is_other_pronoun"], 3)) for n in ("feature_add", "feature_swap", "random_add")}, "norm %.2f" % rec["max_added_norm_model_units"], flush=True)
(od / "selective.json").write_text(json.dumps(out, indent=1))
