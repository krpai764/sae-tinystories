"""Review rerun 1b: tracing with held-out sentence frames, an activation-matched random control, loss changes and
top-1 flip rates. Design and success rules: config.yaml `trace_v2` (committed before this ran).
Writes results/stage7b/{prompts,analysis}.json and effects.npy (git-ignored).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch
import torch.nn.functional as F

from src.collect import load_split
from src.config import ROOT, load_config, set_seed
from src.eval import seqs_from_split, story_losses
from src.model import load_model, residual_hook
from src.sae import SparseAutoencoder
from src.trace import ablate_features, add_vector

cfg = load_config(); t1, tc = cfg["trace"], cfg["trace_v2"]; set_seed(cfg["seed"])
layer, lam = cfg["model"]["layer"], cfg["interpret"]["chosen_lambda"]
scale = json.loads((ROOT / "results" / "stage3_runs.json").read_text())["rescale_factor"]
ck = torch.load(ROOT / "checkpoints" / "sae" / f"lam_{lam}" / "ckpt.pt", map_location="cpu", weights_only=False)
sae = SparseAutoencoder(ck["d"], ck["m"]); sae.load_state_dict(ck["sae"]); sae.eval()
model, tok = load_model(cfg, device="cpu")
od = ROOT / "results" / "stage7b"; od.mkdir(parents=True, exist_ok=True)
PRON = {("girl", "cap"): (" She", " He"), ("boy", "cap"): (" He", " She"), ("girl", "lower"): (" she", " he"), ("boy", "lower"): (" he", " she")}
tid = lambda w: tok(w).input_ids[0]
OTHER = {"girl": "boy", "boy": "girl"}

prompts = []
for split, frames in (("rank", tc["frames_rank"]), ("heldout", tc["frames_heldout"])):
    for fr in frames:
        for g in ("girl", "boy"):
            for n in t1[f"{g}_names_{split}"]:
                ids = [tok.eos_token_id] + tok(fr["text"].replace("{N}", n).replace("{G}", g)).input_ids
                c, w = PRON[(g, fr["case"])]
                prompts.append({"frame": fr["id"], "kind": fr["kind"], "gender": g, "split": split, "name": n, "ids": ids,
                                "name_pos": ids.index(tid(" " + n)), "correct": c, "wrong": w})
P = len(prompts)
groups = {}
for i, p in enumerate(prompts):
    groups.setdefault(p["frame"], []).append(i)
for f, ix in groups.items():
    assert len({len(prompts[i]["ids"]) for i in ix}) == 1 and len({prompts[i]["name_pos"] for i in ix}) == 1, f
(od / "prompts.json").write_text(json.dumps(prompts, indent=1))
C = torch.tensor([tid(p["correct"]) for p in prompts]); W = torch.tensor([tid(p["wrong"]) for p in prompts])
is_ = lambda **kw: np.array([all(p[k] == v for k, v in kw.items()) for p in prompts])
NO, RK, HO = is_(kind="name_only"), is_(split="rank"), is_(split="heldout")
GM = {"girl": is_(gender="girl"), "boy": is_(gender="boy")}


@torch.no_grad()
def run(replace=None):
    """Per prompt: score, argmax token at the last position, mean next-token loss over the prompt."""
    sc, top, loss = np.zeros(P, np.float32), np.zeros(P, np.int64), np.zeros(P, np.float32)
    for f, ix in groups.items():
        ids = torch.tensor([prompts[i]["ids"] for i in ix])
        if replace is None:
            lg = model(ids).logits
        else:
            with residual_hook(model, layer, replace=replace(f)):
                lg = model(ids).logits
        last = lg[:, -1]
        sc[ix] = (last.gather(1, C[ix, None])[:, 0] - last.gather(1, W[ix, None])[:, 0]).numpy()
        top[ix] = last.argmax(-1).numpy()
        loss[ix] = F.cross_entropy(lg[:, :-1].reshape(-1, lg.shape[-1]), ids[:, 1:].reshape(-1), reduction="none").view(len(ix), -1).mean(1).numpy()
    return sc, top, loss


def measures(res, mask, clean):
    sc, top, loss = res
    return {"n": int(mask.sum()), "score": float(sc[mask].mean()), "drop": float((clean[0][mask] - sc[mask]).mean()),
            "pair_preference_correct": float((sc[mask] > 0).mean()), "top1_correct": float((top[mask] == C.numpy()[mask]).mean()),
            "top1_other_pronoun": float((top[mask] == W.numpy()[mask]).mean()), "prompt_loss_change": float((loss[mask] - clean[2][mask]).mean())}


clean = run()
ident = run(lambda f: ablate_features(sae, scale, []))
assert np.allclose(clean[0], ident[0], atol=1e-3)
A = {"n_prompts": P, "baseline": {}}
for name, m in [("heldout_name_only", NO & HO), ("heldout_name_only_girl", NO & HO & GM["girl"]), ("heldout_name_only_boy", NO & HO & GM["boy"]),
                ("heldout_noun_name", ~NO & HO), ("rank_name_only", NO & RK)]:
    A["baseline"][name] = measures(clean, m, clean)
gate = A["baseline"]["heldout_name_only"]["pair_preference_correct"]
A["gate_passed"] = bool(gate >= 0.9)
print("baseline", json.dumps(A["baseline"], indent=0), flush=True)
if not A["gate_passed"]:
    (od / "analysis.json").write_text(json.dumps(A, indent=1)); sys.exit("gate failed")

# ---- activations ----
acts = {}
with torch.no_grad():
    for f, ix in groups.items():
        store = []
        with residual_hook(model, layer, store=store):
            model(torch.tensor([prompts[i]["ids"] for i in ix]))
        acts[f] = sae.encode(store[0][:, 1:] * scale)   # (n, seq-1, m); index p-1 is position p
tot = np.zeros((sae.m, P), np.float32); peak = np.zeros((sae.m, P), np.float32)
for f, ix in groups.items():
    tot[:, ix] = acts[f].sum(1).T.numpy(); peak[:, ix] = acts[f].max(1).values.T.numpy()
firing = np.nonzero((tot > 0).any(1))[0].tolist()
A["n_firing"] = len(firing)
print(len(firing), "features fire", flush=True)

# ---- single-feature ablations (score effect and prompt-loss change) ----
ef = od / "effects.npy"
if ef.exists():
    E, EL = np.load(ef), np.load(od / "loss_effects.npy")
else:
    E, EL = np.zeros((sae.m, P), np.float32), np.zeros((sae.m, P), np.float32)
    for n_, j in enumerate(firing):
        r = run(lambda f, j=j: ablate_features(sae, scale, [j]))
        E[j], EL[j] = clean[0] - r[0], r[2] - clean[2]
        if n_ % 150 == 0:
            print(f"ablated {n_}/{len(firing)}", flush=True)
    np.save(ef, E); np.save(od / "loss_effects.npy", EL)

# ---- sets ----
rank_eff = E[:, NO & RK].mean(1)
top10 = np.argsort(-rank_eff)[:tc["top_k"]].tolist()
sel = {}
for g in GM:
    a, b = peak[:, NO & RK & GM[g]].mean(1), peak[:, NO & RK & GM[OTHER[g]]].mean(1)
    cand = [j for j in firing if a[j] > 0 and a[j] >= tc["selective_ratio"] * b[j]]
    own = E[:, NO & RK & GM[g]].mean(1)
    sel[g] = sorted(cand, key=lambda j: -own[j])[:tc["selective_k"]]
    A[f"n_selective_candidates_{g}"] = len(cand)
tot_ho = tot[:, NO & HO].mean(1)
rng = np.random.default_rng(cfg["seed"] + 21)
fir = np.array(firing)


def matched_sets(S):
    sets = []
    for _ in range(tc["n_random_sets"]):
        used, out = set(S), []
        for j in S:
            pool = [int(x) for x in fir[np.argsort(np.abs(tot_ho[fir] - tot_ho[j]))] if int(x) not in used][:10]
            c = int(rng.choice(pool)); out.append(c); used.add(c)
        sets.append(out)
    return sets


tokens_h = load_split(ROOT / "data", "heldout")
seqs = seqs_from_split(np.asarray(tokens_h[1]), np.asarray(tokens_h[4]))[: tc["loss_stories"]]
sl = lambda idx: (lambda s: float(s[0].sum() / s[1].sum()))(story_losses(model, seqs, layer, "cpu", None if idx is None else ablate_features(sae, scale, idx), pad_id=tok.eos_token_id))
story_clean = sl(None)
A["story_loss_clean"] = story_clean
MASKS = {"overall": NO & HO, "girl": NO & HO & GM["girl"], "boy": NO & HO & GM["boy"]}


def test_set(S, key_mask):
    res = run(lambda f: ablate_features(sae, scale, S))
    out = {"features": S, "total_activation_heldout": float(tot_ho[S].sum()),
           "rank_effect_each": [float(rank_eff[j]) for j in S], "heldout_effect_each": [float(E[j, NO & HO].mean()) for j in S],
           "peak_act_girl_boy_rank": [[float(peak[j, NO & RK & GM["girl"]].mean()), float(peak[j, NO & RK & GM["boy"]].mean())] for j in S],
           "peak_act_heldout_by_name": [{n: float(peak[j, NO & HO & is_(name=n)].mean()) for n in t1["girl_names_heldout"] + t1["boy_names_heldout"]} for j in S],
           "measures": {k: measures(res, m, clean) for k, m in MASKS.items()}, "noun_name": measures(res, ~NO & HO, clean),
           "story_loss_change": sl(S) - story_clean}
    rs = matched_sets(S)
    rr = [run(lambda f, s=s: ablate_features(sae, scale, s)) for s in rs]
    drops = {k: np.array([(clean[0][m] - r[0][m]).mean() for r in rr]) for k, m in MASKS.items()}
    out["matched_random"] = {"activation_ratio_mean": float(np.mean([tot_ho[s].sum() for s in rs]) / tot_ho[S].sum()),
                             **{k: {"drop_mean": float(d.mean()), "drop_max": float(d.max()), "drop_p95": float(np.quantile(d, .95)),
                                    "tested_beats": int((out["measures"][k]["drop"] > d).sum())} for k, d in drops.items()},
                             "pair_preference_correct_mean": float(np.mean([(r[0][MASKS[key_mask]] > 0).mean() for r in rr])),
                             "top1_correct_mean": float(np.mean([(r[1][MASKS[key_mask]] == C.numpy()[MASKS[key_mask]]).mean() for r in rr])),
                             "prompt_loss_change_mean": float(np.mean([(r[2][MASKS[key_mask]] - clean[2][MASKS[key_mask]]).mean() for r in rr])),
                             "story_loss_change_mean_first_sets": float(np.mean([sl(s) - story_clean for s in rs[: tc["loss_random_sets"]]]))}
    if key_mask != "overall":   # specificity: own-gender drop minus other-gender drop
        o = OTHER[key_mask]
        spec = out["measures"][key_mask]["drop"] - out["measures"][o]["drop"]
        out["specificity"] = {"tested": float(spec), "random_mean": float((drops[key_mask] - drops[o]).mean()),
                              "tested_beats": int((spec > (drops[key_mask] - drops[o])).sum())}
    return out


need = 0.95 * tc["n_random_sets"]
A["top10"] = test_set(top10, "overall")
A["R1_passed"] = bool(A["top10"]["matched_random"]["overall"]["tested_beats"] >= need)
print("top10", top10, {k: round(v["drop"], 2) for k, v in A["top10"]["measures"].items()}, A["top10"]["matched_random"]["overall"], "R1", A["R1_passed"], flush=True)
A["selective"] = {}
for g in GM:
    A["selective"][g] = test_set(sel[g], g)
    s = A["selective"][g]
    s["R2_passed"] = bool(s["matched_random"][g]["tested_beats"] >= need and s["specificity"]["tested_beats"] >= need)
    print(g, sel[g], "own drop", round(s["measures"][g]["drop"], 2), "other", round(s["measures"][OTHER[g]]["drop"], 2), s["matched_random"][g], s["specificity"], "R2", s["R2_passed"], flush=True)

# ---- flip test ----
D = sae.W_d.detach(); g2 = torch.Generator().manual_seed(cfg["seed"] + 79)
A["flip"] = {}
for target in GM:
    source = OTHER[target]; Fs = sel[source]
    a_name, a_later, n_l = torch.zeros(len(Fs)), torch.zeros(len(Fs)), 0
    src = [i for i, p in enumerate(prompts) if p["gender"] == source and p["split"] == "rank" and p["kind"] == "name_only"]
    for i in src:
        a = acts[prompts[i]["frame"]][groups[prompts[i]["frame"]].index(i)][:, Fs]; np_ = prompts[i]["name_pos"]
        a_name += a[np_ - 1]; a_later += a[np_:].sum(0); n_l += a[np_:].shape[0]
    v_name, v_later = (a_name / len(src)) @ D[:, Fs].T / scale, (a_later / n_l) @ D[:, Fs].T / scale
    prof = {}
    for f, ix in groups.items():
        L, np_ = len(prompts[ix[0]]["ids"]), prompts[ix[0]]["name_pos"]
        z = torch.zeros(L, D.shape[0]); z[np_] = v_name; z[np_ + 1:] = v_later
        prof[f] = z
    names = t1[f"{target}_names_heldout"]
    recs = []
    for s in tc["flip_strengths"]:
        runs = {"add": run(lambda f: add_vector(s * prof[f])),
                "swap": run(lambda f: (lambda h, f=f: ablate_features(sae, scale, sel[target])(h) + s * prof[f]))}
        rnd = []
        for _ in range(tc["flip_random_draws"]):
            rv = {}
            for f in groups:
                r = torch.randn(prof[f].shape, generator=g2)
                rv[f] = r / r.norm(dim=-1, keepdim=True) * (s * prof[f]).norm(dim=-1, keepdim=True)
            rnd.append(run(lambda f: add_vector(rv[f])))
        rec = {"strength": s, "added_norm_name_pos": float((s * v_name).norm()), "added_norm_later_pos": float((s * v_later).norm())}
        for kind, base in (("name_only", NO), ("noun_name", ~NO)):
            m = base & HO & GM[target]
            c = {"n": int(m.sum())}
            for nm, r in runs.items():
                c[nm] = {"score": float(r[0][m].mean()), "pair_flip": float((r[0][m] < 0).mean()), "top1_other_pronoun": float((r[1][m] == W.numpy()[m]).mean()),
                         "top1_correct": float((r[1][m] == C.numpy()[m]).mean()), "prompt_loss_change": float((r[2][m] - clean[2][m]).mean()),
                         "names_majority_flipped": int(sum((r[0][m & is_(name=n)] < 0).mean() > 0.5 for n in names)),
                         "pair_flip_by_name": {n: float((r[0][m & is_(name=n)] < 0).mean()) for n in names}}
            c["random"] = {"score": float(np.mean([r[0][m].mean() for r in rnd])), "pair_flip": float(np.mean([(r[0][m] < 0).mean() for r in rnd])),
                           "top1_other_pronoun": float(np.mean([(r[1][m] == W.numpy()[m]).mean() for r in rnd])),
                           "top1_correct": float(np.mean([(r[1][m] == C.numpy()[m]).mean() for r in rnd])),
                           "prompt_loss_change": float(np.mean([(r[2][m] - clean[2][m]).mean() for r in rnd])),
                           "names_majority_flipped": int(sum(np.mean([(r[0][m & is_(name=n)] < 0).mean() for r in rnd]) > 0.5 for n in names))}
            c["clean"] = measures(clean, m, clean)
            rec[kind] = c
        recs.append(rec)
        print(target, "<-", source, "s", s, {k: (round(v["score"], 2), v["pair_flip"], round(v["top1_other_pronoun"], 2), v.get("names_majority_flipped")) for k, v in rec["name_only"].items() if k in ("add", "swap", "random")}, flush=True)
    ok = any(r["strength"] <= 1.5 and r["name_only"]["add"]["names_majority_flipped"] >= 4 and r["name_only"]["random"]["names_majority_flipped"] == 0 for r in recs)
    A["flip"][target] = {"added_features_of": source, "added_features": Fs, "by_strength": recs, "R3_passed": bool(ok)}
    print("R3", target, ok, flush=True)
(od / "analysis.json").write_text(json.dumps(A, indent=1))
print("wrote analysis.json")
