"""Review rerun 1a report: applies the pre-registered rule in config.yaml `steering_v2.success_rule`.
Reads results/stage6b/steering_v2.json -> results/stage6b_summary.json, results/stage6b_report.md, figures/stage6b_steering_v2.png."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from src.config import ROOT, load_config

sc = load_config()["steering_v2"]
V3 = "--v3" in sys.argv
TAG = "v3" if V3 else "v2"
if V3:
    sc = {**sc, "multipliers": load_config()["steering_v3"]["multipliers"]}
D = json.loads((ROOT / "results" / "stage6b" / f"steering_{TAG}.json").read_text())
K, P, NR = D["multipliers"], len(D["prompts"]), D["n_random"]
labels = {int(r["feature"]): r for r in csv.DictReader(open(ROOT / "results" / "stage5_blind_per_feature.csv")) if r["set"] == "real"}
un = [r["ppl"] for f in D["features"] for r in f["rows"] if r["kind"] == "none" and r["ppl"] is not None]
thr = 2 * float(np.quantile(un, 0.95))
S = {"fluent_threshold_ppl": thr, "unsteered_ppl_p95": float(np.quantile(un, 0.95)), "unsteered_ppl_median": float(np.median(un)),
     "n_unsteered_samples": len(un), "n_prompts": P, "n_random_directions": NR, "multipliers": K, "features": []}
for f in D["features"]:
    rows = f["rows"]
    none = np.array([next(r["hits"] for r in rows if r["kind"] == "none" and r["p"] == p) for p in range(P)], float)
    rec = {"feature": f["feature"], "group": f["group"], "label": labels[f["feature"]]["label"], "blind": int(labels[f["feature"]]["correct_of_5"]),
           "strict_clear_stage5": labels[f["feature"]]["final_clear"] == "True", "label_words": f["label_words"], "median_act": f["median_act"],
           "unsteered_hits_mean": float(none.mean()), "by_k": {}}
    for k in K:
        fe = np.array([next(r["hits"] for r in rows if r["kind"] == "feature" and r["k"] == k and r["p"] == p) for p in range(P)], float)
        ra = np.array([[next(r["hits"] for r in rows if r["kind"] == "random" and r["r"] == j and r["k"] == k and r["p"] == p) for j in range(NR)] for p in range(P)], float)
        pf = [r["ppl"] for r in rows if r["kind"] == "feature" and r["k"] == k and r["ppl"] is not None]
        pr = [r["ppl"] for r in rows if r["kind"] == "random" and r["k"] == k and r["ppl"] is not None]
        wins = int((fe > ra.mean(1)).sum())
        fluent = bool(np.median(pf) <= thr)
        on_label = bool(wins >= 9 and fe.mean() > none.mean())
        rec["by_k"][str(k)] = {"vector_norm_model_units": f["vector_norm_model_units"][str(k)], "feature_hits_mean": float(fe.mean()),
                               "random_hits_mean": float(ra.mean()), "prompts_feature_beats_random_mean": wins,
                               "feature_ppl_median": float(np.median(pf)), "random_ppl_median": float(np.median(pr)),
                               "random_fluent": bool(np.median(pr) <= thr), "fluent": fluent, "on_label": on_label, "success": fluent and on_label}
    rec["steers"] = any(v["success"] for v in rec["by_k"].values())
    rec["success_strengths"] = [k for k in K if rec["by_k"][str(k)]["success"]]
    rec["on_label_strengths"] = [k for k in K if rec["by_k"][str(k)]["on_label"]]
    rec["fluent_strengths"] = [k for k in K if rec["by_k"][str(k)]["fluent"]]
    S["features"].append(rec)
if V3:
    t2 = json.loads((ROOT / "results" / "stage6b_summary.json").read_text())["fluent_threshold_ppl"]
    S["v2_cutoff"] = t2
    for r in S["features"]:
        r["steers_under_v2_cutoff"] = any(c["on_label"] and c["feature_ppl_median"] <= t2 for c in r["by_k"].values())
S["groups"] = {}
for g in sc["groups"]:
    fs = [r for r in S["features"] if r["group"] == g]
    n = sum(r["steers"] for r in fs)
    S["groups"][g] = {"n_features": len(fs), "n_steer": n, "steering_features": [r["feature"] for r in fs if r["steers"]],
                      "verdict": ("reliably" if n >= 5 else "sometimes" if n >= 2 else "not supported") if len(fs) == 6 else "n/a (group of %d)" % len(fs)}
(ROOT / "results" / ("stage6c_summary.json" if V3 else "stage6b_summary.json")).write_text(json.dumps(S, indent=1, ensure_ascii=False))

fig, axes = plt.subplots(2, 7, figsize=(21, 6), sharex=True)
for ax, r in zip(axes.flat, S["features"]):
    ax.plot(K, [r["by_k"][str(k)]["feature_hits_mean"] for k in K], "-o", label="feature")
    ax.plot(K, [r["by_k"][str(k)]["random_hits_mean"] for k in K], "k:", label="random (mean of 3)")
    ax.axhline(r["unsteered_hits_mean"], color="grey", lw=.8, label="unsteered")
    for k in K:
        if not r["by_k"][str(k)]["fluent"]:
            ax.axvspan(k - .4, k + .4, color="red", alpha=.12)
        if r["by_k"][str(k)]["success"]:
            ax.plot(k, r["by_k"][str(k)]["feature_hits_mean"], "*", ms=16, color="gold", mec="k")
    ax.set_title(f"{r['feature']} [{r['group']}] {r['label'][:26]}", fontsize=8)
axes[0, 0].legend(fontsize=6); fig.supxlabel(("strength (fraction of mean activation length)" if V3 else "strength (x median firing)") + "; red = not fluent; star = fluent and on-label"); fig.supylabel("label words in 50 tokens (mean of 10 prompts)")
fig.tight_layout(); fig.savefig(ROOT / "figures" / f"stage6b_steering_{TAG}.png", dpi=110)

L = [("# Steering, third and last design: strength as a fraction of the mean activation length\n" if V3 else "# Review rerun 1a: steering in units of median firing\n"),
     "> No feature label here has been verified by a human.\n",
     f"Design, word lists and success rule were committed in `config.yaml` (`steering_{TAG}`) before the run. {P} prompts, {NR} random directions per feature, strengths {K} x {'the mean activation length at layer 3' if V3 else 'each feature\'s median non-zero firing'}, 50 tokens.",
     f"Fluent threshold (rule: 2 x the 95th percentile of unsteered perplexity, {len(un)} samples): **{thr:.2f}** (unsteered median {S['unsteered_ppl_median']:.2f}, 95th percentile {S['unsteered_ppl_p95']:.2f}).\n",
     "**Rule.** " + " ".join(f"*{k}*: {v}" for k, v in sc["success_rule"].items()) + "\n",
     "## Result by group\n", "| group | features that steer | verdict under the rule |", "|---|---|---|"]
L += [f"| {g} | {v['n_steer']}/{v['n_features']} ({', '.join(map(str, v['steering_features'])) or 'none'}) | {v['verdict']} |" for g, v in S["groups"].items()]
L += ["\n## Every cell\n", "hits = label words per 50 tokens, mean over prompts. wins = prompts (of 10) where the feature text has more label words than the mean of the random texts.\n",
      "| feature | group | label | label words | k | vector length | unsteered hits | feature hits | random hits | wins | feature ppl | random ppl | fluent | on-label | success |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in S["features"]:
    for k in K:
        c = r["by_k"][str(k)]
        L.append(f"| {r['feature']} | {r['group']} | {r['label'].replace('|', '/')} | {', '.join(r['label_words'][:6])}{'…' if len(r['label_words']) > 6 else ''} | {k} | {c['vector_norm_model_units']:.2f} | {r['unsteered_hits_mean']:.1f} | {c['feature_hits_mean']:.1f} | {c['random_hits_mean']:.1f} | {c['prompts_feature_beats_random_mean']} | {c['feature_ppl_median']:.1f} | {c['random_ppl_median']:.1f} | {'yes' if c['fluent'] else 'no'} | {'yes' if c['on_label'] else 'no'} | {'**yes**' if c['success'] else 'no'} |")
L.append("\n![steering](../figures/stage6b_steering_" + TAG + ".png)\n\n## Sample text (prompts 0 and 4; feature and first random direction)\n")
for f in D["features"]:
    L.append(f"\n### Feature {f['feature']}: {labels[f['feature']]['label']}\n")
    for p in (0, 4):
        L += [f"\n**Prompt:** {D['prompts'][p]}\n", "| run | hits | ppl | text |", "|---|---|---|---|"]
        for r in f["rows"]:
            if r["p"] == p and (r["kind"] != "random" or r["r"] == 0):
                nm = "unsteered" if r["kind"] == "none" else f"{r['kind']} {r['k']}x"
                L.append(f"| {nm} | {r['hits']} | {r['ppl']:.1f} | {r['text'].replace(chr(10), ' ⏎ ').replace('|', '/')} |")
(ROOT / "results" / ("stage6c_report.md" if V3 else "stage6b_report.md")).write_text("\n".join(L) + "\n")
print("threshold", round(thr, 2), "unsteered median", round(S["unsteered_ppl_median"], 2))
print(json.dumps(S["groups"], indent=0))
for r in S["features"]:
    print(r["feature"], r["group"], "med", round(r["median_act"], 2), "unst", r["unsteered_hits_mean"], "|", " ".join(
        f"k{k}:{c['feature_hits_mean']:.1f}/{c['random_hits_mean']:.1f} w{c['prompts_feature_beats_random_mean']} ppl{c['feature_ppl_median']:.0f}{'F' if c['fluent'] else 'x'}{'*' if c['success'] else ''}" for k, c in r["by_k"].items()))
