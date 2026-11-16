"""Stage 2 extra sanity checks -> results/stage2_checks.json
 - how much of the activation is the shared mean vector (matters for centring in Stage 3)
 - train/held-out story overlap (leakage check)
 - file sizes on disk vs the 3 GB budget
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from src.collect import load_split
from src.config import ROOT, load_config

cfg = load_config()
dd = ROOT / cfg["paths"]["data_dir"]
acts, tokens, story, pos, offsets = load_split(dd, "train")
X = np.asarray(acts)[pos > 0]
mean = X.mean(0)
raw = np.linalg.norm(X, axis=1)
cen = np.linalg.norm(X - mean, axis=1)
# variance carried by the top principal components of the centred data (subsample for speed)
sub = (X[:: max(1, len(X) // 200000)] - mean).astype(np.float64)
ev = np.linalg.svd(sub, compute_uv=False) ** 2
ev /= ev.sum()

_, htok, _, _, hoff = load_split(dd, "heldout")
h_stories = {htok[hoff[i]:hoff[i + 1]].tobytes() for i in range(len(hoff) - 1)}
t_stories = {tokens[offsets[i]:offsets[i + 1]].tobytes() for i in range(len(offsets) - 1)}

out = {
    "excluding_pos0": True,
    "mean_vector_norm": float(np.linalg.norm(mean)),
    "mean_raw_norm": float(raw.mean()),
    "mean_centred_norm": float(cen.mean()),
    "fraction_of_squared_norm_in_mean": float(np.linalg.norm(mean) ** 2 / (raw ** 2).mean()),
    "pca_top1_top5_top20_top100_variance_fraction": [float(ev[:k].sum()) for k in (1, 5, 20, 100)],
    "rescale_factor_to_norm_sqrt_width": float(np.sqrt(256) / raw.mean()),
    "train_heldout_identical_stories": len(h_stories & t_stories),
    "heldout_stories": len(h_stories),
    "data_dir_bytes": int(sum(p.stat().st_size for p in dd.iterdir())),
    "data_dir_GB": sum(p.stat().st_size for p in dd.iterdir()) / 1e9,
}
(ROOT / cfg["paths"]["results_dir"] / "stage2_checks.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
