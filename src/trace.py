"""Stage 7 helpers: edit SAE features inside the residual stream while keeping the SAE error."""
from __future__ import annotations

import torch


def feature_acts(sae, h: torch.Tensor, scale: float) -> torch.Tensor:
    """SAE feature activations for model-unit activations h (..., d)."""
    return sae.encode(h * scale)


def ablate_features(sae, scale: float, idx):
    """Replace-fn for residual_hook: zero features `idx` at every position except 0 (EOS prefix),
    decode, and add the SAE's reconstruction error back. With idx empty this is the identity."""
    idx = torch.as_tensor(idx, dtype=torch.long)

    def fn(h):
        x = h[:, 1:] * scale
        f = sae.encode(x)
        err = x - sae.decode(f)
        f = f.clone()
        f[..., idx] = 0
        out = h.clone()
        out[:, 1:] = (sae.decode(f) + err) / scale
        return out
    return fn


def reconstruct_only(sae, scale: float):
    """Replace-fn: SAE reconstruction with the error dropped (positions > 0)."""
    def fn(h):
        out = h.clone()
        out[:, 1:] = sae.decode(sae.encode(h[:, 1:] * scale)) / scale
        return out
    return fn


def add_vector(vec: torch.Tensor):
    """Replace-fn: add vec (seq, d) or (batch, seq, d), model units, to the activations."""
    return lambda h: h + vec
