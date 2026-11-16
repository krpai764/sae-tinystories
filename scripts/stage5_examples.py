"""Stage 5: top and random examples for 200 randomly chosen live features of the chosen SAE.

For each feature: firing frequency on the training activations, top-20 snippets (firing token
marked [[like this]]), 5 uniformly random firing snippets, max/median activation, and the output
tokens its decoder direction promotes (direction, mean-centred as LayerNorm would, times the
unembedding; an approximation because 4 blocks still follow layer 3).

Writes results/stage5/features.json and results/stage5/batch_{k}.md (human-readable).
With --random: same procedure for the shuffled-weights control -> results/stage5_random/.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import torch

from src.collect import load_split
from src.config import ROOT, load_config, set_seed
from src.model import load_model, shuffle_weights
from src.sae import SparseAutoencoder

ap = argparse.ArgumentParser()
ap.add_argument("--random", action="store_true", help="shuffled-weights control")
args = ap.parse_args()
cfg = load_config()
ic = cfg["interpret"]
set_seed(cfg["seed"])
lam = ic["chosen_lambda"]
if args.random:
    scale = json.loads((ROOT / "results" / "stage5_random_control.json").read_text())["rescale_factor"]
    ckdir, data_dir, od = ROOT / "checkpoints" / "sae_random" / f"lam_{lam}", ROOT / "data" / "random", ROOT / "results" / "stage5_random"
else:
    scale = json.loads((ROOT / "results" / "stage3_runs.json").read_text())["rescale_factor"]
    ckdir, data_dir, od = ROOT / "checkpoints" / "sae" / f"lam_{lam}", ROOT / "data", ROOT / "results" / "stage5"
ck = torch.load(ckdir / "ckpt.pt", map_location="cpu", weights_only=False)
sae = SparseAutoencoder(ck["d"], ck["m"])
sae.load_state_dict(ck["sae"])
model, tok = load_model(cfg, device="cpu")
if args.random:
    shuffle_weights(model, cfg["random_control"]["shuffle_seed"])

acts, tokens, story, pos, offsets = load_split(data_dir, "train")
rows = np.nonzero(pos > 0)[0]  # SAE was trained on these rows only
X = acts  # memmap; read in chunks

# ---- choose 200 random live features (live = fires at least once on train) ----
rng = np.random.default_rng(cfg["seed"])
W_e, b_e, b_d = sae.W_e.detach(), sae.b_e.detach(), sae.b_d.detach()

# full firing counts on train for all features (to define 'live' on train, not just held-out)
counts = torch.zeros(sae.m)
CH = 65536
with torch.no_grad():
    for a in range(0, len(rows), CH):
        x = torch.from_numpy(np.asarray(X[rows[a:a + CH]]).astype(np.float32)) * scale
        counts += (torch.relu((x - b_d) @ W_e.T + b_e) > 0).sum(0)
live = np.nonzero(counts.numpy() > 0)[0]
feats = np.sort(rng.choice(live, ic["n_features"], replace=False))
order = rng.permutation(len(feats))  # random presentation order -> batches are random too
feats = feats[order]
print(f"{len(live)}/{sae.m} features live on train; chose {len(feats)}", flush=True)

# ---- all firings of the chosen features ----
We, be = W_e[feats], b_e[feats]
hits_r, hits_f, hits_v = [], [], []
with torch.no_grad():
    for a in range(0, len(rows), CH):
        x = torch.from_numpy(np.asarray(X[rows[a:a + CH]]).astype(np.float32)) * scale
        f = torch.relu((x - b_d) @ We.T + be)
        r, j = torch.nonzero(f, as_tuple=True)
        hits_r.append(rows[a:a + CH][r.numpy()])
        hits_f.append(j.numpy())
        hits_v.append(f[r, j].numpy())
hits_r, hits_f, hits_v = map(np.concatenate, (hits_r, hits_f, hits_v))

# ---- promoted tokens ----
W_U = model.lm_head.weight.detach()  # (vocab, d)
D = sae.W_d.detach()[:, feats]       # (d, 200) unit directions (same in original units)
D = D - D.mean(0, keepdim=True)      # LayerNorm centring
logit_dirs = (W_U @ D).T             # (200, vocab)


def snippet(row: int) -> str:
    s = story[row]
    a = max(offsets[s] + 1, row - ic["context_before"])  # skip the EOS prefix
    b = min(offsets[s + 1], row + ic["context_after"] + 1)
    pre = tok.decode(tokens[a:row])
    mid = tok.decode(tokens[row:row + 1])
    post = tok.decode(tokens[row + 1:b])
    return (pre + "[[" + mid + "]]" + post).replace("\n", "⏎")


n_tok = len(rows)
out = []
for j, fid in enumerate(feats):
    m = hits_f == j
    r, v = hits_r[m], hits_v[m]
    top = np.argsort(-v)[: ic["top_k"]]
    rnd = rng.choice(len(v), min(ic["n_random"], len(v)), replace=False)
    tv = logit_dirs[j]
    out.append({
        "batch": j // ic["batch_size"] + 1, "index_in_list": j, "feature": int(fid),
        "train_firings": int(len(v)), "firing_frequency": len(v) / n_tok,
        "max_act": float(v.max()), "median_act": float(np.median(v)),
        "top": [{"row": int(r[i]), "act": float(v[i]), "text": snippet(r[i])} for i in top],
        "random": [{"row": int(r[i]), "act": float(v[i]), "text": snippet(r[i])} for i in rnd],
        "promoted_tokens": [tok.decode([int(t)]) for t in torch.topk(tv, ic["n_promoted_tokens"]).indices],
        "suppressed_tokens": [tok.decode([int(t)]) for t in torch.topk(-tv, 5).indices],
        "top_token_counts": {k: int(c) for k, c in zip(*np.unique(
            [tok.decode([int(tokens[r[i]])]) for i in top], return_counts=True))},
    })

od.mkdir(parents=True, exist_ok=True)
(od / "features.json").write_text(json.dumps({"lambda": lam, "rescale_factor": scale, "seed": cfg["seed"],
                                              "n_live_train": int(len(live)), "n_train_tokens": int(n_tok),
                                              "features": out}, indent=1, ensure_ascii=False))
for b in sorted({f["batch"] for f in out}):
    lines = [f"# Stage 5 features, batch {b} (SAE λ={lam}{', SHUFFLED-WEIGHTS CONTROL' if args.random else ''})\n",
             "Firing token is in [[double brackets]]; ⏎ = newline. Activations are in SAE units.\n"]
    for f in [f for f in out if f["batch"] == b]:
        lines.append(f"\n## #{f['index_in_list']} — feature {f['feature']}\n")
        lines.append(f"fires on {f['firing_frequency']:.4%} of tokens; max {f['max_act']:.2f}, median {f['median_act']:.2f}  ")
        lines.append(f"promotes: {' | '.join(repr(t) for t in f['promoted_tokens'])}  ")
        lines.append(f"suppresses: {' | '.join(repr(t) for t in f['suppressed_tokens'])}\n")
        lines.append("**Top 20**\n")
        lines += [f"- {e['act']:.2f}: {e['text']}" for e in f["top"]]
        lines.append("\n**Random firings**\n")
        lines += [f"- {e['act']:.2f}: {e['text']}" for e in f["random"]]
    (od / f"batch_{b}.md").write_text("\n".join(lines) + "\n")
print("wrote", od, flush=True)
