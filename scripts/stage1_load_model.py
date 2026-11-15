"""Stage 1: generate 3 fixed-prompt stories, check hook, time cpu vs mps on the real model.

Writes results/stage1_stories.json and results/stage1_model_device_test.json.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch

from src.config import ROOT, load_config, set_seed
from src.model import generate, get_activations, load_model

cfg = load_config()
set_seed(cfg["seed"])
res = ROOT / cfg["paths"]["results_dir"]
res.mkdir(exist_ok=True)
g = cfg["generation"]
layer = cfg["model"]["layer"]

# --- stories (on CPU so the text is not device-dependent) ---
model, tok = load_model(cfg, device="cpu")
stories = []
for i, p in enumerate(g["prompts"]):
    text = generate(model, tok, p, seed=g["seed"] + i, max_new_tokens=g["max_new_tokens"],
                    temperature=g["temperature"])
    stories.append({"prompt": p, "seed": g["seed"] + i, "text": text})
    print(f"--- story {i} (seed {g['seed'] + i}) ---\n{text}\n")
(res / "stage1_stories.json").write_text(json.dumps(
    {"model": cfg["model"]["name"], "temperature": g["temperature"], "top_k": 50,
     "max_new_tokens": g["max_new_tokens"], "stories": stories}, indent=2))

# --- activation shape + norm sanity ---
ids = tok(g["prompts"][0], return_tensors="pt").input_ids
acts = get_activations(model, ids, layer)
print("activation shape:", tuple(acts.shape), "| mean norm:", acts.norm(dim=-1).mean().item())

# --- device timing on the real model: batch of 32 x 256 tokens, forward + hook ---
bench = {"batch": 32, "seq_len": 256, "layer": layer, "forward_seconds": {}}
x = torch.randint(0, cfg["model"]["max_seq_len"] * 100, (32, 256))
for dev in ["cpu"] + (["mps"] if torch.backends.mps.is_available() else []):
    m, _ = load_model(cfg, device=dev)
    xd = x.to(dev)
    with torch.no_grad():
        for _ in range(2):
            get_activations(m, xd, layer).sum().item()
        t = time.perf_counter()
        for _ in range(5):
            a = get_activations(m, xd, layer)
        a.sum().item()
        bench["forward_seconds"][dev] = (time.perf_counter() - t) / 5
    del m
bench["faster"] = min(bench["forward_seconds"], key=bench["forward_seconds"].get)
if "mps" in bench["forward_seconds"]:
    bench["speedup_mps_over_cpu"] = bench["forward_seconds"]["cpu"] / bench["forward_seconds"]["mps"]
(res / "stage1_model_device_test.json").write_text(json.dumps(bench, indent=2))
print(json.dumps(bench, indent=2))
