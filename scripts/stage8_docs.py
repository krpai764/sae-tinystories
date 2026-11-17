"""Stage 8: write README.md and REPORT.md from results/headline_numbers.json.

Every number in the two documents is a format field filled from that file (which scripts/stage8_numbers.py
builds from results/). To change a number, change the experiment; to change wording, edit this script.
Run order: stage8_numbers.py -> stage8_browser.py -> stage8_docs.py.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ROOT

N = json.loads((ROOT / "results" / "headline_numbers.json").read_text())
S, F, I, ST, T = N["setup"], N["faithfulness"], N["interpretation"], N["steering"], N["trace"]
f2 = lambda x: f"{x:.2f}"
f3 = lambda x: f"{x:.3f}"
f1 = lambda x: f"{x:.1f}"
pc = lambda x: f"{x:.0%}"
pc1 = lambda x: f"{x:.1%}"
clean = lambda s: str(s).replace("|", "/")
lam = str(S["chosen_lambda"])
R1, R05, R4 = F["runs"][lam], F["runs"]["0.5"], F["runs"]["4"]
B = I["blind"]

DISCLAIMER = ("> **All feature labels in this project are AI-written (by Claude) and have not been verified by a human.** "
              "They were scored with an automated blind test (see below and `results/stage5_report.md`), but nobody checked them by hand. "
              "The same model family wrote the labels and took the blind test.")

# analysis parameters named in the prose (strength keys are the ones used in results/headline_numbers.json)
KLOW, KHIGH, FA, FB = "0.5", "2", 1, 1.5
CH = B["real_all_200"]["chance"]
LMIN, LMAX = min(F["runs"], key=float), max(F["runs"], key=float)
NB, NSNIP, NFIRE = S["n_blocks"], I["n_snippets_per_puzzle"], I["n_firing_snippets_per_puzzle"]
UMIN, UMAX = f1(ST["unsteered_ppl_min"]), f1(ST["unsteered_ppl_max"])
NSUB = I["n_subagents"]

# ---- derived steering numbers ----
main = ST["main"]
clr = [m for m in main if m["group"] == "clear_5of5"]
weak = [m for m in main if m["group"] != "clear_5of5"]
fluent_half = sum(m["by_k"][KLOW]["feature_broken"] == "0/2" for m in clr)
brk2 = sum(m["by_k"][KHIGH]["feature_broken"] == "2/2" for m in clr)
rbrk2 = sum(m["by_k"][KHIGH]["random_broken"] == "2/2" for m in clr)
h2 = [m["by_k"][KHIGH]["feature_promoted_hits"] for m in clr]
rh2 = [m["by_k"][KHIGH]["random_promoted_hits"] for m in clr]
brk5 = sum(m["by_k"]["5"]["feature_broken"] == "2/2" for m in main)
brk10 = sum(m["by_k"]["10"]["feature_broken"] == "2/2" for m in main)
BRK510 = (f"all {len(main)} main-run features broke on both prompts at 5× and at 10×" if brk5 == brk10 == len(main)
          else f"{brk5} of the {len(main)} main-run features broke on both prompts at 5× and {brk10} of {len(main)} at 10×")
ext = ST["extension"]
for e in ext:
    e["works"] = e["max_theme_words_unbroken_feature"] > e["max_theme_words_unbroken_random"]
ext_ok = [e for e in ext if e["works"]]
ext_bad = [e for e in ext if not e["works"]]
blind_ok = ", ".join(f"{e['blind']}/5" for e in ext_ok)
blind_bad = ", ".join(f"{e['blind']}/5" for e in ext_bad)
fl = {(r["target"], r["strength"], r["kind"]): r for r in T["flip_selective"]}
sg, sb = T["selective"]["girl"], T["selective"]["boy"]
jo = T["top10_joint"]["overall"]
tn = T["name_only"]
min_acc_after = min(sg["own"]["pair_accuracy_after"], sb["own"]["pair_accuracy_after"])
not_levelled = [k for k, v in F["runs"].items() if not v["l0_levelled_off"]]
levelled = [k for k, v in F["runs"].items() if v["l0_levelled_off"]]

# ============================================================ README ============================================================
README = f"""# Sparse autoencoders on TinyStories-8M

Sparse autoencoders on the activations of a small story-writing model ({S['model']}): find features, test whether their labels are any good, steer the model with them, trace one behaviour.
A careful small-scale application of published methods ([Prior work](#prior-work)), **not new research**: one model, one layer, one dictionary size, one seed.

{DISCLAIMER}

## Main findings, and what limits each one

**1. The autoencoder reproduces the model's activations well, but not perfectly.**
The chosen autoencoder (λ={lam}, {S['dictionary_size']} features, residual stream after block {S['layer']}) explains {f3(R1['variance_explained'])} of the
variance of held-out activations using about {f1(R1['l0'])} active features per token, with {R1['never_fire_heldout']:.0%} dead features. Splicing its reconstruction
back into the model recovers {f3(R1['loss_recovered_zero'])} of the loss gap against zeroing the activations and {f3(R1['loss_recovered_mean'])} against replacing them
with their mean, but still raises the model's loss by {f2(R1['extra_loss_nats'])} nats (perplexity {f2(F['perplexity_clean'])} to {f2(R1['perplexity_spliced'])}).
*Limits:* "loss recovered" is measured against very bad baselines, so it flatters. Even the least sparse autoencoder (λ={LMIN}) adds
{f2(R05['extra_loss_nats'])} nats; the sparsest (λ={LMAX}) recovers {f3(R4['loss_recovered_zero'])} and has {R4['dead_last_train_epoch']:.1%} dead features in its last epoch.
One training run per λ; the confidence intervals in `results/stage4_faithfulness.json` are over held-out stories, not over training seeds.

**2. Most features are not cleanly interpretable, though they are better than chance.**
Of {I['n_features_labelled']} randomly chosen features, only **{I['clear_real']} ({pc1(I['clear_real_share'])}) pass a strict rule**: one concept explains the strongest examples *and*
randomly chosen firings. Judged on strongest examples alone, {I['clear_if_random_firings_ignored_real']} would look clear. In a blind test (a fresh reader, given only the label, must pick
{NFIRE} firing snippets out of {NSNIP} from text not used for labelling) the labels scored **{f3(B['real_all_200']['mean_accuracy'])}** against {CH} for guessing.
A control autoencoder trained on a copy of the model with shuffled weights scored {f3(B['control_50']['mean_accuracy'])}, and only {I['clear_control']} of its {I['n_control_labelled']} labelled features
pass the strict rule ({I['clear_if_random_firings_ignored_control']} look clear on strongest examples alone). Labels describe strong firings far better than weak ones:
blind accuracy {f2(I['tercile_real']['strong'])} on the strongest third of firings, {f2(I['tercile_real']['weak'])} on the weakest.
*Limits:* **every label is AI-written and none was checked by a human.** The same model family wrote the labels and took the blind test, the non-firing
snippets are random tokens (an easy contrast), the control used less data (stored at half precision), and the labeller's own "unclear" verdict did not predict blind accuracy
({f3(B['real_suggested_unclear']['mean_accuracy'])} for those {B['real_suggested_unclear']['n']} features, against {f3(B['real_all_200']['mean_accuracy'])} overall).

**3. Steering moves the next word reliably, topics only sometimes, and only in a narrow strength window.**
I added a multiple of a feature's decoder direction to the activations while the model wrote, with a random direction of the same length as control.
For the {len(clr)} features chosen because they were strict-clear *and* scored 5/5 blind, text stayed fluent at {KLOW}× the feature's usual strong firing in {fluent_half} of {len(clr)} cases (neither of the two prompts broke) and
broke on both prompts at {KHIGH}× in {brk2} of {len(clr)} (the unsteered model's own perplexity on this text is {UMIN} to {UMAX}; "broken" means above {ST['break_threshold_ppl']}). Broken text repeated what the feature predicts next ("girl girl girl", "so so so"):
at {KHIGH}× the feature's promoted tokens made up {f1(min(h2))} to {f1(max(h2))} of {S['steer_max_new_tokens']} generated tokens, against at most {f1(max(rh2))} for random directions, which also broke the text in {rbrk2} of {len(clr)} cases but into unrelated words.
In an extension on {len(ext)} features whose labels name a topic, {len(ext_ok)} ({', '.join(str(e['feature']) for e in ext_ok)}) produced more theme words than the random control at strengths where the text stayed fluent;
{len(ext_bad)} ({', '.join(str(e['feature']) for e in ext_bad)}) did not.
*Limits:* two prompts per feature, {ST['n_features_steered_total']} features in all, success judged by word counts and reading the text. The brief's strengths were too strong: {BRK510}, so gentler strengths were added.
Topic steering worked for {len(ext_ok)} of the {len(ext)} topic features tried, and blind-test accuracy did not predict which (blind scores of those that worked: {blind_ok}; of those that did not: {blind_bad}).

**4. Switching off features changes the model's pronoun choice, but the obvious test was misleading.**
The model prefers the right pronoun after a name on all {T['n_prompts']} prompts (mean logit gap {f2(tn['clean_score'])} on name-only prompts).
The test I fixed in advance passed: switching off the top {len(T['top10'])} features together lowers the gap by {f2(jo['top_drop'])} on held-out names, against a mean of {f2(jo['random_drop_mean'])}
(largest {f2(jo['random_drop_max'])}) for {jo['n_random']} random sets, and it beats all {jo['top_beats_n_random']}. **But {T['top10_fire_on_both_genders_count']} of those {len(T['top10'])} features fire equally on girls' and boys' names**
(on these prompts they peak on "One", "day", commas, "park" and "because"), so the test shows the behaviour depends on context features; it does not isolate gender. A follow-up restricted to gender-selective features found
the gender signal: switching off the top {len(sg['features'])} girl-selective features lowers the gap on held-out girl-name prompts by {f2(sg['own']['drop'])} (from {f2(sg['own']['clean_score'])}) and the boy-selective ones by {f2(sb['own']['drop'])} (from {f2(sb['own']['clean_score'])}).
Adding the boy-selective features to girl-name prompts, at their average activation on boy names, flipped the preferred pronoun on {pc(fl[('girl', FA, 'name_only')]['add_flip'])} of prompts; adding the girl-selective features to boy-name prompts flipped {pc(fl[('boy', FA, 'name_only')]['add_flip'])}
(at {FB}× that level, {pc(fl[('girl', FB, 'name_only')]['add_flip'])} and {pc(fl[('boy', FB, 'name_only')]['add_flip'])}; random directions of the same length: at most {pc(max(r['random_flip'] for r in T['flip_selective'] if r['kind'] == 'name_only'))}).
*Limits:* the gender-selective analysis was designed after seeing the first result, so it is exploratory. There are only {T['n_names']} names and {T['n_frames']} sentence frames; flip rates are out of {fl[('girl', FA, 'name_only')]['n']} prompts.
Nearly all of the girl effect comes from one feature (1511, {f2(sg['per_feature']['1511']['heldout_effect_own'])} of the {f2(sg['own']['drop'])}); the boy features are largely tied to particular names (Tom, Tim, Bob) and transfer less
well to held-out names (drop {f2(sb['ranking_names_drop'])} on the names they were ranked on, {f2(sb['own']['drop'])} on held-out names, against {f2(sb['own']['random_drop_max'])} for the best random set).
Switching these features off never changed which pronoun the model preferred (the correct pronoun is still preferred on {'all' if min_acc_after == 1 else 'at least ' + pc(min_acc_after)} of the held-out prompts), so other features or the autoencoder's reconstruction error also carry gender. Layer {S['layer']} only.

## Feature browser

Open [`browser/index.html`](browser/index.html) in any browser (no server, no network). Pick a feature to see its AI-written label, whether it passed the strict rule,
its blind-test score, its strongest and random firings, and any steering or tracing results. A toggle switches to the shuffled-weights control's features for comparison.
It holds the {I['n_features_labelled']} labelled features, the {I['n_control_labelled']} labelled control features, and the features used in Stage 7 that were not among the {I['n_features_labelled']}.

## Results at a glance

| λ | active features per token (L0) | variance explained | loss recovered (zero / mean baseline) | extra loss (nats) | dead in last epoch |
|---|---|---|---|---|---|
""" + "\n".join(
    f"| {k}{' (chosen)' if k == lam else ''} | {f1(v['l0'])} | {f3(v['variance_explained'])} | {f3(v['loss_recovered_zero'])} / {f3(v['loss_recovered_mean'])} | {f2(v['extra_loss_nats'])} | {v['dead_last_train_epoch']:.1%} |"
    for k, v in F["runs"].items()) + f"""

Held-out set: {S['heldout_stories']} stories, {F['n_predicted_tokens']:,} predicted tokens. Unmodified model loss {f3(F['L_clean'])} nats; zero-ablation {f3(F['L_zero'])}; mean-ablation {f3(F['L_mean'])}.
Training data: {S['train_tokens_in_sae']:,} tokens from {S['train_stories']:,} stories, {S['epochs']} epochs.

Figures are in [`figures/`](figures/). Full write-up with method, failures and limits: [`REPORT.md`](REPORT.md).

## How to run

```
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
pytest                                              # tests for the autoencoder, hooks, evaluation and ablation code
```

Some tests load the model from the Hugging Face cache and some read the collected activations, so run `pytest` after Stages 1 and 2.

Everything is configured in `config.yaml` (seed {S['seed']}); results land in `results/`, figures in `figures/`. Long steps checkpoint and can be re-run to resume; start them with `caffeinate -i` on a laptop.
The collected activations take {S['data_dir_GB']:.2f} GB (`data/`, git-ignored, regenerable); checkpoints are git-ignored too. Designed for an M1 MacBook Air (CPU or `mps`), no paid services.

| Stage | Command(s) | Writes |
|---|---|---|
| 0–1 setup, model | `python scripts/device_test.py`, `python scripts/stage1_load_model.py` | `results/device_test.json`, `results/stage1_*.json` |
| 2 activations | `caffeinate -i python scripts/stage2_collect_activations.py`, `python scripts/stage2_checks.py` | `data/`, `results/stage2_*.json` |
| 3 train | `python scripts/stage3_pilot.py`, `caffeinate -i python scripts/stage3_train.py` | `checkpoints/sae/`, `results/stage3_*.json` |
| 4 faithfulness | `python scripts/stage4_faithfulness.py`, `python scripts/stage4_table.py` | `results/stage4_*` |
| 5 features | `python scripts/stage5_examples.py`, `python scripts/stage5_write_labels.py`, `python scripts/stage5_random_control.py`, `python scripts/stage5_examples.py --random`, `python scripts/stage5_write_labels_random.py`, `python scripts/stage5_blind_build.py`, *(blind answering, see note)*, `python scripts/stage5_blind_score.py`, `python scripts/stage5_report.py` | `results/stage5*` |
| 6 steering | `python scripts/stage6_steer.py`, `python scripts/stage6_steer.py --ext`, `python scripts/stage6_report.py`, `python scripts/stage6_ext_report.py` | `results/stage6*` |
| 7 tracing | `python scripts/stage7_trace.py`, `python scripts/stage7_analyse.py`, `python scripts/stage7_selective.py`, `python scripts/stage7_report.py` | `results/stage7*` |
| 8 browser, docs | `python scripts/stage8_numbers.py`, `python scripts/stage8_browser.py`, `python scripts/stage8_docs.py`, `python scripts/stage8_check_numbers.py` | `results/headline_numbers.json`, `browser/index.html`, `README.md`, `REPORT.md` |

**Two steps are not fully scripted.** The labels were written by Claude reading the examples; `stage5_write_labels.py` stores that text, so re-running it rebuilds `labels.csv` but does not re-label.
The blind answers came from {NSUB} fresh Claude sub-agents reading only the puzzle files in `results/stage5_blind/`; their raw answers are saved in `results/stage5_blind/responses.json`, and `stage5_blind_score.py` recomputes every blind-test number from them.
Re-doing the blind test would need new answers and would give slightly different numbers.

**Where numbers come from.** `scripts/stage8_numbers.py` gathers every number cited here into `results/headline_numbers.json`, and `scripts/stage8_docs.py` fills this README and `REPORT.md` from it, and `scripts/stage8_check_numbers.py` flags any number in either document that it cannot trace to that file. Don't edit the numbers by hand.

## Repository layout

```
config.yaml        every setting and the seed
src/               model hooks, data, activation collection, autoencoder, training, evaluation, tracing helpers
scripts/           one or two scripts per stage (table above)
tests/             tests for the autoencoder, hooks, collection, evaluation and ablation code
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

## Credits

Built by a student with Claude Code (Anthropic) as the coding assistant. Claude also wrote all feature labels and took the blind label test, which is why the labels count as unverified.
"""

# ============================================================ REPORT ============================================================
def table(header, rows):
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


faith_rows = [[k + (" (chosen)" if k == lam else ""), f1(v["l0"]), f3(v["variance_explained"]),
               f"{f3(v['loss_recovered_zero'])} [{f3(v['loss_recovered_zero_ci95'][0])}, {f3(v['loss_recovered_zero_ci95'][1])}]",
               f"{f3(v['loss_recovered_mean'])} [{f3(v['loss_recovered_mean_ci95'][0])}, {f3(v['loss_recovered_mean_ci95'][1])}]",
               f2(v["extra_loss_nats"]), f2(v["perplexity_spliced"]), f"{v['dead_last_train_epoch']:.1%}", f"{v['never_fire_heldout']:.1%}",
               "yes" if v["l0_levelled_off"] else "no", v["total_resampled"]] for k, v in F["runs"].items()]
blind_rows = [[name, B[k]["n"], f3(B[k]["mean_accuracy"]), B[k]["n_perfect_5of5"], B[k]["n_at_or_below_chance"]] for name, k in [
    ("Real, all labelled", "real_all_200"), ("Real, first 50 (same size as control)", "real_first_50"), ("Real, strict-clear", "real_final_clear"),
    ("Real, not strict-clear", "real_not_final_clear"), ("Real, labeller said 'unclear'", "real_suggested_unclear"), ("Shuffled-weights control", "control_50")]]
main_rows = []
for m in main:
    for k in ST["multipliers_main"]:
        kk = str(k)
        b = m["by_k"][kk]
        main_rows.append([m["feature"], clean(m["label"]), f"{m['blind']}/5", "clear" if m["group"] == "clear_5of5" else "NOT clear", kk,
                          b["feature_broken"], f1(b["feature_promoted_hits"]), b["random_broken"], f1(b["random_promoted_hits"])])
ext_rows = [[e["feature"], clean(e["label"]), f"{e['blind']}/5", "clear" if e["group"] == "clear" else "NOT clear", f1(e["theme_words_unsteered"]),
             f1(e["max_theme_words_unbroken_feature"]), f1(e["max_theme_words_unbroken_random"]), e["max_unbroken_k"], "yes" if e["works"] else "no"] for e in ext]
flip_rows = []
for tgt in ("girl", "boy"):
    for s in T["flip_strengths"]:
        kk = s
        a = fl[(tgt, kk, "name_only")]
        c = fl[(tgt, kk, "noun_name")]
        flip_rows.append([tgt, "boy" if tgt == "girl" else "girl", kk, pc(a["add_flip"]), pc(a["swap_flip"]), pc(a["random_flip"]), pc(c["add_flip"]), pc(c["swap_flip"]), pc(c["random_flip"])])

REPORT = f"""# Sparse autoencoders on TinyStories-8M: method, results, failures and limits

{DISCLAIMER}

This is a small, careful application of published methods ([Prior work](#7-prior-work)) to one small model, not new research.
Every number below comes from a file in `results/`, gathered by `scripts/stage8_numbers.py` into `results/headline_numbers.json` and filled in by `scripts/stage8_docs.py`.
The README leads with the four main findings and their limits; this report gives the detail.

## 1. Summary

| Question | Answer | Main limit |
|---|---|---|
| Does the autoencoder capture the activations? | λ={lam}: variance explained {f3(R1['variance_explained'])}, L0 {f1(R1['l0'])}, loss recovered {f3(R1['loss_recovered_zero'])} (zero baseline) / {f3(R1['loss_recovered_mean'])} (mean baseline), but +{f2(R1['extra_loss_nats'])} nats | weak baselines; one seed |
| Are its features interpretable? | {I['clear_real']}/{I['n_features_labelled']} strict-clear; blind test {f3(B['real_all_200']['mean_accuracy'])} vs control {f3(B['control_50']['mean_accuracy'])} vs chance 0.5 | AI labels, AI test, no human check |
| Do they steer the model? | next-word steering works, breaks the text at 2×; {len(ext_ok)}/{len(ext)} topic features steered a topic | small test, narrow strength window |
| Can one behaviour be traced? | yes for context features; gender-selective features flip the pronoun | post-hoc analysis, few names |

## 2. Method

### 2.1 Model and activations
- Model: `{S['model']}` (GPT-Neo, 8 blocks, width {S['width']}). Activations are the residual stream after block {S['layer']} (0-indexed; {S['layer'] + 1} blocks before, {NB - S['layer'] - 1} after), captured with a forward hook (`src/model.py`).
- Data: {S['train_stories']:,} training stories from one shard of TinyStories, {S['heldout_stories']:,} stories from its validation split, with no story shared between them (`train_heldout_identical_stories` = {S['train_heldout_identical_stories']}).
  Each story is the end-of-text token plus the story, truncated to 256 tokens, stored as one row per token in fp32 memmaps ({S['data_dir_GB']:.2f} GB total).
- Position 0 (the end-of-text prefix) is always the same vector (norm {f2(S['pos0_norm'])}); it is excluded from autoencoder training. Other positions have mean norm {f2(S['mean_activation_norm_model_units'])}.
  The mean activation vector holds {pc(S['fraction_squared_norm_in_mean'])} of the squared norm, so the decoder bias starts at the data's centre.
- All activations are multiplied by one constant ({f3(S['rescale_factor'])}) so their mean norm is √{S['width']}. Autoencoder-unit activations quoted anywhere are in these scaled units.

### 2.2 Autoencoder and training (`src/sae.py`, `src/train.py`)
- Encode f = ReLU(W_e (x − b_d) + b_e), decode x̂ = W_d f + b_d; untied weights, {S['dictionary_size']} features ({S['expansion']}× the width).
- Loss: squared error summed over dimensions plus λ times the sum of feature strengths, averaged over the batch.
- Decoder columns are kept at unit length, and the gradient component parallel to each column is removed before each step (Bricken et al.).
- b_d starts at the geometric median of the data, which was {f2(S['b_d_geometric_median_minus_mean_norm'])} from the mean vector (whose norm is {f1(S['b_d_mean_norm'])}).
- Adam, learning rate {S['lr']}, batch size {S['batch_size']}, {S['epochs']} epochs over {S['train_tokens_in_sae']:,} tokens (shuffled across stories), λ in {S['lambdas']}.
- Dead features are resampled after epochs {S['resample_after_epochs']} (Bricken's procedure scaled to this run length, using {S['resample_pool']:,} inputs to choose new directions).
- Tests: shapes, decoder normalisation, loss decreasing and true-direction recovery on a toy problem (`tests/test_sae.py`).

### 2.3 Faithfulness (`src/eval.py`)
Splice the autoencoder's reconstruction into the model at layer {S['layer']} and measure next-token loss on the {S['heldout_stories']:,} held-out stories ({F['n_predicted_tokens']:,} predicted tokens).
Loss recovered = (loss with activations ablated − loss with reconstruction) / (loss with activations ablated − unmodified loss), with two ablation baselines: zero, and the mean activation. Intervals are 95% bootstrap over stories.

### 2.4 Interpretation (`scripts/stage5_*.py`)
- {I['n_features_labelled']} features were chosen at random (seed {S['seed']}) from the λ={lam} autoencoder. For each: its top {S['interpret_top_k']} activating snippets, {S['interpret_n_random']} uniformly random firings, firing frequency, and the output tokens its direction promotes.
- **Labelling.** Claude wrote one label per feature from that evidence and a verdict, *clear* only if one concept explains the top examples *and* the random firings also fit. The user chose not to hand-label, so these labels are final. They are AI-written and unverified.
- **Blind test.** For each feature, a fresh Claude sub-agent that had not seen the evidence got only the label and {NSNIP} snippets from text not used for labelling (real: the held-out split): {NFIRE} where the feature fires (sampled uniformly among all firings, so many are weak) and {NSNIP - NFIRE} where it does not.
  It had to pick the firing ones. {I['n_puzzles']} puzzles (real and control, anonymised and shuffled together) were answered by {NSUB} sub-agents; {I['n_invalid']} answers were invalid. Chance is {CH}; p-values are hypergeometric per feature and simulated overall.
- **Control.** An autoencoder with the same settings trained on a copy of the model whose weights were shuffled (Bricken et al.): {I['control_sae']['train_tokens']:,} training tokens at half precision, {I['control_sae']['epochs']} epochs; final variance explained {f3(I['control_sae']['variance_explained'])}, L0 {f1(I['control_sae']['l0'])}.
  Its first {I['n_control_labelled']} features were labelled and tested the same way.

### 2.5 Steering (`scripts/stage6_steer.py`)
Add k × s × d to the residual stream at layer {S['layer']} at every position except position 0, while the model generates {S['steer_max_new_tokens']} tokens (temperature {S['generation_temperature']}, fixed seed per prompt).
d is the feature's unit decoder direction, s its typical strong firing (mean of its top-{S['interpret_top_k']} activations), converted back to model units. Control: a random unit direction of the same length.
Text is "broken" if its perplexity under the unsteered model exceeds {ST['break_threshold_ppl']} (unsteered text scores {UMIN} to {UMAX}). Two prompts per feature.
**Selection.** Main run: features that were strict-clear *and* scored 5/5 blind, then {len(clr)} chosen for labels about visible words, plus {len(weak)} that were not clear. Extension: every Stage 5 label that names a topic or domain (not a syntactic slot or single next word), whatever its verdict or blind score.
Theme words for the extension were written down before reading any steered text.

### 2.6 Tracing (`scripts/stage7_*.py`)
- Behaviour: the model's choice of "she"/"he" (or "She"/"He") after a named character. Score = logit(correct pronoun) − logit(wrong pronoun) at the last position.
- Test set: {T['n_names']} single-token names ({len(T['names']['girl_names_rank'])} girls' and {len(T['names']['boy_names_rank'])} boys' for ranking, {len(T['names']['girl_names_heldout'])} and {len(T['names']['boy_names_heldout'])} held out) in {T['n_frames']} sentence frames = {T['n_prompts']} prompts.
  {T['n_frames_name_only']} frames give the name alone (the headline), {T['n_frames_noun_name']} include "a little girl/boy named" (reported separately, since the noun gives the answer away).
- Ablation: set one feature to zero at all positions after the first, decode, add the autoencoder's reconstruction error back, so only that feature changes (`src/trace.py`, tested). {T['n_firing_features']} of {S['dictionary_size']} features fire on these prompts; each was ablated alone.
- Pre-registered test: rank on the ranking names, switch off the top {len(T['top10'])} together on held-out names, compare with {T['n_random_sets']} random sets of firing features. Post-hoc follow-up: gender-selective features (activation at least {T['selection_ratio']}× larger on one gender's ranking names).
- Flip test: add the other gender's features at that gender's average activation (same frame, same position) × strength; control: random directions of the same length ({T['flip_random_draws']} draws).

## 3. Results

### 3.1 Training and faithfulness
{table(["λ", "L0", "variance explained", "loss recovered, zero baseline [95% CI]", "loss recovered, mean baseline [95% CI]", "extra loss (nats)", "perplexity after splicing", "dead, last epoch", "never fire, held-out", "L0 levelled off", "resampled"], faith_rows)}

Unmodified loss {f3(F['L_clean'])} nats (perplexity {f2(F['perplexity_clean'])}); zero-ablation {f3(F['L_zero'])}; mean-ablation {f3(F['L_mean'])}.
L0 had levelled off (changing under 2% per epoch over the last 3 epochs) for λ = {', '.join(levelled)}{'' if not not_levelled else ' but not for λ = ' + ', '.join(not_levelled)}.
![training](figures/stage3_training.png)
![faithfulness](figures/stage4_faithfulness.png)

Other figure: `figures/stage3_density.png`. λ={lam} was carried forward: sparse enough to read, no dead features, most of the loss recovered.

### 3.2 Interpretability
- Strict-clear: **{I['clear_real']}/{I['n_features_labelled']} ({pc1(I['clear_real_share'])})** real, **{I['clear_control']}/{I['n_control_labelled']} ({pc1(I['clear_control_share'])})** control. Judging on top examples alone: {I['clear_if_random_firings_ignored_real']}/{I['n_features_labelled']} real and {I['clear_if_random_firings_ignored_control']}/{I['n_control_labelled']} control look clear.
  So top examples flatter both autoencoders, including the one trained on a scrambled model; random firings separate them.

{table(["Set", "n", "mean blind accuracy", "5/5 correct", "3/5 or fewer"], blind_rows)}

Chance is {CH}. Real vs chance: p = {B['real_all_200']['p_value_vs_chance']:.5f} (simulated; 0 means none of the simulations reached it); control vs chance: p = {B['control_50']['p_value_vs_chance']:.5f}. For one feature, only 5/5 is significant at p < 0.05.
By firing strength (terciles of activation), real features: weak {f2(I['tercile_real']['weak'])}, middle {f2(I['tercile_real']['middle'])}, strong {f2(I['tercile_real']['strong'])}; control: {f2(I['tercile_control']['weak'])}, {f2(I['tercile_control']['middle'])}, {f2(I['tercile_control']['strong'])}.
{I['real_features_blind_5of5_and_clear']} features are both strict-clear and 5/5 blind; {I['real_features_blind_at_or_below_3of5']} real features scored 3/5 or lower. Per-feature results: `results/stage5_blind_per_feature.csv`. ![blind test](figures/stage5_blind.png)

Write-up with examples of failures: `results/stage5_report.md`.

### 3.3 Steering, main run
Mean over 2 prompts; "broken" is the count of the 2 prompts above the perplexity threshold; "promoted" is how many of {S['steer_max_new_tokens']} generated tokens are among the feature's top-{S['n_promoted']} promoted tokens.

{table(["feature", "label (AI-written)", "blind", "Stage 5", "k", "feature: broken", "feature: promoted", "random: broken", "random: promoted"], main_rows)}

Side-by-side text for every cell, including failures: `results/stage6_report.md`.

![steering](figures/stage6_steering.png)

Of the {len(clr)} strict-clear/5-of-5 features, {fluent_half} stayed fluent at {KLOW}× and {brk2} broke at {KHIGH}×. Random directions broke {rbrk2} of {len(clr)} at {KHIGH}×. At the brief's other strengths, {BRK510}.
The not-clear features: {', '.join(f"{m['feature']} (first broken at {m['first_k_all_broken']}×)" for m in weak)}.

### 3.4 Steering, topic extension
Strengths {', '.join(ST['multipliers_extension'])}. "Theme words" = whole-word matches to a list fixed in `config.yaml` before reading the output, in {S['steer_max_new_tokens']} tokens, mean over 2 prompts; the maximum is taken over strengths where neither prompt broke.
"Steered a topic" = the feature's maximum exceeds the random control's at the same strengths.

{table(["feature", "label (AI-written)", "blind", "Stage 5", "theme words, unsteered", "max, feature", "max, random", "highest unbroken k", "steered a topic"], ext_rows)}

Full text and per-strength tables: `results/stage6_extension_report.md`.

![steering extension](figures/stage6_extension.png)

Features that failed are reported with the rest: {', '.join(str(e['feature']) for e in ext_bad)} produced no more theme words than random directions did.

### 3.5 Tracing the pronoun
- Unmodified model, name-only prompts: correct pronoun beats the wrong one on {pc(tn['clean_pair_accuracy'])} of {tn['n']} prompts, is the model's top-1 token on {pc(tn['clean_top1_is_correct'])}, mean logit gap {f2(tn['clean_score'])}.
- Pre-registered test (held-out names, name-only prompts): switching off the top {len(T['top10'])} features together lowers the gap from {f2(jo['clean_score'])} to {f2(jo['score_after_top_ablation'])} (correct pronoun still preferred on {pc(jo['pair_accuracy_after'])} of prompts);
  {jo['n_random']} random sets of {len(T['top10'])} firing features lower it by {f2(jo['random_drop_mean'])} on average and {f2(jo['random_drop_max'])} at most; the top set beats {jo['top_beats_n_random']}/{jo['n_random']}. The pre-registered test passes.
- **{T['top10_fire_on_both_genders_count']} of the top {len(T['top10'])} (features {', '.join(str(j) for j in T['top10_fire_on_both_genders'])}) fire with equal strength on girls' and boys' names.** They are context features, so this test cannot tell gender from context.
- Post-hoc, gender-selective features (candidates: {sg['n_candidates']} girl-selective, {sb['n_candidates']} boy-selective), top {len(sg['features'])} each, held-out names:

{table(["set", "features", "clean gap", "drop on own gender", "random sets: mean / max drop", "beats", "drop on other gender"], [
    ["girl-selective", sg["features"], f2(sg["own"]["clean_score"]), f2(sg["own"]["drop"]), f"{f2(sg['own']['random_drop_mean'])} / {f2(sg['own']['random_drop_max'])}", f"{sg['own']['beats_n_random']}/{sg['own']['n_random']}", f2(sg["other"]["drop"])],
    ["boy-selective", sb["features"], f2(sb["own"]["clean_score"]), f2(sb["own"]["drop"]), f"{f2(sb['own']['random_drop_mean'])} / {f2(sb['own']['random_drop_max'])}", f"{sb['own']['beats_n_random']}/{sb['own']['n_random']}", f2(sb["other"]["drop"])]])}

- Flip test with the gender-selective features: share of held-out prompts where the wrong pronoun becomes preferred. "add" adds the other gender's features; "swap" also switches off the prompt's own gender-selective features. Left block: name-only prompts ({fl[('girl', 1, 'name_only')]['n']} per gender); right block: noun-plus-name prompts ({fl[('girl', 1, 'noun_name')]['n']} per gender).

{table(["prompts", "features added from", "strength", "add", "swap", "random", "add (noun)", "swap (noun)", "random (noun)"], flip_rows)}

Full tables, per-feature results and the first (confounded) flip test: `results/stage7_report.md`.

![tracing](figures/stage7_trace.png)


## 4. Failures, surprises and things that went wrong

- **The sparsest autoencoder is unhealthy.** At λ={LMAX}, {R4['never_fire_heldout']:.1%} of features never fire on held-out text, {R4['total_resampled']} features were resampled during training, and L0 had not levelled off; it was not used.
- **The pre-registered tracing test passed for the wrong reason** ({T['top10_fire_on_both_genders_count']} of {len(T['top10'])} top features are gender-neutral context features), and the first flip test was confounded by them. The gender-selective analysis fixed this but was designed after seeing the data.
- **Top examples are misleading.** {I['clear_if_random_firings_ignored_real']}/{I['n_features_labelled']} real features and {I['clear_if_random_firings_ignored_control']}/{I['n_control_labelled']} control features look clear from top examples. Only random firings separate them (strict rule: {I['clear_real']} vs {I['clear_control']}).
- **The labeller's "unclear" verdict was not informative:** those features scored {f3(B['real_suggested_unclear']['mean_accuracy'])} blind, the same as all features ({f3(B['real_all_200']['mean_accuracy'])}). Some strict-clear features still scored badly (see `results/stage5_report.md`).
- **The control is not a worthless autoencoder.** It reconstructs as well as the real one (variance explained {f3(I['control_sae']['variance_explained'])} vs {f3(R1['variance_explained'])}) and its blind accuracy ({f3(B['control_50']['mean_accuracy'])}) is above chance (p = {B['control_50']['p_value_vs_chance']:.5f}). Reconstruction quality alone says nothing about interpretability.
- **Steering strengths from the brief were too strong.** {KHIGH}× already broke the text for {brk2} of {len(clr)} strict-clear main features, so gentler strengths were added, and the extension used finer steps. Random directions also broke text at that size.
- **Steering hits the next word more than the topic.** Many features fire on one token and predict the next, so strong steering produces repeats of that word. One weak-label feature (978, "sunshine") produced the most graceful steering of the main run; whether a label was strict-clear or scored well blind did not predict which topic features steered (section 3.4).
- **Promoted-token counts miss some effects.** Feature 978's promoted tokens do not include "sunshine", so its count of promoted tokens stays at 0 even when the text turns to sunshine; I judged by reading the text and, in the extension, by pre-written theme words.
- **Boy-name features are name-specific.** The boy-selective features lowered the gap by {f2(sb['ranking_names_drop'])} on the names they were ranked on but {f2(sb['own']['drop'])} on held-out names, barely above the best random set ({f2(sb['own']['random_drop_max'])}).
- **A real bug caught early:** the first full activation collection ran out of GPU memory because every batch had a different padded length; padding to multiples of 64 and clearing the cache fixed it, and recomputing a random sample on CPU confirmed the saved activations (max difference {S['verify_max_abs_diff']:.1e} over {S['verify_stories_checked']} stories).
- **Held-out leakage caught:** the first held-out sample contained stories also present in the training sample (TinyStories has duplicates); they were excluded and `results/stage2_checks.json` confirms zero overlap.
- **Initialisation deviation:** the brief's encoder initialisation (the transpose of the decoder) made the first reconstruction several times too large; scaling it by {S['enc_init_scale']} fixed that (see section 6).
- **Dataset quirk:** TinyStories contains encoding artefacts (curly quotes appearing as odd byte sequences), and at least one feature tracks them.

## 5. Limits

- One model, one layer ({S['layer']}), one dictionary size ({S['dictionary_size']}), one seed. No variation across training seeds was measured; the confidence intervals are over stories.
- The autoencoder is lossy ({f2(R1['extra_loss_nats'])} nats of extra loss), so anything the reconstruction error carries is invisible to feature-level analysis. In the tracing, ablating features never changed which pronoun was preferred for the gender-selective sets, so some gender information is elsewhere.
- **All labels are AI-written and unverified.** The labeller and the blind guessers are the same model family, so their errors may be correlated; the blind test uses random tokens as the non-firing examples, an easy contrast.
- Only {I['n_features_labelled']} of {S['dictionary_size']} features were labelled, chosen at random; claims about "most features" extend from that sample.
- The shuffled-weights control used {I['control_sae']['train_tokens']:,} half-precision tokens against {S['train_tokens_in_sae']:,} full-precision tokens for the real autoencoder, and its evaluation tokens come from the same stories as its training tokens.
- Steering used 2 prompts and {S['steer_max_new_tokens']} tokens per cell; success was judged by counts and reading. The "broken" threshold ({ST['break_threshold_ppl']}) is a judgement call.
- Tracing used {T['n_names']} names and {T['n_frames']} hand-written frames; the gender-selective analysis was exploratory. The random-set controls match the number of features, not their activation size.
- Promoted-token lists are an approximation (the direction is multiplied by the unembedding although {NB - S['layer'] - 1} blocks remain after layer {S['layer']}).

## 6. Deviations from the brief and from the papers

| Topic | Brief / papers | What I did | Why |
|---|---|---|---|
| Encoder init | W_e = transpose of W_d | W_e = {S['enc_init_scale']} × W_dᵀ | the brief's init gave a first reconstruction several times too large (user approved) |
| b_d init | data mean | geometric median (Bricken) | cheap; was {f2(S['b_d_geometric_median_minus_mean_norm'])} from the mean |
| Decoder gradient | rescale columns only | also remove the gradient component parallel to each column (Bricken) | published and cheap |
| Position 0 | not mentioned | excluded from training | it is a constant vector |
| Data size | Bricken: billions of vectors | {S['train_tokens_in_sae']:,} tokens, {S['epochs']} epochs | disk cap; repeated epochs risk dead features, so resampling was used |
| λ grid | 4 values spaced about 3× | {S['lambdas']} (2× spacing) | after the pilot, 3× spacing would have put half the runs outside the usable range |
| Loss recovered | zero baseline | zero and mean baselines | zero-ablation flatters (Bricken) |
| Labels | not specified | AI-written, no human check | user's decision to not hand-label; blind test added to partly compensate |
| Steering strengths | 2×, 5×, 10× | {', '.join(str(k) for k in ST['multipliers_main'])}× (main), {', '.join(ST['multipliers_extension'])}× (extension) | 2× already broke the text |
| Tracing | one pre-registered test | plus a post-hoc gender-selective analysis and flip test | the first test did not isolate gender; flagged as exploratory |

## 7. Prior work

- Ronen Eldan and Yuanzhi Li. *TinyStories: How Small Can Language Models Be and Still Speak Coherent English?* arXiv:2305.07759, 2023.
- Trenton Bricken, Adly Templeton, Joshua Batson, Brian Chen, Adam Jermyn, Tom Conerly, Nicholas L. Turner, Cem Anil, Carson Denison, Amanda Askell, Robert Lasenby, Yifan Wu, Shauna Kravec, Nicholas Schiefer, Tim Maxwell, Nicholas Joseph, Zac Hatfield-Dodds, Alex Tamkin, Karina Nguyen, Brayden McLean, Josiah E. Burke, Tristan Hume, Shan Carter, Tom Henighan and Chris Olah.
  *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning.* Transformer Circuits Thread, 2023. (The page header omits Hatfield-Dodds; the paper's own BibTeX includes him.)
- Hoagy Cunningham, Aidan Ewart, Logan Riggs, Robert Huben and Lee Sharkey. *Sparse Autoencoders Find Highly Interpretable Features in Language Models.* arXiv:2309.08600, 2023.

Citation details were checked against the sources in Stage 3 (`docs/method_comparison.md`, which also has the full comparison with the brief).

## 8. Reproducibility

- Seed {S['seed']} in `config.yaml`; per-stage seeds derive from it and are recorded in the result files. Device: `mps` on an M1 MacBook Air (a CPU-only run should give the same results up to floating-point differences, which I did not test).
- Commands, in order, are in the README. `data/` ({S['data_dir_GB']:.2f} GB) and `checkpoints/` are git-ignored and regenerable. Long steps resume when re-run.
- Not fully scripted: the label text (stored in `scripts/stage5_write_labels.py`) and the blind answers (stored raw in `results/stage5_blind/responses.json`; the scoring script recomputes everything from them). Re-running the blind test needs new answers and would give slightly different numbers.
- The README and this report are generated from `results/headline_numbers.json`, which `scripts/stage8_numbers.py` builds from the result files. `PROGRESS.md` records each stage's decisions.
"""

(ROOT / "README.md").write_text(README)
(ROOT / "REPORT.md").write_text(REPORT)
print("wrote README.md", len(README.split()), "words; REPORT.md", len(REPORT.split()), "words")
