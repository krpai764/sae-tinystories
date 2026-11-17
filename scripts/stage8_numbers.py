"""Stage 8: collect every number the README and REPORT cite into results/headline_numbers.json.

Reads only files under results/ (plus config.yaml for settings). README.md and REPORT.md are then
generated from this one file by scripts/stage8_docs.py, so no number in them is typed by hand.
"""
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ROOT, load_config

R = ROOT / "results"
J = lambda p: json.loads((R / p).read_text())
cfg = load_config()
N = {}

# ---------- setup ----------
s2, s2c, s3 = J("stage2_stats.json"), J("stage2_checks.json"), J("stage3_runs.json")
width = round((s3["rescale_factor"] * s2c["mean_raw_norm"]) ** 2)  # rescale makes mean norm sqrt(width)
N["setup"] = {
    "model": cfg["model"]["name"], "layer": cfg["model"]["layer"], "seed": cfg["seed"], "width": width,
    "dictionary_size": cfg["sae"]["expansion"] * width, "expansion": cfg["sae"]["expansion"],
    "lr": cfg["sae"]["lr"], "batch_size": cfg["sae"]["batch_size"], "epochs": cfg["sae"]["epochs"],
    "lambdas": cfg["sae"]["l1_coeffs"], "chosen_lambda": cfg["interpret"]["chosen_lambda"],
    "train_stories": s2["splits"]["train"]["num_stories"], "train_tokens_in_sae": s3["train_tokens"],
    "heldout_stories": s2c["heldout_stories"], "heldout_tokens_in_sae_eval": s3["eval_tokens"],
    "train_heldout_identical_stories": s2c["train_heldout_identical_stories"],
    "data_dir_GB": s2c["data_dir_GB"], "rescale_factor": s3["rescale_factor"],
    "mean_activation_norm_model_units": s2["splits"]["train"]["norm_excluding_pos0"]["mean"],
    "fraction_squared_norm_in_mean": s2c["fraction_of_squared_norm_in_mean"],
    "pos0_norm": s2["splits"]["train"]["norm_pos0_only"]["mean"],
    "enc_init_scale": cfg["sae"]["enc_init_scale"], "resample_after_epochs": cfg["sae"]["resample_after_epochs"],
    "resample_pool": cfg["sae"]["resample_pool"],
    "b_d_geometric_median_minus_mean_norm": s3["runs"][str(cfg["interpret"]["chosen_lambda"])]["b_d_init"]["geometric_median_minus_mean_norm"],
    "b_d_mean_norm": s3["runs"][str(cfg["interpret"]["chosen_lambda"])]["b_d_init"]["mean_norm"],
    "generation_temperature": cfg["generation"]["temperature"], "steer_max_new_tokens": cfg["steering"]["max_new_tokens"],
    "interpret_top_k": cfg["interpret"]["top_k"], "interpret_n_random": cfg["interpret"]["n_random"],
    "n_promoted": cfg["interpret"]["n_promoted_tokens"], "verify_max_abs_diff": s2["verification"]["max_abs_diff"],
    "verify_stories_checked": s2["verification"]["stories_checked"],
}
from transformers import AutoConfig
N["setup"]["n_blocks"] = AutoConfig.from_pretrained(cfg["model"]["name"], cache_dir=ROOT / cfg["paths"]["hf_cache_dir"], local_files_only=True).num_layers

# ---------- SAEs (stage 3 + 4) ----------
s4 = J("stage4_faithfulness.json")
p0 = s4["settings"]["p0kept"]
N["faithfulness"] = {"n_stories": s4["n_stories"], "n_predicted_tokens": s4["n_predicted_tokens"],
                     "L_clean": s4["L_clean"], "L_zero": p0["L_zero"], "L_mean": p0["L_mean"],
                     "perplexity_clean": math.exp(s4["L_clean"]), "runs": {}}
for lam, r in s3["runs"].items():
    f4 = p0["saes"][lam]
    N["faithfulness"]["runs"][lam] = {
        "variance_explained": r["final"]["variance_explained"], "l0": r["final"]["l0"],
        "never_fire_heldout": r["final"]["dead_fraction"], "dead_last_train_epoch": f4["dead_fraction_last_train_epoch"],
        "l0_levelled_off": r["l0_levelled_off"], "total_resampled": r["total_resampled"],
        "loss_recovered_zero": f4["loss_recovered_zero"], "loss_recovered_zero_ci95": f4["loss_recovered_zero_ci95"],
        "loss_recovered_mean": f4["loss_recovered_mean"], "loss_recovered_mean_ci95": f4["loss_recovered_mean_ci95"],
        "extra_loss_nats": f4["extra_loss_nats"], "L_spliced": f4["L_spliced"], "perplexity_spliced": math.exp(f4["L_spliced"]),
    }

# ---------- interpretation (stage 5) ----------
b5 = J("stage5_blind_scores.json"); rc = J("stage5_random_control.json")
N["interpretation"] = {
    "n_features_labelled": b5["real_all_200"]["n"], "n_control_labelled": b5["control_50"]["n"],
    "clear_real": b5["final_clear_share"]["real_n"], "clear_real_share": b5["final_clear_share"]["real"],
    "clear_control": b5["final_clear_share"]["control_n"], "clear_control_share": b5["final_clear_share"]["control"],
    "clear_if_random_firings_ignored_real": b5["final_clear_share"]["real_suggested_clear_ignoring_random"],
    "clear_if_random_firings_ignored_control": b5["final_clear_share"]["control_suggested_clear_ignoring_random"],
    "blind": {k: b5[k] for k in ("real_all_200", "real_first_50", "control_50", "real_final_clear", "real_not_final_clear",
                                 "real_suggested_unclear", "control_final_clear")},
    "n_puzzles": b5["n_puzzles"], "n_invalid": b5["n_invalid_responses"],
    "tercile_real": b5["real_firing_detection_by_strength_tercile"], "tercile_control": b5["control_firing_detection_by_strength_tercile"],
    "control_sae": {"variance_explained": rc["final"]["variance_explained"], "l0": rc["final"]["l0"],
                    "train_tokens": rc["train_tokens"], "eval_tokens": rc["eval_tokens"], "epochs": rc["epochs"]},
}
key = J("stage5_blind/key.json")
N["interpretation"]["n_snippets_per_puzzle"] = len(key["puzzles"][0]["snippets"])
N["interpretation"]["n_firing_snippets_per_puzzle"] = len(key["puzzles"][0]["firing_letters"])
assert all(len(p["snippets"]) == N["interpretation"]["n_snippets_per_puzzle"] and len(p["firing_letters"]) == N["interpretation"]["n_firing_snippets_per_puzzle"] for p in key["puzzles"])
N["interpretation"]["n_subagents"] = len(list((R / "stage5_blind").glob("puzzles_*.txt")))
rows = list(csv.DictReader(open(R / "stage5_blind_per_feature.csv")))
real = [r for r in rows if r["set"] == "real"]
N["interpretation"]["real_features_blind_5of5_and_clear"] = sum(r["final_clear"] == "True" and r["correct_of_5"] == "5" for r in real)
N["interpretation"]["real_features_blind_at_or_below_3of5"] = sum(int(r["correct_of_5"]) <= 3 for r in real)

# ---------- steering (stage 6) ----------
sm, se = J("stage6_summary.json"), J("stage6_extension_summary.json")
st = J("stage6/steering.json")
N["steering"] = {"break_threshold_ppl": sm["break_threshold_ppl"], "mean_activation_norm": sm["mean_activation_norm_model_units"],
                 "multipliers_main": st["multipliers"], "n_prompts": len(st["prompts"]), "main": [], "extension": []}
for f in sm["features"]:
    bm = f["by_multiplier"]
    N["steering"]["main"].append({
        "feature": f["feature"], "group": f["group"], "label": f["label"], "blind": f["blind_correct_of_5"],
        "by_k": {k: {"feature_broken": v["feature"]["broken_of_n"], "random_broken": v["random"]["broken_of_n"],
                     "feature_promoted_hits": v["feature"]["promoted_hits_mean"], "random_promoted_hits": v["random"]["promoted_hits_mean"],
                     "feature_ppl": v["feature"]["ppl_median"], "random_ppl": v["random"]["ppl_median"]} for k, v in bm.items()},
        "first_k_all_broken": f["first_multiplier_all_broken"], "unsteered_ppl": f["none"]["ppl_median"]})
for f in se["features"]:
    bm = f["by_multiplier"]
    # best on-theme result among strengths where neither prompt broke, vs random at the same strengths
    ok = [k for k, v in bm.items() if v["feature"]["broken_of_n"].startswith("0/")]
    N["steering"]["extension"].append({
        "feature": f["feature"], "group": f["group"], "label": f["label"], "blind": f["blind_correct_of_5"],
        "theme_words_unsteered": f["none"]["theme_hits_mean"],
        "max_theme_words_unbroken_feature": max([bm[k]["feature"]["theme_hits_mean"] for k in ok], default=None),
        "max_theme_words_unbroken_random": max([bm[k]["random"]["theme_hits_mean"] for k in ok], default=None),
        "max_unbroken_k": max([float(k) for k in ok], default=None),
        "by_k": {k: {"feature_theme": v["feature"]["theme_hits_mean"], "random_theme": v["random"]["theme_hits_mean"],
                     "feature_broken": v["feature"]["broken_of_n"], "random_broken": v["random"]["broken_of_n"]} for k, v in bm.items()}})
un = [r["ppl_clean"] for f in st["features"] + J("stage6/steering_extension.json")["features"] for r in f["runs"] if r["kind"] == "none"]
N["steering"]["unsteered_ppl_min"], N["steering"]["unsteered_ppl_max"] = min(un), max(un)
N["steering"]["n_features_steered_total"] = len(st["features"]) + len(J("stage6/steering_extension.json")["features"])
N["steering"]["multipliers_extension"] = list(se["features"][0]["by_multiplier"].keys())

# ---------- tracing (stage 7) ----------
b7, a7, sel, fl = J("stage7/baseline.json"), J("stage7/analysis.json"), J("stage7/selective.json"), J("stage7/flip.json")
joint = a7["joint"]["overall"]["overall"]
top10 = a7["tops"]["overall"]
shared = [j for j in top10 if min(a7["features"][str(j)]["mean_peak_act_girl_prompts"], a7["features"][str(j)]["mean_peak_act_boy_prompts"]) >= 1.0]
N["trace"] = {
    "n_prompts": b7["n_prompts"], "name_only": b7["name_only"], "name_only_girl": b7["name_only/girl"], "name_only_boy": b7["name_only/boy"],
    "noun_name": b7["noun_name"], "n_firing_features": a7["n_firing"], "top10": top10, "top10_passed": a7["top_k_test_passed"],
    "top10_fire_on_both_genders_count": len(shared), "top10_fire_on_both_genders": shared,
    "top10_joint": {k: a7["joint"]["overall"][k] for k in ("overall", "girl", "boy")},
    "selective": {g: {"features": sel["sets"][g]["features"], "n_candidates": sel["sets"][g]["n_selective_candidates"],
                      "own": sel["sets"][g][f"heldout_{g}_prompts"], "other": sel["sets"][g][f"heldout_{'boy' if g == 'girl' else 'girl'}_prompts"],
                      "ranking_names_drop": sel["sets"][g]["ranking_names_own_gender_drop"],
                      "ranking_names_clean": sel["sets"][g]["ranking_names_clean_score"],
                      "per_feature": sel["sets"][g]["per_feature"]} for g in ("girl", "boy")},
    "selection_ratio": cfg["trace"]["selective_ratio"],
    "n_frames": len(cfg["trace"]["frames"]), "n_frames_name_only": sum(f["kind"] == "name_only" for f in cfg["trace"]["frames"]),
    "n_frames_noun_name": sum(f["kind"] == "noun_name" for f in cfg["trace"]["frames"]),
    "n_names": sum(len(cfg["trace"][k]) for k in ("girl_names_rank", "girl_names_heldout", "boy_names_rank", "boy_names_heldout")),
    "n_names_heldout_per_gender": len(cfg["trace"]["girl_names_heldout"]), "names": {k: cfg["trace"][k] for k in (
        "girl_names_rank", "girl_names_heldout", "boy_names_rank", "boy_names_heldout")},
    "flip_strengths": cfg["trace"]["flip_strengths"],
    "flip_selective": [{"target": r["target_prompts"], "strength": r["strength"], "kind": r["prompt_kind"], "n": r["n"],
                        "add_flip": r["feature_add"]["flip_rate_pair"], "swap_flip": r["feature_swap"]["flip_rate_pair"],
                        "random_flip": r["random_add"]["flip_rate_pair"], "add_score": r["feature_add"]["score"],
                        "clean_score": r["clean_score"]} for r in sel["flip"]],
    "n_random_sets": cfg["trace"]["n_random_sets"], "flip_random_draws": cfg["trace"]["flip_random_draws"],
}


# ---------- review reruns (2026-11-17) ----------
mean_norm = N["setup"]["mean_activation_norm_model_units"]
N["setup"]["density_gt_1pct"] = s3["runs"][str(cfg["interpret"]["chosen_lambda"])]["final"]["density_gt_1pct"]
for lam_, r in N["faithfulness"]["runs"].items():
    r["perplexity_rise"] = r["perplexity_spliced"] / N["faithfulness"]["perplexity_clean"] - 1
b7_ = J("stage7/baseline.json")
N["trace"]["recon_only_name_only"] = b7_["name_only"]["recon_only_score"]

# steering designs side by side; vector lengths as a fraction of the mean activation length
def lengths_d1(fname):
    out = {}
    for f in J(fname)["features"]:
        ks = sorted({r["multiplier"] for r in f["runs"] if r["kind"] == "feature"})
        out[f["feature"]] = {str(k): next(r["vector_norm_model_units"] for r in f["runs"] if r["kind"] == "feature" and r["multiplier"] == k) / mean_norm for k in ks}
    return out
d1len = {**lengths_d1("stage6/steering.json"), **lengths_d1("stage6/steering_extension.json")}
designs = {}
for tag, summ, raw in (("design2", "stage6b_summary.json", "stage6b/steering_v2.json"), ("design3", "stage6c_summary.json", "stage6b/steering_v3.json")):
    S_, D_ = J(summ), J(raw)
    lens = {f["feature"]: {k: v / mean_norm for k, v in f["vector_norm_model_units"].items()} for f in D_["features"]}
    designs[tag] = {"fluent_threshold_ppl": S_["fluent_threshold_ppl"], "unsteered_ppl_median": S_["unsteered_ppl_median"], "multipliers": S_["multipliers"],
                    "n_prompts": S_["n_prompts"], "n_random": S_["n_random_directions"], "groups": S_["groups"],
                    "n_steer_total": sum(r["steers"] for r in S_["features"]), "n_features": len(S_["features"]),
                    "features": {r["feature"]: {"group": r["group"], "steers": r["steers"], "success_strengths": r["success_strengths"],
                                                "on_label_strengths": r["on_label_strengths"], "fluent_strengths": r["fluent_strengths"],
                                                "max_fluent_length_frac": max([lens[r["feature"]][str(k)] for k in r["fluent_strengths"]], default=0.0),
                                                "length_frac_range": [min(lens[r["feature"]].values()), max(lens[r["feature"]].values())],
                                                "best_fluent_hits": max([r["by_k"][str(k)]["feature_hits_mean"] for k in r["fluent_strengths"]], default=0.0),
                                                "best_fluent_random_hits": max([r["by_k"][str(k)]["random_hits_mean"] for k in r["fluent_strengths"]], default=0.0),
                                                "by_k": r["by_k"]} for r in S_["features"]}}
    if tag == "design3":
        designs[tag]["n_steer_under_design2_cutoff"] = sum(r["steers_under_v2_cutoff"] for r in S_["features"])
d1 = {}
for m in N["steering"]["main"]:
    d1[m["feature"]] = {"kind": "main", "first_k_all_broken": m["first_k_all_broken"], "length_frac_range": [min(d1len[m["feature"]].values()), max(d1len[m["feature"]].values())],
                        "first_broken_length_frac": d1len[m["feature"]][str(m["first_k_all_broken"])] if m["first_k_all_broken"] else None}
for e in N["steering"]["extension"]:
    d1[e["feature"]] = {"kind": "extension", "max_unbroken_k": e["max_unbroken_k"], "length_frac_range": [min(d1len[e["feature"]].values()), max(d1len[e["feature"]].values())],
                        "more_theme_words_than_random": e["max_theme_words_unbroken_feature"] > e["max_theme_words_unbroken_random"],
                        "theme_feature": e["max_theme_words_unbroken_feature"], "theme_random": e["max_theme_words_unbroken_random"]}
designs["design1"] = {"features": d1, "n_prompts": len(J("stage6/steering.json")["prompts"]),
                      "n_main_eligible": N["interpretation"]["real_features_blind_5of5_and_clear"]}
N["steering_designs"] = designs

# tracing rerun
t2 = J("stage7b/analysis.json")
N["trace_v2"] = {"baseline": t2["baseline"], "n_firing": t2["n_firing"], "story_loss_clean": t2["story_loss_clean"], "gate_passed": t2["gate_passed"],
                 "R1_passed": t2["R1_passed"], "n_selective_candidates": {g: t2[f"n_selective_candidates_{g}"] for g in ("girl", "boy")},
                 "loss_stories": cfg["trace_v2"]["loss_stories"], "loss_random_sets": cfg["trace_v2"]["loss_random_sets"], "n_random_sets": cfg["trace_v2"]["n_random_sets"],
                 "n_frames_heldout": len(cfg["trace_v2"]["frames_heldout"]), "flip_random_draws": cfg["trace_v2"]["flip_random_draws"]}
for name, s_ in (("top10", t2["top10"]), ("girl", t2["selective"]["girl"]), ("boy", t2["selective"]["boy"])):
    N["trace_v2"][name] = {"features": s_["features"], "measures": s_["measures"], "matched_random": s_["matched_random"], "story_loss_change": s_["story_loss_change"],
                           "specificity": s_.get("specificity"), "R2_passed": s_.get("R2_passed"),
                           "heldout_effect_each": s_["heldout_effect_each"], "rank_effect_each": s_["rank_effect_each"],
                           "n_heldout_effect_near_zero": sum(abs(x) < 0.1 for x in s_["heldout_effect_each"]),
                           "peak_act_heldout_by_name": s_["peak_act_heldout_by_name"]}
N["trace_v2"]["flip"] = {t: {"R3_passed": t2["flip"][t]["R3_passed"], "added_features_of": t2["flip"][t]["added_features_of"],
                             "by_strength": [{"strength": r["strength"], "add": r["name_only"]["add"], "swap": r["name_only"]["swap"], "random": r["name_only"]["random"],
                                              "noun_add": r["noun_name"]["add"], "added_norm_name_pos": r["added_norm_name_pos"]} for r in t2["flip"][t]["by_strength"]]}
                         for t in ("girl", "boy")}
# feature 1511 peak per held-out girl name; 1532 per held-out boy name
pk = {j: d for j, d in zip(t2["top10"]["features"], t2["top10"]["peak_act_heldout_by_name"])}
N["trace_v2"]["peak_1511"] = {n: pk[1511][n] for n in cfg["trace"]["girl_names_heldout"]}
N["trace_v2"]["peak_1532"] = {n: pk[1532][n] for n in cfg["trace"]["boy_names_heldout"]}
N["trace_v2"]["girl_effect_1511"] = t2["selective"]["girl"]["heldout_effect_each"][t2["selective"]["girl"]["features"].index(1511)]

# Stage 5 blind verdicts and fresh-text blind test
s5 = J("stage5b_scores.json")
N["stage5_v2"] = s5
k5 = J("stage5b/key.json")
import statistics
N["stage5_v2"]["median_random_firing_act_real"] = statistics.median(statistics.median(e["act"] for e in it["random"]) for it in k5["verdict_items"] if it["tag"] == "real")
N["stage5_v2"]["median_top_act_real"] = statistics.median(statistics.median(e["act"] for e in it["top"]) for it in k5["verdict_items"] if it["tag"] == "real")
N["stage5_v2"]["n_judges_per_item"] = cfg["stage5_v2"]["blind_verdicts"]["judges"]
N["stage5_v2"]["n_verdict_files"] = len(list((R / "stage5b").glob("verdict_items_*.txt")))
N["stage5_v2"]["n_puzzle_files"] = len(list((R / "stage5b").glob("puzzles_*.txt")))


import re as _re
_r = cfg["stage5_v2"]["blind_verdicts"]["strict_clear_rule"]
m_ = _re.search(r"top_fit >= (\d+) of (\d+) AND random_fit >= (\d+) of (\d+)", _r)
N["stage5_v2"]["rule"] = {"top_min": int(m_.group(1)), "top_n": int(m_.group(2)), "random_min": int(m_.group(3)), "random_n": int(m_.group(4))}
N["stage5_v2"]["selective_ratio"] = cfg["trace_v2"]["selective_ratio"]
m_ = _re.search(r"at least (\d+) of the (\d+) prompts", cfg["steering_v2"]["success_rule"]["on_label"])
N["steering_designs"]["rule_min_wins"], N["steering_designs"]["rule_n_prompts"] = int(m_.group(1)), int(m_.group(2))
N["interpretation"]["puzzles_per_subagent"] = N["interpretation"]["n_puzzles"] // N["interpretation"]["n_subagents"]
lab_ = {int(r["feature"]): r["label"] for r in rows if r["set"] == "real"}
N["steering_designs"]["design1"]["example_topic_label_left_out"] = {"feature": 1470, "label": lab_[1470]}


m_ = _re.search(r"\(([\d,]+) permutations", cfg["stage5_v2"]["success_rule"]["blind_test"])
N["stage5_v2"]["n_permutations"] = int(m_.group(1).replace(",", ""))
N["stage5_v2"]["p_resolution"] = 1 / N["stage5_v2"]["n_permutations"]

(R / "headline_numbers.json").write_text(json.dumps(N, indent=1, ensure_ascii=False))
print("wrote results/headline_numbers.json")
print("width", width, "| top-10 features firing on both genders:", len(shared), shared)
