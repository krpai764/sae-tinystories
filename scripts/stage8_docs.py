"""Stage 8 (rewritten after the review): write README.md and REPORT.md from results/headline_numbers.json.

Every number in the two documents is a format field filled from that file (which scripts/stage8_numbers.py
builds from results/). To change a number, change the experiment; to change wording, edit this script.
Run order: stage8_numbers.py -> stage8_browser.py -> stage8_docs.py -> stage8_check_numbers.py.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ROOT

N = json.loads((ROOT / "results" / "headline_numbers.json").read_text())
S, F, I, ST, T = N["setup"], N["faithfulness"], N["interpretation"], N["steering"], N["trace"]
T2, V5, SD = N["trace_v2"], N["stage5_v2"], N["steering_designs"]
VB, BT = V5["verdicts"], V5["blind_test_fresh_text"]
f1 = lambda x: f"{x:.1f}"
f2 = lambda x: f"{x:.2f}"
f3 = lambda x: f"{x:.3f}"
pc = lambda x: f"{x:.0%}"
pc1 = lambda x: f"{x:.1%}"
clean = lambda s: str(s).replace("|", "/")
p4 = lambda p: f"below {N['stage5_v2']['p_resolution']:g}" if p < N["stage5_v2"]["p_resolution"] else f"{p:.4f}"
lam = str(S["chosen_lambda"])
R1, R05, R4 = F["runs"][lam], F["runs"][min(F["runs"], key=float)], F["runs"][max(F["runs"], key=float)]
LMIN, LMAX = min(F["runs"], key=float), max(F["runs"], key=float)
B = I["blind"]
CH = B["real_all_200"]["chance"]
D1, D2, D3 = SD["design1"], SD["design2"], SD["design3"]
RU = V5["rule"]
MINW = SD["rule_min_wins"]
LEFT = D1["example_topic_label_left_out"]
labels = {}
for m in ST["main"] + ST["extension"]:
    labels[m["feature"]] = (m["label"], m["blind"], m["group"])
FEATS = [m["feature"] for m in ST["main"]] + [e["feature"] for e in ST["extension"]]
GROUP = {**{f: D2["features"][str(f)]["group"] for f in FEATS}}
GNAME = {"main_clear": "main: clear by my non-blind verdict, 5/5 blind", "main_unclear": "main: not clear", "topic": "topic label"}
steer2 = [f for f in FEATS if D2["features"][str(f)]["steers"]]
steer3 = [f for f in FEATS if D3["features"][str(f)]["steers"]]
s2k = {f: D2["features"][str(f)]["success_strengths"] for f in steer2}
s3k = {f: D3["features"][str(f)]["success_strengths"] for f in steer3}
d3_916 = D3["features"]["916"]
d2_916 = D2["features"]["916"]
ext_ok1 = [e["feature"] for e in ST["extension"] if e["max_theme_words_unbroken_feature"] > e["max_theme_words_unbroken_random"]]
tg, tb_, tt = T2["girl"], T2["boy"], T2["top10"]
flip = {t: {r["strength"]: r for r in T2["flip"][t]["by_strength"]} for t in ("girl", "boy")}
FB = 1.5
rand_flip_max = max(r["random"]["pair_flip"] for t in ("girl", "boy") for r in T2["flip"][t]["by_strength"])
rand_top1_max = max(r["random"]["top1_other_pronoun"] for t in ("girl", "boy") for r in T2["flip"][t]["by_strength"])
min_pair_after = min(T2[k]["measures"][g]["pair_preference_correct"] for k, g in (("top10", "overall"), ("girl", "girl"), ("boy", "boy")))
first_full_boy = min(s for s, r in flip["boy"].items() if r["add"]["pair_flip"] == 1.0)
n_girl_names = len(T2["peak_1511"])
n_1511_silent = sum(v < 0.05 for v in T2["peak_1511"].values())
silent_1511 = [n for n, v in T2["peak_1511"].items() if v < 0.05]
n_1532_fires = sum(v > 1 for v in T2["peak_1532"].values())

METHOD = "Feature labels and blind evaluations were generated with a language model and have not been human-verified."
REVIEWED = ("> **This README was rewritten after a sceptical review, and several earlier claims were withdrawn or weakened.** "
            "The [Review and corrections](REPORT.md#9-review-and-corrections) section of REPORT.md lists what the review found and what changed.")

# ============================================================ README ============================================================
README = f"""# Sparse autoencoders on TinyStories-8M

Sparse autoencoders on the activations of a small story-writing model ({S['model']}): find features, test whether their labels hold up, steer the model with them, trace one behaviour.
A careful small-scale application of published methods ([Prior work](#prior-work)), **not new research**: one model, one layer, one dictionary size, one seed.

> {METHOD}

{REVIEWED}

## Main findings, and what limits each one

**1. The autoencoder reconstructs the activations closely, but it is lossy and changes behaviour.**
The chosen autoencoder (λ={lam}, {S['dictionary_size']} features, residual stream after block {S['layer']}) explains {f3(R1['variance_explained'])} of the variance of held-out activations
with about {f1(R1['l0'])} active features per token. No feature is dead, but {pc(S['density_gt_1pct'])} of features fire on more than 1% of tokens, so many are not sparse in the usual sense.
Splicing the reconstruction back into the model recovers {f3(R1['loss_recovered_zero'])} of the loss gap against zero-ablation and {f3(R1['loss_recovered_mean'])} against mean-ablation, yet raises the loss by
{f2(R1['extra_loss_nats'])} nats: perplexity goes from {f2(F['perplexity_clean'])} to {f2(R1['perplexity_spliced'])}, a {pc(R1['perplexity_rise'])} rise. It also changes the behaviour traced below: with the reconstruction alone,
the model's "she/he" logit gap after a name rises from {f2(T['name_only']['clean_score'])} to {f2(T['recon_only_name_only'])}.
*Limits:* "loss recovered" is measured against very bad baselines. One training run per λ; confidence intervals are over held-out stories, not training seeds.

**2. Labels predict where features fire better than chance, but almost no feature passes a strict blind check.**
In a blind test on text neither autoencoder was trained on, a fresh reader given only the label picked the firing snippets with accuracy **{f3(BT['real_50']['mean_accuracy'])}** for the real autoencoder
against **{f3(BT['control_50']['mean_accuracy'])}** for a control trained on a copy of the model with shuffled weights (chance {CH}; difference p {p4(BT['permutation_p_one_sided'])}). The control is not significantly
above chance (p = {f3(BT['control_50']['p_vs_chance'])}).
A stricter test fails: fresh judges, blind to which autoencoder a feature came from, rated a feature clear only if {RU['top_min']} of its {RU['top_n']} strongest examples *and* {RU['random_min']} of {RU['random_n']} randomly chosen firings fit its label.
Only **{VB['real']['strict_clear']} of {VB['real']['n']} real features ({pc1(VB['real']['share'])})** and {VB['control']['strict_clear']} of {VB['control']['n']} control features passed, which does not separate them (p = {f2(VB['fisher_one_sided_p'])}).
Strongest examples fit the labels about equally for both ({f1(VB['real']['mean_top_fit_of_20'])} and {f1(VB['control']['mean_top_fit_of_20'])} of 20), but random firings almost never do ({f1(VB['real']['mean_random_fit_of_10'])} of 10 for real features):
a typical firing is weak (median strength {f2(V5['median_random_firing_act_real'])} against {f1(V5['median_top_act_real'])} for the strongest examples) and lands on loosely related tokens.
**An earlier claim that {I['clear_real']} of {I['n_features_labelled']} features were clear is withdrawn:** I made those verdicts myself, knowing which features were controls, and the blind judges confirmed {VB['real']['old_clear_confirmed_blind']} of them.
*Limits:* no label or verdict has been checked by a human, and the labeller, guessers and judges may share biases; the non-firing snippets in the blind test are random tokens, an easy contrast; the control autoencoder is denser (L0 {f1(I['control_sae']['l0'])} against {f1(R1['l0'])}) and saw less data.

**3. Steering toward a label at fluent strengths is not supported.**
I steered {D2['n_features']} features by adding a multiple of their decoder direction during generation, against random directions of the same length, with three designs.
Under a rule fixed in advance (fluent text, and more label words than the random directions on at least {MINW} of {D2['n_prompts']} prompts), **{D2['n_steer_total']} of {D2['n_features']}** features passed in design 2
(strength in units of each feature's median firing: {', '.join(str(f) for f in steer2)}) and **{D3['n_steer_total']} of {D3['n_features']}** in design 3 (strength as a fraction of the mean activation length: {', '.join(str(f) for f in steer3)}).
Feature {steer3[0] if steer3 else ''} ("bees, hives and honey") steered at {d3_916['success_strengths'][0] if d3_916['success_strengths'] else ''} of the mean activation length; design 2 never pushed it that far (at most {f2(d2_916['length_frac_range'][1])}).
The first design's examples (bee, rain and cold stories, "girl girl girl" repeats) came from {D1['n_prompts']} prompts judged by reading, with success rules written afterwards; they are **exploratory** and are not evidence for the claim.
*Limits:* the label-word lists are narrow (the "rain" feature at 0.35 of the mean length produced puddle stories that the list did not count); one fluency cut-off; 14 hand-picked features.
These are the last steering designs; no further ones were run.

**4. Switching off features shrinks the model's pronoun preference but never changes its choice.**
The model prefers the right pronoun after a name on every test prompt. In a rerun that held out both names and sentence frames and compared against random features matched on activation size:
- Switching off the top {len(tt['features'])} features together lowers the logit gap by {f2(tt['measures']['overall']['drop'])} (from {f2(T2['baseline']['heldout_name_only']['score'])}), against {f2(tt['matched_random']['overall']['drop_mean'])} for matched random sets (beats all {T2['n_random_sets']}).
  **But it also raises the model's loss on ordinary held-out stories by {f3(tt['story_loss_change'])} nats, against {f3(tt['matched_random']['story_loss_change_mean_first_sets'])} for matched random sets**, and {tt['n_heldout_effect_near_zero']} of the 10 have almost no effect on their own in the new frames.
  Part of this drop is general damage, not pronoun-specific.
- *Exploratory* (the idea came from seeing the first result, though the rerun fixed its rules in advance): {len(tg['features'])} girl-selective features lower the gap on held-out girl-name prompts by {f2(tg['measures']['girl']['drop'])} (from {f2(T2['baseline']['heldout_name_only_girl']['score'])})
  while the boy-name gap rises by {f2(-tg['measures']['boy']['drop'])}; {len(tb_['features'])} boy-selective features lower the boy gap by {f2(tb_['measures']['boy']['drop'])} (from {f2(T2['baseline']['heldout_name_only_boy']['score'])}) while the girl-name gap rises by {f2(-tb_['measures']['girl']['drop'])}.
  Their effect on ordinary story loss is small ({f3(tg['story_loss_change'])} and {f3(tb_['story_loss_change'])} nats, against {f3(tg['matched_random']['story_loss_change_mean_first_sets'])} and {f3(tb_['matched_random']['story_loss_change_mean_first_sets'])} for matched random sets).
  One feature (1511) alone accounts for {f2(T2['girl_effect_1511'])} of the girls' {f2(tg['measures']['girl']['drop'])}, and it does not fire on {', '.join(silent_1511)}.
- In none of these ablations did the model's preferred pronoun change (still correct on {'every prompt' if min_pair_after == 1 else 'at least ' + pc(min_pair_after) + ' of prompts'} afterwards).
- Adding the boy-selective features to girl-name prompts at {FB}× their usual level flips the preferred pronoun on {pc(flip['girl'][FB]['add']['pair_flip'])} of prompts (the wrong pronoun becomes the single most likely next word on {pc(flip['girl'][FB]['add']['top1_other_pronoun'])}).
  The reverse direction fails the fixed rule: {pc(flip['boy'][FB]['add']['pair_flip'])} at {FB}×, and {pc(flip['boy'][first_full_boy]['add']['pair_flip'])} only at {first_full_boy}×. Random directions of the same length flipped at most {pc1(rand_flip_max)}.
*Limits:* {N['trace']['n_names']} names in total (5 held out per gender), layer {S['layer']} only, and the autoencoder itself shifts this behaviour (finding 1).

## Feature browser

Open [`browser/index.html`](browser/index.html) in any browser (no server, no network). Pick a feature to see its label, the blind judges' counts, its blind-test score,
its strongest and random firings, and steering and tracing results. A toggle switches to the shuffled-weights control's features.
It holds the {I['n_features_labelled']} labelled features, the {I['n_control_labelled']} labelled control features, and the Stage 7 features that were not among the {I['n_features_labelled']}.

## Results at a glance

| λ | active features per token (L0) | variance explained | loss recovered (zero / mean baseline) | extra loss (nats) | perplexity rise | dead in last epoch |
|---|---|---|---|---|---|---|
""" + "\n".join(
    f"| {k}{' (chosen)' if k == lam else ''} | {f1(v['l0'])} | {f3(v['variance_explained'])} | {f3(v['loss_recovered_zero'])} / {f3(v['loss_recovered_mean'])} | {f2(v['extra_loss_nats'])} | {pc(v['perplexity_rise'])} | {v['dead_last_train_epoch']:.1%} |"
    for k, v in F["runs"].items()) + f"""

| Check on the labels | Real | Control |
|---|---|---|
| Blind label test, fresh text ({BT['real_50']['n']} features each) | {f3(BT['real_50']['mean_accuracy'])} | {f3(BT['control_50']['mean_accuracy'])} |
| Blind strict-clear verdicts | {VB['real']['strict_clear']}/{VB['real']['n']} | {VB['control']['strict_clear']}/{VB['control']['n']} |
| Earlier non-blind verdicts (withdrawn) | {I['clear_real']}/{I['n_features_labelled']} | {I['clear_control']}/{I['n_control_labelled']} |

| Steering design | Strength unit | Prompts | Features that steer under the fixed rule |
|---|---|---|---|
| 1 (exploratory) | multiples of the mean of the top-20 activations | {D1['n_prompts']} | no fixed rule; judged by reading |
| 2 | multiples of the median firing | {D2['n_prompts']} | {D2['n_steer_total']} of {D2['n_features']} |
| 3 | fraction of the mean activation length | {D3['n_prompts']} | {D3['n_steer_total']} of {D3['n_features']} |

Held-out set: {S['heldout_stories']} stories, {F['n_predicted_tokens']:,} predicted tokens. Training data: {S['train_tokens_in_sae']:,} tokens from {S['train_stories']:,} stories, {S['epochs']} epochs.
Figures are in [`figures/`](figures/). Full write-up with method, failures, limits and the review: [`REPORT.md`](REPORT.md).

## How to run

```
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
pytest                                              # tests for the autoencoder, hooks, evaluation, ablation code and docs
```

Some tests load the model from the Hugging Face cache and some read the collected activations, so run `pytest` after Stages 1 and 2.
Everything is configured in `config.yaml` (seed {S['seed']}). The review reruns' designs and success rules are the `steering_v2`, `steering_v3`, `trace_v2` and `stage5_v2` blocks, each committed before its run.
The collected activations take {S['data_dir_GB']:.2f} GB (`data/`, git-ignored, regenerable); checkpoints are git-ignored too. Long steps checkpoint and resume; start them with `caffeinate -i` on a laptop.

| Stage | Command(s) | Writes |
|---|---|---|
| 0–1 setup, model | `python scripts/device_test.py`, `python scripts/stage1_load_model.py` | `results/device_test.json`, `results/stage1_*.json` |
| 2 activations | `caffeinate -i python scripts/stage2_collect_activations.py`, `python scripts/stage2_checks.py` | `data/`, `results/stage2_*.json` |
| 3 train | `python scripts/stage3_pilot.py`, `caffeinate -i python scripts/stage3_train.py` | `checkpoints/sae/`, `results/stage3_*.json` |
| 4 faithfulness | `python scripts/stage4_faithfulness.py`, `python scripts/stage4_table.py` | `results/stage4_*` |
| 5 features | `python scripts/stage5_examples.py`, `python scripts/stage5_write_labels.py`, `python scripts/stage5_random_control.py`, `python scripts/stage5_examples.py --random`, `python scripts/stage5_write_labels_random.py`, `python scripts/stage5_blind_build.py`, *(blind answering)*, `python scripts/stage5_blind_score.py`, `python scripts/stage5_report.py` | `results/stage5*` |
| 5 review rerun | `python scripts/stage5b_build.py`, *(blind judging and answering)*, `python scripts/stage5b_score.py` | `results/stage5b*` |
| 6 steering, design 1 | `python scripts/stage6_steer.py`, `python scripts/stage6_steer.py --ext`, `python scripts/stage6_report.py`, `python scripts/stage6_ext_report.py` | `results/stage6*` |
| 6 steering, designs 2 and 3 | `python scripts/stage6b_steer_v2.py`, `python scripts/stage6b_report.py`, `python scripts/stage6b_steer_v2.py --v3`, `python scripts/stage6b_report.py --v3` | `results/stage6b*`, `results/stage6c*` |
| 7 tracing | `python scripts/stage7_trace.py`, `python scripts/stage7_analyse.py`, `python scripts/stage7_selective.py`, `python scripts/stage7_report.py` | `results/stage7*` |
| 7 review rerun | `python scripts/stage7b_trace_v2.py`, `python scripts/stage7b_report.py` | `results/stage7b*` |
| 8 browser, docs | `python scripts/stage8_numbers.py`, `python scripts/stage8_browser.py`, `python scripts/stage8_docs.py`, `python scripts/stage8_check_numbers.py` | `results/headline_numbers.json`, `browser/index.html`, `README.md`, `REPORT.md` |

**Not fully scripted.** The label text is stored in `stage5_write_labels.py`, so re-running it does not re-label. The blind answers and blind verdicts came from fresh judges
reading only the puzzle or item files; their raw answers are saved under `results/stage5_blind/` and `results/stage5b/responses/`, and the scoring scripts recompute every number from them. Re-doing these steps needs new answers and would give slightly different numbers.

**Where numbers come from.** `scripts/stage8_numbers.py` gathers every number cited here into `results/headline_numbers.json`; `scripts/stage8_docs.py` fills this README and `REPORT.md` from it;
`scripts/stage8_check_numbers.py` flags any number it cannot trace to that file. The checker cannot check wording; the review in REPORT section 9 is where wording was checked.

## Repository layout

```
config.yaml        every setting, the seed, and the pre-registered rules of the review reruns
src/               model hooks, data, activation collection, autoencoder, training, evaluation, tracing helpers
scripts/           one or more scripts per stage (table above)
tests/             tests for the autoencoder, hooks, collection, evaluation, ablation code and docs
results/           every result file; results/stage*_report.md are per-stage write-ups
figures/           plots
browser/           the static feature browser
docs/              method comparison against the papers
PROGRESS.md        stage-by-stage log and decisions
LEARNING_NOTES.md  plain-language explanations and interview questions per stage
```

## Prior work

- Ronen Eldan and Yuanzhi Li. *TinyStories: How Small Can Language Models Be and Still Speak Coherent English?* arXiv:2305.07759, 2023. (The model and data.)
- Trenton Bricken et al. *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning.* Transformer Circuits Thread, 2023. (Autoencoder design, resampling, shuffled-weights control.)
- Hoagy Cunningham, Aidan Ewart, Logan Riggs, Robert Huben and Lee Sharkey. *Sparse Autoencoders Find Highly Interpretable Features in Language Models.* arXiv:2309.08600, 2023.

`docs/method_comparison.md` lists where this project follows each paper and where it differs.
"""

# ============================================================ REPORT ============================================================
def table(header, rows):
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


faith_rows = [[k + (" (chosen)" if k == lam else ""), f1(v["l0"]), f3(v["variance_explained"]),
               f"{f3(v['loss_recovered_zero'])} [{f3(v['loss_recovered_zero_ci95'][0])}, {f3(v['loss_recovered_zero_ci95'][1])}]",
               f"{f3(v['loss_recovered_mean'])} [{f3(v['loss_recovered_mean_ci95'][0])}, {f3(v['loss_recovered_mean_ci95'][1])}]",
               f2(v["extra_loss_nats"]), f2(v["perplexity_spliced"]), pc(v["perplexity_rise"]), f"{v['dead_last_train_epoch']:.1%}", f"{v['never_fire_heldout']:.1%}",
               "yes" if v["l0_levelled_off"] else "no", v["total_resampled"]] for k, v in F["runs"].items()]
blind_rows = [[name, B[k]["n"], f3(B[k]["mean_accuracy"]), B[k]["n_perfect_5of5"], B[k]["n_at_or_below_chance"]] for name, k in [
    ("Real, all labelled", "real_all_200"), ("Real, first 50", "real_first_50"), ("Shuffled-weights control (its own training text)", "control_50")]]


def d1_text(f):
    d = D1["features"][str(f)]
    if d["kind"] == "main":
        return f"{f2(d['length_frac_range'][0])}–{f2(d['length_frac_range'][1])}; both prompts broken from {f2(d['first_broken_length_frac'])}" if d["first_broken_length_frac"] else f"{f2(d['length_frac_range'][0])}–{f2(d['length_frac_range'][1])}"
    return (f"{f2(d['length_frac_range'][0])}–{f2(d['length_frac_range'][1])}; theme words {f1(d['theme_feature'])} vs random {f1(d['theme_random'])} "
            f"({'more' if d['more_theme_words_than_random'] else 'not more'}; rule written afterwards)")


def dx_text(D, f, unit):
    d = D["features"][str(f)]
    s = f"{f2(d['length_frac_range'][0])}–{f2(d['length_frac_range'][1])}; " + (f"fluent up to {f2(d['max_fluent_length_frac'])}; " if d["fluent_strengths"] else "never fluent; ")
    s += f"**steers** at {', '.join(str(k) for k in d['success_strengths'])}{unit}" if d["steers"] else "does not steer"
    if not d["steers"] and d["on_label_strengths"]:
        s += f" (on-label only where not fluent: {', '.join(str(k) for k in d['on_label_strengths'])}{unit})"
    return s


steer_rows = [[f, clean(labels[f][0]), f"{labels[f][1]}/5", GNAME[GROUP[f]],
               d1_text(f), dx_text(D2, f, "×"), dx_text(D3, f, "")] for f in FEATS]

t_rows = []
for name, s_, key in (("top 10 (R1)", tt, "overall"), ("girl-selective (R2, exploratory)", tg, "girl"), ("boy-selective (R2, exploratory)", tb_, "boy")):
    m, r = s_["measures"][key], s_["matched_random"]
    t_rows.append([name, s_["features"], key, f"{f2(m['drop'])}", f"{f2(r[key]['drop_mean'])} / {f2(r[key]['drop_max'])}", f"{r[key]['tested_beats']}/{T2['n_random_sets']}",
                   pc(m["pair_preference_correct"]), f"{pc(m['top1_correct'])} ({pc(r['top1_correct_mean'])})", f"{f3(s_['story_loss_change'])} ({f3(r['story_loss_change_mean_first_sets'])})",
                   f2(r["activation_ratio_mean"])])
flip_rows = []
for t in ("girl", "boy"):
    for s_, r in flip[t].items():
        c = lambda k: f"{(pc1 if k == 'random' else pc)(r[k]['pair_flip'])} / {pc(r[k]['top1_other_pronoun'])} / {r[k]['names_majority_flipped']}"
        flip_rows.append([t, T2["flip"][t]["added_features_of"], s_, c("add"), c("swap"), c("random"), f"{pc(r['noun_add']['pair_flip'])} / {pc(r['noun_add']['top1_other_pronoun'])}"])

old_joint = T["top10_joint"]["overall"]
REVIEW_ROWS = [
    ["1", "serious", "Steering headline ('moves the next word reliably') had no evidence at fluent strengths; effects appeared only where text was already broken",
     f"Two new designs with fixed rules, {D2['n_prompts']} prompts, {D2['n_random']} random directions, label-only word lists", f"{D2['n_steer_total']}/{D2['n_features']} and {D3['n_steer_total']}/{D3['n_features']} features steer; claim withdrawn (finding 3)"],
    ["2", "serious", "'The brief's strengths were too strong' was an artefact of using the top-20 mean as the unit", "Design 2 uses the median firing (the brief's 'usual firing strength'); design 3 uses the mean activation length",
     "Statement removed; the side-by-side table shows the vector lengths each design covered"],
    ["3", "serious", "The promoted-token measure is close to circular (the decoder direction promotes those tokens by construction)", "Word lists written from the label text only, fixed before the runs", "Design 1 counts kept only as exploratory"],
    ["4", "serious", "Tracing control not matched on activation size, so 'beats 100/100' was nearly guaranteed", "Random sets matched on total activation (ratio reported); overall loss on held-out stories measured",
     f"Top-10 still beats matched sets, but raises story loss by {f3(tt['story_loss_change'])} nats vs {f3(tt['matched_random']['story_loss_change_mean_first_sets'])}: partly general damage"],
    ["5", "serious", "Held-out names shared the same sentence frames", f"{T2['n_frames_heldout']} new frames used only for testing", f"{tt['n_heldout_effect_near_zero']} of the top 10 have almost no effect in the new frames"],
    ["6", "serious", "'Found the gender signal' overreached (post hoc, 5 names per gender, boy set barely beat the best random set)", "Rules fixed in advance for the rerun; analysis labelled exploratory",
     f"Both selective sets pass; flip passes one way only ({pc(flip['girl'][FB]['add']['pair_flip'])} vs {pc(flip['boy'][FB]['add']['pair_flip'])} at {FB}×)"],
    ["7", "serious", "Finding 4 heading said ablation changes the pronoun choice; it only changed the logit gap", "Heading and text rewritten", "Choice unchanged in every ablation of the rerun"],
    ["8", "serious", f"The strict-clear comparison ({I['clear_real']}/{I['n_features_labelled']} vs {I['clear_control']}/{I['n_control_labelled']}) was judged non-blind by the labeller", f"Blind verdicts by {V5['n_judges_per_item']} fresh judges per feature, real and control mixed",
     f"{VB['real']['strict_clear']}/{VB['real']['n']} vs {VB['control']['strict_clear']}/{VB['control']['n']} (p = {f2(VB['fisher_one_sided_p'])}); old claim withdrawn"],
    ["9", "serious", "False claim that the extension used every topic label; main six were hand-picked from 20 without saying so", f"Selection described as hand-picked (e.g. {LEFT['feature']}, {LEFT['label']}, was left out)", "Corrected in README and REPORT"],
    ["10", "moderate", "Control differs in more than weights; its blind-test text was its own training text", "Control blind test rerun on held-out text it never saw", f"{f3(BT['control_50']['mean_accuracy'])} (not significantly above chance); real {f3(BT['real_50']['mean_accuracy'])}; density and data differences stated as limits"],
    ["11", "moderate", "Blind test is easy and partly measures label style", "Stated as a limit", "Unchanged"],
    ["12", "moderate", f"p-values assume independent puzzles, but answers come in batches of {I['puzzles_per_guesser']}", "Per-guesser accuracies reported", "All guessers show the same gap (`results/stage5b_report.md`)"],
    ["13", "moderate", "'3 of 6 topic features steered' used a rule written afterwards", "Marked exploratory; superseded by designs 2 and 3", f"Designs 2 and 3: {sum(D2['features'][str(f)]['steers'] for f in FEATS if GROUP[f] == 'topic')} and {sum(D3['features'][str(f)]['steers'] for f in FEATS if GROUP[f] == 'topic')} of 6 topic features steer"],
    ["14", "moderate", "'Blind accuracy does not predict steering' drawn from 6 features", "Removed", "-"],
    ["15", "moderate", "'Reproduces the activations well' was generous; dense features not mentioned", "Perplexity rise and density stated", f"{pc(R1['perplexity_rise'])} perplexity rise; {pc(S['density_gt_1pct'])} of features fire on more than 1% of tokens"],
    ["16", "moderate", "Firing-strength terciles pooled across features", "Stated as a limit", "Unchanged"],
    ["17", "moderate", "The reconstruction alone raises the pronoun gap; not reported", "Reported in finding 1", f"{f2(T['name_only']['clean_score'])} to {f2(T['recon_only_name_only'])}"],
    ["18", "moderate", "Flip rates used pair preference only", "Top-1 rates reported beside them", f"At {FB}×, girl prompts: {pc(flip['girl'][FB]['add']['pair_flip'])} pair, {pc(flip['girl'][FB]['add']['top1_other_pronoun'])} top-1"],
    ["19", "moderate", "'Broken' used an arbitrary perplexity of 20", "Cut-off defined from unsteered text (2 × its 95th percentile)", f"{f2(D2['fluent_threshold_ppl'])} (design 2), {f2(D3['fluent_threshold_ppl'])} (design 3)"],
    ["20", "minor", "PROGRESS.md had stale headers and one over-broad sentence", "Rewritten", "-"],
    ["21", "minor", "Ambiguous phrase 'the unsteered model's own perplexity on this text'", "Removed", "-"],
    ["22", "minor", "The number checker cannot check wording", "Stated in README", "-"],
    ["23", "minor", "Only exact duplicate stories were excluded from the held-out set", "Stated as a limit", "Unchanged"],
    ["24", "minor", "Feature 1511 described as carrying the girl effect may be narrower than 'girls' names'", "Its per-name activations reported", f"Silent on {', '.join(silent_1511)}"],
]

REPORT = f"""# Sparse autoencoders on TinyStories-8M: method, results, failures and limits

> **This report was rewritten after a sceptical review.** Several claims in the first version were withdrawn or weakened, three experiments were rerun under rules fixed in advance,
> and a third steering design was added. Section 9 lists what the review found and what changed. Every number below comes from a file in `results/` via `results/headline_numbers.json`.

This is a small application of published methods ([Prior work](#7-prior-work)) to one small model, not new research.

## 1. Summary

| Question | Answer | Main limit |
|---|---|---|
| Does the autoencoder capture the activations? | variance explained {f3(R1['variance_explained'])}, L0 {f1(R1['l0'])}, loss recovered {f3(R1['loss_recovered_zero'])} / {f3(R1['loss_recovered_mean'])}, but perplexity +{pc(R1['perplexity_rise'])} | weak baselines; one seed |
| Do labels say where features fire? | better than chance: blind accuracy {f3(BT['real_50']['mean_accuracy'])} vs control {f3(BT['control_50']['mean_accuracy'])} | no human check; easy distractors |
| Are features cleanly interpretable? | almost none by a strict blind check: {VB['real']['strict_clear']}/{VB['real']['n']}, not different from control | no human check; one strict rule |
| Do features steer the model toward their label? | not supported: {D2['n_steer_total']}/{D2['n_features']} (design 2), {D3['n_steer_total']}/{D3['n_features']} (design 3) | narrow word lists; 14 hand-picked features |
| Can the pronoun choice be traced? | ablation shrinks the gap but never changes the choice; one flip direction works | exploratory analysis, few names |

## 2. Method

### 2.1 Model and activations
- `{S['model']}` (GPT-Neo, {S['n_blocks']} blocks, width {S['width']}); residual stream after block {S['layer']}, captured with a forward hook (`src/model.py`).
- {S['train_stories']:,} training stories and {S['heldout_stories']:,} held-out stories (validation split), with no exact duplicate shared between them. One row per token, fp32 memmaps ({S['data_dir_GB']:.2f} GB).
- Position 0 (the end-of-text prefix) is a constant vector (norm {f2(S['pos0_norm'])}) and is excluded from training. Other positions have mean length {f2(S['mean_activation_norm_model_units'])}; all activations are scaled by {f3(S['rescale_factor'])} so their mean length is √{S['width']}.

### 2.2 Autoencoder and training (`src/sae.py`, `src/train.py`)
- f = ReLU(W_e (x − b_d) + b_e), x̂ = W_d f + b_d; untied weights; {S['dictionary_size']} features ({S['expansion']}× the width); loss = summed squared error + λ × sum of feature strengths, averaged over the batch.
- Unit-length decoder columns with the parallel gradient component removed (Bricken et al.); b_d starts at the geometric median ({f2(S['b_d_geometric_median_minus_mean_norm'])} from the mean vector, whose norm is {f1(S['b_d_mean_norm'])}); W_e starts at {S['enc_init_scale']} × W_dᵀ.
- Adam, learning rate {S['lr']}, batch {S['batch_size']}, {S['epochs']} epochs over {S['train_tokens_in_sae']:,} tokens, λ in {S['lambdas']}; dead features resampled after epochs {S['resample_after_epochs']}.

### 2.3 Faithfulness (`src/eval.py`)
Splice the reconstruction into the model at layer {S['layer']} and measure next-token loss on the held-out stories ({F['n_predicted_tokens']:,} predicted tokens), against zero-ablation and mean-ablation baselines. 95% bootstrap intervals over stories.

### 2.4 Interpretation (`scripts/stage5_*.py`, `scripts/stage5b_*.py`)
- {I['n_features_labelled']} features chosen at random (seed {S['seed']}); for each, its top {S['interpret_top_k']} snippets, {S['interpret_n_random']} random firings and promoted output tokens. One label was written per feature. {METHOD}
- **Original blind test:** a fresh judge sees only the label and {I['n_snippets_per_puzzle']} snippets ({I['n_firing_snippets_per_puzzle']} firing, sampled uniformly among all firings; the rest non-firing) and picks the firing ones. Real snippets came from held-out text, but the control's came from its own training text.
- **Review rerun, blind test on fresh text:** the first 50 real and the 50 control features, on held-out stories that neither autoencoder trained on (the shuffled model was run on them), mixed and anonymised; {V5['n_puzzle_files']} fresh guessers.
- **Review rerun, blind strict-clear verdicts:** all {VB['n_items']} features mixed and anonymised; each judged by {V5['n_judges_per_item']} fresh judges who were not told there were two sources. Each counted how many of the {RU['top_n']} strongest examples and of {RU['random_n']} new uniformly sampled firings fit the label.
  Clear = at least {RU['top_min']} of {RU['top_n']} and {RU['random_min']} of {RU['random_n']}, by both judges. Rules in `config.yaml` `stage5_v2`, committed before the run.
- **Control:** an autoencoder with the same settings trained on a shuffled-weights copy of the model (Bricken et al.): {I['control_sae']['train_tokens']:,} half-precision tokens, {I['control_sae']['epochs']} epochs; variance explained {f3(I['control_sae']['variance_explained'])}, L0 {f1(I['control_sae']['l0'])}.

### 2.5 Steering (`scripts/stage6_steer.py`, `scripts/stage6b_*.py`)
A vector along a feature's unit decoder direction is added at layer {S['layer']} at every position after the first while the model writes {S['steer_max_new_tokens']} tokens; the control is a random direction of the same length. Three designs, run in this order:
1. **Design 1 (exploratory).** Strength in multiples of the mean of the feature's top-20 activations; {D1['n_prompts']} prompts, one random direction; judged by reading, by promoted-token counts (near-circular) and, for topic features, by theme words with a success rule written afterwards.
2. **Design 2.** Strength in multiples of the feature's median firing ({', '.join(str(k) for k in D2['multipliers'])}×); {D2['n_prompts']} prompts, {D2['n_random']} random directions; label words written from the label text only.
3. **Design 3 (third and last).** Strength as a fraction of the mean activation length ({', '.join(str(k) for k in D3['multipliers'])}); everything else as design 2.

Designs 2 and 3 share a rule fixed before each run (`config.yaml` `steering_v2`, `steering_v3`): a strength is *fluent* if the median perplexity of the steered text under the unsteered model is at most twice the 95th percentile of unsteered text
({f2(D2['fluent_threshold_ppl'])} and {f2(D3['fluent_threshold_ppl'])}); *on-label* if the steered text has more label words than the mean of the random directions on at least {MINW} of {D2['n_prompts']} prompts and more than unsteered text; a feature *steers* if one strength is both.
**Feature selection was by hand:** the six main features were picked from the {D1['n_main_eligible']} that my (non-blind) verdicts called clear and that scored 5/5 blind; the six topic features were picked from the topic-like labels, not all of them (for example {LEFT['feature']}, "{LEFT['label']}", was left out); two not-clear features were added.

### 2.6 Tracing (`scripts/stage7_*.py`, `scripts/stage7b_*.py`)
- Behaviour: "she"/"he" after a named character. Score = logit(correct pronoun) − logit(wrong pronoun) at the last position.
- Ablation: zero one feature (or a set) at every position after the first, decode, add the reconstruction error back (`src/trace.py`, tested).
- **First run (superseded):** {N['trace']['n_names']} names × {N['trace']['n_frames']} frames; ranking and test shared the frames; random sets not matched on activation.
- **Review rerun:** rank on ranking names × the original frames; test on held-out names × {T2['n_frames_heldout']} new frames. Random sets matched on total activation ({T2['n_random_sets']} per test).
  Also reported: change in loss on the test prompts and on {T2['loss_stories']} held-out stories, and the rate at which the wrong pronoun becomes the model's top-1 next token. Rules in `config.yaml` `trace_v2`, committed before the run.
- The gender-selective analysis (features at least {V5['selective_ratio']}× more active on one gender's names) is **exploratory**: the idea came from seeing the first run, although the rerun fixed its rules in advance and tested it on new names and frames.

## 3. Results

### 3.1 Training and faithfulness
{table(["λ", "L0", "variance explained", "loss recovered, zero [95% CI]", "loss recovered, mean [95% CI]", "extra loss (nats)", "perplexity after splicing", "perplexity rise", "dead, last epoch", "never fire, held-out", "L0 levelled off", "resampled"], faith_rows)}

Unmodified loss {f3(F['L_clean'])} nats (perplexity {f2(F['perplexity_clean'])}); zero-ablation {f3(F['L_zero'])}; mean-ablation {f3(F['L_mean'])}.
At λ={lam}, {pc(S['density_gt_1pct'])} of features fire on more than 1% of held-out tokens. The reconstruction alone raises the pronoun logit gap of the tracing section from {f2(T['name_only']['clean_score'])} to {f2(T['recon_only_name_only'])}, so the autoencoder changes the behaviour studied.

![training](figures/stage3_training.png)
![faithfulness](figures/stage4_faithfulness.png)

### 3.2 Interpretability

**Blind label test.**

{table(["Set", "n", "mean accuracy", "5/5", "3/5 or fewer"], blind_rows + [["Real, first 50, fresh text (rerun)", BT['real_50']['n'], f3(BT['real_50']['mean_accuracy']), BT['real_50']['n_5of5'], BT['real_50']['n_at_or_below_3of5']], ["Control, fresh text (rerun)", BT['control_50']['n'], f3(BT['control_50']['mean_accuracy']), BT['control_50']['n_5of5'], BT['control_50']['n_at_or_below_3of5']]])}

Fresh text: real minus control = {f3(BT['difference'])}, one-sided permutation p {p4(BT['permutation_p_one_sided'])}; control vs chance ({CH}) p = {f3(BT['control_50']['p_vs_chance'])}. Each of the {len(BT['per_guesser'])} guessers shows the same direction.
On its own training text the control scored {f3(B['control_50']['mean_accuracy'])}, significantly above chance; on fresh text it does not. By firing-strength tercile (pooled across features, so this mixes strength with feature identity),
the original test detected weak firings at {f2(I['tercile_real']['weak'])} and strong at {f2(I['tercile_real']['strong'])}.

**Blind strict-clear verdicts (rerun).**

{table(["Set", "n", "strict-clear by both judges", "clear by judge 1 / 2", "mean top fit (of 20)", "mean random fit (of 10)", "old non-blind clear", "of those, confirmed"],
       [[t, VB[t]['n'], f"{VB[t]['strict_clear']} ({pc1(VB[t]['share'])})", f"{VB[t]['j1_clear']} / {VB[t]['j2_clear']}", f1(VB[t]['mean_top_fit_of_20']), f1(VB[t]['mean_random_fit_of_10']), VB[t]['old_nonblind_clear'], VB[t]['old_clear_confirmed_blind']] for t in ("real", "control")])}

One-sided Fisher exact p = {f2(VB['fisher_one_sided_p'])}: not supported. The judges agreed on {pc(VB['judge_agreement_on_clear'])} of calls. Random firings are mostly weak (median strength {f2(V5['median_random_firing_act_real'])} vs {f1(V5['median_top_act_real'])} for the strongest examples),
and on most features they land on tokens that do not fit the label. A guesser can still use loose associations (a "little" feature also firing weakly on "tiny"), which explains why the label test separates real from control while the strict verdicts do not.
Per-feature results: `results/stage5b_per_feature.csv`; write-up: `results/stage5b_report.md`.

### 3.3 Steering: the three designs side by side
Vector lengths are given as a fraction of the mean activation length ({f2(S['mean_activation_norm_model_units'])} in model units), so the designs can be compared. Strengths in the design 2 column are in its own unit (× median firing), in the design 3 column as fractions.

{table(["feature", "label", "blind", "how chosen", "design 1 (exploratory): lengths covered; outcome", "design 2: lengths; fluent up to; outcome", "design 3: lengths; fluent up to; outcome"], steer_rows)}

- Design 2 rule verdicts: {'; '.join(f"{GNAME[g]}: {v['n_steer']}/{v['n_features']} ({v['verdict']})" for g, v in D2['groups'].items())}.
- Design 3 rule verdicts: {'; '.join(f"{GNAME[g]}: {v['n_steer']}/{v['n_features']} ({v['verdict']})" for g, v in D3['groups'].items())}. Using design 2's numeric cut-off instead changes {D3['n_steer_total'] - D3['n_steer_under_design2_cutoff']} verdicts.
- The designs disagree mostly because they cover different lengths: design 2 gave topic features very short vectors (median firings are small), design 3 gave every feature the same lengths.
  Where design 1 found topic stories (bees, rain, cold), its fluent vectors were about as long as design 3's. Under design 3's fixed rule only the bees feature passed; the rain feature wrote puddle stories at {D3['multipliers'][2]} that its word list did not count.
- Each feature had {len(D2['multipliers'])} or {len(D3['multipliers'])} chances to pass, so one pass among {D2['n_features']} features is consistent with chance (`config.yaml` gives the per-feature false-pass bound).

Full tables and sample text: `results/stage6b_report.md` (design 2), `results/stage6c_report.md` (design 3), `results/stage6_report.md` and `results/stage6_extension_report.md` (design 1). Figures: `figures/stage6b_steering_v2.png`, `figures/stage6b_steering_v3.png`.

### 3.4 Tracing the pronoun

**Rerun (held-out names × held-out frames, name-only prompts).** Unmodified model: correct pronoun preferred on {pc(T2['baseline']['heldout_name_only']['pair_preference_correct'])} of {T2['baseline']['heldout_name_only']['n']} prompts, top-1 on {pc(T2['baseline']['heldout_name_only']['top1_correct'])}, mean gap {f2(T2['baseline']['heldout_name_only']['score'])}
(girls {f2(T2['baseline']['heldout_name_only_girl']['score'])}, boys {f2(T2['baseline']['heldout_name_only_boy']['score'])}). {T2['n_firing']} features fire on the prompts. Story loss without ablation: {f3(T2['story_loss_clean'])} nats.

{table(["set", "features", "scored on", "drop", "matched random: mean / max", "beats", "pair preference correct after", "top-1 correct after (random)", "story loss change (random)", "random/tested activation"], t_rows)}

- Specificity (own-gender drop minus other-gender drop): girl set {f2(tg['specificity']['tested'])} vs random {f2(tg['specificity']['random_mean'])}; boy set {f2(tb_['specificity']['tested'])} vs random {f2(tb_['specificity']['random_mean'])} (each beats {tg['specificity']['tested_beats']} and {tb_['specificity']['tested_beats']} of {T2['n_random_sets']}).
- Feature 1511 alone accounts for {f2(T2['girl_effect_1511'])} of the girl set's drop; its activation on the held-out girls' names: {', '.join(f'{n} {f1(v)}' for n, v in T2['peak_1511'].items())}. Feature 1532 fires on {n_1532_fires} of the 5 held-out boys' names.
- Of the top 10, {tt['n_heldout_effect_near_zero']} have an effect below 0.1 on their own in the new frames: their effect does not carry over from the ranking frames to the new ones.

**Flip test (rerun).** "pair" = the wrong pronoun's logit exceeds the correct one's; "top-1" = the wrong pronoun becomes the model's most likely next token; "names" = held-out names (of 5) with most of their prompts pair-flipped.

{table(["prompts", "features added from", "strength", "add: pair / top-1 / names", "swap: pair / top-1 / names", "random: pair / top-1 / names", "add, noun-plus-name prompts: pair / top-1"], flip_rows)}

The fixed rule (most prompts flipped for at least 4 of 5 names at a strength of at most {FB}×, random 0 names) passes for girl prompts (boy features added) and fails for boy prompts (girl features added).
Random directions flipped at most {pc1(rand_flip_max)} of prompts{' and never made the wrong pronoun the top-1 token' if rand_top1_max == 0 else ' and made the wrong pronoun the top-1 token on at most ' + pc(rand_top1_max)}.

**First run (superseded).** The top 10 lowered the gap on held-out names by {f2(old_joint['top_drop'])} (from {f2(old_joint['clean_score'])}) against unmatched random sets averaging {f2(old_joint['random_drop_mean'])}; {T['top10_fire_on_both_genders_count']} of the 10 fire equally on girls' and boys' names.
Its tables remain in `results/stage7_report.md`. Rerun write-up: `results/stage7b_report.md`.

## 4. Failures, surprises and things that went wrong

- **The first write-up overclaimed** (see Review and corrections): the strict-clear comparison was not blind, the steering headline had no fluent-strength evidence, the tracing control was not matched, and one selection claim was false.
- **The strict-clear verdicts collapse when made blind:** {I['clear_real']} non-blind to {VB['real']['strict_clear']} blind for real features; the real and control autoencoders no longer differ on this measure.
- **The control looked above chance only on its own training text** ({f3(B['control_50']['mean_accuracy'])}); on fresh text {f3(BT['control_50']['mean_accuracy'])}.
- **Steering toward the label did not hold up** under fixed rules in two designs ({D2['n_steer_total']} and {D3['n_steer_total']} of {D2['n_features']}).
- **The top-10 tracing result is partly damage:** it raises story loss {f3(tt['story_loss_change'])} nats against {f3(tt['matched_random']['story_loss_change_mean_first_sets'])} for matched sets.
- **The autoencoder distorts the behaviour it is used to explain:** the reconstruction alone raises the pronoun gap ({f2(T['name_only']['clean_score'])} to {f2(T['recon_only_name_only'])}).
- **The sparsest autoencoder is unhealthy:** at λ={LMAX}, {R4['never_fire_heldout']:.1%} of features never fire on held-out text and {R4['total_resampled']} were resampled; it was not used.
- **Bugs caught during the project:** an out-of-memory crash during activation collection (fixed by padding to multiples of 64; saved activations matched a CPU recomputation to {S['verify_max_abs_diff']:.1e}), held-out stories duplicated in training (excluded), and an encoder initialisation several times too large (scaled by {S['enc_init_scale']}).
- **Dataset quirk:** TinyStories contains encoding artefacts, and at least one feature tracks them.

## 5. Limits

- One model, one layer, one dictionary size, one seed; no training-seed variation measured.
- The autoencoder is lossy (+{pc(R1['perplexity_rise'])} perplexity) and shifts the traced behaviour; anything carried by the reconstruction error is invisible to feature-level analysis.
- **No label or verdict has been checked by a human, and the labeller, guessers and judges may share biases.** The blind test's non-firing snippets are random tokens (easy), and the strict-verdict rule ({RU['top_min']}/{RU['top_n']} and {RU['random_min']}/{RU['random_n']}) is one choice among many.
- Only {I['n_features_labelled']} of {S['dictionary_size']} features were labelled; the control is denser (L0 {f1(I['control_sae']['l0'])} vs {f1(R1['l0'])}), used {I['control_sae']['train_tokens']:,} half-precision tokens against {S['train_tokens_in_sae']:,}, and is not a perfect match.
- p-values treat puzzles as independent, although each guesser answered {I['puzzles_per_guesser']}; per-guesser results are reported.
- Steering: 14 hand-picked features, narrow label-word lists, one fluency rule; three designs in total, the last fixed by the user as final.
- Tracing: {N['trace']['n_names']} names, 5 held out per gender; frames hand-written; layer {S['layer']} only; the gender-selective analysis is exploratory.
- Only exact duplicate stories were excluded from the held-out set; near-duplicates are possible.
- Promoted-token lists are approximate (the direction is multiplied by the unembedding although {S['n_blocks'] - S['layer'] - 1} blocks remain).

## 6. Deviations from the brief and from the papers

| Topic | Brief / papers | What I did | Why |
|---|---|---|---|
| Encoder init | W_e = W_dᵀ | {S['enc_init_scale']} × W_dᵀ | the brief's init gave a first reconstruction several times too large (user approved) |
| b_d init | data mean | geometric median (Bricken) | cheap; close to the mean |
| Decoder gradient | rescale columns only | also remove the parallel gradient component (Bricken) | published and cheap |
| Data size | Bricken: billions of vectors | {S['train_tokens_in_sae']:,} tokens, {S['epochs']} epochs, with resampling | disk cap |
| λ grid | 4 values about 3× apart | {S['lambdas']} | 3× spacing would have put half the runs outside the usable range |
| Loss recovered | zero baseline | zero and mean baselines | zero-ablation flatters |
| Labels | not specified | no human check | user's decision not to hand-label |
| Steering strength | 2, 5 and 10 × "usual firing strength" | design 1 used the top-20 mean as the unit (an error); design 2 the median firing at {', '.join(str(k) for k in D2['multipliers'])}×; design 3 fractions of the mean activation length | review |
| Tracing | one test | plus a rerun with held-out frames, matched controls and loss measures, and an exploratory gender-selective analysis | review |

## 7. Prior work

- Ronen Eldan and Yuanzhi Li. *TinyStories: How Small Can Language Models Be and Still Speak Coherent English?* arXiv:2305.07759, 2023.
- Trenton Bricken, Adly Templeton, Joshua Batson, Brian Chen, Adam Jermyn, Tom Conerly, Nicholas L. Turner, Cem Anil, Carson Denison, Amanda Askell, Robert Lasenby, Yifan Wu, Shauna Kravec, Nicholas Schiefer, Tim Maxwell, Nicholas Joseph, Zac Hatfield-Dodds, Alex Tamkin, Karina Nguyen, Brayden McLean, Josiah E. Burke, Tristan Hume, Shan Carter, Tom Henighan and Chris Olah.
  *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning.* Transformer Circuits Thread, 2023.
- Hoagy Cunningham, Aidan Ewart, Logan Riggs, Robert Huben and Lee Sharkey. *Sparse Autoencoders Find Highly Interpretable Features in Language Models.* arXiv:2309.08600, 2023.

## 8. Reproducibility

- Seed {S['seed']} in `config.yaml`. The review reruns' designs and success rules are in `config.yaml` and were committed before each run (git history shows the order).
- Commands are in the README. `data/` and `checkpoints/` are git-ignored and regenerable.
- Not fully scripted: the label text and the judges' answers and verdicts, which are stored raw; scoring scripts recompute every number from them.
- README and this report are generated from `results/headline_numbers.json` by `scripts/stage8_docs.py`; `scripts/stage8_check_numbers.py` flags untraceable numbers but cannot check wording.

## 9. Review and corrections

After the first version was finished, a sceptical review listed every claim the results did not support. This was followed by reruns with rules fixed in advance,
a third and final steering design, and a rewrite. The table lists each finding, ranked by seriousness, what changed, and what the evidence now says. Nothing here has had a human check.

{table(["#", "seriousness", "what the review found", "what changed", "outcome"], REVIEW_ROWS)}

**Claims that got weaker or were withdrawn:** "37/200 features are clear" (withdrawn; blind: {VB['real']['strict_clear']}/{VB['real']['n']}); "the control is above chance" (not on fresh text); "steering moves text toward the label" (not supported);
"the brief's strengths are too strong" (an artefact of my unit); "3 of 6 topic features steered" (exploratory); "switching off features changes the pronoun choice" (it changes only the gap); "the gender signal was found" (exploratory; one flip direction fails).
**Claims that held up:** the faithfulness numbers; real labels predict firings better than control labels on fresh text; the top-10 and gender-selective ablations beat activation-matched random sets; boy features added to girl-name prompts flip the pronoun while random directions do not.
"""

(ROOT / "README.md").write_text(README)
(ROOT / "REPORT.md").write_text(REPORT)
print("wrote README.md", len(README.split()), "words; REPORT.md", len(REPORT.split()), "words")
