"""Sparse autoencoder, written from scratch (no interpretability library).

    x_bar = x - b_d                    (pre-encoder bias, tied to the decoder bias)
    f     = ReLU(W_e x_bar + b_e)      feature strengths, shape (m,)
    x_hat = W_d f + b_d                reconstruction
    loss  = mean_batch( ||x - x_hat||^2 + lam * ||f||_1 )

W_d has unit-norm columns (each column is one feature's direction). Following
Bricken et al. (2023) we (1) remove the gradient component parallel to each
decoder column before every optimiser step and (2) renormalise columns after it.
See docs/method_comparison.md for where this differs from the brief and papers.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class SparseAutoencoder(nn.Module):
    def __init__(self, d: int, m: int, seed: int = 0, enc_init_scale: float = 1.0):
        super().__init__()
        g = torch.Generator().manual_seed(seed)
        W_d = torch.randn(d, m, generator=g)
        W_d /= W_d.norm(dim=0, keepdim=True)
        self.W_d = nn.Parameter(W_d)                    # (d, m), unit columns
        # (m, d), starts along W_d^T (brief). enc_init_scale=2d/m calibrates the initial
        # reconstruction: with scale 1, W_d W_d^T ~ (m/d) I and ReLU halves it, so the
        # initial output is ~m/(2d) = 4x too large (tested in Stage 3; see PROGRESS.md).
        self.W_e = nn.Parameter(W_d.T.clone() * enc_init_scale)
        self.b_e = nn.Parameter(torch.zeros(m))
        self.b_d = nn.Parameter(torch.zeros(d))
        self.d, self.m = d, m

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return torch.relu((x - self.b_d) @ self.W_e.T + self.b_e)

    def decode(self, f: torch.Tensor) -> torch.Tensor:
        return f @ self.W_d.T + self.b_d

    def forward(self, x: torch.Tensor):
        f = self.encode(x)
        return self.decode(f), f

    @staticmethod
    def loss_terms(x, x_hat, f, lam: float):
        """Returns (total, reconstruction, sparsity), each averaged over the batch."""
        recon = (x - x_hat).pow(2).sum(-1).mean()
        sparsity = f.abs().sum(-1).mean()
        return recon + lam * sparsity, recon, sparsity

    @torch.no_grad()
    def remove_parallel_decoder_grad(self) -> None:
        """Project out the gradient along each (unit) decoder column (Bricken et al.)."""
        if self.W_d.grad is None:
            return
        parallel = (self.W_d.grad * self.W_d).sum(0, keepdim=True)
        self.W_d.grad -= parallel * self.W_d

    @torch.no_grad()
    def normalize_decoder(self) -> None:
        self.W_d /= self.W_d.norm(dim=0, keepdim=True).clamp_min(1e-8)

    @torch.no_grad()
    def resample(self, dead: torch.Tensor, x_pool: torch.Tensor, optimizer,
                 generator: torch.Generator | None = None, enc_scale: float = 0.2,
                 batch: int = 8192) -> int:
        """Re-initialise dead features toward badly reconstructed inputs (Bricken et al.).

        dead:   bool mask (m,) of features to resample
        x_pool: (N, d) inputs (already rescaled) on the SAE's device
        For each dead feature: sample an input with probability proportional to its
        squared reconstruction loss; decoder column = that input (centred by b_d),
        unit norm; encoder row = same direction with norm 0.2 x mean alive encoder
        norm; b_e = 0; Adam state for the touched entries reset to zero.
        Deviation: Bricken uses the raw input; we centre by b_d because ~39% of
        the squared norm of our activations is a shared mean vector, so raw
        inputs would all point nearly the same way.
        """
        idx = dead.nonzero().squeeze(-1)
        k = idx.numel()
        if k == 0:
            return 0
        losses = []
        for a in range(0, len(x_pool), batch):
            xb = x_pool[a:a + batch]
            losses.append((xb - self(xb)[0]).pow(2).sum(-1))
        sq = torch.cat(losses).pow(2)  # probability ∝ square of the loss (paper)
        pick = torch.multinomial(sq.float().cpu(), k, replacement=k > len(sq), generator=generator)
        v = x_pool[pick.to(x_pool.device)] - self.b_d
        v = v / v.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        alive = ~dead
        enc_norm = self.W_e[alive].norm(dim=-1).mean() if alive.any() else torch.tensor(1.0)
        self.W_d[:, idx] = v.T
        self.W_e[idx] = v * enc_norm * enc_scale
        self.b_e[idx] = 0.0
        for p, sl in [(self.W_d, (slice(None), idx)), (self.W_e, (idx,)), (self.b_e, (idx,))]:
            st = optimizer.state.get(p, {})
            for key in ("exp_avg", "exp_avg_sq"):
                if key in st:
                    st[key][sl] = 0.0
        return k


@torch.no_grad()
def geometric_median(x: torch.Tensor, iters: int = 200, tol: float = 1e-6) -> torch.Tensor:
    """Weiszfeld's algorithm: the point minimising the sum of Euclidean distances."""
    y = x.mean(0)
    for _ in range(iters):
        dist = (x - y).norm(dim=-1).clamp_min(1e-8)
        w = 1.0 / dist
        y_new = (w[:, None] * x).sum(0) / w.sum()
        if (y_new - y).norm() < tol * max(1.0, y.norm().item()):
            return y_new
        y = y_new
    return y
