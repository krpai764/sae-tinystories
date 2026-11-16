"""Stage 5 blind test, step 2: score the blind guesser's picks against the answer key.

Input: results/stage5_blind/key.json, results/stage5_blind/responses.json ({puzzle_id: [5 letters]})
Output: results/stage5_blind_scores.json, results/stage5_blind_per_feature.csv, figures/stage5_blind.png

Accuracy per feature = correct picks / 5 (the guesser always picks 5 of 10, so this equals
accuracy over all 10 snippets). Chance = 0.5. Per-feature p = P(>= k correct) under random guessing
(hypergeometric 10/5/5). Overall p by simulating random guessing over the same number of puzzles.
'clear' (final) = suggested verdict clear AND random firings agree == 'yes'.
"""
import csv
import json
import sys
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.config import ROOT, load_config

cfg = load_config()
od = ROOT / "results" / "stage5_blind"
key = json.loads((od / "key.json").read_text())["puzzles"]
resp = json.loads((od / "responses.json").read_text())
hyp = {k: comb(5, k) * comb(5, 5 - k) / comb(10, 5) for k in range(6)}
p_ge = {k: sum(hyp[j] for j in range(k, 6)) for k in range(6)}
rng = np.random.default_rng(cfg["seed"])

rows, strength = [], []
for p in key:
    picks = resp.get(p["puzzle_id"])
    valid = isinstance(picks, list) and len(set(picks)) == 5
    k = len(set(picks) & set(p["firing_letters"])) if valid else None
    clear = p["verdict"] == "clear" and p["random_agree"] == "yes"
    rows.append({"puzzle_id": p["puzzle_id"], "set": p["tag"], "index_in_list": p["index_in_list"],
                 "feature": p["feature"], "label": p["label"], "verdict_suggested": p["verdict"],
                 "random_agree": p["random_agree"], "final_clear": clear, "valid_response": valid,
                 "correct_of_5": k, "accuracy": None if k is None else k / 5,
                 "p_value_vs_chance": None if k is None else p_ge[k]})
    if valid:
        for L, a in zip(p["firing_letters"], p["firing_acts"]):
            strength.append((p["tag"], a, L in picks))


def summary(sel):
    acc = [r["accuracy"] for r in sel if r["accuracy"] is not None]
    if not acc:
        return {"n": 0}
    n = len(acc)
    sim = rng.hypergeometric(5, 5, 5, size=(100_000, n)).mean(1) / 5  # random guessing
    return {"n": n, "mean_accuracy": float(np.mean(acc)), "chance": 0.5,
            "p_value_vs_chance": float((sim >= np.mean(acc)).mean()),
            "n_perfect_5of5": sum(a == 1.0 for a in acc),
            "n_significant_p05": sum(r["p_value_vs_chance"] < 0.05 for r in sel if r["accuracy"] is not None),
            "n_at_or_below_chance": sum(a <= 0.6 for a in acc)}


real = [r for r in rows if r["set"] == "real"]
ctrl = [r for r in rows if r["set"] == "control"]
real50 = [r for r in real if r["index_in_list"] < 50]
out = {
    "n_puzzles": len(rows), "n_invalid_responses": sum(not r["valid_response"] for r in rows),
    "real_all_200": summary(real), "real_first_50": summary(real50), "control_50": summary(ctrl),
    "real_final_clear": summary([r for r in real if r["final_clear"]]),
    "real_not_final_clear": summary([r for r in real if not r["final_clear"]]),
    "real_suggested_unclear": summary([r for r in real if r["verdict_suggested"] == "unclear"]),
    "control_final_clear": summary([r for r in ctrl if r["final_clear"]]),
    "final_clear_share": {"real": sum(r["final_clear"] for r in real) / len(real),
                          "real_n": sum(r["final_clear"] for r in real),
                          "control": sum(r["final_clear"] for r in ctrl) / len(ctrl),
                          "control_n": sum(r["final_clear"] for r in ctrl),
                          "real_suggested_clear_ignoring_random": sum(r["verdict_suggested"] == "clear" for r in real),
                          "control_suggested_clear_ignoring_random": sum(r["verdict_suggested"] == "clear" for r in ctrl)},
}
# detection rate of firing snippets by activation strength (terciles within each set)
for tag in ("real", "control"):
    s = [(a, hit) for t, a, hit in strength if t == tag]
    a = np.array([x[0] for x in s]); h = np.array([x[1] for x in s])
    q = np.quantile(a, [1 / 3, 2 / 3])
    out[f"{tag}_firing_detection_by_strength_tercile"] = {
        "weak": float(h[a <= q[0]].mean()), "middle": float(h[(a > q[0]) & (a <= q[1])].mean()),
        "strong": float(h[a > q[1]].mean()), "tercile_edges": q.tolist()}
(ROOT / "results" / "stage5_blind_scores.json").write_text(json.dumps(out, indent=2))
with open(ROOT / "results" / "stage5_blind_per_feature.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(sorted(rows, key=lambda r: (r["set"], r["index_in_list"])))

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
bins = np.arange(-0.1, 1.2, 0.2)
for sel, lab in ((real, "real SAE (200)"), (ctrl, "shuffled-weights control (50)")):
    acc = [r["accuracy"] for r in sel if r["accuracy"] is not None]
    ax[0].hist(acc, bins=bins, alpha=0.6, density=True, label=f"{lab}, mean {np.mean(acc):.2f}")
ax[0].bar([k / 5 for k in range(6)], [hyp[k] for k in range(6)], width=0.05, color="k", label="random guessing")
ax[0].axvline(0.5, color="grey", ls=":")
ax[0].set(xlabel="blind accuracy per feature", ylabel="share of features", title="Label → pick the 5 firing snippets")
ax[0].legend(fontsize=8)
for i, tag in enumerate(("real", "control")):
    d = out[f"{tag}_firing_detection_by_strength_tercile"]
    ax[1].bar(np.arange(3) + i * 0.38, [d["weak"], d["middle"], d["strong"]], width=0.38, label=tag)
ax[1].set_xticks(np.arange(3) + 0.19, ["weak", "middle", "strong"])
ax[1].set(ylabel="firing snippets correctly picked", title="Detection vs firing strength (terciles)", ylim=(0, 1))
ax[1].axhline(0.5, color="grey", ls=":")
ax[1].legend()
fig.tight_layout()
fig.savefig(ROOT / "figures" / "stage5_blind.png", dpi=120)
print(json.dumps(out, indent=1))
