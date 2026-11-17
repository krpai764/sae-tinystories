"""Stage 6 summary: table, figure and side-by-side report from results/stage6/steering.json.

Writes results/stage6_summary.json, figures/stage6_steering.png, results/stage6_report.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.config import ROOT

D = json.loads((ROOT / "results" / "stage6" / "steering.json").read_text())
mults = D["multipliers"]
BREAK = 20.0  # 'broken' = perplexity under the unsteered model above this (unsteered runs: <= 2.5)

summary = []
for f in D["features"]:
    row = {"feature": f["feature"], "group": f["group"], "label": f["label"],
           "blind_correct_of_5": f["blind_correct_of_5"], "typical_strength": f["typical_strength_sae_units"],
           "by_multiplier": {}}
    base = [r for r in f["runs"] if r["kind"] == "none"]
    row["none"] = {"promoted_hits_mean": float(np.mean([r["promoted_hits"] for r in base])),
                   "ppl_median": float(np.median([r["ppl_clean"] for r in base]))}
    for m in mults:
        cell = {}
        for kind in ("feature", "random"):
            rs = [r for r in f["runs"] if r["kind"] == kind and r["multiplier"] == m]
            cell[kind] = {"promoted_hits_mean": float(np.mean([r["promoted_hits"] for r in rs])),
                          "ppl_median": float(np.median([r["ppl_clean"] for r in rs])),
                          "broken_of_n": f"{sum(r['ppl_clean'] > BREAK for r in rs)}/{len(rs)}",
                          "vector_norm": rs[0]["vector_norm_model_units"]}
        row["by_multiplier"][str(m)] = cell
    # first multiplier at which both prompts are broken
    first = [m for m in mults if row["by_multiplier"][str(m)]["feature"]["broken_of_n"].startswith(str(len(D["prompts"])))]
    row["first_multiplier_all_broken"] = first[0] if first else None
    summary.append(row)

(ROOT / "results" / "stage6_summary.json").write_text(json.dumps(
    {"break_threshold_ppl": BREAK, "mean_activation_norm_model_units": D["mean_activation_norm_model_units"],
     "features": summary}, indent=1, ensure_ascii=False))

# ---- figure ----
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
for row in summary:
    ls = "-" if row["group"] == "clear_5of5" else "--"
    ax[0].plot(mults, [row["by_multiplier"][str(m)]["feature"]["promoted_hits_mean"] for m in mults], ls, marker="o",
               label=f"{row['feature']}{'' if row['group'] == 'clear_5of5' else ' (not clear)'}")
    ax[1].plot(mults, [row["by_multiplier"][str(m)]["feature"]["ppl_median"] for m in mults], ls, marker="o")
rnd = np.array([[row["by_multiplier"][str(m)]["random"]["ppl_median"] for m in mults] for row in summary])
ax[1].plot(mults, np.median(rnd, 0), "k:", lw=3, label="random direction (median over features)")
for a in ax:
    a.set_xscale("log"); a.set_xticks(mults); a.set_xticklabels([str(m) for m in mults])
    a.set_xlabel("steering strength (x feature's typical strong firing)")
ax[0].set_ylabel("generated tokens that are the feature's top-10 promoted tokens (of 50)")
ax[1].set_yscale("log"); ax[1].axhline(BREAK, color="grey", lw=0.8)
ax[1].set_ylabel("perplexity of output under unsteered model")
ax[0].legend(fontsize=7); ax[1].legend(fontsize=7)
ax[0].set_title("Does the text move toward the feature?"); ax[1].set_title("Does the text break? (grey = threshold 20)")
fig.tight_layout()
fig.savefig(ROOT / "figures" / "stage6_steering.png", dpi=130)

# ---- report ----
L = ["# Stage 6: steering report\n",
     "> No feature label here has been verified by a human.\n",
     f"Model TinyStories-8M, residual stream after block {D['layer']}, SAE λ={D['lambda']}. "
     f"Seed {D['seed']} per prompt (prompt i uses seed {D['seed']}+i); 50 new tokens; temperature 0.8, top-k 50.\n",
     "**How features were selected.** The six main features were taken only from features that were "
     "labelled *clear* under the strict Stage 5 rule (random firings also fit the label) **and** scored 5/5 "
     "on the blind label test; among those 20, I picked ones whose labels are about content visible in "
     "text. Two features that were *not* clear were added to show steering with a weak label.\n",
     "**Steering.** Add `k × s × d` to the residual stream at every position except the EOS prefix, where d is "
     "the feature's unit decoder direction, s its typical strong firing (mean of its top-20 activations), and k the "
     "strength. Converted to model units by dividing by the rescale factor "
     f"{D['rescale_factor']:.4f}. Mean activation length at this layer is "
     f"{D['mean_activation_norm_model_units']:.2f} in model units. **Control:** a random unit direction with "
     "the same length, per feature and strength.\n",
     f"**Strengths.** The brief asks for 2, 5 and 10×. The smoke test showed 2× already breaks the text for "
     f"strongly-firing features, so 0.5× and 1× were added. Used: {mults}.\n",
     f"**Measures.** *Promoted hits*: how many of the 50 generated tokens are among the feature's top-10 promoted "
     f"tokens (Stage 5). *Perplexity*: of the generated text under the unsteered model; above {BREAK:.0f} is counted as broken "
     "(unsteered generations score 1.4 and 2.5).\n",
     "![steering](../figures/stage6_steering.png)\n",
     "## Summary table (medians/means over the 2 prompts)\n",
     "| feature | group | label | blind | k | vector length | feature: hits / ppl / broken | random: hits / ppl / broken |",
     "|---|---|---|---|---|---|---|---|"]
for row in summary:
    for m in mults:
        c = row["by_multiplier"][str(m)]
        L.append(f"| {row['feature']} | {row['group']} | {row['label']} | {row['blind_correct_of_5']}/5 | {m} | "
                 f"{c['feature']['vector_norm']:.2f} | {c['feature']['promoted_hits_mean']:.1f} / "
                 f"{c['feature']['ppl_median']:.1f} / {c['feature']['broken_of_n']} | "
                 f"{c['random']['promoted_hits_mean']:.1f} / {c['random']['ppl_median']:.1f} / {c['random']['broken_of_n']} |")
L.append("\n## Side-by-side text\n")
for f in D["features"]:
    L.append(f"\n### Feature {f['feature']} ({'clear, 5/5 blind' if f['group'] == 'clear_5of5' else 'NOT clear'}, "
             f"blind {f['blind_correct_of_5']}/5): {f['label']}\n")
    L.append(f"promoted tokens: {' | '.join(repr(t) for t in f['promoted_tokens'])}\n")
    for pi, p in enumerate(D["prompts"]):
        L.append(f"\n**Prompt:** {p}\n")
        L.append("| run | ppl | text |\n|---|---|---|")
        for r in [r for r in f["runs"] if r["prompt_index"] == pi]:
            name = "no steering" if r["kind"] == "none" else f"{r['kind']} {r['multiplier']}×"
            txt = r["text"].replace("\n", " ⏎ ").replace("|", "\\|")
            L.append(f"| {name} | {r['ppl_clean']:.1f} | {txt} |")
(ROOT / "results" / "stage6_report.md").write_text("\n".join(L) + "\n")
print("wrote stage6_summary.json, stage6_steering.png, stage6_report.md")
for row in summary:
    print(row["feature"], row["group"], "first all-broken k:", row["first_multiplier_all_broken"],
          {m: (row["by_multiplier"][str(m)]["feature"]["promoted_hits_mean"], row["by_multiplier"][str(m)]["feature"]["broken_of_n"],
               row["by_multiplier"][str(m)]["random"]["broken_of_n"]) for m in mults})
