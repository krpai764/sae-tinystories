"""Stage 6 extension report: theme features at gentle strengths.
Reads results/stage6/steering_extension.json + config theme_words -> results/stage6_extension_summary.json,
figures/stage6_extension.png, results/stage6_extension_report.md."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from src.config import ROOT, load_config

cfg = load_config(); tw = {int(k): set(v) for k, v in cfg["steering_extension"]["theme_words"].items()}
D = json.loads((ROOT / "results" / "stage6" / "steering_extension.json").read_text())
mults, BREAK = D["multipliers"], 20.0
words = lambda t: re.findall(r"[a-z]+", t.lower())
summ = []
for f in D["features"]:
    T = tw[f["feature"]]
    for r in f["runs"]:
        r["theme_hits"] = sum(w in T for w in words(r["text"]))
    row = {"feature": f["feature"], "group": f["group"], "label": f["label"], "blind_correct_of_5": f["blind_correct_of_5"],
           "theme_words": sorted(T), "none": {"theme_hits_mean": float(np.mean([r["theme_hits"] for r in f["runs"] if r["kind"] == "none"]))},
           "by_multiplier": {}}
    for m in mults:
        row["by_multiplier"][str(m)] = {k: {
            "theme_hits_mean": float(np.mean([r["theme_hits"] for r in rs])),
            "promoted_hits_mean": float(np.mean([r["promoted_hits"] for r in rs])),
            "ppl_median": float(np.median([r["ppl_clean"] for r in rs])),
            "broken_of_n": f"{sum(r['ppl_clean'] > BREAK for r in rs)}/{len(rs)}"}
            for k in ("feature", "random") for rs in [[r for r in f["runs"] if r["kind"] == k and r["multiplier"] == m]]}
    # 'on-theme and fluent': feature run with theme_hits > max(random theme hits at same k, unsteered) and ppl <= BREAK
    row["fluent_on_theme_runs"] = [{"prompt": r["prompt_index"], "k": r["multiplier"], "theme_hits": r["theme_hits"]}
        for r in f["runs"] if r["kind"] == "feature" and r["ppl_clean"] <= BREAK and r["theme_hits"] >
        max([q["theme_hits"] for q in f["runs"] if q["prompt_index"] == r["prompt_index"] and (q["kind"] == "none" or (q["kind"] == "random" and q["multiplier"] == r["multiplier"]))])]
    summ.append(row)
(ROOT / "results" / "stage6_extension_summary.json").write_text(json.dumps({"break_threshold_ppl": BREAK, "features": summ}, indent=1, ensure_ascii=False))

fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
for row in summ:
    ax[0].plot(mults, [row["by_multiplier"][str(m)]["feature"]["theme_hits_mean"] for m in mults], marker="o", label=f"{row['feature']} {row['label'][:28]}")
    ax[1].plot(mults, [row["by_multiplier"][str(m)]["feature"]["ppl_median"] for m in mults], marker="o")
ax[0].plot(mults, [np.mean([r["by_multiplier"][str(m)]["random"]["theme_hits_mean"] for r in summ]) for m in mults], "k:", lw=3, label="random direction (mean)")
ax[1].plot(mults, [np.median([r["by_multiplier"][str(m)]["random"]["ppl_median"] for r in summ]) for m in mults], "k:", lw=3, label="random direction (median)")
ax[1].set_yscale("log"); ax[1].axhline(BREAK, color="grey", lw=.8)
for a in ax: a.set_xlabel("steering strength (x typical strong firing)")
ax[0].set_ylabel("theme words in 50 generated tokens"); ax[1].set_ylabel("perplexity under unsteered model")
ax[0].legend(fontsize=7); ax[1].legend(fontsize=7); fig.tight_layout(); fig.savefig(ROOT / "figures" / "stage6_extension.png", dpi=130)

L = ["# Stage 6 extension: steering context/theme features\n",
     "> All feature labels are AI-written (by Claude) and have not been verified by a human.\n",
     "**How features were chosen.** Every Stage 5 label that names a topic or domain (weather, bees, chores, music, "
     "danger) rather than a syntactic slot or one predicted next word, whatever its clear verdict or blind score, "
     "excluding features already steered. That gave 6: " + ", ".join(f"{r['feature']} ({r['label']}, {r['blind_correct_of_5']}/5 blind, {'clear' if r['group']=='clear' else 'not clear'})" for r in summ) + ".\n",
     f"Same method as the main Stage 6 run (same prompts, seeds, random-direction control of equal length), strengths {mults}. "
     f"**Theme words** were fixed in config.yaml before reading any steered text; counted as whole words. "
     f"'Broken' = perplexity under the unsteered model > {BREAK:.0f}. A run counts as *fluent and on-theme* if not broken and it has "
     "more theme words than both the unsteered text and the random control at the same strength and prompt.\n",
     "![extension](../figures/stage6_extension.png)\n", "## Summary\n",
     "| feature | label | blind | fluent & on-theme runs (of 12) | k where both prompts broken |", "|---|---|---|---|---|"]
for row in summ:
    br = [m for m in mults if row["by_multiplier"][str(m)]["feature"]["broken_of_n"] == "2/2"]
    L.append(f"| {row['feature']} | {row['label']} | {row['blind_correct_of_5']}/5 | {len(row['fluent_on_theme_runs'])} "
             f"({', '.join(f'p{x['prompt']} k={x['k']}' for x in row['fluent_on_theme_runs']) or 'none'}) | {br[0] if br else 'none up to 2'} |")
L += ["\n| feature | k | feature: theme / ppl / broken | random: theme / ppl / broken |", "|---|---|---|---|"]
for row in summ:
    for m in mults:
        c = row["by_multiplier"][str(m)]
        L.append(f"| {row['feature']} | {m} | {c['feature']['theme_hits_mean']:.1f} / {c['feature']['ppl_median']:.1f} / {c['feature']['broken_of_n']} | "
                 f"{c['random']['theme_hits_mean']:.1f} / {c['random']['ppl_median']:.1f} / {c['random']['broken_of_n']} |")
L.append("\n## Side-by-side text\n")
for f in D["features"]:
    L.append(f"\n### Feature {f['feature']} ({f['group'].replace('_', ' ')}, blind {f['blind_correct_of_5']}/5): {f['label']}\n")
    L.append(f"theme words: {', '.join(sorted(tw[f['feature']]))}\n")
    for pi, p in enumerate(D["prompts"]):
        L += [f"\n**Prompt:** {p}\n", "| run | theme | ppl | text |", "|---|---|---|---|"]
        for r in [r for r in f["runs"] if r["prompt_index"] == pi]:
            name = "no steering" if r["kind"] == "none" else f"{r['kind']} {r['multiplier']}×"
            L.append(f"| {name} | {r['theme_hits']} | {r['ppl_clean']:.1f} | {r['text'].replace(chr(10), ' ⏎ ').replace('|', chr(92) + '|')} |")
(ROOT / "results" / "stage6_extension_report.md").write_text("\n".join(L) + "\n")
for row in summ:
    print(row["feature"], row["label"][:35], "fluent-on-theme:", [(x["prompt"], x["k"], x["theme_hits"]) for x in row["fluent_on_theme_runs"]],
          {m: (row["by_multiplier"][str(m)]["feature"]["theme_hits_mean"], row["by_multiplier"][str(m)]["feature"]["broken_of_n"], row["by_multiplier"][str(m)]["random"]["theme_hits_mean"]) for m in mults})
