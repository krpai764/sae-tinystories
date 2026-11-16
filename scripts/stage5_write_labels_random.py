"""Stage 5 control: write results/stage5_random/labels.csv (shuffled-weights SAE, first 50 features) with Claude's SUGGESTED labels for one batch.

Suggestions are hand-written (by reading results/stage5/batch_k.md) and kept in this script so the
file can be regenerated. User columns are never overwritten if already filled.
Usage: python scripts/stage5_write_labels.py
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT

# index_in_list: (suggested label, suggested verdict clear/unclear, do random examples agree? yes/partly/no)
SUGGESTIONS = {
    0: ("Opening quote after 'says,' / 'asked his mom,'", "clear", "partly"),
    1: ("Mixed tokens (moo, from, paws, dreaming); no theme", "unclear", "no"),
    2: ("' been' (had been / never been)", "clear", "partly"),
    3: ("' Every' in 'Every day/morning'", "clear", "partly"),
    4: ("' stick' (noun or verb)", "clear", "no"),
    5: ("' adventure'", "clear", "no"),
    6: ("Sentence-initial ' We' in speech", "clear", "partly"),
    7: ("Mixed (seemed, patient, tiny)", "unclear", "no"),
    8: ("Name-initial sub-token ' L' (Lila) / 'O'(w); mixed", "unclear", "no"),
    9: ("' brave'", "clear", "partly"),
    10: ("' likes' / ' money' (two unrelated tokens)", "unclear", "no"),
    11: ("' and' after laughing/emotion ('Mommy laughed and')", "clear", "yes"),
    12: ("' man' (the old man)", "clear", "no"),
    13: ("' wish'", "clear", "no"),
    14: ("' loved' after 'She' in a character introduction", "clear", "no"),
    15: ("' hand'", "clear", "no"),
    16: ("' hear'", "clear", "no"),
    17: ("' name'", "clear", "no"),
    18: ("' felt' after a sensory action; mixed (5.5% dense)", "unclear", "no"),
    19: ("'-' inside hyphenated compounds", "clear", "no"),
    20: ("Mixed (working, cat, tea, away)", "unclear", "no"),
    21: ("' rabbit'", "clear", "no"),
    22: ("'Yes' at the start of a reply", "clear", "no"),
    23: ("'ite' completing kite / excite", "clear", "no"),
    24: ("'ite' completing kite / excite (duplicate of #23)", "clear", "no"),
    25: ("'.\"' closing a spoken sentence", "clear", "no"),
    26: ("Mixed (steel, gives, silly, wand)", "unclear", "no"),
    27: ("' late' in 'it was too late'", "clear", "no"),
    28: ("' Billy'", "clear", "no"),
    29: ("' broken'", "clear", "no"),
    30: ("' brought'", "clear", "no"),
    31: ("' matter' / ' longer' in 'no matter', 'any longer'", "clear", "no"),
    32: ("' bench'", "clear", "no"),
    33: ("' just'", "clear", "no"),
    34: ("' Ho' (start of Hoppy/Hopper)", "clear", "no"),
    35: ("' hold'", "clear", "no"),
    36: ("Mixed ('.', calm, clown, decided)", "unclear", "no"),
    37: ("' spot' (a place)", "clear", "no"),
    38: ("' feel' in 'make you feel'", "clear", "no"),
    39: ("'apped' completing flapped/clapped", "clear", "no"),
    40: ("' tell'", "clear", "no"),
    41: ("' go'", "clear", "partly"),
    42: ("Mojibake byte of an opening curly quote", "clear", "no"),
    43: ("' though' in 'even though'", "clear", "no"),
    44: ("'.' ending a mid-paragraph sentence (dense)", "unclear", "partly"),
    45: ("' stop'", "clear", "no"),
    46: ("'Let' at the start of a quote (\"Let's\")", "clear", "no"),
    47: ("' castle'", "clear", "no"),
    48: ("' some' (get/have some)", "clear", "no"),
    49: ("' home' (back home / go home)", "clear", "partly"),
}

od = ROOT / "results" / "stage5_random"
feats = json.loads((od / "features.json").read_text())["features"]
path = od / "labels.csv"
cols = ["index_in_list", "batch", "feature", "firing_frequency", "suggested_label (SUGGESTION)",
        "suggested_verdict (SUGGESTION)", "random_examples_agree (SUGGESTION)",
        "your_label", "your_verdict (clear/unclear/dead-or-junk)", "your_notes"]
existing = {}
if path.exists():
    with open(path) as f:
        for r in csv.DictReader(f):
            existing[int(r["index_in_list"])] = r
rows = []
for f in feats:
    i = f["index_in_list"]
    if i not in SUGGESTIONS and i not in existing:
        continue
    r = existing.get(i, {c: "" for c in cols})
    lab, ver, agree = SUGGESTIONS.get(i, ("", "", ""))
    r.update({"index_in_list": i, "batch": f["batch"], "feature": f["feature"],
              "firing_frequency": f"{f['firing_frequency']:.5f}",
              "suggested_label (SUGGESTION)": lab, "suggested_verdict (SUGGESTION)": ver,
              "random_examples_agree (SUGGESTION)": agree})
    rows.append(r)
with open(path, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
print(f"wrote {len(rows)} rows to {path}")
