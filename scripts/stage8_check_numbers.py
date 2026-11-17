"""Stage 8 check: every number in README.md and REPORT.md must be traceable to results/headline_numbers.json.

Extracts numeric tokens from the two documents (skipping headings, citation lines, code blocks and file/script names)
and reports any that match no value in headline_numbers.json at a plausible rounding, nor an allowed structural number
(stage numbers, section numbers, the 0/5-style scale of the blind test, percent-thresholds written as criteria).
Exit code 1 if anything is untraceable. This is a safety net, not a proof: small integers and the strength values
are allowed through because they also appear as criteria and parameters; the main protection is that the documents are
generated from the file (scripts/stage8_docs.py).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT

N = json.loads((ROOT / "results" / "headline_numbers.json").read_text())
vals = []


def walk(x):
    if isinstance(x, bool):
        return
    if isinstance(x, (int, float)):
        vals.append(float(x))
    elif isinstance(x, dict):
        [walk(v) for v in x.values()]
    elif isinstance(x, list):
        [walk(v) for v in x]
    elif isinstance(x, str):  # numbers embedded in strings such as '0/2', '5/5'
        for t in re.findall(r"\d+(?:\.\d+)?", x):
            vals.append(float(t))


walk(N)
# derived values the docs compute from the file (differences are not stored, so also allow sums of counts handled via the file itself)
known = set()
for v in vals:
    for fmt in ("{:.0f}", "{:.1f}", "{:.2f}", "{:.3f}", "{:.4f}", "{:.5f}", "{:,.0f}", "{:g}"):
        known.add(fmt.format(v))
    for pct in (v * 100,):
        for fmt in ("{:.0f}", "{:.1f}"):
            known.add(fmt.format(pct))
    known.add(f"{v:.1e}")
# structural numbers that are definitions, not results: the 5-of-5 / 3-of-5 criteria, 'p < 0.05', and list indices
ALLOWED = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "0.05", "10", "100", "0.5", "1.5", "0.75", "1.25", "2023"}  # 2023 = citation year
tok = re.compile(r"(?<![A-Za-z_\d./-])\d[\d,]*(?:\.\d+)?(?:e-?\d+)?(?![A-Za-z_\d])")
bad = []
for name in ("README.md", "REPORT.md"):
    in_code = False
    for ln, line in enumerate((ROOT / name).read_text().splitlines(), 1):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or line.startswith("#") or "arXiv" in line or "Transformer Circuits" in line or line.startswith("- Trenton") or "*Towards" in line:
            continue
        clean = re.sub(r"`[^`]*`", "", line)           # drop inline code (file names, commands)
        clean = re.sub(r"\]\([^)]*\)", "]", clean)      # drop link targets
        for m in tok.finditer(clean):
            t = m.group(0).rstrip(",.")
            if t in known or t.replace(",", "") in known or t in ALLOWED or t.replace(",", "") in ALLOWED:
                continue
            bad.append((name, ln, t, clean[max(0, m.start() - 50):m.end() + 30].strip()))
for b in bad:
    print(f"{b[0]}:{b[1]}  '{b[2]}'  ...{b[3]}...")
print(f"{len(bad)} untraceable numbers")
sys.exit(1 if bad else 0)
