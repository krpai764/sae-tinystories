"""Load the TinyStories model, generate text, and hook the residual stream.

Residual stream convention used everywhere in this project
----------------------------------------------------------
`layer = L` means the residual stream *after* transformer block L (0-indexed),
i.e. the output of `model.transformer.h[L]`, before block L+1. With 8 blocks and
L = 3 that is the midpoint: 4 blocks have run, 4 remain.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.config import ROOT, load_config


def load_model(cfg: dict | None = None, device: str = "cpu", random_init: bool = False):
    """Return (model, tokenizer). Model is in eval mode on `device`.

    random_init=True returns an untrained copy with identical architecture
    (used for the Stage 5 sanity check).
    """
    cfg = cfg or load_config()
    name = cfg["model"]["name"]
    cache = ROOT / cfg["paths"]["hf_cache_dir"]
    tok = AutoTokenizer.from_pretrained(name, cache_dir=cache)
    if random_init:
        from transformers import AutoConfig

        torch.manual_seed(cfg["seed"])
        model = AutoModelForCausalLM.from_config(AutoConfig.from_pretrained(name, cache_dir=cache))
    else:
        model = AutoModelForCausalLM.from_pretrained(name, cache_dir=cache)
    return model.eval().to(device), tok


@torch.no_grad()
def generate(model, tok, prompt: str, seed: int, max_new_tokens: int = 80,
             temperature: float = 0.8, device: str = "cpu") -> str:
    """Sample a continuation with a fixed seed (same seed + prompt -> same text)."""
    ids = tok(prompt, return_tensors="pt").input_ids.to(device)
    torch.manual_seed(seed)  # HF sampling uses the global generator
    out = model.generate(
        ids, max_new_tokens=max_new_tokens, do_sample=True, temperature=temperature,
        top_k=50, pad_token_id=tok.eos_token_id,
    )
    return tok.decode(out[0], skip_special_tokens=True)


def _split(output):
    """Blocks return a tuple (hidden, ...) or a bare tensor; normalise."""
    return (output[0], output[1:]) if isinstance(output, tuple) else (output, None)


def _join(hidden, rest):
    return hidden if rest is None else (hidden, *rest)


@contextmanager
def residual_hook(model, layer: int, store: list | None = None,
                  replace: Callable[[torch.Tensor], torch.Tensor] | None = None):
    """Hook the residual stream after block `layer`.

    store:   if given, a detached copy of the (batch, seq, width) activations is
             appended to it on every forward pass.
    replace: if given, a function mapping activations -> new activations; its
             result is passed on to the rest of the model (used for splicing in
             SAE reconstructions, zero-ablation and steering).
    With neither argument the hook is a pure no-op.
    """
    def fn(module, inputs, output):
        hidden, rest = _split(output)
        if store is not None:
            store.append(hidden.detach().clone())
        if replace is not None:
            return _join(replace(hidden), rest)
        return None  # leave output untouched

    handle = model.transformer.h[layer].register_forward_hook(fn)
    try:
        yield
    finally:
        handle.remove()


@torch.no_grad()
def get_activations(model, input_ids: torch.Tensor, layer: int) -> torch.Tensor:
    """Residual-stream activations after block `layer`: (batch, seq, width)."""
    store: list = []
    with residual_hook(model, layer, store=store):
        model(input_ids)
    return store[0]
