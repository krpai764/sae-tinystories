"""Review rerun 1b report: results/stage7b/analysis.json -> results/stage7b_report.md."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT, load_config

tc = load_config()["trace_v2"]
A = json.loads((ROOT / "results" / "stage7b" / "analysis.json").read_text())
f2 = lambda x: f"{x:.2f}"; f3 = lambda x: f"{x:.3f}"; pc = lambda x: f"{x:.0%}"
L = ["# Review rerun 1b: tracing with held-out frames and an activation-matched control\n",
     "> Any feature descriptions are AI-written (by Claude) and have not been verified by a human.\n",
     "Design and success rules were committed in `config.yaml` (`trace_v2`) before the run. Ranking uses ranking names x ranking frames; every test uses held-out names x held-out frames (name-only unless marked).\n",
     "**Rules.** " + " ".join(f"*{k}*: {v}" for k, v in tc["success_rule"].items()) + "\n",
     "## Baseline (unmodified model)\n", "| prompts | n | score | pair preference correct | top-1 is correct pronoun |", "|---|---|---|---|---|"]
for k, v in A["baseline"].items():
    L.append(f"| {k} | {v['n']} | {f2(v['score'])} | {pc(v['pair_preference_correct'])} | {pc(v['top1_correct'])} |")
L += [f"\nGate passed: {A['gate_passed']}. {A['n_firing']} features fire on the prompts. Clean loss on the {tc['loss_stories']} held-out stories: {f3(A['story_loss_clean'])} nats.\n",
      "## Set ablations (held-out names x held-out frames)\n",
      "| set | features | scored on | drop | matched random: mean / max drop | beats | pair pref. correct after | top-1 correct after (random) | prompt loss change (random) | story loss change (random) | random/tested activation |",
      "|---|---|---|---|---|---|---|---|---|---|---|"]
for name, s, key in [("top 10 (R1)", A["top10"], "overall"), ("girl-selective (R2)", A["selective"]["girl"], "girl"), ("boy-selective (R2)", A["selective"]["boy"], "boy")]:
    m, r = s["measures"][key], s["matched_random"]
    L.append(f"| {name} | {s['features']} | {key} | {f2(m['drop'])} (to {f2(m['score'])}) | {f2(r[key]['drop_mean'])} / {f2(r[key]['drop_max'])} | {r[key]['tested_beats']}/{tc['n_random_sets']} | {pc(m['pair_preference_correct'])} | "
             f"{pc(m['top1_correct'])} ({pc(r['top1_correct_mean'])}) | {f3(m['prompt_loss_change'])} ({f3(r['prompt_loss_change_mean'])}) | {f3(s['story_loss_change'])} ({f3(r['story_loss_change_mean_first_sets'])}) | {f2(r['activation_ratio_mean'])} |")
L.append(f"\nR1 passed: **{A['R1_passed']}**. R2 girl: **{A['selective']['girl']['R2_passed']}**; R2 boy: **{A['selective']['boy']['R2_passed']}**.\n")
for g in ("girl", "boy"):
    s = A["selective"][g]; o = "boy" if g == "girl" else "girl"
    L.append(f"- {g}-selective: own-gender drop {f2(s['measures'][g]['drop'])}, other-gender drop {f2(s['measures'][o]['drop'])}; specificity {f2(s['specificity']['tested'])} vs random mean {f2(s['specificity']['random_mean'])} (beats {s['specificity']['tested_beats']}/{tc['n_random_sets']}).")
L += ["\n### Each feature in the tested sets\n", "| set | feature | effect on ranking prompts | effect on held-out prompts | peak activation girl / boy (ranking) | peak activation by held-out name |", "|---|---|---|---|---|---|"]
for name, s in [("top 10", A["top10"]), ("girl-selective", A["selective"]["girl"]), ("boy-selective", A["selective"]["boy"])]:
    for j, a, b, pk, byn in zip(s["features"], s["rank_effect_each"], s["heldout_effect_each"], s["peak_act_girl_boy_rank"], s["peak_act_heldout_by_name"]):
        L.append(f"| {name} | {j} | {f2(a)} | {f2(b)} | {pk[0]:.1f} / {pk[1]:.1f} | {', '.join(f'{n} {v:.1f}' for n, v in byn.items())} |")
L += ["\n## Flip test (held-out names x held-out frames)\n",
      "pair = wrong pronoun's logit exceeds the correct one's; top-1 = the wrong pronoun is the model's single most likely next token; names = held-out names (of 5) with a majority of their 4 prompts pair-flipped.\n",
      "| prompts | features added from | strength | added length at name | add: pair / top-1 / names | swap: pair / top-1 / names | random: pair / top-1 / names | add: prompt loss change (random) | add on noun-plus-name prompts: pair / top-1 |", "|---|---|---|---|---|---|---|---|---|"]
for t in ("girl", "boy"):
    for r in A["flip"][t]["by_strength"]:
        n, nn = r["name_only"], r["noun_name"]
        c = lambda k: f"{pc(n[k]['pair_flip'])} / {pc(n[k]['top1_other_pronoun'])} / {n[k]['names_majority_flipped']}"
        L.append(f"| {t} | {A['flip'][t]['added_features_of']} | {r['strength']} | {f2(r['added_norm_name_pos'])} | {c('add')} | {c('swap')} | {c('random')} | {f3(n['add']['prompt_loss_change'])} ({f3(n['random']['prompt_loss_change'])}) | {pc(nn['add']['pair_flip'])} / {pc(nn['add']['top1_other_pronoun'])} |")
L.append(f"\nR3 girl prompts (boy features added): **{A['flip']['girl']['R3_passed']}**. R3 boy prompts (girl features added): **{A['flip']['boy']['R3_passed']}**.")
L.append("\nThe selective features' activation after the name position is zero to two decimals (added length at later positions: " + ", ".join(f2(r["added_norm_later_pos"]) for r in A["flip"]["girl"]["by_strength"]) + "), so the vector is in effect added at the name token only.")
(ROOT / "results" / "stage7b_report.md").write_text("\n".join(L) + "\n")
print("wrote results/stage7b_report.md")
