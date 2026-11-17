"""Review rerun 1c, step 2: score the blind verdicts and the fresh-text control blind test.
Rules: config.yaml `stage5_v2` (committed before the run). Reads results/stage5b/key.json and responses/*.json.
Writes results/stage5b_scores.json, results/stage5b_per_feature.csv, results/stage5b_report.md."""
import csv
import json
import sys
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from src.config import ROOT, load_config

cfg = load_config(); v2 = cfg["stage5_v2"]
od = ROOT / "results" / "stage5b"; K = json.loads((od / "key.json").read_text())
S = {}

# ---------------- blind verdicts ----------------
J = {1: {}, 2: {}}
for j in (1, 2):
    for f in sorted((od / "responses").glob(f"verdict_*_j{j}.json")):
        J[j].update(json.loads(f.read_text()))
rows, invalid = [], 0
clear = lambda a: a["top_fit"] >= 16 and a["random_fit"] >= 8
for it in K["verdict_items"]:
    a, b = J[1].get(it["item_id"]), J[2].get(it["item_id"])
    ok = all(isinstance(x, dict) and isinstance(x.get("top_fit"), int) and isinstance(x.get("random_fit"), int)
             and 0 <= x["top_fit"] <= 20 and 0 <= x["random_fit"] <= len(it["random"]) for x in (a, b))
    if not ok:
        invalid += 1; continue
    rows.append({"item_id": it["item_id"], "set": it["tag"], "index_in_list": it["index_in_list"], "feature": it["feature"], "label": it["label"],
                 "old_nonblind_clear": it["old_final_clear"], "j1_top_fit": a["top_fit"], "j1_random_fit": a["random_fit"],
                 "j2_top_fit": b["top_fit"], "j2_random_fit": b["random_fit"], "j1_clear": clear(a), "j2_clear": clear(b),
                 "blind_strict_clear": clear(a) and clear(b)})


def fisher_greater(k1, n1, k2, n2):   # P(real count >= k1) given margins
    K_, N = k1 + k2, n1 + n2
    return sum(comb(K_, x) * comb(N - K_, n1 - x) for x in range(k1, min(K_, n1) + 1)) / comb(N, n1)


V = {"n_items": len(K["verdict_items"]), "n_invalid": invalid}
for tag in ("real", "control"):
    r = [x for x in rows if x["set"] == tag]
    V[tag] = {"n": len(r), "strict_clear": sum(x["blind_strict_clear"] for x in r), "share": float(np.mean([x["blind_strict_clear"] for x in r])),
              "clear_by_either_judge": sum(x["j1_clear"] or x["j2_clear"] for x in r), "j1_clear": sum(x["j1_clear"] for x in r), "j2_clear": sum(x["j2_clear"] for x in r),
              "mean_top_fit_of_20": float(np.mean([(x["j1_top_fit"] + x["j2_top_fit"]) / 2 for x in r])),
              "mean_random_fit_of_10": float(np.mean([(x["j1_random_fit"] + x["j2_random_fit"]) / 2 for x in r])),
              "old_nonblind_clear": sum(x["old_nonblind_clear"] for x in r),
              "old_clear_confirmed_blind": sum(x["old_nonblind_clear"] and x["blind_strict_clear"] for x in r)}
V["fisher_one_sided_p"] = fisher_greater(V["real"]["strict_clear"], V["real"]["n"], V["control"]["strict_clear"], V["control"]["n"])
V["supported"] = bool(V["fisher_one_sided_p"] < 0.05)
V["judge_agreement_on_clear"] = float(np.mean([x["j1_clear"] == x["j2_clear"] for x in rows]))
V["judge_corr_random_fit"] = float(np.corrcoef([x["j1_random_fit"] for x in rows], [x["j2_random_fit"] for x in rows])[0, 1])
V["judge_mean_abs_diff_random_fit"] = float(np.mean([abs(x["j1_random_fit"] - x["j2_random_fit"]) for x in rows]))
S["verdicts"] = V
with open(ROOT / "results" / "stage5b_per_feature.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# ---------------- control blind test on fresh text ----------------
resp = {}
for f in sorted((od / "responses").glob("puzzles_*.json")):
    for k, v in json.loads(f.read_text()).items():
        resp[k] = (v, f.stem)
if len(resp) >= len(K["puzzles"]):
    acc, by_guesser, bad = {"real": [], "control": []}, {}, 0
    for p in K["puzzles"]:
        ans, who = resp.get(p["puzzle_id"], (None, None))
        if not (isinstance(ans, list) and len(set(ans)) == 5 and set(ans) <= set("ABCDEFGHIJ")):
            bad += 1; continue
        a = len(set(ans) & set(p["firing_letters"])) / 5
        acc[p["tag"]].append(a); by_guesser.setdefault(who, {"real": [], "control": []})[p["tag"]].append(a)
    r, c = np.array(acc["real"]), np.array(acc["control"])
    rng = np.random.default_rng(cfg["seed"] + 303)
    obs = r.mean() - c.mean(); pool = np.concatenate([r, c])
    perm = np.array([(lambda q: q[:len(r)].mean() - q[len(r):].mean())(rng.permutation(pool)) for _ in range(10000)])
    # chance simulation: number of the 5 picks that are firing ~ hypergeometric(10, 5, 5)
    sim = rng.hypergeometric(5, 5, 5, size=(100000, len(c))).mean(1) / 5
    old = json.loads((ROOT / "results" / "stage5_blind_scores.json").read_text())
    S["blind_test_fresh_text"] = {
        "n_invalid": bad, "real_50": {"n": len(r), "mean_accuracy": float(r.mean()), "n_5of5": int((r == 1).sum()), "n_at_or_below_3of5": int((r <= .6).sum())},
        "control_50": {"n": len(c), "mean_accuracy": float(c.mean()), "n_5of5": int((c == 1).sum()), "n_at_or_below_3of5": int((c <= .6).sum()),
                       "p_vs_chance": float((sim >= c.mean()).mean())},
        "difference": float(obs), "permutation_p_one_sided": float((perm >= obs).mean()), "supported": bool((perm >= obs).mean() < 0.05),
        "per_guesser": {k: {t: float(np.mean(v[t])) for t in v} for k, v in by_guesser.items()},
        "original_test": {"real_first_50": old["real_first_50"]["mean_accuracy"], "control_50_on_its_training_text": old["control_50"]["mean_accuracy"]}}
(ROOT / "results" / "stage5b_scores.json").write_text(json.dumps(S, indent=1))

L = ["# Review rerun 1c: blind strict-clear verdicts and control blind test on fresh text\n",
     "> No feature label or verdict here has been verified by a human.\n",
     "Design and rules were committed in `config.yaml` (`stage5_v2`) before the run.\n", "## Blind verdicts\n",
     f"{V['n_items']} items (real and control mixed, anonymised), each judged by 2 fresh judges who were not told there were two sources; {invalid} invalid. "
     f"Rule: {v2['blind_verdicts']['strict_clear_rule']}\n",
     "| set | n | blind strict-clear (both judges) | clear by judge 1 / judge 2 | mean top fit (of 20) | mean random fit (of 10) | old non-blind clear | of those, confirmed blind |", "|---|---|---|---|---|---|---|---|"]
for tag in ("real", "control"):
    x = V[tag]
    L.append(f"| {tag} | {x['n']} | **{x['strict_clear']} ({x['share']:.1%})** | {x['j1_clear']} / {x['j2_clear']} | {x['mean_top_fit_of_20']:.1f} | {x['mean_random_fit_of_10']:.1f} | {x['old_nonblind_clear']} | {x['old_clear_confirmed_blind']} |")
L.append(f"\nOne-sided Fisher exact p = {V['fisher_one_sided_p']:.4f}; claim 'real more often strict-clear than control' supported: **{V['supported']}**. "
         f"Judges agreed on the clear/not-clear call for {V['judge_agreement_on_clear']:.0%} of items; their random-fit counts correlate at {V['judge_corr_random_fit']:.2f} (mean absolute difference {V['judge_mean_abs_diff_random_fit']:.1f} of 10).\n")
if "blind_test_fresh_text" in S:
    T = S["blind_test_fresh_text"]
    L += ["## Blind label test on fresh text (control never trained on it)\n", "| set | n | mean accuracy | 5/5 | 3/5 or fewer |", "|---|---|---|---|---|",
          f"| real, first 50 | {T['real_50']['n']} | {T['real_50']['mean_accuracy']:.3f} | {T['real_50']['n_5of5']} | {T['real_50']['n_at_or_below_3of5']} |",
          f"| control | {T['control_50']['n']} | {T['control_50']['mean_accuracy']:.3f} | {T['control_50']['n_5of5']} | {T['control_50']['n_at_or_below_3of5']} |",
          f"\nDifference {T['difference']:.3f}, one-sided permutation p = {T['permutation_p_one_sided']:.4f}; supported: **{T['supported']}**. Control vs chance (0.5): p = {T['control_50']['p_vs_chance']:.4f}. {T['n_invalid']} invalid answers.",
          f"Original test for comparison: real first 50 = {T['original_test']['real_first_50']:.3f}, control on its own training text = {T['original_test']['control_50_on_its_training_text']:.3f}.",
          "Per guesser (real / control): " + "; ".join(f"{k}: {v.get('real', float('nan')):.2f} / {v.get('control', float('nan')):.2f}" for k, v in T["per_guesser"].items()) + "\n"]
L.append("Known limits (stated before the run): " + v2["success_rule"]["known_limits"])
(ROOT / "results" / "stage5b_report.md").write_text("\n".join(L) + "\n")
print(json.dumps({k: v for k, v in S.items()}, indent=1))
