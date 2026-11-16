"""Stage 5 blind test, step 1: build puzzles.

For each labelled feature (200 real + 50 shuffled-weights control): 5 firing tokens sampled uniformly
among ALL its firings, and 5 non-firing tokens sampled uniformly, from text NOT shown during labelling
(real: held-out split; control: rows other than the displayed examples). Puzzles are anonymised and
shuffled together. Writes results/stage5_blind/puzzles_{k}.txt and key.json (answer key).
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
from src.model import load_model
from src.sae import SparseAutoencoder

cfg = load_config()
ic = cfg["interpret"]
lam = ic["chosen_lambda"]
rng = np.random.default_rng(cfg["seed"] + 99)
_, tok = load_model(cfg, device="cpu")
LETTERS = "ABCDEFGHIJ"


def snippet(tokens, story, offsets, row):
    s = story[row]
    a = max(offsets[s] + 1, row - ic["context_before"])
    b = min(offsets[s + 1], row + ic["context_after"] + 1)
    return (tok.decode(tokens[a:row]) + "[[" + tok.decode(tokens[row:row + 1]) + "]]" +
            tok.decode(tokens[row + 1:b])).replace("\n", "⏎")


def build(tag, ckdir, data_dir, split, feat_json, labels_csv, scale, exclude_shown):
    ck = torch.load(ckdir / "ckpt.pt", map_location="cpu", weights_only=False)
    sae = SparseAutoencoder(ck["d"], ck["m"])
    sae.load_state_dict(ck["sae"])
    feats = {f["index_in_list"]: f for f in json.loads(feat_json.read_text())["features"]}
    labels = list(csv.DictReader(open(labels_csv)))
    acts, tokens, story, pos, offsets = load_split(data_dir, split)
    rows = np.nonzero(pos > 0)[0]
    ids = [feats[int(r["index_in_list"])]["feature"] for r in labels]
    We, be, bd = sae.W_e.detach()[ids], sae.b_e.detach()[ids], sae.b_d.detach()
    F = np.zeros((len(rows), len(ids)), dtype=np.float32)
    with torch.no_grad():
        for a in range(0, len(rows), 65536):
            x = torch.from_numpy(np.asarray(acts[rows[a:a + 65536]]).astype(np.float32)) * scale
            F[a:a + 65536] = torch.relu((x - bd) @ We.T + be).numpy()
    out = []
    for j, r in enumerate(labels):
        f = feats[int(r["index_in_list"])]
        shown = {e["row"] for e in f["top"] + f["random"]} if exclude_shown else set()
        ok = np.array([rw not in shown for rw in rows])
        fire = np.nonzero((F[:, j] > 0) & ok)[0]
        quiet = np.nonzero((F[:, j] == 0) & ok)[0]
        if len(fire) < 5:
            out.append({"tag": tag, "index_in_list": int(r["index_in_list"]), "feature": f["feature"],
                        "skipped": f"only {len(fire)} fresh firings"})
            continue
        fp = rng.choice(fire, 5, replace=False)
        qp = rng.choice(quiet, 5, replace=False)
        items = [(rows[i], True, float(F[i, j])) for i in fp] + [(rows[i], False, 0.0) for i in qp]
        order = rng.permutation(10)
        items = [items[k] for k in order]
        out.append({"tag": tag, "index_in_list": int(r["index_in_list"]), "feature": f["feature"],
                    "label": r["suggested_label (SUGGESTION)"],
                    "verdict": r["suggested_verdict (SUGGESTION)"],
                    "random_agree": r["random_examples_agree (SUGGESTION)"],
                    "snippets": [snippet(tokens, story, offsets, it[0]) for it in items],
                    "firing_letters": [LETTERS[k] for k, it in enumerate(items) if it[1]],
                    "firing_acts": [it[2] for it in items if it[1]],
                    "fresh_firings_available": int(len(fire))})
    return out


s3 = json.loads((ROOT / "results/stage3_runs.json").read_text())["rescale_factor"]
sr = json.loads((ROOT / "results/stage5_random_control.json").read_text())["rescale_factor"]
puz = build("real", ROOT / f"checkpoints/sae/lam_{lam}", ROOT / "data", "heldout",
            ROOT / "results/stage5/features.json", ROOT / "results/stage5/labels.csv", s3, False)
puz += build("control", ROOT / f"checkpoints/sae_random/lam_{lam}", ROOT / "data/random", "train",
             ROOT / "results/stage5_random/features.json", ROOT / "results/stage5_random/labels.csv", sr, True)
skipped = [p for p in puz if "skipped" in p]
puz = [p for p in puz if "skipped" not in p]
perm = rng.permutation(len(puz))
puz = [puz[i] for i in perm]
od = ROOT / "results" / "stage5_blind"
od.mkdir(parents=True, exist_ok=True)
for i, p in enumerate(puz):
    p["puzzle_id"] = f"P{i:03d}"
(od / "key.json").write_text(json.dumps({"puzzles": puz, "skipped": skipped}, indent=1, ensure_ascii=False))
CH = 25
for k in range(0, len(puz), CH):
    lines = []
    for p in puz[k:k + CH]:
        lines.append(f"### {p['puzzle_id']}\nLABEL: {p['label']}")
        lines += [f"{LETTERS[i]}. {s}" for i, s in enumerate(p["snippets"])]
        lines.append("")
    (od / f"puzzles_{k // CH:02d}.txt").write_text("\n".join(lines))
print(f"{len(puz)} puzzles ({sum(p['tag']=='real' for p in puz)} real, {sum(p['tag']=='control' for p in puz)} control); "
      f"skipped {len(skipped)}: {skipped}; files: {len(range(0, len(puz), CH))}")
