"""Stage 7 report from results/stage7/*.json -> results/stage7_report.md, figures/stage7_trace.png."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from src.config import ROOT, load_config

tc = load_config()["trace"]; od = ROOT / "results" / "stage7"
J = lambda n: json.loads((od / n).read_text())
base, an, sel, flip1, ex, prompts = J("baseline.json"), J("analysis.json"), J("selective.json"), J("flip.json"), J("top_feature_examples.json"), J("prompts.json")
E = np.load(od / "effects.npy")
is_ = lambda **kw: np.array([all(p[k] == v for k, v in kw.items()) for p in prompts])
NO, HO = is_(kind="name_only"), is_(split="heldout")

fig, ax = plt.subplots(1, 3, figsize=(15, 4.3))
g, b = E[:, NO & HO & is_(gender="girl")].mean(1), E[:, NO & HO & is_(gender="boy")].mean(1)
ax[0].scatter(g, b, s=6, c="grey")
for j in an["tops"]["overall"]:
    ax[0].annotate(str(j), (g[j], b[j]), fontsize=7)
for k, c in (("girl", "tab:red"), ("boy", "tab:blue")):
    ax[0].scatter(g[sel["sets"][k]["features"]], b[sel["sets"][k]["features"]], s=30, c=c, label=f"{k}-selective top 5")
ax[0].set_xlabel("score drop on girl-name prompts (held-out)"); ax[0].set_ylabel("score drop on boy-name prompts (held-out)")
ax[0].set_title("One feature off at a time"); ax[0].legend(fontsize=7)
names = ["top-10\n(pre-registered)", "girl-selective 5\non girl prompts", "boy-selective 5\non boy prompts"]
recs = [an["joint"]["overall"]["overall"], sel["sets"]["girl"]["heldout_girl_prompts"], sel["sets"]["boy"]["heldout_boy_prompts"]]
drops = [recs[0]["top_drop"], recs[1]["drop"], recs[2]["drop"]]
ax[1].bar(range(3), drops, color="tab:green", label="chosen features"); ax[1].bar(range(3), [r["random_drop_max"] for r in recs], color="black", width=.4, label="largest of 100 random sets")
ax[1].set_xticks(range(3)); ax[1].set_xticklabels(names, fontsize=8); ax[1].set_ylabel("drop in score, held-out names (logits)"); ax[1].legend(fontsize=7)
ax[1].set_title("Features off together vs random sets")
for tg, c in (("girl", "tab:red"), ("boy", "tab:blue")):
    rs = [r for r in sel["flip"] if r["target_prompts"] == tg and r["prompt_kind"] == "name_only"]
    x = [r["strength"] for r in rs]
    ax[2].plot(x, [r["feature_add"]["flip_rate_pair"] for r in rs], "-o", c=c, label=f"{tg} prompts: add other gender's features")
    ax[2].plot(x, [r["feature_swap"]["flip_rate_pair"] for r in rs], "--s", c=c, label=f"{tg} prompts: add + switch off own")
    ax[2].plot(x, [r["random_add"]["flip_rate_pair"] for r in rs], ":", c=c, label=f"{tg} prompts: random direction")
ax[2].set_xlabel("strength (1 = other gender's average level)"); ax[2].set_ylabel("share of prompts where the pronoun preference flips")
ax[2].set_title("Flip test (gender-selective features)"); ax[2].legend(fontsize=6)
fig.tight_layout(); fig.savefig(ROOT / "figures" / "stage7_trace.png", dpi=130)

f2 = lambda x: f"{x:.2f}"
L = ["# Stage 7: tracing 'she'/'he' after a named character\n",
     "> Any feature descriptions here are AI-written (by Claude) and have not been verified by a human.\n",
     "## Setup\n",
     f"- {base['n_prompts']} prompts: 20 names x 6 frames. Names (ranking half / held-out half): girls {tc['girl_names_rank']} / {tc['girl_names_heldout']}; boys {tc['boy_names_rank']} / {tc['boy_names_heldout']}.",
     "- Frames (the name always follows an opening phrase, because most girls' names are only single tokens with a leading space):"]
L += [f"  - `{fr['id']}` ({fr['kind']}): \"{fr['text']}\" -> {'She/He' if fr['case'] == 'cap' else 'she/he'}" for fr in tc["frames"]]
L += ["- Score = logit(correct pronoun) - logit(wrong pronoun) at the last position. Headline = name-only prompts.",
      "- Ablation: zero one feature at every position after the start token, decode, add the SAE error back.\n",
      "## 1. The behaviour exists\n", "| prompts | n | clean score | correct beats wrong | correct is top-1 token | score with SAE reconstruction only |", "|---|---|---|---|---|---|"]
for k in ("name_only", "name_only/girl", "name_only/boy", "noun_name", "noun_name/girl", "noun_name/boy"):
    v = base[k]; L.append(f"| {k} | {v['n']} | {f2(v['clean_score'])} | {v['clean_pair_accuracy']:.0%} | {v['clean_top1_is_correct']:.0%} | {f2(v['recon_only_score'])} |")
L += [f"\nSplicing with the error added back reproduces the clean scores (max difference {base['identity_max_abs_diff']:.1e}).\n",
      f"## 2. Pre-registered test: top {an['top_k']} features by effect on the ranking names\n",
      f"{an['n_firing']} of 2048 features fire on at least one prompt; each was switched off alone. Joint test on held-out names, name-only prompts, against {tc['n_random_sets']} random sets of {an['top_k']} firing features:\n",
      "| ranked on | prompts scored | clean | drop (top set) | score after | random sets: mean / max drop | top beats |", "|---|---|---|---|---|---|---|"]
for rk in ("overall", "girl", "boy"):
    for mk in ("overall", "girl", "boy"):
        v = an["joint"][rk][mk]
        L.append(f"| {rk} | held-out {mk} | {f2(v['clean_score'])} | {f2(v['top_drop'])} | {f2(v['score_after_top_ablation'])} | {f2(v['random_drop_mean'])} / {f2(v['random_drop_max'])} | {v['top_beats_n_random']}/{v['n_random']} |")
L += [f"\n**The pre-registered test passes** ({an['joint']['overall']['overall']['top_beats_n_random']}/100). **But it does not show what it was meant to.** "
      "Most of the top 10 are context features that fire identically on girl and boy prompts (see table): removing them shrinks the score for both genders. "
      "They are needed for the pronoun gap to be large, but carry no information about gender.\n",
      "| feature | in top-10 of | held-out effect girl / boy | peak activation girl / boy prompts | fires on | top training examples |", "|---|---|---|---|---|---|"]
for j, d in sorted(an["features"].items(), key=lambda kv: -kv[1]["rank_effect"]["overall"]):
    exs = "; ".join(e["text"][-45:].replace("|", "/") for e in ex[j]["top"][:3:1])
    L.append(f"| {j} | {', '.join(d['in_top'])} | {f2(d['heldout_effect']['girl'])} / {f2(d['heldout_effect']['boy'])} | {d['mean_peak_act_girl_prompts']:.1f} / {d['mean_peak_act_boy_prompts']:.1f} | "
             f"{', '.join(f'{k.strip()} ({v})' for k, v in d['peak_token_counts'].items())} | {exs} |")
L += ["\n## 3. Post-hoc analysis: gender-selective features\n",
      f"**This analysis was designed after seeing section 2, so treat it as exploratory.** A feature is selective for a gender if its mean peak activation on that gender's ranking-name prompts is at least {tc['selective_ratio']}x the other's. "
      f"Selective features were ranked by ablation effect on their own gender's ranking names; the top {sel['k']} were switched off together on held-out names.\n",
      "| set | features | candidates | drop on own gender (held-out) | random mean / max | beats | drop on other gender | drop on own gender (ranking names) |", "|---|---|---|---|---|---|---|---|"]
for g, o in (("girl", "boy"), ("boy", "girl")):
    s = sel["sets"][g]; v = s[f"heldout_{g}_prompts"]
    L.append(f"| {g}-selective | {s['features']} | {s['n_selective_candidates']} | {f2(v['drop'])} of {f2(v['clean_score'])} (still correct on {v['pair_accuracy_after']:.0%}) | {f2(v['random_drop_mean'])} / {f2(v['random_drop_max'])} | {v['beats_n_random']}/100 | "
             f"{f2(s[f'heldout_{o}_prompts']['drop'])} | {f2(s['ranking_names_own_gender_drop'])} of {f2(s['ranking_names_clean_score'])} |")
L += ["\nPer selective feature (held-out effect on own gender; peak activation per held-out name):\n", "| set | feature | effect on ranking names | effect on held-out names | activation by held-out name |", "|---|---|---|---|---|"]
for g in ("girl", "boy"):
    for j, d in sel["sets"][g]["per_feature"].items():
        L.append(f"| {g} | {j} | {f2(d['rank_effect_own'])} | {f2(d['heldout_effect_own'])} | {', '.join(f'{n} {v:.1f}' for n, v in d['heldout_names_peak_act'].items())} |")
L += ["\n## 4. Flip test\n",
      "Target prompts are held-out names. Added vector = strength x the features' mean activation on the *other* gender's ranking-name prompts (same frame, same position) x their decoder directions. "
      f"Control: random directions of the same length at each position ({tc['flip_random_draws']} draws). 'Flip' = the wrong pronoun's logit exceeds the correct one's. 'Swap' also switches off the prompt's own gender-selective features.\n",
      "### 4a. With gender-selective features (post-hoc set, name-only prompts unless marked)\n",
      "| prompts | added | kind | strength | longest added vector | add: score / flips / other pronoun top-1 | swap: score / flips / top-1 | random: score / flips / top-1 |", "|---|---|---|---|---|---|---|---|"]
for r in sel["flip"]:
    c = lambda n: f"{f2(r[n]['score'])} / {r[n]['flip_rate_pair']:.0%} / {r[n]['top1_is_other_pronoun']:.0%}"
    L.append(f"| {r['target_prompts']} | {r['added_features_of']} feats | {r['prompt_kind']} | {r['strength']} | {f2(r['max_added_norm_model_units'])} | {c('feature_add')} | {c('feature_swap')} | {c('random_add')} |")
L += ["\n### 4b. As first run: top features by per-gender effect (confounded: these sets include the shared context features)\n",
      "| prompts | added | k | strength | add: score / flips / top-1 | swap: score / flips / top-1 | random: score / flips / top-1 |", "|---|---|---|---|---|---|---|"]
for r in flip1["results"]:
    if r["prompt_kind"] != "name_only":
        continue
    c = lambda n: f"{f2(r[n]['score'])} / {r[n]['flip_rate_pair']:.0%} / {r[n]['top1_is_other_pronoun']:.0%}"
    L.append(f"| {r['target_prompts']} | {r['added_features_of']} feats | {r['k']} | {r['strength']} | {c('feature_add')} | {c('feature_swap')} | {c('random_add')} |")
L += ["\n![trace](../figures/stage7_trace.png)\n", "## Limits\n",
      "- Section 3 and 4a were designed after seeing the data; only section 2 was fixed in advance.",
      "- 20 names, 6 hand-written frames, 10 held-out names per analysis (20 name-only prompts per gender). Flip rates are out of 20 prompts.",
      "- Random-set controls are matched in count, not in activation size; context features have large activations, which is part of why they rank high.",
      "- Only layer 3 is tested. Ablation shows a feature is needed there, not how later layers use it.",
      "- The boy-selective features look name-specific (Tom, Tim, Bob) rather than a general 'male name' feature, and transfer less well to held-out names."]
(ROOT / "results" / "stage7_report.md").write_text("\n".join(L) + "\n")
print("ok")
