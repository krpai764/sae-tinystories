"""Review rerun 1c, step 1: build (a) blind-verdict items and (b) a control blind test on fresh text.

Design: config.yaml `stage5_v2` (committed before this ran). Fresh text = held-out split; for the control the
shuffled-weights model is run on those stories here (activations cast to fp16 like its training data, not saved).
Writes results/stage5b/verdict_items_XX.txt, puzzles_XX.txt and key.json.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from src.collect import load_split
from src.config import ROOT, load_config
from src.model import get_activations, load_model, shuffle_weights
from src.sae import SparseAutoencoder

cfg = load_config(); ic, v2 = cfg["interpret"], cfg["stage5_v2"]; lam = ic["chosen_lambda"]
model, tok = load_model(cfg, device="cpu")
acts, tokens, story, pos, offsets = load_split(ROOT / "data", "heldout")
tokens, story, pos, offsets = map(np.asarray, (tokens, story, pos, offsets))
rows = np.nonzero(pos > 0)[0]
labels = list(csv.DictReader(open(ROOT / "results" / "stage5_blind_per_feature.csv")))
LETTERS = "ABCDEFGHIJ"


def snippet(row):
    s = story[row]
    a = max(offsets[s] + 1, row - ic["context_before"]); b = min(offsets[s + 1], row + ic["context_after"] + 1)
    return (tok.decode(tokens[a:row]) + "[[" + tok.decode(tokens[row:row + 1]) + "]]" + tok.decode(tokens[row + 1:b])).replace("\n", "⏎")


def load_sae(d):
    ck = torch.load(d / "ckpt.pt", map_location="cpu", weights_only=False)
    s = SparseAutoencoder(ck["d"], ck["m"]); s.load_state_dict(ck["sae"]); return s


def encode(sae, X, scale, ids):
    We, be, bd = sae.W_e.detach()[ids], sae.b_e.detach()[ids], sae.b_d.detach()
    out = np.zeros((len(X), len(ids)), np.float32)
    with torch.no_grad():
        for a in range(0, len(X), 65536):
            out[a:a + 65536] = torch.relu((torch.from_numpy(np.asarray(X[a:a + 65536]).astype(np.float32)) * scale - bd) @ We.T + be).numpy()
    return out


sets = {}
# real: saved held-out activations
fr = {f["index_in_list"]: f for f in json.loads((ROOT / "results/stage5/features.json").read_text())["features"]}
lr = [r for r in labels if r["set"] == "real"]
s3 = json.loads((ROOT / "results/stage3_runs.json").read_text())["rescale_factor"]
sets["real"] = (lr, fr, encode(load_sae(ROOT / f"checkpoints/sae/lam_{lam}"), acts[rows], s3, [int(r["feature"]) for r in lr]))
# control: shuffled model on the same held-out stories
shuffle_weights(model, cfg["random_control"]["shuffle_seed"])
Xc = np.zeros((len(tokens), 256), np.float16)
with torch.no_grad():
    for s in range(len(offsets) - 1):
        ids = torch.from_numpy(tokens[offsets[s]:offsets[s + 1]].astype(np.int64))[None]
        Xc[offsets[s]:offsets[s + 1]] = get_activations(model, ids, cfg["model"]["layer"])[0].numpy().astype(np.float16)
fc = {f["index_in_list"]: f for f in json.loads((ROOT / "results/stage5_random/features.json").read_text())["features"]}
lc = [r for r in labels if r["set"] == "control"]
sr = json.loads((ROOT / "results/stage5_random_control.json").read_text())["rescale_factor"]
sets["control"] = (lc, fc, encode(load_sae(ROOT / f"checkpoints/sae_random/lam_{lam}"), Xc[rows], sr, [int(r["feature"]) for r in lc]))
print("control fresh-text mean norm x scale:", float(np.linalg.norm(Xc[rows][:5000].astype(np.float32), axis=1).mean() * sr), flush=True)

od = ROOT / "results" / "stage5b"; od.mkdir(parents=True, exist_ok=True)
# ---------- (a) verdict items ----------
rng = np.random.default_rng(cfg["seed"] + v2["blind_verdicts"]["seed_offset"])
NRF = v2["blind_verdicts"]["n_random_firings"]
items = []
for tag, (lab, feats, F) in sets.items():
    for j, r in enumerate(lab):
        f = feats[int(r["index_in_list"])]
        fire = np.nonzero(F[:, j] > 0)[0]
        pick = rng.choice(fire, min(NRF, len(fire)), replace=False)
        items.append({"tag": tag, "index_in_list": int(r["index_in_list"]), "feature": int(r["feature"]), "label": r["label"],
                      "old_final_clear": r["final_clear"] == "True", "old_random_agree": r["random_agree"],
                      "fresh_firings_available": int(len(fire)), "fresh_firing_rate": float(len(fire) / len(rows)),
                      "top": [{"act": e["act"], "text": e["text"]} for e in f["top"]],
                      "random": [{"act": float(F[i, j]), "text": snippet(rows[i])} for i in pick]})
items = [items[i] for i in rng.permutation(len(items))]
for i, it in enumerate(items):
    it["item_id"] = f"V{i:03d}"
for k in range(0, len(items), 25):
    L = []
    for it in items[k:k + 25]:
        L.append(f"### {it['item_id']}\nLABEL: {it['label']}\nTOP EXAMPLES (20 strongest firings; number = firing strength):")
        L += [f"T{n + 1}. ({e['act']:.2f}) {e['text']}" for n, e in enumerate(it["top"])]
        L.append(f"RANDOM FIRINGS ({len(it['random'])} firings chosen at random; number = firing strength):")
        L += [f"R{n + 1}. ({e['act']:.2f}) {e['text']}" for n, e in enumerate(it["random"])]
        L.append("")
    (od / f"verdict_items_{k // 25:02d}.txt").write_text("\n".join(L))
# ---------- (b) control blind test on fresh text ----------
rng = np.random.default_rng(cfg["seed"] + v2["control_blind_test"]["seed_offset"])
puz = []
for tag, (lab, feats, F) in sets.items():
    for j, r in enumerate(lab):
        if int(r["index_in_list"]) >= 50:
            continue
        fire, quiet = np.nonzero(F[:, j] > 0)[0], np.nonzero(F[:, j] == 0)[0]
        if len(fire) < 5:
            puz.append({"tag": tag, "feature": int(r["feature"]), "skipped": f"only {len(fire)} firings on fresh text"}); continue
        its = [(i, True) for i in rng.choice(fire, 5, replace=False)] + [(i, False) for i in rng.choice(quiet, 5, replace=False)]
        its = [its[k] for k in rng.permutation(10)]
        puz.append({"tag": tag, "index_in_list": int(r["index_in_list"]), "feature": int(r["feature"]), "label": r["label"],
                    "snippets": [snippet(rows[i]) for i, _ in its], "firing_letters": [LETTERS[k] for k, it in enumerate(its) if it[1]],
                    "firing_acts": [float(F[i, j]) for i, fl in its if fl]})
skipped = [p for p in puz if "skipped" in p]; puz = [p for p in puz if "skipped" not in p]
puz = [puz[i] for i in rng.permutation(len(puz))]
for i, p in enumerate(puz):
    p["puzzle_id"] = f"Q{i:03d}"
for k in range(0, len(puz), 25):
    L = []
    for p in puz[k:k + 25]:
        L.append(f"### {p['puzzle_id']}\nLABEL: {p['label']}")
        L += [f"{LETTERS[i]}. {s}" for i, s in enumerate(p["snippets"])] + [""]
    (od / f"puzzles_{k // 25:02d}.txt").write_text("\n".join(L))
(od / "key.json").write_text(json.dumps({"verdict_items": items, "puzzles": puz, "skipped": skipped}, indent=1, ensure_ascii=False))
print(f"{len(items)} verdict items in {len(range(0, len(items), 25))} files; {len(puz)} puzzles ({sum(p['tag'] == 'real' for p in puz)} real, {sum(p['tag'] == 'control' for p in puz)} control), skipped {skipped}")
for tag in sets:
    print(tag, "median fresh firing rate", float(np.median([i["fresh_firing_rate"] for i in items if i["tag"] == tag])), "min firings", min(i["fresh_firings_available"] for i in items if i["tag"] == tag))
