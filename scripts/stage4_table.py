"""Stage 4: build the carry-forward comparison table (markdown) from results/stage4_faithfulness.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT, load_config

cfg = load_config()
res = ROOT / cfg["paths"]["results_dir"]
o = json.loads((res / "stage4_faithfulness.json").read_text())
S = o["settings"]["p0kept"]
rows = ["| λ | L0 | VE | dead (last train epoch) | never fire (held-out) | loss recovered, zero base | loss recovered, mean base | extra loss (nats) |",
        "|---|---|---|---|---|---|---|---|"]
for lam, e in S["saes"].items():
    rows.append(f"| {lam} | {e['stage3']['l0']:.1f} | {e['stage3']['variance_explained']:.3f} | "
                f"{e['dead_fraction_last_train_epoch']:.3f} | {e['stage3']['dead_fraction']:.3f} | "
                f"{e['loss_recovered_zero']:.3f} | {e['loss_recovered_mean']:.3f} | +{e['extra_loss_nats']:.3f} |")
txt = (f"Held-out: {o['n_stories']} stories, {o['n_predicted_tokens']} predicted tokens. "
       f"Clean loss {o['L_clean']:.3f}; zero-ablation {S['L_zero']:.3f}; mean-ablation {S['L_mean']:.3f} nats "
       f"(position 0 left real).\n\n" + "\n".join(rows) + "\n")
(res / "stage4_table.md").write_text(txt)
print(txt)
