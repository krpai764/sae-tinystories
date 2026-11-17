"""Stage 7 analysis: rank features on the ranking names, test on held-out names, joint top-k vs random
sets, per-gender breakdown, and (if the top-k test passes) the flip test.
Reads results/stage7/{prompts.json,effects.npy,acts.pt,firing.json}; writes results/stage7/analysis.json,
results/stage7/flip.json, results/stage7/top_feature_examples.json.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from src.collect import load_split
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
P = len(prompts); K = tc["top_k"]
tid = lambda w: tok(w).input_ids[0]
C = torch.tensor([tid(p["correct"]) for p in prompts]); W = torch.tensor([tid(p["wrong"]) for p in prompts])
is_ = lambda **kw: np.array([all(p[k] == v for k, v in kw.items()) for p in prompts])
NO, RK, HO, G, B = is_(kind="name_only"), is_(split="rank"), is_(split="heldout"), is_(gender="girl"), is_(gender="boy")


@torch.no_grad()
def run(replace=None):
    sc = torch.zeros(P); top = torch.zeros(P, dtype=torch.long)
    for f, ix in groups.items():
        ids = torch.tensor([prompts[i]["ids"] for i in ix])
        if replace is None:
            lg = model(ids).logits[:, -1]
        else:
            with residual_hook(model, layer, replace=replace(f, ix)):
                lg = model(ids).logits[:, -1]
        sc[ix] = lg.gather(1, C[ix, None])[:, 0] - lg.gather(1, W[ix, None])[:, 0]
        top[ix] = lg.argmax(-1)
    return sc.numpy(), top


clean, clean_top = run()
masks = {"overall": NO & HO, "girl": NO & HO & G, "boy": NO & HO & B}
rank_scores = {"overall": E[:, NO & RK].mean(1), "girl": E[:, NO & RK & G].mean(1), "boy": E[:, NO & RK & B].mean(1)}
tops = {k: np.argsort(-v)[:K].tolist() for k, v in rank_scores.items()}

# ---- Stage 5 labels where available ----
labels = {}
with open(ROOT / "results" / "stage5_blind_per_feature.csv") as fh:
    for r in csv.DictReader(fh):
        if r["set"] == "real":
            labels[int(r["feature"])] = {"label": r["label"], "final_clear": r["final_clear"], "blind": int(r["correct_of_5"])}


def describe(j):
    """Where the feature fires on the test prompts: mean activation by gender, and its main token position."""
    g = np.mean([acts[p["frame"]][groups[p["frame"]].index(i), :, j].max().item() for i, p in enumerate(prompts) if p["gender"] == "girl"])
    b = np.mean([acts[p["frame"]][groups[p["frame"]].index(i), :, j].max().item() for i, p in enumerate(prompts) if p["gender"] == "boy"])
    pos_tokens = {}
    for i, p in enumerate(prompts):
        a = acts[p["frame"]][groups[p["frame"]].index(i), :, j]
        if a.max() > 0:
            t = tok.decode([p["ids"][1 + int(a.argmax())]])
            t = "<name>" if t.strip() == p["name"] else t
            pos_tokens[t] = pos_tokens.get(t, 0) + 1
    return {"mean_peak_act_girl_prompts": float(g), "mean_peak_act_boy_prompts": float(b),
            "peak_token_counts": dict(sorted(pos_tokens.items(), key=lambda kv: -kv[1])[:4]),
            "stage5_label_AI_written": labels.get(j)}


res = {"n_firing": len(firing), "top_k": K, "tops": tops, "features": {}, "joint": {}}
others = {k: [j for j in firing if j not in tops[k]] for k in tops}
for j in sorted(set(sum(tops.values(), []))):
    d = {"rank_effect": {k: float(rank_scores[k][j]) for k in tops}, "heldout_effect": {k: float(E[j, m].mean()) for k, m in masks.items()},
         "in_top": [k for k in tops if j in tops[k]], **describe(j)}
    d["heldout_percentile_among_firing"] = {k: float((E[firing][:, m].mean(1) < E[j, m].mean()).mean()) for k, m in masks.items()}
    res["features"][str(j)] = d

# ---- joint ablation: top-K together vs random sets of K firing features ----
rng = np.random.default_rng(cfg["seed"])
drop = lambda idx: clean - run(lambda f, ix: ablate_features(sae, scale, idx))[0]
for key in tops:
    d_top = drop(tops[key])
    rsets = [rng.choice(others[key], K, replace=False).tolist() for _ in range(tc["n_random_sets"])]
    d_rand = np.stack([drop(s) for s in rsets])
    out = {"features": tops[key]}
    for mk, m in masks.items():
        t, r = float(d_top[m].mean()), d_rand[:, m].mean(1)
        out[mk] = {"clean_score": float(clean[m].mean()), "top_drop": t, "score_after_top_ablation": float((clean - d_top)[m].mean()),
                   "pair_accuracy_after": float(((clean - d_top)[m] > 0).mean()),
                   "random_drop_mean": float(r.mean()), "random_drop_max": float(r.max()), "random_drop_p95": float(np.quantile(r, .95)),
                   "top_beats_n_random": int((t > r).sum()), "n_random": len(r)}
    out["noun_name_heldout_drop"] = float(d_top[~NO & HO].mean())
    res["joint"][key] = out
    print(key, tops[key], {mk: (round(out[mk]["top_drop"], 2), round(out[mk]["random_drop_mean"], 3), out[mk]["top_beats_n_random"]) for mk in masks}, flush=True)
passed = res["joint"]["overall"]["overall"]["top_beats_n_random"] >= tc["pass_fraction"] * tc["n_random_sets"]
res["top_k_test_passed"] = bool(passed)
(od / "analysis.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
print("top-k test passed:", passed, flush=True)

# ---- top examples from the training text for the top features ----
want = sorted(set(sum(tops.values(), [])))
tacts, tokens, story, pos, offsets = load_split(ROOT / "data", "train")
rows = np.nonzero(pos > 0)[0]
We, be, bd = sae.W_e.detach()[want], sae.b_e.detach()[want], sae.b_d.detach()
best = [[] for _ in want]; count = np.zeros(len(want))
with torch.no_grad():
    for a in range(0, len(rows), 65536):
        r = rows[a:a + 65536]
        f = torch.relu((torch.from_numpy(np.asarray(tacts[r]).astype(np.float32)) * scale - bd) @ We.T + be)
        count += (f > 0).sum(0).numpy()
        v, i = f.topk(12, 0)
        for c in range(len(want)):
            best[c] = sorted(best[c] + list(zip(v[:, c].tolist(), r[i[:, c].numpy()].tolist())), reverse=True)[:12]


def snippet(row):
    s = story[row]; a = max(offsets[s] + 1, row - 12); b = min(offsets[s + 1], row + 4)
    return (tok.decode(tokens[a:row]) + "[[" + tok.decode(tokens[row:row + 1]) + "]]" + tok.decode(tokens[row + 1:b])).replace("\n", "⏎")


ex = {str(j): {"firing_frequency": float(count[c] / len(rows)), "top": [{"act": v, "text": snippet(r)} for v, r in best[c]]} for c, j in enumerate(want)}
(od / "top_feature_examples.json").write_text(json.dumps(ex, indent=1, ensure_ascii=False))

# ---- flip test ----
if not passed:
    print("flip test skipped (top-k test failed)"); sys.exit()
OPP = {" She": " He", " He": " She", " she": " he", " he": " she"}
Wtop = torch.tensor([tid(p["wrong"]) for p in prompts])
D = sae.W_d.detach()
flip = {"note": "target prompts = held-out names; activation profiles = mean over the OTHER gender's ranking names, same frame and position",
        "strengths": tc["flip_strengths"], "results": []}
g2 = torch.Generator().manual_seed(cfg["seed"] + 77)
for target, source in (("boy", "girl"), ("girl", "boy")):
    for k in tc["flip_top_k"]:
        add_feats = np.argsort(-rank_scores[source])[:k].tolist()   # top features of the gender being added
        own_feats = np.argsort(-rank_scores[target])[:k].tolist()   # top features of the prompts' own gender (for 'swap')
        prof = {}
        for f, ix in groups.items():
            src = [n for n, i in enumerate(ix) if prompts[i]["gender"] == source and prompts[i]["split"] == "rank"]
            prof[f] = acts[f][src].mean(0)[:, add_feats] @ D[:, add_feats].T / scale   # (seq-1, d) model units
        for s in tc["flip_strengths"]:
            def vec(f, v=None):
                z = torch.zeros(prof[f].shape[0] + 1, prof[f].shape[1]); z[1:] = s * prof[f] if v is None else v
                return z
            runs = {"feature_add": run(lambda f, ix: add_vector(vec(f))),
                    "feature_swap": run(lambda f, ix: (lambda h, f=f: ablate_features(sae, scale, own_feats)(h) + vec(f)))}
            rsc, rtop = [], []
            for _ in range(tc["flip_random_draws"]):
                rv = {}
                for f in groups:
                    r = torch.randn(prof[f].shape, generator=g2)
                    rv[f] = r / r.norm(dim=-1, keepdim=True) * (s * prof[f]).norm(dim=-1, keepdim=True)
                a, b = run(lambda f, ix: add_vector(vec(f, rv[f]))); rsc.append(a); rtop.append(b)
            for kind in ("name_only", "noun_name"):
                m = is_(kind=kind, split="heldout", gender=target); mt = torch.from_numpy(m)
                rec = {"target_prompts": target, "added_features_of": source, "k": k, "strength": s, "prompt_kind": kind, "n": int(m.sum()),
                       "added_features": add_feats, "clean_score": float(clean[m].mean()),
                       "mean_added_norm_model_units": float(np.mean([(s * prof[f]).norm(dim=-1).mean() for f in groups]))}
                for name, (sc, tp) in runs.items():
                    rec[name] = {"score": float(sc[m].mean()), "flip_rate_pair": float((sc[m] < 0).mean()),
                                 "top1_is_other_pronoun": float((tp[mt] == Wtop[mt]).float().mean())}
                rec["random_add"] = {"score": float(np.mean([x[m].mean() for x in rsc])),
                                     "flip_rate_pair": float(np.mean([(x[m] < 0).mean() for x in rsc])),
                                     "top1_is_other_pronoun": float(np.mean([(x[mt] == Wtop[mt]).float().mean() for x in rtop]))}
                flip["results"].append(rec)
                if kind == "name_only":
                    print(target, "<-", source, "k", k, "s", s, {n: (round(rec[n]["score"], 2), rec[n]["flip_rate_pair"], rec[n]["top1_is_other_pronoun"]) for n in ("feature_add", "feature_swap", "random_add")}, flush=True)
flip["clean_top1_is_other_pronoun_heldout"] = float((clean_top[torch.from_numpy(HO)] == Wtop[torch.from_numpy(HO)]).float().mean())
(od / "flip.json").write_text(json.dumps(flip, indent=1))
print("wrote flip.json")
