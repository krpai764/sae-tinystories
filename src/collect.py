"""Collect residual-stream activations into a memory-mapped .npy file (resumable).

Files written under out_dir for a given `name` (e.g. 'train'):
  {name}_acts.npy    float32 (N, width)   activations, row i <-> token i
  {name}_tokens.npy  int32   (N,)         token ids
  {name}_story.npy   int32   (N,)         story index of each token
  {name}_pos.npy     int16   (N,)         position inside story (0 = the EOS prefix)
  {name}_offsets.npy int64   (S+1,)       first row of each story
  {name}_progress.json                    stories done (for resume)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from src.data import flatten
from src.model import get_activations


def collect(model, seqs: list[np.ndarray], out_dir: Path, name: str, layer: int, device: str,
            batch_size: int = 32, checkpoint_every: int = 50, pad_id: int = 50256,
            pad_multiple: int = 64, dtype=np.float32, log=print) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    f = lambda suffix: out_dir / f"{name}_{suffix}"
    width = model.config.hidden_size

    tokens, story, pos, offsets = flatten(seqs)
    for suffix, arr in [("tokens", tokens), ("story", story), ("pos", pos), ("offsets", offsets)]:
        np.save(f(suffix + ".npy"), arr)
    n = len(tokens)

    prog_path = f("progress.json")
    done = 0
    if prog_path.exists() and f("acts.npy").exists():
        done = json.loads(prog_path.read_text())["stories_done"]
        acts = np.load(f("acts.npy"), mmap_mode="r+")
        assert acts.shape == (n, width), "existing file does not match plan; delete it"
        log(f"resuming {name}: {done}/{len(seqs)} stories already done")
    else:
        acts = np.lib.format.open_memmap(f("acts.npy"), mode="w+", dtype=dtype, shape=(n, width))

    batches = list(range(done, len(seqs), batch_size))
    for bi, a in enumerate(batches):
        chunk = seqs[a:a + batch_size]
        # Pad to a multiple of `pad_multiple` (right padding + causal attention = real tokens
        # unaffected). Few distinct shapes keeps MPS from caching a kernel/buffer set per shape,
        # which exhausted memory on the first full run.
        L = max(len(s) for s in chunk)
        L = -(-L // pad_multiple) * pad_multiple
        ids = torch.full((len(chunk), L), pad_id, dtype=torch.long)
        mask = torch.zeros((len(chunk), L), dtype=torch.long)
        for j, s in enumerate(chunk):
            ids[j, :len(s)] = torch.from_numpy(s.astype(np.int64))
            mask[j, :len(s)] = 1
        with torch.no_grad():
            h = get_activations(model, ids.to(device), layer).float().cpu().numpy()
        for j, s in enumerate(chunk):  # real tokens only, right padding never attended to
            r0 = offsets[a + j]
            acts[r0:r0 + len(s)] = h[j, :len(s)]
        stories_done = a + len(chunk)
        if device == "mps" and (bi + 1) % 10 == 0:
            torch.mps.empty_cache()
        if (bi + 1) % checkpoint_every == 0 or stories_done == len(seqs):
            acts.flush()
            prog_path.write_text(json.dumps({"stories_done": stories_done}))
            mem = f", mps driver mem {torch.mps.driver_allocated_memory() / 1e9:.2f} GB" if device == "mps" else ""
            log(f"{name}: {stories_done}/{len(seqs)} stories, {offsets[stories_done]}/{n} tokens{mem}")
    acts.flush()
    prog_path.write_text(json.dumps({"stories_done": len(seqs)}))
    return {"name": name, "num_tokens": int(n), "num_stories": len(seqs), "width": width}


def load_split(out_dir: Path, name: str):
    """Open a collected split: (acts memmap, tokens, story, pos, offsets)."""
    out_dir = Path(out_dir)
    ld = lambda s, **kw: np.load(out_dir / f"{name}_{s}.npy", **kw)
    return ld("acts", mmap_mode="r"), ld("tokens"), ld("story"), ld("pos"), ld("offsets")
