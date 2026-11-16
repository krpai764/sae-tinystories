"""SAE training loop with per-epoch metrics, checkpoint/resume, optional resampling."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from src.collect import load_split
from src.sae import SparseAutoencoder, geometric_median


def load_activations(data_dir: Path, name: str, exclude_pos0: bool = True) -> torch.Tensor:
    """Load a split's activations into RAM as a float32 CPU tensor (pos-0 rows dropped)."""
    acts, _, _, pos, _ = load_split(data_dir, name)
    keep = pos > 0 if exclude_pos0 else np.ones(len(pos), dtype=bool)
    return torch.from_numpy(np.asarray(acts)[keep])


def rescale_factor(x: torch.Tensor) -> float:
    """Constant c so that mean ||c x|| = sqrt(d)."""
    return float(np.sqrt(x.shape[1]) / x.norm(dim=-1).mean().item())


@torch.no_grad()
def evaluate(sae: SparseAutoencoder, x: torch.Tensor, lam: float, device: str,
             batch: int = 8192) -> dict:
    """Metrics on (already rescaled) data x (CPU tensor)."""
    sse = l0 = l1 = 0.0
    fires = torch.zeros(sae.m, device=device)
    for a in range(0, len(x), batch):
        xb = x[a:a + batch].to(device)
        x_hat, f = sae(xb)
        sse += (xb - x_hat).pow(2).sum().item()
        active = f > 0
        l0 += active.sum().item()
        l1 += f.sum().item()
        fires += active.sum(0)
    n = len(x)
    total_var = (x - x.mean(0)).pow(2).sum().item()
    density = (fires / n).cpu()
    return {
        "variance_explained": 1 - sse / total_var,
        "mse_per_token": sse / n,
        "l0": l0 / n,
        "l1": l1 / n,
        "loss": sse / n + lam * l1 / n,
        "dead_fraction": float((density == 0).float().mean()),
        "density_gt_1pct": float((density > 0.01).float().mean()),
        "density": density.numpy(),
    }


def train_sae(x_train: torch.Tensor, x_eval: torch.Tensor, lam: float, cfg: dict, out_dir: Path,
              epochs: int, device: str, seed: int, resample_after_epochs: tuple = (),
              resample_pool: int = 200_000, log=print) -> dict:
    """Train one SAE. x_train / x_eval must already be rescaled. Resumes from out_dir/ckpt.pt.

    'Dead in epoch' = feature fired 0 times on the 2.5M training tokens of that epoch.
    """
    s = cfg["sae"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = out_dir / "ckpt.pt"
    d = x_train.shape[1]
    m = d * s["expansion"]
    bs = s["batch_size"]

    sae = SparseAutoencoder(d, m, seed=seed, enc_init_scale=s.get("enc_init_scale", 1.0)).to(device)
    opt = torch.optim.Adam(sae.parameters(), lr=s["lr"])
    hist = {"lam": lam, "epochs": [], "steps": []}
    start_epoch = 0
    if ckpt_path.exists():
        ck = torch.load(ckpt_path, map_location=device, weights_only=False)
        sae.load_state_dict(ck["sae"])
        opt.load_state_dict(ck["opt"])
        hist, start_epoch = ck["hist"], ck["epoch"]
        log(f"[lam={lam}] resumed at epoch {start_epoch}")
    else:
        g = torch.Generator().manual_seed(seed)
        sub = x_train[torch.randperm(len(x_train), generator=g)[:100_000]]
        gm = geometric_median(sub.double()).float()
        with torch.no_grad():
            sae.b_d.copy_(gm.to(device))
        hist["b_d_init"] = {"geometric_median_minus_mean_norm": float((gm - sub.mean(0)).norm()),
                            "mean_norm": float(sub.mean(0).norm())}

    n = len(x_train)
    steps_per_epoch = n // bs
    for epoch in range(start_epoch, epochs):
        t0 = time.time()
        g = torch.Generator().manual_seed(seed * 1000 + epoch)  # reproducible shuffle per epoch
        perm = torch.randperm(n, generator=g)
        fires = torch.zeros(m, device=device)
        sums = {"loss": 0.0, "recon": 0.0, "sparsity": 0.0}
        for i in range(steps_per_epoch):
            xb = x_train[perm[i * bs:(i + 1) * bs]].to(device, non_blocking=True)
            x_hat, f = sae(xb)
            loss, recon, sp = sae.loss_terms(xb, x_hat, f, lam)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            sae.remove_parallel_decoder_grad()
            opt.step()
            sae.normalize_decoder()
            fires += (f > 0).sum(0).detach()
            if i % 50 == 0:
                hist["steps"].append({"step": epoch * steps_per_epoch + i, "loss": loss.item(),
                                      "recon": recon.item(), "sparsity": sp.item(),
                                      "l0": (f > 0).float().sum(-1).mean().item()})
        dead_train = float((fires == 0).float().mean())
        ev = evaluate(sae, x_eval, lam, device)
        resampled = 0
        if (epoch + 1) in resample_after_epochs:
            g2 = torch.Generator().manual_seed(seed + 7 + epoch)
            pool = x_train[torch.randperm(n, generator=g2)[:resample_pool]].to(device)
            resampled = sae.resample(fires == 0, pool, opt, generator=g2)
            del pool
        rec = {"epoch": epoch + 1, "seconds": time.time() - t0,
               "dead_fraction_train_epoch": dead_train, "resampled": resampled,
               **{k: v for k, v in ev.items() if k != "density"}}
        hist["epochs"].append(rec)
        log(f"[lam={lam}] epoch {epoch + 1}/{epochs}: VE {ev['variance_explained']:.4f} "
            f"L0 {ev['l0']:.1f} dead(train epoch) {dead_train:.3f} dead(held-out) {ev['dead_fraction']:.3f} "
            f"resampled {resampled} ({rec['seconds']:.0f}s)")
        torch.save({"sae": sae.state_dict(), "opt": opt.state_dict(), "hist": hist,
                    "epoch": epoch + 1, "lam": lam, "d": d, "m": m}, ckpt_path)
        if device == "mps":
            torch.mps.empty_cache()
    final = evaluate(sae, x_eval, lam, device)
    np.save(out_dir / "density_heldout.npy", final["density"])
    (out_dir / "history.json").write_text(json.dumps(hist, indent=1))
    return {"sae": sae, "hist": hist, "final": {k: v for k, v in final.items() if k != "density"}}
