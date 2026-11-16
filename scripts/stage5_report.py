"""Stage 5: write results/stage5_report.md from results files (no hand-typed numbers)."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT

R = ROOT / "results"
s = json.loads((R / "stage5_blind_scores.json").read_text())
rc = json.loads((R / "stage5_random_control.json").read_text())
st3 = json.loads((R / "stage3_runs.json").read_text())["runs"]["1"]["final"]
rows = list(csv.DictReader(open(R / "stage5_blind_per_feature.csv")))
real = [r for r in rows if r["set"] == "real"]
fc = s["final_clear_share"]
pct = lambda x: f"{100 * x:.1f}%"


def ex(sel, n):
    return "\n".join(f"- #{r['index_in_list']} (feature {r['feature']}): {r['label']} — blind accuracy {float(r['accuracy']):.1f}" for r in sel[:n])


clear_good = [r for r in real if r["final_clear"] == "True" and float(r["accuracy"]) == 1.0]
unclear = [r for r in real if r["verdict_suggested"] == "unclear"]
clear_bad = [r for r in real if r["final_clear"] == "True" and float(r["accuracy"]) <= 0.6]
notclear_low = sorted([r for r in real if float(r["accuracy"]) <= 0.4], key=lambda r: float(r["accuracy"]))
A, C = s["real_all_200"], s["control_50"]
txt = f"""# Stage 5 report: interpreting features (SAE λ=1)

> **All feature labels in this project are AI-written (by Claude) and have NOT been verified by a human.**
> The user chose not to hand-label. Labels were written from the top-20 and 5 random firing snippets plus
> promoted output tokens, and then scored with a blind test (below), but nobody checked them by hand.

## What was labelled
- 200 features chosen at random (seed 1234) from the 2048 in the λ=1 SAE (all 2048 fire on training data).
- Control: SAE with the same settings trained on a **shuffled-weights** copy of the model (Bricken et al. 2023);
  {rc['train_tokens']} training tokens (fp16), final VE {rc['final']['variance_explained']:.3f}, L0 {rc['final']['l0']:.1f}
  (real SAE: VE {st3['variance_explained']:.3f}, L0 {st3['l0']:.1f}). The first 50 of 200 randomly chosen control features were labelled the same way.

## Clear vs unclear (labeller's own verdict)
A feature is **clear** only if one concept explains the top examples **and** the 5 uniformly random firings also fit ("yes").
- Real SAE: **{fc['real_n']}/200 clear ({pct(fc['real'])})**. If random firings are ignored, {fc['real_suggested_clear_ignoring_random']}/200 look clear from top examples alone.
- Control: **{fc['control_n']}/50 clear ({pct(fc['control'])})**; {fc['control_suggested_clear_ignoring_random']}/50 look clear from top examples alone.
- Lesson: top examples flatter both SAEs, including the one trained on a meaningless model. Random firings separate them.

## Blind test of the labels
For each feature, a fresh model instance that never saw the evidence got only the label and 10 snippets from text not used
for labelling (real: held-out split; control: rows not shown), each with one marked token: 5 where the feature fires
(sampled uniformly among all firings, so many are weak) and 5 where it does not. It had to pick the 5 firing ones.
Puzzles from both SAEs were anonymised and shuffled together. Chance = 0.50.

| Set | n | mean accuracy | 5/5 correct | ≤ 3/5 correct | p vs chance |
|---|---|---|---|---|---|
| Real SAE, all | {A['n']} | {A['mean_accuracy']:.3f} | {A['n_perfect_5of5']} | {A['n_at_or_below_chance']} | {A['p_value_vs_chance']:.5f} |
| Real SAE, first 50 (size-matched) | {s['real_first_50']['n']} | {s['real_first_50']['mean_accuracy']:.3f} | {s['real_first_50']['n_perfect_5of5']} | {s['real_first_50']['n_at_or_below_chance']} | {s['real_first_50']['p_value_vs_chance']:.5f} |
| Real, labelled clear | {s['real_final_clear']['n']} | {s['real_final_clear']['mean_accuracy']:.3f} | {s['real_final_clear']['n_perfect_5of5']} | {s['real_final_clear']['n_at_or_below_chance']} | |
| Real, not clear | {s['real_not_final_clear']['n']} | {s['real_not_final_clear']['mean_accuracy']:.3f} | {s['real_not_final_clear']['n_perfect_5of5']} | {s['real_not_final_clear']['n_at_or_below_chance']} | |
| Real, labeller said "unclear" | {s['real_suggested_unclear']['n']} | {s['real_suggested_unclear']['mean_accuracy']:.3f} | | | |
| Shuffled-weights control | {C['n']} | {C['mean_accuracy']:.3f} | {C['n_perfect_5of5']} | {C['n_at_or_below_chance']} | {C['p_value_vs_chance']:.5f} |

p = probability of a mean at least this high under random guessing (100,000 simulations; 0.00000 means none reached it).
Per feature, only 5/5 is significant at p<0.05 (p=0.004); 4/5 has p=0.10. Per-feature results: `results/stage5_blind_per_feature.csv`.

Detection of firing snippets by firing strength (terciles): real weak/middle/strong =
{s['real_firing_detection_by_strength_tercile']['weak']:.2f} / {s['real_firing_detection_by_strength_tercile']['middle']:.2f} / {s['real_firing_detection_by_strength_tercile']['strong']:.2f};
control = {s['control_firing_detection_by_strength_tercile']['weak']:.2f} / {s['control_firing_detection_by_strength_tercile']['middle']:.2f} / {s['control_firing_detection_by_strength_tercile']['strong']:.2f}.
Labels describe strong firings well; weak firings are often off-label.

## Examples (not only good ones)
Clear and perfectly predicted:
{ex(clear_good, 5)}

Labelled clear but blind accuracy ≤ 0.6:
{ex(clear_bad, 5) or '- none'}

Labeller said unclear:
{ex(unclear, 5)}

Lowest blind accuracy:
{ex(notclear_low, 6)}

## Caveats
- One AI wrote the labels and another instance of the same model family guessed; shared biases could inflate scores.
- The labeller's "unclear" verdicts did not predict blind accuracy (see table), so those verdicts are weak evidence.
- Control used 400k tokens (fp16) vs 2.5M (fp32), and its eval is a random 10% of the same stories, so it is not a perfectly matched comparison.
- Non-firing snippets are random tokens, an easy contrast; harder distractors (same token, feature off) would lower scores.
"""
(R / "stage5_report.md").write_text(txt)
print(txt)
