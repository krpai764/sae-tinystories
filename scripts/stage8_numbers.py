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

(R / "headline_numbers.json").write_text(json.dumps(N, indent=1, ensure_ascii=False))
print("wrote results/headline_numbers.json")
print("width", width, "| top-10 features firing on both genders:", len(shared), shared)
