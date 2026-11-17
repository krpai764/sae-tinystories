"""Stage 8 checks: the browser page is self-contained and carries the AI-label disclaimer; README/REPORT numbers trace to results."""
import json
import re
import subprocess
import sys

from src.config import ROOT


def _page():
    return (ROOT / "browser" / "index.html").read_text()


def test_browser_has_disclaimer_and_valid_embedded_data():
    html = _page()
    assert "have not been verified by a human" in html
    assert not re.search(r"""(src|href)=["']https?://""", html), "page must not load anything from the network"
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</"))
    real = [e for e in data["entries"] if e["sae"] == "real" and not e.get("unlabelled")]
    control = [e for e in data["entries"] if e["sae"] == "control"]
    assert len(real) == 200 and len(control) == 50
    assert all(e["label"] and len(e["top"]) == 20 and len(e["random"]) == 5 for e in real)
    assert sum(e["clear"] for e in real) == data["summary"]["clear"]
    assert all("steer" in e for e in real if e["feature"] in (144, 916, 978))


def test_docs_have_disclaimer_and_numbers_trace_to_results():
    for name in ("README.md", "REPORT.md"):
        assert "AI-written" in (ROOT / name).read_text() and "have not been verified by a human" in (ROOT / name).read_text()
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "stage8_check_numbers.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
