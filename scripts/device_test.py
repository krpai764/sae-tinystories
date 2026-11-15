"""Stage 0: time CPU vs mps and write results/device_test.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch

from src.config import ROOT, load_config, set_seed
from src.device_bench import time_matmul

cfg = load_config()
set_seed(cfg["seed"])
n, reps = cfg["device"]["speed_test_matrix"], cfg["device"]["speed_test_repeats"]
# (batch, model width, dictionary size): the encoder matmul of an SAE with width 512, 8x dictionary
shapes = {"square": (n, n, n), "sae_encoder_4096x512x4096": (4096, 512, 4096)}

out = {"torch_version": torch.__version__, "repeats": reps, "shapes": {}}
mps = torch.backends.mps.is_available()
for name, (m, k, nn) in shapes.items():
    flops = 2 * m * k * nn
    row = {"shape": [m, k, nn], "cpu_ms": time_matmul("cpu", m, k, nn, reps) * 1e3}
    row["cpu_gflops"] = flops / (row["cpu_ms"] / 1e3) / 1e9
    if mps:
        row["mps_ms"] = time_matmul("mps", m, k, nn, reps) * 1e3
        row["mps_gflops"] = flops / (row["mps_ms"] / 1e3) / 1e9
        row["speedup_mps_over_cpu"] = row["cpu_ms"] / row["mps_ms"]
    out["shapes"][name] = row

out["mps_available"] = mps
out["faster_overall"] = (
    "mps" if mps and all(r["mps_ms"] < r["cpu_ms"] for r in out["shapes"].values()) else "cpu"
)
res = ROOT / cfg["paths"]["results_dir"]
res.mkdir(exist_ok=True)
(res / "device_test.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
