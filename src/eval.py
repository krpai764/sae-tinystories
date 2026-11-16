"""Stage 4: next-token loss with the layer-3 residual stream replaced by something else."""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from src.model import residual_hook


def seqs_from_split(tokens: np.ndarray, offsets: np.ndarray) -> list[np.ndarray]:
    return [tokens[offsets[i]:offsets[i + 1]] for i in range(len(offsets) - 1)]


def keep_pos0(fn):
    """Wrap a replacement so position 0 (the EOS prefix) keeps its real activation."""
    def wrapped(h):
        out = fn(h)
        return torch.cat([h[:, :1], out[:, 1:]], dim=1)
    return wrapped


def sae_replace(sae, scale: float):
    """Replacement fn: rescale -> SAE reconstruction -> undo the rescaling."""
    def fn(h):
        x = h * scale
        x_hat, _ = sae(x)
        return x_hat / scale
    return fn


def const_replace(vec: torch.Tensor | None):
    """Replace every activation by `vec` (zeros if None)."""
    def fn(h):
        if vec is None:
            return torch.zeros_like(h)
        return vec.to(h.device, h.dtype).expand_as(h).clone()
    return fn


@torch.no_grad()
def story_losses(model, seqs, layer: int, device: str, replace=None, batch_size: int = 32,
                 pad_id: int = 50256, pad_multiple: int = 64):
    """Per-story (sum of next-token cross-entropy in nats, number of predicted tokens).

    A story of L tokens gives L-1 predictions (token t+1 from the prefix up to t).
    replace=None gives the clean model. Same batching/padding for every condition.
    """
    sums, counts = np.zeros(len(seqs)), np.zeros(len(seqs))
    order = list(range(len(seqs)))
    for a in range(0, len(order), batch_size):
        idx = order[a:a + batch_size]
        chunk = [seqs[i] for i in idx]
        L = -(-max(len(s) for s in chunk) // pad_multiple) * pad_multiple
        ids = torch.full((len(chunk), L), pad_id, dtype=torch.long)
        mask = torch.zeros((len(chunk), L), dtype=torch.bool)
        for j, s in enumerate(chunk):
            ids[j, :len(s)] = torch.from_numpy(s.astype(np.int64))
            mask[j, :len(s)] = True
        ids, mask = ids.to(device), mask.to(device)
        if replace is None:
            logits = model(ids).logits
        else:
            with residual_hook(model, layer, replace=replace):
                logits = model(ids).logits
        ce = F.cross_entropy(logits[:, :-1].float().reshape(-1, logits.shape[-1]),
                             ids[:, 1:].reshape(-1), reduction="none").view(len(chunk), L - 1)
        valid = mask[:, 1:]  # target position must be a real token
        s_ = (ce * valid).sum(1).cpu().numpy()
        c_ = valid.sum(1).cpu().numpy()
        for j, i in enumerate(idx):
            sums[i], counts[i] = s_[j], c_[j]
    return sums, counts


def loss_recovered(L_clean: float, L_zero: float, L_spliced: float) -> float:
    return (L_zero - L_spliced) / (L_zero - L_clean)
